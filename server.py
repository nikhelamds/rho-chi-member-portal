"""Local chapter hub. Google credentials required for authenticated mode."""
import os,json,time,secrets,hashlib,base64
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse,parse_qs,urlencode,quote
from urllib.request import Request,urlopen
import data_provider
from store import Store,Conflict,Invalid
ROOT=Path(__file__).resolve().parent
PRIVATE=Path(os.environ.get('HUB_PRIVATE_DIR',str(ROOT/'private')))
PREVIEW=os.environ.get('HUB_PREVIEW')=='1'
ORIGIN=os.environ.get('HUB_ORIGIN','http://127.0.0.1:8765').rstrip('/')
CLIENT=os.environ.get('GOOGLE_CLIENT_ID',''); SECRET=os.environ.get('GOOGLE_CLIENT_SECRET','')
SESSIONS={}; STATES={}
PREVIEW_CSRF=secrets.token_urlsafe(32)
PREVIEW_EMAIL=os.environ.get('HUB_PREVIEW_EMAIL','demo@example.com').lower()
STORE=Store(PRIVATE/('preview-portal.sqlite3' if PREVIEW else 'portal.sqlite3'))
CACHE={}
SYNC=None
if PREVIEW and os.environ.get('HUB_AUTO_SYNC','1')=='1':
 from sheets_sync import SheetsSync
 SYNC=SheetsSync(PRIVATE)

def officer(email):
 return email in {e.strip().lower() for e in os.environ.get('HUB_OFFICER_EMAILS','').split(',') if e.strip()}
def portal_data(s):
 if PREVIEW:
  raw=json.loads((PRIVATE/'source-data.json').read_text());synced=raw.get('_sync',{}).get('lastSuccess');source='Google Sheets · automatic sync every minute' if SYNC else 'Imported Google Sheets snapshot'
 else:
  cached=CACHE.get(s['token'])
  if not cached or cached[0]<time.time():
   raw=data_provider.live_source(s['token']);CACHE[s['token']]=(time.time()+60,raw)
  else:raw=cached[1]
  source='Google Sheets · refreshed within the last minute';synced=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 data=data_provider.normalize(raw,s['email'])
 originals={e['id']:e for e in data['events']}
 for e in STORE.records('event',True):originals[e['id']]=e
 data['events']=[e for e in originals.values() if not e.get('archived')]
 all_announcements=STORE.records('announcement',True)
 today=time.strftime('%Y-%m-%d')
 data['announcements']=[a for a in all_announcements if not a['archived'] and (not a.get('expires') or a['expires']>=today)]
 data['announcements'].sort(key=lambda a:a['created'],reverse=True)
 data['announcements'].sort(key=lambda a:not a.get('pinned'))
 data['source']=source;data['synced']=synced
 data['sync']=SYNC.status() if PREVIEW and SYNC else dict(enabled=not PREVIEW,lastSuccess=synced,intervalSeconds=60,error=None)
 if s.get('officer'):
  data['officerRecords']={'events':list(originals.values()),'announcements':all_announcements}
  data['feedback']=STORE.records('feedback')
 else:data['feedback']=[f for f in STORE.records('feedback') if f['author']==s['email']]
 return data
CAL='1Q6qbbT4jWOnMvDWujShQzNNRmgi2CiA0pOXlrmSO1BU'
def remote(url,data=None,token=None):
 req=Request(url,data=urlencode(data).encode() if data else None,headers={'Authorization':'Bearer '+token} if token else {})
 with urlopen(req,timeout=20) as r:return json.load(r)
def members():
 try:return set(json.loads((PRIVATE/'members.json').read_text()))
 except (OSError,ValueError):return set()
def parse_calendar(rows):
 import datetime
 out=[]
 for i,row in enumerate(rows):
  r=list(row)+['']*8
  if not r[3] or r[3]=='Task':continue
  date=''
  if isinstance(r[2],(float,int)):date=(datetime.datetime(1899,12,30)+datetime.timedelta(days=r[2])).strftime('%Y-%m-%d')
  t=r[4]
  if isinstance(t,(float,int)):
   mins=round(t*1440);t=f'{mins//60:02d}:{mins%60:02d}'
  out.append(dict(id=i,date=date,title=str(r[3]).strip(),time=str(t or 'TBD'),location=str(r[5] or 'TBD'),category=str(r[6] or 'Other').strip(),mandatory=str(r[7]).lower()=='yes',tentative='?' in str(r[3])))
 return out
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass # Do not log authorization codes or member details.
 def cookie(self,name):
  try:return SimpleCookie(self.headers.get('Cookie',''))[name].value
  except (KeyError,ValueError):return ''
 def respond(self,status,data,typ='application/json',headers=None):
  self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write((json.dumps(data) if typ=='application/json' else data).encode())
 def redirect(self,url,cookie=None):self.respond(302,'','text/plain',{'Location':url,**({'Set-Cookie':cookie} if cookie else {})})
 def session(self):
  if PREVIEW:return {'email':PREVIEW_EMAIL,'expiry':time.time()+100,'officer':True,'csrf':PREVIEW_CSRF}
  s=SESSIONS.get(self.cookie('session'))
  if s and s['expiry']>time.time() and s['email'] in members():
   s['officer']=officer(s['email']);return s
  return None
 def do_POST(self):
  if self.headers.get('Host')!=urlparse(ORIGIN).netloc:return self.respond(403,{'error':'Invalid host.'})
  if self.headers.get('Origin')!=ORIGIN:return self.respond(403,{'error':'Invalid origin.'})
  s=self.session()
  if not s:return self.respond(401,{'error':'Sign in again to continue.'})
  if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),s.get('csrf','')):return self.respond(403,{'error':'Refresh the page and try again.'})
  if self.path=='/logout':
   old=SESSIONS.pop(self.cookie('session'),None)
   if old:CACHE.pop(old.get('token'),None)
   return self.respond(200,{},headers={'Set-Cookie':'session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'})
  if self.path=='/api/refresh':
   if SYNC and not SYNC.refresh():return self.respond(502,{'error':SYNC.status()['error']})
   CACHE.pop(s.get('token'),None);return self.respond(200,{'ok':True})
  allowed={'/api/events':'event','/api/announcements':'announcement','/api/feedback':'feedback'}
  kind=allowed.get(self.path)
  if not kind:return self.respond(404,{'error':'Not found.'})
  if kind!='feedback' and not s.get('officer'):return self.respond(403,{'error':'Officer access required.'})
  try:
   size=int(self.headers.get('Content-Length','0'))
   if size<=0 or size>16000:return self.respond(413,{'error':'The submitted record is too large.'})
   payload=json.loads(self.rfile.read(size))
   if not isinstance(payload,dict):raise Invalid('Invalid form.')
   if kind=='feedback':
    if payload.get('id'):
     if not s.get('officer'):return self.respond(403,{'error':'Officer access required.'})
     existing=next((f for f in STORE.records('feedback') if f['id']==payload['id']),None)
     if not existing:return self.respond(404,{'error':'Feedback not found.'})
     payload=dict(existing,status=payload.get('status'),version=payload.get('version'))
    else:payload={k:payload.get(k,'') for k in ('subject','body')}|{'status':'New'}
   identifier=STORE.save(kind,payload,s['email'])
   return self.respond(200,{'ok':True,'id':identifier})
  except Conflict as e:return self.respond(409,{'error':str(e)})
  except (ValueError,Invalid) as e:return self.respond(400,{'error':str(e)})
  except Exception:return self.respond(500,{'error':'Could not save. Your changes have not been confirmed. Try again.'})
 def do_GET(self):
  if self.headers.get('Host')!=urlparse(ORIGIN).netloc:return self.respond(403,{'error':'Invalid host.'})
  p=urlparse(self.path);q=parse_qs(p.query)
  secure='; Secure' if ORIGIN.startswith('https://') else ''
  if p.path=='/auth/google':
   if not CLIENT or not SECRET:return self.redirect('/?error=setup')
   state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
   for k in list(STATES):
    if STATES[k][0]<time.time():STATES.pop(k,None)
   STATES[state]=(time.time()+600,verifier)
   params=dict(client_id=CLIENT,redirect_uri=ORIGIN+'/auth/callback',response_type='code',scope='openid email https://www.googleapis.com/auth/spreadsheets.readonly',state=state,code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),code_challenge_method='S256',prompt='select_account')
   return self.redirect('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params),'oauth_state='+state+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=600'+secure)
  if p.path=='/auth/callback':
   state=q.get('state',[''])[0]
   if not state or not secrets.compare_digest(state,self.cookie('oauth_state')):return self.redirect('/?error=signin')
   pending=STATES.pop(state,None)
   if not pending or pending[0]<time.time():return self.redirect('/?error=signin')
   try:
    token=remote('https://oauth2.googleapis.com/token',dict(code=q.get('code',[''])[0],client_id=CLIENT,client_secret=SECRET,redirect_uri=ORIGIN+'/auth/callback',grant_type='authorization_code',code_verifier=pending[1]))
    user=remote('https://openidconnect.googleapis.com/v1/userinfo',token=token['access_token'])
    email=user.get('email','').lower()
    if user.get('email_verified') is not True or email not in members():return self.redirect('/?error=member')
    sid=secrets.token_urlsafe(48)
    for k in list(SESSIONS):
     if SESSIONS[k]['expiry']<time.time():SESSIONS.pop(k,None)
    SESSIONS[sid]=dict(email=email,token=token['access_token'],expiry=time.time()+min(token.get('expires_in',3600),3600),csrf=secrets.token_urlsafe(32))
    return self.redirect('/','session='+sid+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=3600'+secure)
   except Exception:return self.redirect('/?error=signin')
  if p.path=='/api/session':return self.respond(200,dict(authenticated=bool(self.session()),preview=PREVIEW,configured=bool(CLIENT and SECRET),email=(self.session() or {}).get('email',''),officer=(self.session() or {}).get('officer',False),csrf=(self.session() or {}).get('csrf','')))
  if p.path in ('/api/calendar','/api/portal'):
   s=self.session()
   if not s:return self.respond(401,{'error':'Sign in with an approved member account.'})
   try:
    data=portal_data(s)
    return self.respond(200,data if p.path=='/api/portal' else {'events':data['events'],'source':data['source']})
   except Exception:return self.respond(502,{'error':'Chapter records could not be loaded. Confirm that your Google account can open all three source sheets, then retry.'})
  if p.path=='/app.js' and not self.session():return self.respond(401,{'error':'Member sign-in required'})
  if p.path in ['/', '/app.js','/login.js','/style.css']:
   name={'/':'index.html','/app.js':'app.js','/login.js':'login.js','/style.css':'style.css'}[p.path]
   typ={'/':'text/html','/app.js':'text/javascript','/login.js':'text/javascript','/style.css':'text/css'}[p.path]
   body=(ROOT/'public'/name).read_text()
   if p.path=='/' and not self.session():body=body.replace('/app.js','/login.js')
   return self.respond(200,body,typ)
  self.respond(404,{'error':'Not found'})
if __name__=='__main__':
 if SYNC:SYNC.start()
 if PREVIEW and urlparse(ORIGIN).hostname not in ('localhost','127.0.0.1'):raise SystemExit('Preview is local-only')
 print('Chapter hub: '+ORIGIN+(' (local snapshot preview)' if PREVIEW else ' (member sign-in required)'),flush=True)
 ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8765'))),Handler).serve_forever()

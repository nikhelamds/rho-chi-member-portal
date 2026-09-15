"""SQLite persistence for website-owned events, announcements, and feedback."""
import sqlite3,json,uuid,datetime
class Conflict(Exception):pass
class Invalid(Exception):pass
class Store:
 def __init__(self,path):
  self.path=str(path);path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as db:
   db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, version INTEGER NOT NULL, archived INTEGER NOT NULL DEFAULT 0, author TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)')
   db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, actor TEXT, action TEXT, record_id TEXT, created TEXT)')
 def connect(self):
  db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row;return db
 def records(self,kind,include_archived=False):
  with self.connect() as db:rows=db.execute('SELECT * FROM records WHERE kind=? '+('' if include_archived else 'AND archived=0 ')+'ORDER BY updated DESC',(kind,)).fetchall()
  return [dict(json.loads(r['body']),id=r['id'],version=r['version'],archived=bool(r['archived']),author=r['author'],created=r['created'],updated=r['updated'],origin='website') for r in rows]
 def save(self,kind,payload,actor):
  if kind not in ('event','announcement','feedback'):raise Invalid('Unknown record type.')
  body={}
  allowed={'event':{'title':160,'date':10,'time':100,'location':200,'category':80,'description':4000},'announcement':{'title':160,'body':5000,'expires':10},'feedback':{'subject':160,'body':5000,'status':20}}[kind]
  for key,limit in allowed.items():
   value=payload.get(key,'')
   if not isinstance(value,str) or len(value)>limit:raise Invalid('Invalid '+key+'.')
   body[key]=value.strip()
  required={'event':['title','category'],'announcement':['title','body'],'feedback':['subject','body']}[kind]
  if any(not body[k] for k in required):raise Invalid('Complete all required fields.')
  for k in ('date','expires'):
   if body.get(k):
    try:datetime.date.fromisoformat(body[k])
    except ValueError:raise Invalid('Enter a valid date.')
  for key in {'event':['mandatory','tentative'],'announcement':['pinned'],'feedback':[]}[kind]:
   if not isinstance(payload.get(key,False),bool):raise Invalid('Invalid '+key+'.')
   body[key]=payload.get(key,False)
  if kind=='feedback' and body['status'] not in ('New','Reviewed','Resolved'):raise Invalid('Invalid feedback status.')
  identifier=payload.get('id') or kind+'-'+uuid.uuid4().hex
  if not isinstance(identifier,str) or len(identifier)>100:raise Invalid('Invalid record ID.')
  version=payload.get('version',0)
  if type(version) is not int:raise Invalid('Invalid record version.')
  archived=payload.get('archived',False)
  if not isinstance(archived,bool):raise Invalid('Invalid archive flag.')
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   row=db.execute('SELECT * FROM records WHERE id=?',(identifier,)).fetchone()
   if row and (row['kind']!=kind or row['version']!=version):raise Conflict('This record changed. Refresh and try again.')
   if not row and version!=0:raise Conflict('This record is no longer available. Refresh and try again.')
   if row:
    db.execute('UPDATE records SET body=?,version=version+1,archived=?,updated=? WHERE id=?',(json.dumps(body),int(archived),now,identifier))
   else:db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?)',(identifier,kind,json.dumps(body),1,int(archived),actor,now,now))
   db.execute('INSERT INTO audit(actor,action,record_id,created) VALUES (?,?,?,?)',(actor,'archive' if archived else 'save',identifier,now))
  return identifier

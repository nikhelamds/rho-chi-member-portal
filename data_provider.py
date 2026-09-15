"""Read-only Sheets adapter. Website-owned records are stored separately."""
import datetime,json,time,urllib.parse,urllib.request,os
CAL=os.environ.get('HUB_CAL_SHEET_ID','')
ACT=os.environ.get('HUB_ACT_SHEET_ID','')
RUSH=os.environ.get('HUB_RUSH_SHEET_ID','')
URLS={'calendar':f'https://docs.google.com/spreadsheets/d/{CAL}/edit','actives':f'https://docs.google.com/spreadsheets/d/{ACT}/edit','rush':f'https://docs.google.com/spreadsheets/d/{RUSH}/edit'}
def text(v):return '' if v is None else str(v).strip()
def cell(row,i):return row[i] if i<len(row) else None
def date(v):
 if isinstance(v,(int,float)) and 30000<v<90000:return (datetime.datetime(1899,12,30)+datetime.timedelta(days=v)).strftime('%Y-%m-%d')
 if isinstance(v,str):
  try:return datetime.date.fromisoformat(v).isoformat()
  except ValueError:pass
 return ''
def display(v):
 d=date(v)
 if d:return d
 if isinstance(v,(int,float)) and 0<=v<1:
  mins=round(v*1440);return f'{mins//60:02d}:{mins%60:02d}'
 return text(v)
def attendance_credit(value):
 code=text(value).casefold()
 if code=='x':return dict(status='Attended',credit=1.0,creditLabel='Full points (100%)')
 if code=='c':return dict(status='Exempt',credit=0.5,creditLabel='Half points (50%)')
 if code=='':return dict(status='No points recorded',credit=0.0,creditLabel='0 points')
 return dict(status='Needs review',credit=None,creditLabel='Unrecognized attendance code')
def column_index(label):
 n=0
 for c in label:n=n*26+ord(c)-64
 return n-1
# Only attendance inputs, never totals, notes, hour counts, or formula summaries.
ATTENDANCE_COLUMNS=set()
for start,end in [('E','E'),('H','H'),('K','K'),('Q','Q'),('T','T'),('W','W'),('Z','Z'),('AC','AC'),('AF','AF'),('AI','AI'),('AL','AL'),('AO','AO'),('AR','AR'),('AV','AV'),('AY','AY'),('BB','BB'),('BE','BE'),('BH','BH'),('BS','BS'),('BX','BX'),('CC','CC'),('CI','CI'),('CK','CK'),('CM','CM'),('CO','CO'),('CQ','CQ'),('CS','CS'),('CY','DU'),('EB','EB'),('EE','EE'),('EH','EH'),('EJ','EJ'),('EL','EL'),('EN','EN'),('EU','FA'),('FE','FN'),('FR','FW'),('GA','GJ'),('GN','GO'),('GS','GV'),('GZ','HB'),('HI','HO'),('HS','HS')]:
 ATTENDANCE_COLUMNS.update(range(column_index(start),column_index(end)+1))
def normalize(raw,email):
 directory=[]
 for r in raw.get('directory',[])[8:]:
  mail=text(cell(r,3)).lower()
  if '@' not in mail:continue
  directory.append(dict(name=(text(cell(r,1))+' '+text(cell(r,0))).strip(),first=text(cell(r,1)),last=text(cell(r,0)),email=mail,role=text(cell(r,5)),officerEmail=text(cell(r,6)),major=text(cell(r,7)),graduation=text(cell(r,9)),pledgeClass=text(cell(r,10))))
 events=[]
 for n,r in enumerate(raw.get('calendar',[])[3:],4):
  title=text(cell(r,3))
  if not title:continue
  identifier=cell(r,1)
  eid='sheet-'+str(int(identifier)) if isinstance(identifier,(int,float)) else 'sheet-row-'+str(n)
  events.append(dict(id=eid,date=date(cell(r,2)),title=title,time=display(cell(r,4)) or 'TBD',location=text(cell(r,5)) or 'TBD',category=text(cell(r,6)) or 'Other',mandatory=text(cell(r,7)).lower()=='yes',tentative='?' in title,description='',origin='sheet',version=0))
 buddies=[]
 for i,r in enumerate(raw.get('buddies',[])[1:],2):
  if text(cell(r,0)) and text(cell(r,1)):buddies.append(dict(id=i,first=text(cell(r,0)),second=text(cell(r,1)),status=text(cell(r,2)) or 'Not recorded'))
 academics=[];course='';course_name=''
 for i,r in enumerate(raw.get('academics',[])[2:],3):
  if text(cell(r,0)):course=text(cell(r,0));course_name=text(cell(r,1));continue
  if not text(cell(r,2)) or not text(cell(r,1)):continue
  academics.append(dict(id=i,course=course,courseName=course_name,professor=text(cell(r,1)),reviewer=text(cell(r,2)),rating=cell(r,3),difficulty=cell(r,4),review=text(cell(r,5)),tips=text(cell(r,6))))
 shifts=[];rows=raw.get('shifts',[])
 # Source uses two side-by-side blocks; preserve labels rather than infer corrupted time headers.
 for offset in (0,8):
  starts=[i for i,r in enumerate(rows) if text(cell(r,offset)) and 'table lead' not in text(cell(r,offset)).lower() and not text(cell(r,offset)).lower().startswith('location')]
  for j,start in enumerate(starts):
   end=starts[j+1] if j+1<len(starts) else len(rows)
   block=[[display(cell(r,k)) for k in range(offset,min(offset+7,15))] for r in rows[start:end]]
   while block and not any(block[-1]):block.pop()
   if block:shifts.append(dict(id=str(offset)+'-'+str(start),title=display(cell(rows[start],offset)),headers=block[0],rows=block[1:]))
 attendance=None;person=next((d for d in directory if d['email']==email),None);ar=raw.get('attendance',[])
 if person and len(ar)>2:
  matches=[r for r in ar[2:] if text(cell(r,0)).casefold()==person['last'].casefold() and text(cell(r,1)).casefold()==person['first'].casefold()]
  if len(matches)==1:
   r=matches[0];entries=[]
   for i in range(4,min(len(r),len(ar[0]))):
    h=text(cell(ar[0],i));value=cell(r,i)
    if h and i in ATTENDANCE_COLUMNS:entries.append(dict(label=h,date=display(cell(ar[1],i)),value=text(value),**attendance_credit(value)))
   attendance=dict(name=person['name'],total=cell(r,248),meetingPoints=cell(r,3),entries=entries)
 policy=raw.get('policy',[]);requirements=[]
 for r in policy[5:10]:requirements.append(dict(event=text(cell(r,0)),required=cell(r,2),points=cell(r,3)))
 extra=[]
 for r in policy[15:33]:
  if text(cell(r,0)):extra.append(dict(event=text(cell(r,0)),points=cell(r,3)))
 return dict(directory=directory,events=events,buddies=buddies,academics=academics,shifts=shifts,attendance=attendance,requirements=requirements,extraPoints=extra,pointTarget=cell(policy[12],3) if len(policy)>12 else None,links=raw.get('links',[]),urls=URLS)
def request(url,token):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+token}),timeout=25) as r:return json.load(r)
def live_source(token):
 base='https://sheets.googleapis.com/v4/spreadsheets/'
 meta=request(base+ACT+'?fields=sheets(properties(title,sheetId))',token)
 titles={s['properties']['title']:s['properties']['sheetId'] for s in meta['sheets']}
 classes=next((t for t in titles if t.startswith('Classes')),'Classes (23)')
 specs={'directory':("Actives Fall 2026",'A1:K200'),'policy':('Point System','A1:I100'),'buddies':('Buddy of the Month','A1:H200'),'attendance':('Fall 2026 Attendance','A1:IO1000'),'academics':(classes,'A1:G1000')}
 ranges=["'"+t.replace("'","''")+"'!"+r for t,r in specs.values()]
 params=urllib.parse.urlencode([('ranges',r) for r in ranges]+[('valueRenderOption','UNFORMATTED_VALUE'),('dateTimeRenderOption','SERIAL_NUMBER')])
 values=request(base+ACT+'/values:batchGet?'+params,token)['valueRanges'];raw={key:v.get('values',[]) for key,v in zip(specs,values)}
 for key,book,rng in [('calendar',CAL,"'Dynamic Calendar'!A1:H1002"),('shifts',RUSH,"'Sheet1'!A1:O200")]:
  raw[key]=request(base+book+'/values/'+urllib.parse.quote(rng,safe='')+'?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=SERIAL_NUMBER',token).get('values',[])
 # Fetch hyperlinks from the exact user-supplied workbook, not from linked documents.
 params=urllib.parse.urlencode([('ranges',"'Actives Fall 2026'!D1:G7"),('ranges',"'Comment Box'!D17"),('includeGridData','true'),('fields','sheets(properties(title),data(rowData(values(formattedValue,hyperlink))))')])
 links=[]
 grid=request(base+ACT+'?'+params,token)
 for sheet in grid.get('sheets',[]):
  for grid_data in sheet.get('data',[]):
   for row in grid_data.get('rowData',[]):
    for c in row.get('values',[]):
     if c.get('hyperlink','').startswith('https://'):links.append(dict(label=c.get('formattedValue','Resource'),url=c['hyperlink'],sheet=sheet['properties']['title']))
 raw['links']=links
 return raw

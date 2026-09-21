from flask import Flask, jsonify, request, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, math, os
from datetime import datetime

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, 'database', 'emergency.db')
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'sih-demo-only-change-me')

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def rows(q, args=()):
    c=conn(); r=[dict(x) for x in c.execute(q,args).fetchall()]; c.close(); return r
def row(q,args=()):
    r=rows(q,args); return r[0] if r else None
def execute(q,args=()):
    c=conn(); cur=c.execute(q,args); c.commit(); ident=cur.lastrowid; c.close(); return ident
def out(data, code=200): return jsonify(data), code
def hav(a,b,c,d):
    R=6371; p=math.pi/180; x=math.sin((c-a)*p/2)**2+math.cos(a*p)*math.cos(c*p)*math.sin((d-b)*p/2)**2
    return R*2*math.atan2(math.sqrt(x),math.sqrt(1-x))
def require(*roles):
    u=session.get('user')
    return u and (not roles or u['role'] in roles)
def valid_text(value, limit=120): return isinstance(value,str) and value.strip() and len(value.strip())<=limit
def action_allowed(emergency):
    if require('COORDINATOR'): return True
    if not require('DRIVER') or not emergency.get('assigned_ambulance_id'): return False
    owner=row('select d.user_id from ambulances a join drivers d on d.id=a.driver_id where a.id=?',(emergency['assigned_ambulance_id'],))
    return bool(owner and owner['user_id']==session['user']['id'])

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,email TEXT UNIQUE,password_hash TEXT,role TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS drivers(id INTEGER PRIMARY KEY,user_id INTEGER,license_number TEXT,verification_status TEXT);
CREATE TABLE IF NOT EXISTS ambulances(id INTEGER PRIMARY KEY,driver_id INTEGER,registration_number TEXT UNIQUE,ambulance_type TEXT,vehicle_model TEXT,status TEXT,latitude REAL,longitude REAL,created_at TEXT);
CREATE TABLE IF NOT EXISTS emergency_requests(id INTEGER PRIMARY KEY,patient_id INTEGER,patient_name TEXT,emergency_type TEXT,priority TEXT,patient_count INTEGER DEFAULT 1,incident_id TEXT,severity TEXT,traffic_level TEXT,hospital_status TEXT,latitude REAL,longitude REAL,notes TEXT,status TEXT,assigned_ambulance_id INTEGER,assigned_at TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE IF NOT EXISTS tracking_events(id INTEGER PRIMARY KEY,emergency_id INTEGER,ambulance_id INTEGER,latitude REAL,longitude REAL,status TEXT,timestamp TEXT);
CREATE TABLE IF NOT EXISTS hospital_alerts(id INTEGER PRIMARY KEY,emergency_id INTEGER,hospital_name TEXT,eta TEXT,status TEXT,created_at TEXT);
'''
def init_db():
    os.makedirs(os.path.dirname(DB),exist_ok=True); c=conn(); c.executescript(SCHEMA)
    columns={x['name'] for x in c.execute('pragma table_info(emergency_requests)').fetchall()}
    for name, definition in [('patient_name','text'),('assigned_at','text'),('patient_count','integer default 1'),('incident_id','text'),('severity','text'),('traffic_level','text'),('hospital_status','text')]:
        if name not in columns: c.execute(f'alter table emergency_requests add column {name} {definition}')
    c.execute('create unique index if not exists one_active_sos_per_patient on emergency_requests(patient_id) where status not in ("COMPLETED","CANCELLED")')
    c.commit(); c.close()
    if not row('select id from users where email=?',('coordinator@demo.in',)): reset_demo()
def add_user(name,phone,email,password,role): return execute('insert into users(name,phone,email,password_hash,role,created_at) values(?,?,?,?,?,?)',(name,phone,email,generate_password_hash(password),role,now()))
def reset_demo():
    c=conn(); c.executescript('DELETE FROM hospital_alerts;DELETE FROM tracking_events;DELETE FROM emergency_requests;DELETE FROM ambulances;DELETE FROM drivers;DELETE FROM users;'); c.commit(); c.close()
    add_user('Demo Coordinator','9000000000','coordinator@demo.in','coord123','COORDINATOR')
    add_user('Demo Patient','9111111111','patient@demo.in','patient123','PATIENT')
    data=[('Rahul Sharma','9222222222','rahul@demo.in','MH-12-AB-1234','Advanced Life Support','Tata Winger',18.5204,73.8567,'AVAILABLE'),('Amit Patil','9333333333','amit@demo.in','MH-14-CD-5678','Basic Life Support','Force Traveller',18.5310,73.8470,'AVAILABLE'),('Sameer Jadhav','9444444444','sameer@demo.in','MH-12-EF-9012','Patient Transport','Maruti Omni',18.5120,73.8700,'BUSY')]
    for n,p,e,reg,typ,model,lat,lng,status in data:
        uid=add_user(n,p,e,'driver123','DRIVER'); did=execute('insert into drivers(user_id,license_number,verification_status) values(?,?,?)',(uid,'MH-DL-'+str(uid)+'-2026','VERIFIED')); execute('insert into ambulances(driver_id,registration_number,ambulance_type,vehicle_model,status,latitude,longitude,created_at) values(?,?,?,?,?,?,?,?)',(did,reg,typ,model,status,lat,lng,now()))

@app.get('/')
def home(): return render_template('index.html')
@app.post('/api/register')
def register():
    d=request.json or {}; required=['name','phone','email','password','role']
    if any(not d.get(x) for x in required) or len(str(d.get('phone',''))) < 10: return out({'error':'Complete all required fields with a valid phone number.'},400)
    try: uid=add_user(d['name'],d['phone'],d['email'],d['password'],d['role']); return out({'message':'Account created','id':uid},201)
    except sqlite3.IntegrityError: return out({'error':'Email already registered.'},409)
@app.post('/api/login')
def login():
    d=request.json or {}; u=row('select * from users where email=?',(d.get('email',''),))
    if not u or not check_password_hash(u['password_hash'],d.get('password','')):
        return out({'success':False,'message':'Invalid credentials','error':'Invalid credentials'},401)
    session['user']={'id':u['id'],'name':u['name'],'role':u['role']}
    redirect={'DRIVER':'/driver','COORDINATOR':'/coordinator','PATIENT':'/patient'}.get(u['role'],'/')
    return out({'success':True,'message':'Login successful','user':session['user'],'redirect':redirect})

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return out({'success':False,'message':'API endpoint not found','error':'API endpoint not found'},404)
    return error

@app.errorhandler(Exception)
def api_exception(error):
    if request.path.startswith('/api/'):
        app.logger.exception('API request failed')
        return out({'success':False,'message':'Server error. Please try again.','error':'Server error'},500)
    raise error
@app.post('/api/logout')
def logout(): session.clear(); return out({'message':'Logged out'})
@app.get('/api/me')
def me(): return out({'user':session.get('user')})
@app.get('/api/patient-profile')
def patient_profile():
    user=session.get('user')
    if user and user['role']=='PATIENT': return out({'patient':user})
    demo=row('select id,name,phone,email,role from users where email=?',('patient@demo.in',))
    return out({'patient':demo})

@app.post('/api/ambulances/register')
def ambulance_register():
    d=request.json or {}; required=['name','phone','email','password','registration_number','ambulance_type','vehicle_model','license_number']
    if any(not d.get(x) for x in required): return out({'error':'Please complete required registration fields.'},400)
    if row('select id from ambulances where registration_number=?',(d['registration_number'],)): return out({'error':'Ambulance registration already exists.'},409)
    try: uid=add_user(d['name'],d['phone'],d['email'],d['password'],'DRIVER')
    except sqlite3.IntegrityError: return out({'error':'Email already registered.'},409)
    did=execute('insert into drivers(user_id,license_number,verification_status) values(?,?,?)',(uid,d['license_number'],'PENDING'))
    aid=execute('insert into ambulances(driver_id,registration_number,ambulance_type,vehicle_model,status,latitude,longitude,created_at) values(?,?,?,?,?,?,?,?)',(did,d['registration_number'],d['ambulance_type'],d['vehicle_model'],'OFFLINE',18.5204,73.8567,now()))
    return out({'message':'Registered: Pending Verification','ambulance_id':aid},201)
@app.get('/api/ambulances')
def ambulances(): return out({'ambulances': ambulance_data()})
def ambulance_data(): return rows('''select a.*,u.name driver_name,u.phone,d.verification_status from ambulances a join drivers d on a.driver_id=d.id join users u on d.user_id=u.id order by a.id''')
@app.patch('/api/ambulances/<int:aid>/status')
def ambulance_status(aid):
    if not require('DRIVER','COORDINATOR'): return out({'error':'Unauthorized'},403)
    a=row('select a.*,d.user_id,d.verification_status from ambulances a join drivers d on d.id=a.driver_id where a.id=?',(aid,)); s=(request.json or {}).get('status')
    if not a or (session['user']['role']=='DRIVER' and a['user_id']!=session['user']['id']): return out({'error':'Not found'},404)
    if s=='AVAILABLE' and a['verification_status']!='VERIFIED': return out({'error':'Only verified drivers can go online.'},400)
    if s not in ['AVAILABLE','OFFLINE','BUSY']: return out({'error':'Invalid status'},400)
    execute('update ambulances set status=? where id=?',(s,aid)); return out({'message':'Status updated'})
@app.post('/api/ambulances/<int:aid>/verify')
def verify(aid):
    if not require('COORDINATOR'): return out({'error':'Coordinator access required'},403)
    decision=(request.json or {}).get('decision','VERIFY'); status='VERIFIED' if decision=='VERIFY' else 'REJECTED'; execute('update drivers set verification_status=? where id=(select driver_id from ambulances where id=?)',(status,aid)); return out({'message':status})

def emergency_view(e):
    a=row('''select a.registration_number,a.ambulance_type,a.latitude ambulance_latitude,a.longitude ambulance_longitude,u.name driver_name,a.status ambulance_status from ambulances a join drivers d on d.id=a.driver_id join users u on u.id=d.user_id where a.id=?''',(e['assigned_ambulance_id'],)) if e['assigned_ambulance_id'] else None
    e['ambulance']=a
    if a: e['distance_km']=round(hav(a['ambulance_latitude'],a['ambulance_longitude'],e['latitude'],e['longitude']),1); e['eta_minutes']=max(2,round(e['distance_km']*2.4))
    e['patient_count']=e.get('patient_count') or 1; e['incident_id']=e.get('incident_id') or f'INC-{e["id"]:04d}'; e['traffic_level']=e.get('traffic_level') or 'Moderate'; e['hospital_status']=e.get('hospital_status') or 'PENDING'
    return e
@app.post('/api/emergency')
def emergency_create():
    d=request.json or {}; typ=d.get('emergency_type','Medical Emergency'); priority=d.get('priority') or d.get('severity','HIGH')
    try: lat=float(d.get('latitude',18.5204)); lng=float(d.get('longitude',73.8567)); count=int(d.get('patient_count',1))
    except (TypeError,ValueError): return out({'error':'Use a valid location and whole-number patient count.'},400)
    if not (-90<=lat<=90 and -180<=lng<=180 and 1<=count<=6): return out({'error':'Location or patient count is outside the permitted demo range.'},400)
    if typ not in ('Accident','Medical Emergency','Pregnancy','Other') or priority not in ('LOW','MEDIUM','HIGH','CRITICAL'): return out({'error':'Choose a valid emergency type and severity.'},400)
    profile=session.get('user',{}) if session.get('user',{}).get('role')=='PATIENT' else row('select id,name from users where email=?',('patient@demo.in',)) or {}
    pid=profile.get('id'); patient_name=d.get('name') or profile.get('name') or 'Demo Patient'
    active=row('select * from emergency_requests where (patient_id=? or patient_name=?) and status not in ("COMPLETED","CANCELLED") order by id desc',(pid,patient_name))
    if active: return out({'duplicate':True,'message':'An active emergency request already exists.','emergency':emergency_view(active)},409)
    near=rows('select * from emergency_requests where status not in ("COMPLETED","CANCELLED") and abs(latitude-?)<0.006 and abs(longitude-?)<0.006',(lat,lng)); incident=(near[0].get('incident_id') if near and near[0].get('incident_id') else f'INC-{datetime.now().strftime("%H%M%S")}')
    traffic=['Light','Moderate','Heavy'][int(abs(lat*1000+lng*1000))%3]
    try:
        eid=execute('insert into emergency_requests(patient_id,patient_name,emergency_type,priority,patient_count,incident_id,severity,traffic_level,hospital_status,latitude,longitude,notes,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,patient_name,typ,priority,count,incident,priority,traffic,'PENDING',lat,lng,d.get('notes',''),'SEARCHING',now(),now()))
    except sqlite3.IntegrityError:
        active=row('select * from emergency_requests where patient_id=? and status not in ("COMPLETED","CANCELLED") order by id desc',(pid,))
        return out({'duplicate':True,'message':'An active emergency request already exists.','emergency':emergency_view(active)},409)
    e=emergency_view(row('select * from emergency_requests where id=?',(eid,))); e['nearby_count']=len(near)+1; e['incident_patients']=sum((x.get('patient_count') or 1) for x in near)+count
    return out({'message':'Emergency request created. Finding nearest available ambulance…','emergency':e},201)
@app.get('/api/emergency')
def emergencies(): return out({'emergencies':[emergency_view(x) for x in rows('select * from emergency_requests order by id desc')]})
@app.get('/api/emergency/<int:eid>')
def emergency_get(eid):
    e=row('select * from emergency_requests where id=?',(eid,)); return out({'emergency':emergency_view(e)}) if e else out({'error':'Not found'},404)
@app.post('/api/emergency/<int:eid>/match')
def match(eid):
    e=row('select * from emergency_requests where id=?',(eid,)); available=[a for a in ambulance_data() if a['status']=='AVAILABLE' and a['verification_status']=='VERIFIED']
    if not e: return out({'error':'Not found'},404)
    if e['status']!='SEARCHING' or e['assigned_ambulance_id']: return out({'error':'This emergency has already been assigned or is no longer searchable.'},409)
    if not available: return out({'error':'No verified available ambulances.'},409)
    ranked=[]
    needs_als=e.get('priority') in ('CRITICAL','HIGH') or (e.get('patient_count') or 1)>1
    for a in available:
        dist=hav(a['latitude'],a['longitude'],e['latitude'],e['longitude']); traffic=1.35 if e.get('traffic_level')=='Heavy' else 1.15 if e.get('traffic_level')=='Moderate' else 1; eta=max(2,round(dist*2.4*traffic)); capability=0 if (not needs_als or a['ambulance_type']=='Advanced Life Support') else 8; ranked.append((capability+eta,eta,dist,a))
    ranked.sort(key=lambda x:(x[0],x[1],x[2])); score,eta,dist,a=ranked[0]
    c=conn(); c.execute('begin immediate'); claimed=c.execute('update ambulances set status=? where id=? and status=?',('BUSY',a['id'],'AVAILABLE')).rowcount
    assigned=c.execute('update emergency_requests set assigned_ambulance_id=?,assigned_at=?,status=?,updated_at=? where id=? and status=? and assigned_ambulance_id is null',(a['id'],now(),'ASSIGNED',now(),eid,'SEARCHING')).rowcount
    if claimed!=1 or assigned!=1: c.rollback(); c.close(); return out({'error':'Ambulance availability changed. Please run matching again.'},409)
    c.commit(); c.close()
    cards=[{'registration_number':x[3]['registration_number'],'ambulance_type':x[3]['ambulance_type'],'distance_km':round(x[2],1),'eta_minutes':x[1],'traffic_level':e.get('traffic_level') or 'Moderate','best_match':x[3]['id']==a['id']} for x in ranked]
    return out({'message':'Recommended Ambulance: '+a['registration_number'],'reason':'Selected using emergency severity, required capability, ETA, availability and simulated traffic.','available_count':len(available),'candidates':cards,'emergency':emergency_view(row('select * from emergency_requests where id=?',(eid,)))})
def driver_action(eid, status, ambulance_status='BUSY'):
    e=row('select * from emergency_requests where id=?',(eid,));
    if not e: return out({'error':'Not found'},404)
    if not action_allowed(e): return out({'error':'Driver or coordinator access required for this case.'},403)
    allowed={'EN_ROUTE':'ASSIGNED','ARRIVED':'EN_ROUTE','PATIENT_PICKED':'ARRIVED','HOSPITAL_EN_ROUTE':'PATIENT_PICKED','COMPLETED':'HOSPITAL_EN_ROUTE'}
    if e['status']!=allowed.get(status): return out({'error':'This action is not valid for the current emergency status.'},409)
    execute('update emergency_requests set status=?,updated_at=? where id=?',(status,now(),eid)); execute('update ambulances set status=? where id=?',(ambulance_status,e['assigned_ambulance_id']))
    if e['assigned_ambulance_id']: execute('insert into tracking_events(emergency_id,ambulance_id,latitude,longitude,status,timestamp) select ?,id,latitude,longitude,?,? from ambulances where id=?',(eid,status,now(),e['assigned_ambulance_id']))
    return out({'message':'Case updated','emergency':emergency_view(row('select * from emergency_requests where id=?',(eid,)))})
@app.post('/api/emergency/<int:eid>/accept')
def accept(eid): return driver_action(eid,'EN_ROUTE')
@app.post('/api/emergency/<int:eid>/reject')
def reject(eid):
    e=row('select * from emergency_requests where id=?',(eid,));
    if not e: return out({'error':'Not found'},404)
    if not action_allowed(e): return out({'error':'Driver or coordinator access required for this case.'},403)
    if e['status']!='ASSIGNED': return out({'error':'Only a pending assignment can be rejected.'},409)
    execute('update ambulances set status=? where id=?',('AVAILABLE',e['assigned_ambulance_id'])); execute('update emergency_requests set assigned_ambulance_id=NULL,assigned_at=NULL,status=?,updated_at=? where id=?',('SEARCHING',now(),eid)); return out({'message':'Request returned for matching'})
@app.post('/api/emergency/<int:eid>/arrived')
def arrived(eid): return driver_action(eid,'ARRIVED')
@app.post('/api/emergency/<int:eid>/picked-up')
def picked(eid): return driver_action(eid,'PATIENT_PICKED')
@app.post('/api/emergency/<int:eid>/hospital-trip')
def trip(eid):
    driver_action(eid,'HOSPITAL_EN_ROUTE'); execute('update emergency_requests set hospital_status=? where id=?',('ACCEPTED',eid)); execute('insert into hospital_alerts(emergency_id,hospital_name,eta,status,created_at) values(?,?,?,?,?)',(eid,'Demo City Hospital','8 minutes','ACCEPTED · Patient onboard',now())); return out({'message':'Hospital pre-alert accepted','emergency':emergency_view(row('select * from emergency_requests where id=?',(eid,)))})
@app.post('/api/emergency/<int:eid>/complete')
def complete(eid): return driver_action(eid,'COMPLETED','AVAILABLE')
@app.post('/api/tracking/update')
def tracking():
    d=request.json or {}; execute('update ambulances set latitude=?,longitude=? where id=?',(d['latitude'],d['longitude'],d['ambulance_id'])); execute('insert into tracking_events(emergency_id,ambulance_id,latitude,longitude,status,timestamp) values(?,?,?,?,?,?)',(d['emergency_id'],d['ambulance_id'],d['latitude'],d['longitude'],d.get('status','EN_ROUTE'),now())); return out({'message':'Location updated'})
@app.get('/api/tracking/<int:eid>')
def track(eid): return out({'events':rows('select * from tracking_events where emergency_id=? order by id desc',(eid,))})
@app.get('/api/dashboard/stats')
def stats():
    a=ambulance_data(); es=rows('select * from emergency_requests where status not in ("COMPLETED","CANCELLED")'); return out({'total_ambulances':len(a),'available':sum(x['status']=='AVAILABLE' for x in a),'busy':sum(x['status']=='BUSY' for x in a),'pending':sum(x['verification_status']=='PENDING' for x in a),'active_emergencies':len(es)})
@app.get('/api/dashboard/ambulances')
def dash_amb(): return out({'ambulances':ambulance_data()})
@app.get('/api/dashboard/emergencies')
def dash_em(): return emergencies()
def history_data(search='', status='ALL'):
    where=['e.status in ("COMPLETED", "CANCELLED")']; args=[]
    if status in ('COMPLETED','CANCELLED'): where.append('e.status=?'); args.append(status)
    if search:
        term=f'%{search.strip()}%'; where.append('(e.patient_name like ? or a.registration_number like ? or u.name like ? or e.emergency_type like ?)'); args.extend([term,term,term,term])
    return rows(f'''select e.id,e.patient_name,e.emergency_type,e.priority,e.status,e.created_at,e.updated_at,e.assigned_at,
        coalesce(a.registration_number,'Unassigned') ambulance_number,coalesce(u.name,'Unassigned') driver_name,
        coalesce((select hospital_name from hospital_alerts h where h.emergency_id=e.id order by h.id desc limit 1),'Not recorded') hospital_name,
        case when e.assigned_at is not null then max(0,round((julianday(e.assigned_at)-julianday(e.created_at))*1440)) else null end response_minutes
        from emergency_requests e left join ambulances a on a.id=e.assigned_ambulance_id left join drivers d on d.id=a.driver_id left join users u on u.id=d.user_id
        where {' and '.join(where)} order by e.updated_at desc''',args)
@app.get('/api/history')
def history():
    if not require('COORDINATOR'): return out({'error':'Coordinator access required'},403)
    return out({'records':history_data(request.args.get('search',''),request.args.get('status','ALL'))})
@app.delete('/api/history/<int:eid>')
def delete_history(eid):
    if not require('COORDINATOR'): return out({'error':'Coordinator access required'},403)
    record=row('select id from emergency_requests where id=? and status in ("COMPLETED","CANCELLED")',(eid,))
    if not record: return out({'error':'History record not found'},404)
    c=conn(); c.execute('delete from hospital_alerts where emergency_id=?',(eid,)); c.execute('delete from tracking_events where emergency_id=?',(eid,)); c.execute('delete from emergency_requests where id=?',(eid,)); c.commit(); c.close()
    return out({'message':'History record deleted'})
@app.delete('/api/history')
def clear_history():
    if not require('COORDINATOR'): return out({'error':'Coordinator access required'},403)
    targets=rows('select id from emergency_requests where status in ("COMPLETED","CANCELLED")'); ids=[x['id'] for x in targets]
    if ids:
        marks=','.join('?' for _ in ids); c=conn(); c.execute(f'delete from hospital_alerts where emergency_id in ({marks})',ids); c.execute(f'delete from tracking_events where emergency_id in ({marks})',ids); c.execute(f'delete from emergency_requests where id in ({marks})',ids); c.commit(); c.close()
    return out({'message':'History cleared','deleted':len(ids)})
@app.post('/api/hospital-alert')
def alert(): return out({'message':'Alert sent (demo)'})
@app.get('/api/hospital-alerts')
def alerts(): return out({'alerts':rows('select * from hospital_alerts order by id desc')})
@app.post('/api/demo/reset')
def reset():
    reset_demo(); session.clear(); return out({'message':'Demo reset. Default demo data restored.'})
if __name__=='__main__':
    init_db()
    app.run(port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
else: init_db()

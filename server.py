"""Pefrien local application server. Python 3.10+, standard library only.

Development phone codes are deliberately displayed by the client. This mode
binds to loopback only. External auth must be supplied through auth_adapters.py.
"""
import argparse, base64, hashlib, hmac, json, re, secrets, sqlite3, time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from auth_adapters import AUTH_PROVIDERS, send_sms

ROOT=Path(__file__).resolve().parent
DAY=86400
class APIError(Exception):
    def __init__(self,status,message,**extra):self.status=status;self.payload={'error':message,**extra}

class Store:
    def __init__(self,path,clock=time.time,test_phone=None):
        self.path=str(path);self.clock=clock
        if test_phone is not None and (not isinstance(test_phone,str) or not re.fullmatch(r'1[0-9]{10}',test_phone)):raise ValueError('Invalid local test phone')
        self.test_phone=test_phone
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,phone TEXT UNIQUE,nickname TEXT,created REAL,disabled_until REAL DEFAULT 0,permanent INTEGER DEFAULT 0,penalty_at REAL DEFAULT 0,seed INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS codes(phone TEXT PRIMARY KEY,hash TEXT,expires REAL,attempts INTEGER,sent REAL);
            CREATE TABLE IF NOT EXISTS profiles(user_id TEXT PRIMARY KEY,payload TEXT,revision INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS matches(id TEXT PRIMARY KEY,user_id TEXT,target_id TEXT,pet_id TEXT,distance INTEGER,completed INTEGER DEFAULT 0,created REAL);
            CREATE TABLE IF NOT EXISTS likes(actor TEXT,pet_id TEXT,target TEXT,created REAL,PRIMARY KEY(actor,pet_id));
            CREATE TABLE IF NOT EXISTS blocks(actor TEXT,target TEXT,active INTEGER,updated REAL,PRIMARY KEY(actor,target));
            CREATE TABLE IF NOT EXISTS block_events(actor TEXT,target TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,user_id TEXT,kind TEXT,body TEXT,contact TEXT,status TEXT DEFAULT '待处理',reply TEXT DEFAULT '',created REAL);
            CREATE TABLE IF NOT EXISTS rates(bucket TEXT PRIMARY KEY,count INTEGER,expires REAL);
            ''')
            for i,(breed,name,distance) in enumerate(zip(['金毛','柯基','柴犬','比熊','拉布拉多','边牧'],['栗子','年糕','团团','棉花','可可','奥利'],[350,800,1500,2200,4200,6500])):
                uid='demo-'+str(i);pid='demo-pet-'+str(i)
                c.execute('INSERT OR IGNORE INTO users(id,nickname,created,seed) VALUES(?,?,?,1)',(uid,'附近的狗友',self.clock()))
                pet={'id':pid,'name':name,'breed':breed,'age':'2','weight':str([26,12,10,5,28,18][i]),'sex':'女孩子' if i%2 else '男孩子','want':[],'avoid':[],'ready':True,'image':'assets/golden-sample.webp' if i==0 else ''}
                payload={'seen':True,'pets':[pet],'selected':[pid],'radius':'2','demoDistance':distance}
                c.execute('INSERT OR IGNORE INTO profiles VALUES(?,?,0)',(uid,json.dumps(payload,ensure_ascii=False)))
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE');yield c;c.commit()
        except: c.rollback();raise
        finally:c.close()
    def rate(self,bucket,limit,seconds):
        now=self.clock()
        with self.db() as c:
            r=c.execute('SELECT * FROM rates WHERE bucket=?',(bucket,)).fetchone()
            if r and r['expires']>now:
                if r['count']>=limit:raise APIError(429,'操作有点频繁，请稍后再试。')
                c.execute('UPDATE rates SET count=count+1 WHERE bucket=?',(bucket,))
            else:c.execute('INSERT OR REPLACE INTO rates VALUES(?,1,?)',(bucket,now+seconds))
    def request_code(self,phone,development=True):
        if not (isinstance(phone,str) and len(phone)==11 and phone.startswith('1') and phone.isascii() and phone.isdigit()):raise APIError(400,'请输入 11 位手机号。')
        now=self.clock();code=str(secrets.randbelow(1000000)).zfill(6)
        with self.db() as c:
            old=c.execute('SELECT sent FROM codes WHERE phone=?',(phone,)).fetchone()
            if old and now-old['sent']<60:raise APIError(429,'请在 60 秒后重新获取验证码。')
            if not development:send_sms(phone,code)
            c.execute('INSERT OR REPLACE INTO codes VALUES(?,?,?,?,?)',(phone,hashlib.sha256(code.encode()).hexdigest(),now+300,0,now))
        result={'expiresIn':300,'retryAfter':60,'mode':'local' if development else 'sms'}
        if development:result['developmentCode']=code
        return result
    def verify(self,phone,code,allow_test_login=False):
        now=self.clock();error=None;result=None
        test_login=allow_test_login and self.test_phone is not None and phone==self.test_phone
        if test_login and (not isinstance(code,str) or not code.strip()):raise APIError(400,'测试账号也请填写一个验证码，例如 123456。')
        with self.db() as c:
            row=c.execute('SELECT * FROM codes WHERE phone=?',(phone,)).fetchone()
            if not test_login and (not row or row['expires']<=now or row['attempts']>=5):error=APIError(400,'验证码已失效，请重新获取。')
            elif not test_login and not hmac.compare_digest(row['hash'],hashlib.sha256(str(code).encode()).hexdigest()):
                c.execute('UPDATE codes SET attempts=attempts+1 WHERE phone=?',(phone,));error=APIError(400,'验证码不正确。')
            else:
                c.execute('DELETE FROM codes WHERE phone=?',(phone,))
                user=c.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                if not user:
                    uid=secrets.token_hex(12);c.execute('INSERT INTO users(id,phone,nickname,created) VALUES(?,?,?,?)',(uid,phone,'狗友'+phone[-4:],now))
                    c.execute('INSERT INTO profiles VALUES(?,?,0)',(uid,json.dumps({'seen':True,'pets':[],'selected':[],'radius':'2'})))
                else:uid=user['id']
                token=secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,now+30*DAY));result=(uid,token)
        if error:raise error
        return result
    def session(self,token):
        if not token:return None
        with self.db() as c:
            row=c.execute('SELECT user_id FROM sessions WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),self.clock())).fetchone()
            return row['user_id'] if row else None
    def logout(self,token):
        with self.db() as c:c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def behavior(self,c,uid):
        now=self.clock();r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not r:raise APIError(404,'账号不存在。')
        count=c.execute('SELECT COUNT(DISTINCT actor) FROM block_events WHERE target=? AND created>?',(uid,now-30*DAY)).fetchone()[0]
        # First block alone does not lower the score. Threshold penalties are server-owned.
        return {'score':max(0,100-5*max(0,count-1)),'blocks30d':count,'warning':count>=3,'disabledUntil':r['disabled_until'],'permanent':bool(r['permanent']),'canMatch':not r['permanent'] and r['disabled_until']<=now}
    def account(self,uid):
        with self.db() as c:
            r=c.execute('SELECT id,phone,nickname FROM users WHERE id=?',(uid,)).fetchone()
            return {**dict(r),'phone':r['phone'][:3]+'****'+r['phone'][-4:] if r['phone'] else '', 'behavior':self.behavior(c,uid)}
    def profile(self,uid):
        with self.db() as c:
            r=c.execute('SELECT * FROM profiles WHERE user_id=?',(uid,)).fetchone()
            return {'family':json.loads(r['payload']),'revision':r['revision']}
    def save_profile(self,uid,body):
        f=body.get('family');revision=body.get('revision')
        if not isinstance(f,dict) or not isinstance(f.get('pets'),list) or len(f['pets'])>20:raise APIError(400,'每个账户最多保存 20 只小狗。')
        pets=[];ids=set()
        for p in f['pets']:
            if not isinstance(p,dict):raise APIError(400,'宠物资料格式不正确。')
            pid=p.get('id','')
            if not isinstance(pid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',pid) or pid in ids:raise APIError(400,'宠物编号无效。')
            ids.add(pid)
            image=p.get('image','')
            if not isinstance(image,str) or len(image)>900000:raise APIError(400,'照片太大，请重新上传。')
            if image:
                if not image.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise APIError(400,'照片格式不支持。')
                try:base64.b64decode(image.split(',',1)[1],validate=True)
                except:raise APIError(400,'照片内容无效。')
            item={'id':pid,'image':image,'ready':p.get('ready') is True}
            for key,size in [('name',12),('breed',40),('age',8),('weight',8),('sex',8)]:item[key]=str(p.get(key,''))[:size]
            for key in ['want','avoid']:
                values=p.get(key,[])
                if not isinstance(values,list):raise APIError(400,'交友偏好格式不正确。')
                item[key]=list(dict.fromkeys(str(v)[:40] for v in values))[:200]
            draft=p.get('searchDraft',{});item['searchDraft']={k:str(draft.get(k,''))[:40] for k in ['want','avoid']} if isinstance(draft,dict) else {}
            pets.append(item)
        radius=str(f.get('radius','2'))
        if radius not in ['0.5','1','2','3','5','plus']:radius='2'
        selected=f.get('selected',[])
        clean={'seen':bool(f.get('seen',True)),'pets':pets,'selected':[x for x in selected if x in ids] if isinstance(selected,list) else [],'radius':radius}
        with self.db() as c:
            old=c.execute('SELECT revision FROM profiles WHERE user_id=?',(uid,)).fetchone()
            if revision!=old['revision']:raise APIError(409,'其他页面或设备更新了资料，请先载入最新版本。',revision=old['revision'])
            c.execute('UPDATE profiles SET payload=?,revision=revision+1 WHERE user_id=?',(json.dumps(clean,ensure_ascii=False),uid))
            return {'revision':revision+1}
    @staticmethod
    def complete(p):
        try:return p.get('ready') and str(p.get('name','')).strip() and str(p.get('breed','')).strip() and p.get('sex') in ['男孩子','女孩子'] and .1<=float(p.get('age',0))<=30 and .1<=float(p.get('weight',0))<=100
        except (ValueError,TypeError):return False
    @staticmethod
    def breed(b):
        return {'边境牧羊犬':'边牧','二哈':'哈士奇','西伯利亚雪橇犬':'哈士奇','黄金猎犬':'金毛','泰迪':'贵宾 / 泰迪','贵宾犬':'贵宾 / 泰迪'}.get(b,b)
    def compatible(self,own,others):
        def accepts(a,b):return self.breed(b['breed']) not in [self.breed(x) for x in a.get('avoid',[])] and (not a.get('want') or self.breed(b['breed']) in [self.breed(x) for x in a['want']])
        return all(accepts(a,b) and accepts(b,a) for a in own for b in others)
    def candidates(self,c,uid):
        if not self.behavior(c,uid)['canMatch']:raise APIError(403,'账户暂不能匹配，可在「我的」查看原因或提交反馈。')
        own=json.loads(c.execute('SELECT payload FROM profiles WHERE user_id=?',(uid,)).fetchone()[0]);selected=[p for p in own['pets'] if p['id'] in own['selected'] and self.complete(p)]
        if not selected:raise APIError(400,'先补齐小狗资料，并选好今天出门的小分队。')
        limit=20000 if own.get('radius')=='plus' else float(own.get('radius','2'))*1000;out=[]
        for row in c.execute('SELECT p.*,u.seed FROM profiles p JOIN users u ON p.user_id=u.id WHERE user_id<>?',(uid,)).fetchall():
            target=row['user_id']
            if not self.behavior(c,target)['canMatch']:continue
            if c.execute('SELECT 1 FROM blocks WHERE active=1 AND ((actor=? AND target=?) OR (actor=? AND target=?))',(uid,target,target,uid)).fetchone():continue
            f=json.loads(row['payload']);dogs=[p for p in f['pets'] if p['id'] in f['selected'] and self.complete(p)]
            distance=f.get('demoDistance',800)
            if not dogs or distance>limit or not self.compatible(selected,dogs):continue
            for p in dogs:
                liked=bool(c.execute('SELECT 1 FROM likes WHERE actor=? AND pet_id=? AND target=?',(uid,p['id'],target)).fetchone())
                out.append({'target':target,'pet':p,'distance':distance,'weight':3 if liked else 1,'sample':bool(row['seed'])})
        return out
    def match(self,uid):
        with self.db() as c:
            choices=self.candidates(c,uid)
            if not choices:return {'match':None}
            roll=secrets.randbelow(sum(x['weight'] for x in choices));chosen=choices[-1]
            for x in choices:
                roll-=x['weight']
                if roll<0:chosen=x;break
            mid=secrets.token_hex(16);c.execute('INSERT INTO matches VALUES(?,?,?,?,?,0,?)',(mid,uid,chosen['target'],chosen['pet']['id'],chosen['distance'],self.clock()))
            return {'match':{'id':mid,'distance':chosen['distance'],'localRoute':True}}
    def encounter(self,c,uid,mid,complete=False):
        m=c.execute('SELECT * FROM matches WHERE id=? AND user_id=?',(mid,uid)).fetchone()
        if not m:raise APIError(404,'这次相遇不存在。')
        if complete:c.execute('UPDATE matches SET completed=1 WHERE id=?',(mid,))
        elif not m['completed']:raise APIError(400,'相遇后再留下评价吧。')
        return m
    def finish(self,uid,mid):
        with self.db() as c:
            m=self.encounter(c,uid,mid,True);f=json.loads(c.execute('SELECT payload FROM profiles WHERE user_id=?',(m['target_id'],)).fetchone()[0]);p=next((x for x in f['pets'] if x['id']==m['pet_id']),None)
            if not p:raise APIError(404,'对方的小狗档案已经更新。')
            public={k:p.get(k,'') for k in ['id','name','breed','age','weight','sex','image']}
            return {'pet':public,'liked':bool(c.execute('SELECT 1 FROM likes WHERE actor=? AND pet_id=? AND target=?',(uid,m['pet_id'],m['target_id'])).fetchone()),'blocked':bool(c.execute('SELECT 1 FROM blocks WHERE actor=? AND target=? AND active=1',(uid,m['target_id'])).fetchone())}
    def react(self,uid,mid,kind,value):
        if type(value) is not bool:raise APIError(400,'请选择有效操作。')
        with self.db() as c:
            m=self.encounter(c,uid,mid);target=m['target_id'];now=self.clock()
            if kind=='like':
                if value:c.execute('INSERT OR IGNORE INTO likes VALUES(?,?,?,?)',(uid,m['pet_id'],target,now))
                else:c.execute('DELETE FROM likes WHERE actor=? AND pet_id=? AND target=?',(uid,m['pet_id'],target))
            elif kind=='block':
                c.execute('INSERT OR REPLACE INTO blocks VALUES(?,?,?,?)',(uid,target,int(value),now))
                if value:
                    duplicate=c.execute('SELECT 1 FROM block_events WHERE actor=? AND target=? AND created>?',(uid,target,now-30*DAY)).fetchone()
                    if not duplicate:c.execute('INSERT INTO block_events VALUES(?,?,?)',(uid,target,now))
                    b=self.behavior(c,target);u=c.execute('SELECT * FROM users WHERE id=?',(target,)).fetchone()
                    if b['blocks30d']>=10:c.execute('UPDATE users SET permanent=1 WHERE id=?',(target,))
                    elif b['blocks30d']>=5 and u['penalty_at']<=now-30*DAY:c.execute('UPDATE users SET disabled_until=?,penalty_at=? WHERE id=?',(now+DAY,now,target))
            else:raise APIError(404,'操作不存在。')
            return {'ok':True}
    def relations(self,uid):
        with self.db() as c:
            likes=[dict(x) for x in c.execute('SELECT pet_id,target,created FROM likes WHERE actor=?',(uid,))];blocks=[dict(x) for x in c.execute('SELECT target,updated FROM blocks WHERE actor=? AND active=1',(uid,))]
            for x in likes+blocks:
                f=json.loads(c.execute('SELECT payload FROM profiles WHERE user_id=?',(x['target'],)).fetchone()[0]);x['names']='、'.join(p['name'] for p in f['pets']);x['petName']=next((p['name'] for p in f['pets'] if p['id']==x.get('pet_id')),'')
            return {'likes':likes,'blocks':blocks}
    def feedback(self,uid,b):
        body=str(b.get('body','')).strip();kind=b.get('kind','建议')
        if not 5<=len(body)<=2000:raise APIError(400,'请填写 5–2000 字的反馈。')
        if kind not in ['建议','功能问题','账户申诉','其他']:raise APIError(400,'请选择反馈类型。')
        fid=secrets.token_hex(8)
        with self.db() as c:c.execute('INSERT INTO feedback(id,user_id,kind,body,contact,created) VALUES(?,?,?,?,?,?)',(fid,uid,kind,body,str(b.get('contact',''))[:120],self.clock()))
        return {'id':fid,'message':'反馈已收到，谢谢你帮 Pefrien 变得更好。'}

class Handler(SimpleHTTPRequestHandler):
    server_version='PefrienLocal/0.1'
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def log_message(self,format,*args):pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin');self.send_header('X-Frame-Options','DENY')
        if not self.path.startswith('/api/'):self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def do_GET(self):
        if self.path.startswith('/api/'):self.dispatch('GET')
        else:
            path=urlsplit(self.path).path
            if any(x.startswith('.') for x in path.split('/') if x):self.send_error(404);return
            super().do_GET()
    def do_POST(self):self.dispatch('POST')
    def do_PUT(self):self.dispatch('PUT')
    def do_DELETE(self):self.dispatch('DELETE')
    def reply(self,status,data,cookie=None):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)
    def dispatch(self,method):
        try:
            # Local dev cannot be exposed publicly; reject browser requests from another origin.
            origin=self.headers.get('Origin');host=self.headers.get('Host','')
            if host not in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']:raise APIError(403,'只允许本机访问。')
            if origin and urlsplit(origin).netloc!=host:raise APIError(403,'跨站请求被拒绝。')
            if method!='GET' and self.headers.get('Content-Type','').split(';')[0]!='application/json':raise APIError(415,'请使用 JSON 请求。')
            size=int(self.headers.get('Content-Length','0'))
            if size<0:raise APIError(400,'请求长度无效。')
            if size>20000000:raise APIError(413,'资料体积过大。')
            b=json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(b,dict):raise APIError(400,'请求格式不正确。')
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie['pefrien_session'].value if 'pefrien_session' in cookie else ''
            s=self.server.store;uid=s.session(token);path=urlsplit(self.path).path;result=None;set_cookie=None
            expected=self.headers.get('X-Pefrien-Account')
            if expected and uid!=expected and not path.startswith('/api/auth/'):raise APIError(401,'登录身份已变化，请刷新页面。本机草稿仍保留。')
            if path=='/api/config' and method=='GET':result={'mode':'local','providers':[{'id':k,'name':v['name'],'configured':False} for k,v in AUTH_PROVIDERS.items()]}
            elif path=='/api/auth/code' and method=='POST':s.rate('sms:'+self.client_address[0],20,3600);result=s.request_code(b.get('phone',''))
            elif path=='/api/auth/verify' and method=='POST':
                local_test=self.server.server_address[0] in ('127.0.0.1','::1') and self.client_address[0] in ('127.0.0.1','::1')
                s.rate('verify:'+self.client_address[0],60,3600);uid,token=s.verify(b.get('phone',''),b.get('code',''),allow_test_login=local_test);result={'user':s.account(uid)};set_cookie='pefrien_session='+token+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000'
            elif path=='/api/auth/oauth/start' and method=='POST':raise APIError(503,'尚未配置此平台的正式应用。请先用手机号本地验证码体验。')
            elif path=='/api/auth/logout' and method=='POST':s.logout(token);result={'ok':True};set_cookie='pefrien_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
            elif path=='/api/me' and method=='GET':result={'user':s.account(uid) if uid else None}
            elif path=='/api/feedback' and method=='POST':s.rate('feedback:'+str(uid or self.client_address[0]),10,3600);result=s.feedback(uid,b)
            elif path.startswith('/api/ops/'):
                supplied=self.headers.get('Authorization','').removeprefix('Bearer ')
                if not hmac.compare_digest(supplied,self.server.ops_key):raise APIError(401,'运营密钥不正确。')
                if path=='/api/ops/feedback' and method=='GET':
                    with s.db() as c:result={'items':[dict(r) for r in c.execute('SELECT * FROM feedback ORDER BY created DESC LIMIT 500')]}
                elif path=='/api/ops/feedback' and method=='PUT':
                    if b.get('status') not in ['待处理','处理中','已解决']:raise APIError(400,'处理状态无效。')
                    with s.db() as c:c.execute('UPDATE feedback SET status=?,reply=? WHERE id=?',(b['status'],str(b.get('reply',''))[:1000],b.get('id','')))
                    result={'ok':True}
                else:raise APIError(404,'接口不存在。')
            else:
                if not uid:raise APIError(401,'请先登录，让小狗档案跟着你走。')
                if path=='/api/profile' and method=='GET':result=s.profile(uid)
                elif path=='/api/profile' and method=='PUT':result=s.save_profile(uid,b)
                elif path=='/api/matches' and method=='POST':result=s.match(uid)
                elif path=='/api/matches/complete' and method=='POST':result=s.finish(uid,b.get('id',''))
                elif path=='/api/reactions' and method=='PUT':result=s.react(uid,b.get('matchId',''),b.get('kind'),b.get('value'))
                elif path=='/api/relations' and method=='GET':result=s.relations(uid)
                elif path=='/api/relations' and method=='DELETE':
                    with s.db() as c:
                        if b.get('kind')=='block':c.execute('UPDATE blocks SET active=0 WHERE actor=? AND target=?',(uid,b.get('target')))
                        elif b.get('kind')=='like':c.execute('DELETE FROM likes WHERE actor=? AND target=? AND pet_id=?',(uid,b.get('target'),b.get('petId')))
                        else:raise APIError(400,'操作无效。')
                    result={'ok':True}
                elif path=='/api/feedback' and method=='GET':
                    with s.db() as c:result={'items':[dict(r) for r in c.execute('SELECT id,kind,body,status,reply,created FROM feedback WHERE user_id=? ORDER BY created DESC',(uid,))]}
                else:raise APIError(404,'接口不存在。')
            self.reply(200,result,set_cookie)
        except APIError as e:self.reply(e.status,e.payload)
        except (ValueError,TypeError,KeyError):self.reply(400,{'error':'请求格式不正确。'})
        except Exception:self.reply(500,{'error':'服务器暂时遇到问题，请稍后重试。'})

def serve(port=8767,data=None):
    runtime=Path(data or ROOT/'.runtime');runtime.mkdir(parents=True,exist_ok=True)
    keyfile=runtime/'ops-key.txt'
    if not keyfile.exists():keyfile.write_text(secrets.token_urlsafe(32),encoding='utf8')
    configfile=runtime/'local-auth.json'
    config=json.loads(configfile.read_text(encoding='utf8')) if configfile.exists() else {}
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.store=Store(runtime/'pefrien.sqlite3',test_phone=config.get('testPhone'));server.ops_key=keyfile.read_text(encoding='utf8').strip()
    print(f'Pefrien local: http://127.0.0.1:{port}/',flush=True);server.serve_forever()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);p.add_argument('--data');args=p.parse_args();serve(args.port,args.data)

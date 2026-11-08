"""Isolated HTTP/session/security smoke test; does not touch the preview database."""
import http.cookiejar,json,sys,tempfile,threading,time,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Store,Handler,ThreadingHTTPServer
scratch=Path(__file__).resolve().parents[1]/'.runtime'/'tests';scratch.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=scratch) as temp:
    now=[time.time()];srv=ThreadingHTTPServer(('127.0.0.1',0),Handler);srv.store=Store(Path(temp)/'http.db',lambda:now[0]);srv.ops_key='isolated-test-operator-key'
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(srv.server_port)
    jars=[http.cookiejar.CookieJar(),http.cookiejar.CookieJar()];clients=[urllib.request.build_opener(urllib.request.HTTPCookieProcessor(j)) for j in jars]
    def req(path,method='GET',data=None,client=0,headers=None,expected=200):
        h={'Content-Type':'application/json',**(headers or {})};r=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=h)
        try:res=clients[client].open(r)
        except urllib.error.HTTPError as e:res=e
        assert res.status==expected,(path,res.status,expected);raw=res.read()
        return json.loads(raw) if 'json' in res.headers.get('Content-Type','') else raw
    try:
        req('/api/profile',expected=401);req('/api/auth/code','POST',{'phone':'13800000288'},headers={'Origin':'https://untrusted.example'},expected=403)
        code=req('/api/auth/code','POST',{'phone':'13800000288'})['developmentCode'];a=req('/api/auth/verify','POST',{'phone':'13800000288','code':code})['user']
        assert any(c.name=='pefrien_session' and 'HttpOnly' in c._rest for c in jars[0]);assert req('/api/me')['user']['id']==a['id']
        f={'seen':True,'pets':[],'selected':[],'radius':'5'};req('/api/profile','PUT',{'family':f,'revision':0})
        now[0]+=61;code=req('/api/auth/code','POST',{'phone':'13800000288'},client=1)['developmentCode'];req('/api/auth/verify','POST',{'phone':'13800000288','code':code},client=1)
        assert req('/api/profile',client=1)['family']['radius']=='5'
        req('/api/profile','PUT',{'family':f,'revision':0},client=1,expected=409)
        req('/api/profile','PUT',{'family':f,'revision':1},headers={'X-Pefrien-Account':'different-account'},expected=401)
        req('/api/auth/oauth/start','POST',{'provider':'wechat'},expected=503)
        r=req('/api/feedback','POST',{'kind':'建议','body':'测试反馈链路，收到后可标记已解决。'})
        req('/api/ops/feedback',expected=401)
        h={'Authorization':'Bearer '+srv.ops_key};items=req('/api/ops/feedback',headers=h)['items'];assert items[0]['id']==r['id']
        req('/api/ops/feedback','PUT',{'id':r['id'],'status':'已解决','reply':'收到，谢谢。'},headers=h)
        assert req('/api/feedback')['items'][0]['reply']=='收到，谢谢。'
        req('/.runtime/ops-key.txt',expected=404);req('/server.py',expected=404)
        req('/api/auth/logout','POST',{});assert req('/api/me')['user'] is None
        print('PASS: HTTP sessions, same-account second client, conflicts, account switch guard, CSRF, OAuth unavailable state, protected ops reply, private file isolation, logout.')
    finally:srv.shutdown();srv.server_close();thread.join()

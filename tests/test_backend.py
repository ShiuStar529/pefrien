import base64,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Store,APIError,DAY

class BackendTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).resolve().parents[1]/'.runtime'/'tests';scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch);self.now=100*DAY;self.s=Store(Path(self.temp.name)/'test.db',lambda:self.now)
        self.user,self.token=self.login('13800000001')
        self.pet={'id':'mydog','name':'豆包','breed':'金毛','age':'2','weight':'24','sex':'男孩子','ready':True,'want':[],'avoid':[],'image':'data:image/webp;base64,'+base64.b64encode(b'photo').decode()}
        self.f={'seen':True,'pets':[self.pet],'selected':['mydog'],'radius':'2'}
        self.s.save_profile(self.user,{'family':self.f,'revision':0})
    def tearDown(self):self.temp.cleanup()
    def login(self,phone):
        code=self.s.request_code(phone)['developmentCode'];return self.s.verify(phone,code)
    def encounter(self,actor,target,petid='demo-pet-0'):
        mid=actor+'-'+target
        with self.s.db() as c:c.execute('INSERT OR REPLACE INTO matches VALUES(?,?,?,?,?,1,?)',(mid,actor,target,petid,350,self.now))
        return mid
    def behavior(self,uid):
        with self.s.db() as c:return self.s.behavior(c,uid)
    def candidates(self):
        with self.s.db() as c:return self.s.candidates(c,self.user)
    def test_auth_otp_expiry_replay_and_sessions(self):
        self.assertEqual(self.s.session(self.token),self.user)
        with self.assertRaises(APIError):self.s.verify('13800000001','000000')
        self.now+=61;code=self.s.request_code('13800000001')['developmentCode']
        uid,newtoken=self.s.verify('13800000001',code);self.assertEqual(uid,self.user);self.assertEqual(self.s.profile(uid)['family']['pets'][0]['image'],self.pet['image'])
        self.s.logout(newtoken);self.assertIsNone(self.s.session(newtoken));self.assertEqual(self.s.session(self.token),uid)
        code=self.s.request_code('13800000002')['developmentCode'];self.now+=301
        with self.assertRaises(APIError):self.s.verify('13800000002',code)
        self.now+=31*DAY;self.assertIsNone(self.s.session(self.token))
    def test_wrong_codes_are_limited(self):
        r=self.s.request_code('13800000002');wrong='000000' if r['developmentCode']!='000000' else '111111'
        for _ in range(5):
            with self.assertRaises(APIError):self.s.verify('13800000002',wrong)
        with self.assertRaises(APIError):self.s.verify('13800000002',r['developmentCode'])
    def test_profile_isolation_and_conflict(self):
        other,_=self.login('13800000002');self.assertEqual(self.s.profile(other)['family']['pets'],[])
        with self.assertRaises(APIError) as e:self.s.save_profile(self.user,{'family':self.f,'revision':0})
        self.assertEqual(e.exception.status,409)
        self.f['pets'][0]['name']='新名字';self.s.save_profile(self.user,{'family':self.f,'revision':1});self.assertEqual(self.s.profile(self.user)['revision'],2)
    def test_distance_likes_blocks_and_preferences(self):
        self.assertEqual(len(self.candidates()),3)
        self.f['radius']='0.5';self.s.save_profile(self.user,{'family':self.f,'revision':1});self.assertEqual(len(self.candidates()),1)
        mid=self.s.match(self.user)['match']['id'];self.assertNotIn('pet',self.s.match(self.user)['match'])
        with self.assertRaises(APIError):self.s.react(self.user,mid,'like',True)
        public=self.s.finish(self.user,mid);self.assertNotIn('avoid',public['pet']);self.assertNotIn('want',public['pet']);self.s.react(self.user,mid,'like',True);self.assertEqual(self.candidates()[0]['weight'],3)
        self.s.react(self.user,mid,'block',True);self.assertEqual(self.candidates(),[])
        self.s.react(self.user,mid,'block',False);self.assertEqual(len(self.candidates()),1)
        self.f['pets'][0]['avoid']=['黄金猎犬'];self.s.save_profile(self.user,{'family':self.f,'revision':2});self.assertEqual(self.candidates(),[])
    def test_account_wide_bilateral_blocks(self):
        other,_=self.login('13800000002');f={'pets':[dict(self.pet,id='otherdog')],'selected':['otherdog'],'radius':'2'};self.s.save_profile(other,{'family':f,'revision':0})
        self.s.react(other,self.encounter(other,self.user,'mydog'),'block',True)
        self.assertNotIn(other,[x['target'] for x in self.candidates()])
    def test_thresholds_duplicate_expiry_permanent(self):
        for i in range(1,11):
            actor,_=self.login('13900000'+str(i).zfill(3));mid=self.encounter(actor,self.user,'mydog');self.s.react(actor,mid,'block',True)
            self.s.react(actor,mid,'block',False);self.s.react(actor,mid,'block',True)
            b=self.behavior(self.user);self.assertEqual(b['blocks30d'],i)
            if i==1:self.assertEqual(b['score'],100)
            if i==3:self.assertTrue(b['warning']);self.assertTrue(b['canMatch'])
            if i==5:self.assertFalse(b['canMatch']);self.assertEqual(b['disabledUntil'],self.now+DAY)
            if i==6:
                original=b['disabledUntil'];self.now+=DAY+1;self.assertTrue(self.behavior(self.user)['canMatch']);self.s.react(actor,mid,'block',True);self.assertEqual(self.behavior(self.user)['disabledUntil'],original)
        self.assertTrue(self.behavior(self.user)['permanent']);self.now+=31*DAY
        b=self.behavior(self.user);self.assertEqual(b['blocks30d'],0);self.assertEqual(b['score'],100);self.assertTrue(b['permanent']);self.assertFalse(b['canMatch'])
    def test_feedback_stored_even_when_blocked(self):
        with self.s.db() as c:c.execute('UPDATE users SET permanent=1 WHERE id=?',(self.user,))
        result=self.s.feedback(self.user,{'kind':'账户申诉','body':'希望运营查看我的申诉','contact':''})
        with self.s.db() as c:self.assertEqual(c.execute('SELECT user_id FROM feedback WHERE id=?',(result['id'],)).fetchone()[0],self.user)
    def test_unsafe_pet_identifier_is_rejected(self):
        self.f['pets'][0]['id']="x');alert(1)//"
        with self.assertRaises(APIError):self.s.save_profile(self.user,{'family':self.f,'revision':1})
    def test_reaction_requires_owned_completed_match(self):
        other,_=self.login('13800000002');mid=self.encounter(other,'demo-0')
        with self.assertRaises(APIError):self.s.react(self.user,mid,'block',True)

if __name__=='__main__':unittest.main()

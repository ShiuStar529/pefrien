const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../accounts.js'),'utf8');
const prefix=source.split('/* Local account UI.')[0];
const data=new Map();let now=1000000000000,quota=false;
const storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>{if(quota)throw Error('QuotaExceeded');data.set(k,v)}};
function boot(host='shiustar529.github.io'){
 const ctx=vm.createContext({location:{hostname:host,pathname:'/pefrien/'},localStorage:storage});
 vm.runInContext(prefix,ctx);ctx.storage=storage;ctx.clock=()=>now;ctx.roll=()=>.7;
 return vm.runInContext('isPagesDemo ? createPagesDemo(storage,clock,roll) : pagesDemoApi',ctx);
}
(async()=>{
 let api=boot();assert.equal((await api('/me')).user,null);
 await assert.rejects(api('/auth/verify','POST',{phone:'13800000009',code:'123456'}));
 await assert.rejects(api('/auth/verify','POST',{phone:'15012345678',code:' '}));
 const login=await api('/auth/verify','POST',{phone:'15012345678',code:'1'});assert.equal(login.user.id,'pages-demo-user');
 await assert.rejects(api('/matches','POST',{}));
 let p=await api('/profile');const dog={id:'mydog',name:'测试边牧',breed:'边牧',age:'2',weight:'18',sex:'男孩子',ready:true,want:[],avoid:[],image:'data:image/webp;base64,cGhvdG8='};
 p.family.pets=[dog];p.family.selected=['mydog'];p.family.radius='0.5';
 await api('/profile','PUT',{family:p.family,revision:p.revision});
 api=boot();assert.equal((await api('/me')).user.id,login.user.id);assert.equal((await api('/profile')).family.pets[0].image,dog.image);
 await assert.rejects(api('/profile','PUT',{family:p.family,revision:0}),e=>e.status===409);
 let m=(await api('/matches','POST',{})).match;assert.equal(m.distance,350);assert.equal(m.pet,undefined);
 await assert.rejects(api('/reactions','PUT',{matchId:m.id,kind:'like',value:true}));
 const pet=(await api('/matches/complete','POST',{id:m.id})).pet;assert.equal(pet.breed,'金毛');assert.equal(pet.avoid,undefined);
 await api('/reactions','PUT',{matchId:m.id,kind:'like',value:true});assert.equal((await api('/relations')).likes.length,1);
 await api('/reactions','PUT',{matchId:m.id,kind:'block',value:true});api=boot();assert.equal((await api('/matches','POST',{})).match,null);
 await api('/relations','DELETE',{kind:'block',target:'sample-owner-0'});assert.ok((await api('/matches','POST',{})).match);
 p=await api('/profile');p.family.pets[0].avoid=['黄金猎犬'];await api('/profile','PUT',p);assert.equal((await api('/matches','POST',{})).match,null);
 const f=await api('/feedback','POST',{body:'手机演示反馈保存测试',kind:'建议'});assert.equal(f.localOnly,true);assert.equal((await api('/feedback')).items[0].status,'仅保存在本机');
 quota=true;await assert.rejects(api('/feedback','POST',{body:'不能假装保存成功'}));quota=false;
 await api('/auth/logout','POST',{});assert.equal((await boot()('/me')).user,null);await assert.rejects(api('/profile'),e=>e.status===401);
 await api('/auth/verify','POST',{phone:'15012345678',code:'abc'});assert.equal((await api('/profile')).family.pets.length,1);
 now+=31*86400000;assert.equal((await api('/me')).user,null);
 assert.equal(boot('127.0.0.1'),null);assert.equal(boot('example.com'),null);
 console.log('PASS: Pages test login, old phone rejection, profile/photo persistence, automatic login, conflicts, matching, likes/blocks, local feedback, quota errors, logout and host isolation.');
})().catch(e=>{console.error(e);process.exitCode=1});

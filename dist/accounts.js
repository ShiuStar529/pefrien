/* GitHub Pages demo only. This is browser-local sample data, never real authentication. */
const isPagesDemo=location.hostname==='shiustar529.github.io' && /^\/pefrien(?:\/|$)/.test(location.pathname);
function createPagesDemo(storage,now=Date.now,random=Math.random){
  const key='pefrien.pages-demo.v1',phone='15012345678',clone=v=>JSON.parse(JSON.stringify(v));
  const fail=(message,status=400)=>{const e=new Error(message);e.status=status;throw e};
  const blank=()=>({sessionExpires:0,family:{seen:true,pets:[],selected:[],radius:'2'},revision:0,matches:{},likes:[],blocks:[],feedback:[]});
  const read=()=>{try{return JSON.parse(storage.getItem(key)||'null')||blank()}catch(e){fail('无法读取本机演示资料，请检查浏览器存储权限。')}};
  const save=s=>{try{storage.setItem(key,JSON.stringify(s))}catch(e){fail('本机存储空间不足，资料尚未保存，请减小照片后重试。')}};
  const user=()=>({id:'pages-demo-user',phone:'150****5678',nickname:'测试狗友',behavior:{score:100,blocks30d:0,warning:false,disabledUntil:0,permanent:false,canMatch:true}});
  const samples=['金毛','柯基','柴犬','比熊','拉布拉多','边牧'].map((breed,i)=>({target:'sample-owner-'+i,distance:[350,800,1500,2200,4200,6500][i],pet:{id:'sample-pet-'+i,name:['栗子','年糕','团团','棉花','可可','奥利'][i],breed,age:'2',weight:String([26,12,10,5,28,18][i]),sex:i%2?'女孩子':'男孩子',image:i===0?'assets/golden-sample.webp':'',want:[],avoid:[],ready:true}}));
  const breed=b=>({'边境牧羊犬':'边牧','黄金猎犬':'金毛','二哈':'哈士奇','西伯利亚雪橇犬':'哈士奇','贵宾犬':'贵宾 / 泰迪','泰迪':'贵宾 / 泰迪'}[b]||b);
  const complete=p=>p.ready&&String(p.name||'').trim()&&String(p.breed||'').trim()&&['男孩子','女孩子'].includes(p.sex)&&Number(p.age)>=.1&&Number(p.age)<=30&&Number(p.weight)>=.1&&Number(p.weight)<=100;
  const accepts=(a,b)=>!(a.avoid||[]).map(breed).includes(breed(b.breed))&&(!(a.want||[]).length||a.want.map(breed).includes(breed(b.breed)));
  return async function(path,method='GET',body={}){
    const s=read(),signedIn=s.sessionExpires>now();
    if(path==='/me')return {user:signedIn?user():null};
    if(path==='/auth/oauth/start')fail('演示版暂未接入第三方登录，请使用测试手机号。',503);
    if(path==='/auth/code'||path==='/auth/verify'){
      if(body.phone!==phone)fail('手机演示版请使用测试手机号 15012345678。');
      if(path==='/auth/code')return {mode:'pages-demo',developmentCode:'123456'};
      if(typeof body.code!=='string'||!body.code.trim())fail('随便填一个验证码即可，例如 123456。');
      s.sessionExpires=now()+30*86400000;save(s);return {user:user()};
    }
    if(path==='/auth/logout'){s.sessionExpires=0;save(s);return {ok:true}}
    if(path==='/feedback'&&method==='POST'){
      const text=String(body.body||'').trim();if(text.length<5||text.length>2000)fail('请填写 5–2000 字的反馈。');
      const id='demo-feedback-'+now()+'-'+s.feedback.length;s.feedback.push({id,userId:signedIn?'pages-demo-user':null,kind:body.kind||'建议',body:text,contact:String(body.contact||'').slice(0,120),status:'仅保存在本机',reply:'',created:now()/1000});save(s);return {id,localOnly:true};
    }
    if(!signedIn)fail('请先使用测试手机号登录。',401);
    if(path==='/profile'){
      if(method==='GET')return {family:clone(s.family),revision:s.revision};
      if(body.revision!==s.revision)fail('其他页面更新了资料，请载入最新版本。',409);
      if(!body.family||!Array.isArray(body.family.pets)||body.family.pets.length>20)fail('小狗档案格式不正确。');
      s.family=clone(body.family);s.revision++;save(s);return {revision:s.revision};
    }
    if(path==='/matches'){
      const f=s.family,own=f.pets.filter(p=>(f.selected||[]).includes(p.id)&&complete(p));
      if(!own.length)fail('先补齐小狗资料，并选好今天出门的小分队。');
      const limit=f.radius==='plus'?20000:Number(f.radius||2)*1000;
      const choices=samples.filter(x=>x.distance<=limit&&!s.blocks.includes(x.target)&&own.every(p=>accepts(p,x.pet)&&accepts(x.pet,p)));
      if(!choices.length)return {match:null};
      const weight=x=>s.likes.includes(x.pet.id)?3:1;let roll=random()*choices.reduce((n,x)=>n+weight(x),0),chosen=choices[choices.length-1];
      for(const x of choices){roll-=weight(x);if(roll<0){chosen=x;break}}
      const id='demo-match-'+now()+'-'+Object.keys(s.matches).length;s.matches[id]={target:chosen.target,petId:chosen.pet.id,completed:false};save(s);return {match:{id,distance:chosen.distance,localRoute:true}};
    }
    if(path==='/matches/complete'||path==='/reactions'){
      const m=s.matches[body.id||body.matchId];if(!m)fail('这次相遇不存在。',404);
      const x=samples.find(x=>x.pet.id===m.petId);if(!x)fail('小狗档案不存在。',404);
      if(path==='/matches/complete'){m.completed=true;save(s);const {want,avoid,ready,...pet}=x.pet;return {pet,liked:s.likes.includes(m.petId),blocked:s.blocks.includes(m.target)}}
      if(!m.completed)fail('相遇后再留下评价吧。');
      if(!['like','block'].includes(body.kind)||typeof body.value!=='boolean')fail('操作无效。');
      const list=body.kind==='like'?'likes':'blocks',value=body.kind==='like'?m.petId:m.target;s[list]=s[list].filter(x=>x!==value);if(body.value)s[list].push(value);save(s);return {ok:true};
    }
    if(path==='/relations'){
      if(method==='DELETE'){if(body.kind==='like')s.likes=s.likes.filter(x=>x!==body.petId);else if(body.kind==='block')s.blocks=s.blocks.filter(x=>x!==body.target);else fail('操作无效。');save(s);return {ok:true}}
      const map=x=>({target:x.target,pet_id:x.pet.id,names:x.pet.name,petName:x.pet.name});return {likes:samples.filter(x=>s.likes.includes(x.pet.id)).map(map),blocks:samples.filter(x=>s.blocks.includes(x.target)).map(map)};
    }
    if(path==='/feedback')return {items:clone(s.feedback.filter(x=>x.userId==='pages-demo-user').reverse())};
    fail('演示版暂不支持此操作。',404);
  };
}
const pagesDemoApi=isPagesDemo?createPagesDemo(localStorage):null;

/* Local account UI. Server sessions own identity; localStorage is only a draft cache. */
const accountState={user:null,ready:false,revision:0,dirty:false,syncing:false,syncError:'',syncTimer:null,conflict:false,requestGeneration:0};
let currentEncounter=null,loginPhone='',localCodeHint='',feedbackDraft={};
const radiusLabels={'0.5':'500 m','1':'1 km','2':'2 km','3':'3 km','5':'5 km',plus:'5 km+'};
async function api(path,method='GET',body){
  if(pagesDemoApi)return pagesDemoApi(path,method,body);
  let res;try{res=await fetch('/api'+path,{method,credentials:'same-origin',headers:{...(method==='GET'?{}:{'Content-Type':'application/json'}),...(accountState.user?{'X-Pefrien-Account':accountState.user.id}:{})},body:body===undefined?undefined:JSON.stringify(body)})}catch(e){throw new Error('暂时连接不上本地服务，资料仍留在这台设备。')}
  const data=await res.json().catch(()=>({error:'请启动 Pefrien 本地后端后重试。'}));
  if(!res.ok){const e=new Error(data.error||'操作未完成，请重试。');e.status=res.status;throw e}return data;
}
function openSheet(title,content){const d=document.getElementById('app-dialog');d.innerHTML=`<div class="sheet-head"><h2>${esc(title)}</h2><button type="button" class="quiet" aria-label="关闭弹窗" onclick="closeSheet()">×</button></div>${content}`;if(!d.open)d.showModal()}
function closeSheet(){document.getElementById('app-dialog').close()}
function tell(message){openSheet('小提示',`<p class="sheet-copy">${esc(message)}</p><button class="primary" onclick="closeSheet()">知道啦</button>`)}
function accountHeader(title,back='home()'){return `<header class="subhead"><button class="back-btn" aria-label="返回" onclick="${back}">${lineIcon('back')}</button><h2>${title}</h2></header>`}
function bottomNav(){return `<nav class="bottom-nav" aria-label="主要导航"><button onclick="home()">${paw()}<span>去散步</span></button><button onclick="familyPage()"><span class="nav-symbol">♡</span><span>小分队</span></button><button onclick="accountPage()"><span class="nav-symbol">☺</span><span>${accountState.user?'我的':'登录 / 我的'}</span></button></nav>`}
function home(){clearTimeout(timer);show(`<section class="home-screen"><header class="top">${brand()}<button class="badge nearby radius-button" onclick="chooseRadius()" aria-label="设置匹配距离，当前${radiusLabels[family.radius||'2']}">附近 ${radiusLabels[family.radius||'2']} <span>⌄</span></button></header><section class="hero"><span class="day-label">今日宜 · 出门撒欢</span><h1>走呀，<br>去交个<em>狗朋友！</em></h1><p>让小鼻子碰个面，让散步多点惊喜。</p></section><div class="puppy-scene"><span class="say hello">一起玩？</span><span class="say woof">汪！</span>${puppyArt()}<span class="scene-note">下一位狗朋友，见面才揭晓</span></div><button class="primary" onclick="match()"><span class="button-label">${paw()} 出发，找狗朋友</span><span class="arr">${lineIcon()}</span></button><p class="under-button">牵好小绳子，带上好奇心。</p>${familySummary()}${bottomNav()}</section>`)}
function chooseRadius(){openSheet('今天想走多远？',`<p class="note">近一点碰面，远一点发现新朋友。</p><div class="radius-grid">${['0.5','1','2','3','5','plus'].map(k=>`<button class="chip ${k===(family.radius||'2')?'on':''}" onclick="setRadius('${k}')">${radiusLabels[k]}</button>`).join('')}</div><p class="note">5 km+ 会扩大搜索范围，请量力安排散步。</p>`)}
function setRadius(v){if(!radiusLabels[v])return;family.radius=v;persist();closeSheet();home()}

const localPersist=persist;
persist=function(){const ok=localPersist();if(accountState.user){accountState.dirty=true;accountState.syncError='';try{localStorage.setItem('pefrien.pending.'+accountState.user.id,JSON.stringify({family,revision:accountState.revision}))}catch(e){storageFailed=true}clearTimeout(accountState.syncTimer);accountState.syncTimer=setTimeout(()=>pushProfile(),450)}refreshSaveStatus();return ok};
const localSaveStatus=refreshSaveStatus;
refreshSaveStatus=function(){localSaveStatus();const el=document.getElementById('autosave-status');if(!el||!accountState.user)return;el.textContent=storageFailed?'本机保存失败，请不要关闭页面。':photoJobs.has(editingId)?'照片处理中，完成后自动同步…':accountState.syncError?'已保留本机草稿，尚未同步到账户':accountState.dirty||accountState.syncing?'已保存本机，正在同步到账户…':(isPagesDemo?'已自动保存在当前浏览器':'已自动保存到账户');if(accountState.conflict)el.innerHTML+=' <button class="text-action" onclick="resolveSyncConflict()">处理版本冲突</button>'};
async function pushProfile(){
  clearTimeout(accountState.syncTimer);
  if(accountState.syncing){while(accountState.syncing)await new Promise(r=>setTimeout(r,30));return !accountState.syncError&&!accountState.dirty}
  if(!accountState.user||!accountState.dirty)return true;
  if(accountState.conflict)return false;
  accountState.syncing=true;refreshSaveStatus();
  try{
    while(accountState.dirty){accountState.dirty=false;const snapshot=JSON.parse(JSON.stringify(family));const result=await api('/profile','PUT',{family:snapshot,revision:accountState.revision});accountState.revision=result.revision;accountState.syncError='';if(!accountState.dirty)localStorage.removeItem('pefrien.pending.'+accountState.user.id);else localStorage.setItem('pefrien.pending.'+accountState.user.id,JSON.stringify({family,revision:accountState.revision}))}
    return true;
  }catch(e){accountState.dirty=true;accountState.syncError=e.message;accountState.conflict=e.status===409;return false}
  finally{accountState.syncing=false;refreshSaveStatus()}
}
async function resolveSyncConflict(){openSheet('资料在别处更新了',`<p class="sheet-copy">当前草稿还在这台设备上。你可以载入账户中的最新资料，或用当前草稿替换它。</p><button class="primary" onclick="reloadAccountProfile()">载入账户最新资料</button><button class="cancel" onclick="overwriteAccountProfile()">确认用这份草稿替换</button>`)}
async function reloadAccountProfile(){try{const r=await api('/profile');family=r.family;accountState.revision=r.revision;accountState.dirty=false;accountState.conflict=false;accountState.syncError='';localStorage.removeItem('pefrien.pending.'+accountState.user.id);localPersist();closeSheet();familyPage()}catch(e){tell(e.message)}}
async function overwriteAccountProfile(){try{const r=await api('/profile');accountState.revision=r.revision;accountState.conflict=false;accountState.dirty=true;if(await pushProfile()){closeSheet();familyPage()}else tell(accountState.syncError)}catch(e){tell(e.message)}}
async function activateAccount(user){
  const guest=JSON.parse(localStorage.getItem('pefrien.family.v1')||'null');
  const r=await api('/profile');accountState.user=user;accountState.revision=r.revision;accountState.dirty=false;accountState.conflict=false;accountState.syncError='';STORAGE_KEY='pefrien.family.user.'+user.id;family=r.family;
  let pending;try{pending=JSON.parse(localStorage.getItem('pefrien.pending.'+user.id)||'null')}catch(e){}
  if(pending){family=pending.family;accountState.dirty=true;accountState.conflict=pending.revision!==r.revision;accountState.syncError=accountState.conflict?'资料在其他设备更新，请处理版本冲突。':'';if(!accountState.conflict)pushProfile()}
  localPersist();home();
  if(!family.pets.length&&guest?.pets?.length){window.guestToImport=guest;openSheet('把小狗名片带过来',`<p class="sheet-copy">这台设备上有 ${guest.pets.length} 只小狗的资料，要绑定到当前账号 ${esc(user.phone)} 吗？</p><button class="primary" onclick="importGuestPets()">绑定并同步小狗档案</button><button class="cancel" onclick="closeSheet()">先不绑定</button>`)}else checkBehaviorNotice();
}
async function importGuestPets(){if(!window.guestToImport)return;family={...window.guestToImport,radius:window.guestToImport.radius||'2',seen:true};window.guestToImport=null;persist();closeSheet();const synced=await pushProfile();familyPage(synced?'小狗名片已绑定到账户！':'本机草稿已保留，稍后可重试同步。')}
async function initializeAccounts(){try{const r=await api('/me');accountState.ready=true;if(r.user)await activateAccount(r.user);else home()}catch(e){accountState.ready=true;accountState.syncError=e.message;home()}}
function checkBehaviorNotice(){const b=accountState.user?.behavior;if(!b?.warning&&!b?.permanent&&!(!b?.canMatch&&b))return false;const stamp=accountState.user.id+':'+b.blocks30d+':'+b.permanent;if(sessionStorage.getItem('pefrien.notice')===stamp)return false;sessionStorage.setItem('pefrien.notice',stamp);openSheet(b.permanent?'账户已停用':b.canMatch?'散步相处小提醒':'匹配暂时停用',`<p class="sheet-copy">${b.permanent?'近 30 天内收到 10 位不同狗友的拉黑，账户已永久停止匹配。':!b.canMatch?'近 30 天收到至少 5 位不同狗友的拉黑，匹配暂停 24 小时。':'近 30 天已有 '+b.blocks30d+' 位不同狗友选择不再相遇。请留意牵绳、距离和彼此的感受。'}</p><p class="note">有误会或需要申诉，可以联系运营。</p><button class="primary" onclick="closeSheet();feedbackPage('账户申诉')">提交反馈 / 申诉</button><button class="cancel" onclick="closeSheet()">知道啦</button>`);return true}

function loginPage(){show(`${accountHeader('先认识一下你')}<section class="login-intro">${petMark()}<h1>小狗的朋友，<br>也是你的朋友。</h1><p>${isPagesDemo?'手机演示版 · 资料只保存在当前浏览器。':'登录后，名片和交友偏好会保存在账户里。'}</p></section><form id="login-form" onsubmit="signIn(event)"><label class="field">手机号<input name="phone" type="tel" inputmode="numeric" autocomplete="tel" maxlength="11" required value="${esc(loginPhone)}" placeholder="输入 11 位手机号"></label><label class="field">验证码<div class="code-row"><input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required placeholder="6 位验证码"><button type="button" class="code-send" onclick="sendCode(this)">获取验证码</button></div></label><p id="login-hint" class="notice" role="status">${esc(localCodeHint||(isPagesDemo?'测试手机号 15012345678，验证码随便填，无需获取短信。':'本地联调：验证码显示在这里，不会发送真实短信。'))}</p><button class="primary" id="login-submit">登录 / 注册</button></form><p class="note center">首次验证会创建账号 · 下次打开自动登录</p><div class="third-party-label">也可以用这些方式登录</div><div class="provider-row">${[['wechat','微信','微'],['qq','QQ','Q'],['alipay','支付宝','支']].map(([id,name,icon])=>`<button onclick="providerLogin('${id}')"><span class="provider-icon ${id}">${icon}</span><strong>${name}</strong><small>待接入</small></button>`).join('')}</div><button class="cancel" onclick="feedbackPage()">登录遇到问题？告诉我们</button>`)}
async function sendCode(button){const input=document.querySelector('#login-form [name=phone]');loginPhone=input.value.trim();button.disabled=true;try{const r=await api('/auth/code','POST',{phone:loginPhone});localCodeHint=isPagesDemo?'演示验证码随便填，例如 123456，不会发送短信。':'本地测试验证码：'+r.developmentCode+'（5 分钟有效，未发送短信）';document.getElementById('login-hint').textContent=localCodeHint;button.textContent='60 秒后可重发';setTimeout(()=>{if(button.isConnected){button.disabled=false;button.textContent='重新获取'}},60000)}catch(e){document.getElementById('login-hint').textContent=e.message;button.disabled=false}}
async function signIn(e){e.preventDefault();const data=new FormData(e.target),button=document.getElementById('login-submit');button.disabled=true;loginPhone=String(data.get('phone')).trim();try{const r=await api('/auth/verify','POST',{phone:loginPhone,code:String(data.get('code')).trim()});localCodeHint='';await activateAccount(r.user)}catch(err){const hint=document.getElementById('login-hint');if(hint)hint.textContent=err.message;if(button.isConnected)button.disabled=false}}
async function providerLogin(provider){try{await api('/auth/oauth/start','POST',{provider})}catch(e){tell(e.message)}}
async function logoutAccount(){await Promise.all([...photoJobs.values()]);if(!await pushProfile()){tell('还有资料未同步，请先重试同步后再退出。');return}try{await api('/auth/logout','POST',{});accountState.user=null;accountState.dirty=false;STORAGE_KEY='pefrien.family.v1';family={seen:true,pets:[],selected:[],radius:'2'};loadFamily();home()}catch(e){tell(e.message)}}
async function accountPage(){if(!accountState.user){loginPage();return}try{const r=await api('/me');if(r.user)accountState.user=r.user;else{accountState.user=null;loginPage();return}}catch(e){}const u=accountState.user,b=u.behavior;show(`${accountHeader('我的')}<section class="account-card">${petMark()}<h2>${esc(u.nickname)}</h2><p>${esc(u.phone)}</p><span class="badge">${isPagesDemo?'演示资料仅存在当前浏览器':'小狗名片跟着账户走'}</span></section><section class="behavior-card"><div><span>相处行为分</span><strong>${b.score}</strong><small>/ 100</small></div><p>${b.permanent?'已永久停止匹配':!b.canMatch?'暂停匹配至 '+new Date(b.disabledUntil*1000).toLocaleString('zh-CN'):b.warning?'留意最近的相处反馈，一起温柔散步。':'好好相处，让每次碰面都安心。'}</p><small>近 30 天收到 ${b.blocks30d} 位不同狗友的拉黑</small><button class="text-action" onclick="behaviorRules()">查看规则 ↗</button></section><div class="account-links"><button onclick="familyPage()">我家小分队 <span>→</span></button><button onclick="relationsPage()">喜欢的伙伴 / 黑名单 <span>→</span></button><button onclick="feedbackPage()">意见反馈 <span>→</span></button><button onclick="feedbackHistory()">我的反馈进度 <span>→</span></button><button onclick="retrySync()">${accountState.syncError?'重试账户同步':(isPagesDemo?'演示资料已保存在本机':'资料已自动同步')} <span>↻</span></button></div><button class="cancel" onclick="logoutAccount()">退出登录</button>${bottomNav()}`)}
function behaviorRules(){openSheet('相处规则',`<p class="sheet-copy">以滚动 30 天、不同账号的拉黑记录统计。同一个人反复拉黑只计一次。</p><ul class="rule-list"><li>1 次：不扣分，不做处罚</li><li>从第 2 次起，每多一位扣 5 分</li><li>3 次：弹窗提醒</li><li>5 次：暂停匹配 24 小时；30 天内不重复延长</li><li>10 次：永久停止匹配</li></ul><p class="note">解除拉黑会恢复彼此匹配资格，但不抹掉已发生的行为记录。停用期间仍可登录、查看资料和申诉。</p>`)}
async function retrySync(){if(accountState.conflict){resolveSyncConflict();return}accountState.dirty=true;if(await pushProfile())tell(isPagesDemo?'演示资料已保存到当前浏览器。':'资料已经同步到账户。');else tell(accountState.syncError)}

async function match(){
  if(!accountState.user){loginPage();return}try{const latest=await api('/me');if(!latest.user){loginPage();return}accountState.user=latest.user;if(checkBehaviorNotice())return}catch(e){tell(e.message);return}if(!matchGate())return;
  await Promise.all([...photoJobs.values()]);if(!await pushProfile()){tell(accountState.syncError||'请先完成资料同步。');return}
  const generation=++accountState.requestGeneration;show(`<header class="top">${brand()}<span class="badge">寻找伙伴</span></header><section class="status"><div class="match-art">${puppyArt()}<span class="sniff">嗅嗅…</span></div><h1>谁也想出来玩？</h1><p>在 ${radiusLabels[family.radius||'2']} 范围内找合拍的小伙伴。</p></section><button class="cancel" onclick="accountState.requestGeneration++;home()">先等等，取消匹配</button>`);
  try{const r=await api('/matches','POST',{});if(generation!==accountState.requestGeneration)return;if(!r.match){empty();return}currentEncounter=r.match;show(`<header class="top">${brand()}<span class="badge">找到伙伴啦</span></header><section class="status"><div class="match-art">${puppyArt()}<span class="sniff found">尾巴摇起来啦</span></div><h1>有只小可爱，<br>也想和你一起玩！</h1><p>相距约 ${currentEncounter.distance} 米。<br>先不告诉你是谁，见面再认识。</p></section><button class="primary" onclick="startEncounterWalk()">走，去碰个面 ${lineIcon()}</button><p class="foot">${isPagesDemo?'演示狗友与路线，不会连接真实用户':'本地联调使用示例位置与路线'}</p><button class="cancel" onclick="home()">这次先不出门</button>`)}catch(e){if(generation===accountState.requestGeneration){home();tell(e.message)}}
}
function empty(){show(`${accountHeader('再换个散步机会')}<section class="empty"><h1>暂时没有合适的伙伴</h1><p>试试扩大距离，或调整交友偏好。<br>拉黑的狗友不会再次匹配。</p></section><button class="primary" onclick="chooseRadius()">调整匹配距离</button><button class="cancel" onclick="familyPage()">看看交友偏好</button>`)}
function startEncounterWalk(){const d=currentEncounter.distance;legs[0].dist=d;legs[1].dist=Math.round(d*.6);legs[2].dist=Math.round(d*.26);legs[3].dist=30;step=0;nav()}
async function reveal(){try{const r=await api('/matches/complete','POST',{id:currentEncounter.id});partner=r.pet;currentEncounter.liked=r.liked;currentEncounter.blocked=r.blocked;setMeetingPhoto(partner);renderEncounter()}catch(e){tell(e.message)}}
function renderEncounter(){show(`<header class="top">${brand()}<span class="badge">相遇完成</span></header><div class="reveal-top"><div class="eyebrow">叮！今天的新朋友。</div><h1>可喜可贺，<br>你们相遇啦！</h1></div><img class="portrait" src="${petPhoto(partner)}" alt="${esc(petPhotoAlt(partner))}"><div class="reveal-card"><span class="tiny">你好呀，我是</span><h2>${esc(partner.name)}</h2><div class="facts"><span>${esc(partner.breed)}</span><span>${esc(partner.age)} 岁</span><span>${esc(partner.weight)} kg</span><span>${esc(partner.sex)}</span></div></div><div class="reaction-row"><button id="like-button" class="${currentEncounter.liked?'selected':''}" onclick="reactToEncounter('like')">${currentEncounter.liked?'♥ 已喜欢':'♡ 玩得开心，喜欢它'}</button><button id="block-button" class="${currentEncounter.blocked?'selected':''}" onclick="confirmBlock()">${currentEncounter.blocked?'已拉黑':'不再遇见'}</button></div><p id="reaction-status" class="note center" role="status">喜欢的狗狗，以后更有机会遇见。</p><button class="primary" onclick="home()">带着好心情回首页 ${lineIcon()}</button>`)}
async function reactToEncounter(kind){const key=kind==='like'?'liked':'blocked';const button=document.getElementById(kind==='like'?'like-button':'block-button');if(button)button.disabled=true;try{const value=!currentEncounter[key];await api('/reactions','PUT',{matchId:currentEncounter.id,kind,value});currentEncounter[key]=value;if(button){button.textContent=kind==='like'?(value?'♥ 已喜欢':'♡ 玩得开心，喜欢它'):(value?'已拉黑':'不再遇见');button.classList.toggle('selected',value)}document.getElementById('reaction-status').textContent=kind==='like'?(value?'记住啦，以后更有机会遇见它。':'已取消喜欢。'):(value?'不会再匹配到这位狗友及其小狗。':'已解除拉黑。')}catch(e){tell(e.message)}finally{if(button)button.disabled=false}}
function confirmBlock(){if(currentEncounter.blocked){reactToEncounter('block');return}openSheet('以后不再遇见？',`<p class="sheet-copy">拉黑后，你和这位狗友将不再互相匹配。对方不会看到是谁拉黑了自己。</p><button class="primary" onclick="closeSheet();reactToEncounter('block')">确认拉黑</button><button class="cancel" onclick="closeSheet()">再想想</button>`)}
async function relationsPage(){try{const r=await api('/relations');show(`${accountHeader('小狗交友记录','accountPage()')}<h3>喜欢的伙伴</h3>${r.likes.length?r.likes.map(x=>`<div class="relation-card"><span>♥ ${esc(x.petName||x.names)}</span><button class="text-action" onclick="removeRelation('like','${esc(x.target)}','${esc(x.pet_id)}')">取消喜欢</button></div>`).join(''):'<p class="note">碰到玩得来的小狗，给它一颗心吧。</p>'}<h3>不再遇见</h3>${r.blocks.length?r.blocks.map(x=>`<div class="relation-card"><span>${esc(x.names)}的狗友</span><button class="text-action" onclick="removeRelation('block','${esc(x.target)}','')">解除拉黑</button></div>`).join(''):'<p class="note">这里暂时空空的。</p>'}`)}catch(e){tell(e.message)}}
async function removeRelation(kind,target,petId){try{await api('/relations','DELETE',{kind,target,petId});relationsPage()}catch(e){tell(e.message)}}
function feedbackPage(kind='建议'){show(`${accountHeader('想说的话，我们听')}<div class="feedback-intro">${petMark()}<h2>一个小建议，<br>也能让散步更美好。</h2></div><form onsubmit="submitFeedback(event)"><label class="field">反馈类型<select name="kind">${['建议','功能问题','账户申诉','其他'].map(x=>`<option ${x===kind?'selected':''}>${x}</option>`).join('')}</select></label><label class="field">想告诉我们的事<textarea name="body" minlength="5" maxlength="2000" required rows="5" placeholder="哪里不顺手，或有什么新点子？">${esc(feedbackDraft.body||'')}</textarea></label><label class="field">联系方式（选填）<input name="contact" maxlength="120" value="${esc(feedbackDraft.contact||'')}" placeholder="邮箱或其他方便回复的方式"></label><p id="feedback-status" class="note" role="status">${isPagesDemo?'演示反馈仅保存在当前浏览器，尚不会发送给运营。':accountState.user?'提交后可在「我的反馈进度」查看运营回复。':'也可以不登录，直接留下反馈。'}</p><button class="primary" type="submit">把想法交给我们 ↗</button></form>`)}
async function submitFeedback(e){e.preventDefault();const f=new FormData(e.target);feedbackDraft=Object.fromEntries(f);const b=e.target.querySelector('button[type=submit]');b.disabled=true;try{const r=await api('/feedback','POST',feedbackDraft);feedbackDraft={};show(`${accountHeader(isPagesDemo?'演示反馈已保存':'反馈已收到')}<section class="empty">${petMark()}<h1>谢谢你，<br>认真陪我们长大。</h1><p>反馈编号：${esc(r.id)}<br>${isPagesDemo?'仅保存在这台设备，尚未发送给运营。':'运营会在后台查看处理。'}</p></section><button class="primary" onclick="${accountState.user?'feedbackHistory()':'home()'}">${accountState.user?'查看反馈进度':'返回首页'}</button>`)}catch(err){document.getElementById('feedback-status').textContent=err.message;b.disabled=false}}
async function feedbackHistory(){try{const r=await api('/feedback');show(`${accountHeader('我的反馈进度','accountPage()')}${r.items.length?r.items.map(x=>`<article class="feedback-card"><span class="badge">${esc(x.status)}</span><h3>${esc(x.kind)}</h3><p>${esc(x.body)}</p>${x.reply?`<blockquote>运营回复：${esc(x.reply)}</blockquote>`:''}<small>${new Date(x.created*1000).toLocaleString('zh-CN')}</small></article>`).join(''):'<p class="note">还没有反馈，有想法随时告诉我们。</p>'}<button class="primary" onclick="feedbackPage()">写一条反馈</button>`)}catch(e){tell(e.message)}}

function storageNote(){if(isPagesDemo)return '演示资料与照片只保存在当前浏览器，不会跨设备同步。';return accountState.user?(accountState.syncError?'本机草稿已保留，账户同步待重试。':'资料与照片会自动保存到账户。'):'尚未登录，资料暂存在这台设备。'}

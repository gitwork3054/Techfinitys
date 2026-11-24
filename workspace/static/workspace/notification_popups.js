/* Per-recipient toast notifications across all Techfinitys CRM accounts. */
(function(){
 'use strict';
 const containerId='tfNotificationPopups';
 let accountId=null,initialized=false,polling=false;
 let lastIds=new Set(),active=new Set();
 const autoClose=new Map();
 // Native desktop notifications are visible while another browser tab is active.
 // Request permission only following a user's explicit click in Settings.
 let pageFocused=document.hasFocus();
 let pushRegistered=false;
 function toBytes(base64url){
   const padded=base64url.replace(/-/g,'+').replace(/_/g,'/');
   const raw=atob(padded.padEnd(Math.ceil(padded.length/4)*4,'='));
   return Uint8Array.from(raw,c=>c.charCodeAt(0));
 }
 function csrfToken(){
   const token=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='));
   return decodeURIComponent(token?.split('=').slice(1).join('=')||'');
 }
 async function postPush(action,subscription){
   return fetch('/api/push/subscription/',{
     method:'POST',credentials:'same-origin',
     headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},
     body:JSON.stringify({action,endpoint:subscription.endpoint,keys:subscription.toJSON()?.keys})
   }).then(async response=>{
     const result=await response.json();
     if(!response.ok)throw Error(result.error||'Could not register notifications');
     return result;
   });
 }
 async function registerPush(){
   if(!('serviceWorker' in navigator)||!('PushManager' in window))return 'unsupported';
   if(Notification.permission!=='granted')return 'not-granted';
   const config=await fetch('/api/push/config/',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json());
   if(!config.available||!config.publicKey)return 'unavailable';
   const registration=await navigator.serviceWorker.register('/sw.js',{scope:'/'});
   const ready=await navigator.serviceWorker.ready;
   let subscription=await ready.pushManager.getSubscription();
   if(!subscription)subscription=await ready.pushManager.subscribe({
     userVisibleOnly:true,applicationServerKey:toBytes(config.publicKey)
   });
   await postPush('subscribe',subscription);
   pushRegistered=true;
   return 'enabled';
 }
 async function enableDesktopNotifications(){
   if(!('Notification' in window))return 'unsupported';
   if(Notification.permission!=='granted'){
     const result=await Notification.requestPermission();
     if(result!=='granted')return result;
   }
   try{return await registerPush()}catch(error){
     console.warn('Background push registration unavailable:',error);
     return 'tab-only';
   }
 }
 async function disableDesktopNotifications(){
   if(!('serviceWorker' in navigator))return;
   try{
     const registration=await navigator.serviceWorker.getRegistration('/');
     const subscription=await registration?.pushManager?.getSubscription();
     if(subscription){
       await postPush('unsubscribe',subscription);
       await subscription.unsubscribe();
     }
   }catch(error){console.warn('Push unsubscription failed:',error)}
   pushRegistered=false;
 }
 async function syncPushSubscription(){
   if(window.state?.ctx?.preferences?.desktopNotifications===false)return;
   if(!('Notification' in window)||Notification.permission!=='granted')return;
   if(!('serviceWorker' in navigator))return;
   try{
     const registration=await navigator.serviceWorker.getRegistration('/');
     const subscription=await registration?.pushManager?.getSubscription();
     if(subscription){await postPush('subscribe',subscription);pushRegistered=true;}
   }catch(_){/* Retry on next login or explicit user action. */}
 }

 window.addEventListener('focus',()=>{pageFocused=true});
 window.addEventListener('blur',()=>{pageFocused=false});
 function showDesktopNotification(n){
   if(!('Notification' in window)||Notification.permission!=='granted')return;
   if(window.state?.ctx?.preferences?.desktopNotifications===false)return;
   if(document.visibilityState==='visible'&&pageFocused)return;
   if(pushRegistered)return; // Service worker owns background desktop notifications.
   try{
     const notice=new Notification(n.title||'Techfinitys CRM',{
       body:n.body||'You have a new update.',
       tag:'techfinitys-'+String(n.id),
       icon:'/static/images/techfinitys-logo.png',
       silent:true
     });
     notice.onclick=()=>{
       window.focus();notice.close();openItem(String(n.id));
     };
   }catch(_){/* Browser-level notification support varies by platform. */}
 }
 async function requestDesktopNotifications(){
   try{return await enableDesktopNotifications()}catch(_){return 'denied'}
 }

 // Web Audio has no external file dependency. Browsers require a user gesture
 // before playing sound; enable the context on first interaction.
 let audioContext=null,lastChimeAt=0;
 function unlockAudio(){
   try{
     const AudioContextClass=window.AudioContext||window.webkitAudioContext;
     if(!AudioContextClass)return;
     if(!audioContext)audioContext=new AudioContextClass();
     if(audioContext.state==='suspended')audioContext.resume().catch(()=>{});
   }catch(_){/* Audio is optional and never blocks notifications. */}
 }
 function playChime(force=false){
   if(!force && window.state?.ctx?.preferences?.soundNotifications===false)return;
   if(!force && window.state?.ctx?.preferences?.feedNotifications===false)return;
   const now=Date.now();
   if(!force && now-lastChimeAt<1800)return; // one chime for a burst of popups
   if(!audioContext||audioContext.state!=='running')return;
   lastChimeAt=now;
   try{
     const start=audioContext.currentTime+0.02;
     [[660,0,.14],[880,.16,.21]].forEach(([frequency,offset,duration])=>{
       const oscillator=audioContext.createOscillator();
       const envelope=audioContext.createGain();
       oscillator.type='sine';
       oscillator.frequency.value=frequency;
       envelope.gain.setValueAtTime(0.0001,start+offset);
       envelope.gain.exponentialRampToValueAtTime(0.17,start+offset+0.025);
       envelope.gain.exponentialRampToValueAtTime(0.0001,start+offset+duration);
       oscillator.connect(envelope);envelope.connect(audioContext.destination);
       oscillator.start(start+offset);oscillator.stop(start+offset+duration+0.01);
     });
   }catch(_){/* Keep the visual notification if audio fails. */}
 }

 function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[m]));}
 function container(){
   let el=document.getElementById(containerId);
   if(!el){el=document.createElement('div');el.id=containerId;el.className='tf-notification-popups';el.setAttribute('aria-label','New CRM notifications');document.body.appendChild(el);}
   return el;
 }
 function dismiss(id){
   const node=document.getElementById('tf-alert-'+id);
   if(node)node.remove();active.delete(String(id));
   const timer=autoClose.get(String(id));if(timer)clearTimeout(timer);
   autoClose.delete(String(id));
 }
 async function openItem(id){
   const notice=(window.state?.notifications||[]).find(n=>String(n.id)===String(id));
   const node=document.getElementById('tf-alert-'+id);
   const link=node?.dataset?.link||notice?.link||'';
   dismiss(id);
   try{
     const csrf=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||'';
     const response=await fetch('/api/workspace/',{
       method:'POST',credentials:'same-origin',
       headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf)},
       body:JSON.stringify({action:'read_notification',id})
     });
     if(response.ok){
       const item=(window.state?.notifications||[]).find(n=>String(n.id)===String(id));
       if(item)item.read=true;
     }
   }catch(_){/* Navigation remains available if read acknowledgement fails. */}
   // Accept only local SPA hashes and same-origin relative paths.
   if(link.startsWith('#workchat/')){
     const chatId=link.slice('#workchat/'.length);
     if(/^[0-9a-f-]{36}$/i.test(chatId)&&window.TFCollab?.openNotificationChat){
       window.TFCollab.openNotificationChat(chatId);
     }else if(window.TFCollab?.show)window.TFCollab.show('chats');
   }else if(link.startsWith('#')){
     const route=link.slice(1).split('/')[0];
     if(['projects','tasks','updates','admin_activity','overview','leaves','approvals'].includes(route)){
       window.go?.(route); // Existing navigation checks this account's permissions.
       const project=link.match(/^#projects\/([0-9a-f-]{36})/i);
       if(project && window.TFPlus?.openProject)window.TFPlus.openProject(project[1]);
     }else document.getElementById('bellBtn')?.click();
   }else if(link.startsWith('/')&&!link.startsWith('//')){
     window.location.assign(link);
   }else if(window.state?.ctx?.role==='admin'&&/leave|approval/i.test(node?.dataset?.title||'')){
     window.go?.('admin_activity');
   }else{
     document.getElementById('bellBtn')?.click();
   }
 }
 function show(n){
   const id=String(n.id);
   if(active.has(id)||document.getElementById('tf-alert-'+id))return;
   const box=container();
   // Limit to 3 visible messages without hiding the remainder in the bell.
   if(box.childElementCount>=3)dismiss(box.firstElementChild.id.replace('tf-alert-',''));
   const el=document.createElement('section');
   el.className='tf-alert-popup';
   el.id='tf-alert-'+id;
   el.dataset.title=n.title||'';
   el.dataset.link=n.link||'';
   el.setAttribute('role','status');
   el.innerHTML='<span class="tf-alert-icon" aria-hidden="true">✦</span>'+
     '<div class="tf-alert-copy"><strong>'+esc(n.title||'New notification')+'</strong>'+
     '<p>'+esc(n.body||'You have a new CRM update.')+'</p>'+
     '<button type="button" class="tf-alert-open">View notification</button></div>'+
     '<button type="button" class="tf-alert-close" aria-label="Dismiss notification">×</button>';
   el.querySelector('.tf-alert-close').addEventListener('click',()=>dismiss(id));
   el.querySelector('.tf-alert-open').addEventListener('click',()=>openItem(id));
   box.appendChild(el);active.add(id);
   playChime();
   showDesktopNotification(n);
   autoClose.set(id,setTimeout(()=>dismiss(id),9000));
 }
 async function check(){
   if(polling||!window.state?.ctx)return;
   const id=String(window.state.ctx.id);
   if(accountId!==id){
     accountId=id;initialized=false;lastIds=new Set();
     document.getElementById(containerId)?.replaceChildren();
     active.clear();for(const timer of autoClose.values())clearTimeout(timer);autoClose.clear();
   }
   polling=true;
   try{
     const res=await fetch('/api/workspace/?notifications_only=1',{credentials:'same-origin',cache:'no-store'});
     if(!res.ok)return;
     const data=await res.json();
     if(!Array.isArray(data.notifications))return;
     const rows=data.notifications;
     const incoming=rows.filter(n=>!n.read&&!lastIds.has(String(n.id)));
     const prefs=window.state?.ctx?.preferences||{};
     if(prefs.feedNotifications!==false){
       if(initialized){
         incoming.slice(0,3).reverse().forEach(show);
       }else{
         // Restore recent unread inbox alerts when an employee signs back in;
         // keep the remainder in the bell to avoid flooding the screen.
         rows.filter(n=>!n.read &&
           Number.isFinite(Date.parse(n.createdAt)) &&
           Date.now()-Date.parse(n.createdAt)<7*86400000)
           .slice(0,2).reverse().forEach(show);
       }
     }
     initialized=true;
     lastIds=new Set(rows.map(n=>String(n.id)));
     if(window.state){
       const byId=new Map((window.state.notifications||[]).map(n=>[String(n.id),n]));
       rows.forEach(n=>byId.set(String(n.id),n));
       window.state.notifications=[...byId.values()].sort((a,b)=>Date.parse(b.createdAt)-Date.parse(a.createdAt)).slice(0,100);
       const bell=document.getElementById('bellBtn');
       if(bell && window.state?.ctx?.role!=='admin'){
         const count=rows.filter(n=>!n.read).length;
         bell.title='Notifications ('+count+' unread)';
         bell.setAttribute('aria-label',bell.title);
         bell.innerHTML='♧'+(count?'<span class="notification-dot">'+(count>99?'99+':count)+'</span>':'');
       }
     }
   }catch(_){/* Network blips must not interfere with other CRM controls. */}
   finally{polling=false;}
 }
 function begin(){
   document.addEventListener('pointerdown',unlockAudio,{once:true,capture:true});
   document.addEventListener('keydown',unlockAudio,{once:true,capture:true});
   if(window.state?.ctx){check();syncPushSubscription()}
   setInterval(check,20000);
   setInterval(()=>{if(window.state?.ctx&&!pushRegistered)syncPushSubscription()},60000);
   navigator.serviceWorker?.addEventListener?.('message',event=>{
     if(event.data?.type!=='tf-push-open')return;
     const link=event.data.link||'';
     if(link.startsWith('#workchat/')){
       const id=link.slice('#workchat/'.length);
       if(/^[0-9a-f-]{36}$/i.test(id))window.TFCollab?.openNotificationChat?.(id);
     }else if(link.startsWith('#'))window.go?.(link.slice(1).split('/')[0]);
   });
   const pendingChat=new URLSearchParams(location.search).get('openChat');
   if(pendingChat&&/^[0-9a-f-]{36}$/i.test(pendingChat)){
     const tryOpen=()=>{if(window.TFCollab?.openNotificationChat&&window.state?.ctx){
       window.TFCollab.openNotificationChat(pendingChat);
       history.replaceState(null,'',location.pathname+location.hash);
     }else setTimeout(tryOpen,600)};
     setTimeout(tryOpen,650);
   }
   document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')check()});
   window.addEventListener('focus',check);
 }
 // Settings uses this to play a sample chime immediately after the user clicks.
 window.TFNotificationSounds={test:()=>{unlockAudio();audioContext?.resume?.().then(()=>playChime(true)).catch(()=>{});},requestDesktopNotifications,enableDesktopNotifications,disableDesktopNotifications,syncPushSubscription,notificationPermission:()=>('Notification' in window?Notification.permission:'unsupported')};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',begin);
 else begin();
})();

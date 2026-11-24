/* Per-recipient toast notifications across all Techfinitys CRM accounts. */
(function(){
 'use strict';
 const containerId='tfNotificationPopups';
 let accountId=null,initialized=false,polling=false;
 let lastIds=new Set(),active=new Set();
 const autoClose=new Map();
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
   if(link.startsWith('#')){
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
   autoClose.set(id,setTimeout(()=>dismiss(id),9000));
 }
 async function check(){
   if(polling||document.visibilityState!=='visible'||!window.state?.ctx)return;
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
   if(window.state?.ctx)check();
   setInterval(check,20000);
   document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')check()});
   window.addEventListener('focus',check);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',begin);
 else begin();
})();

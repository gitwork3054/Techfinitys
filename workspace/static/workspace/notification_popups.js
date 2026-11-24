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
     if((window.menus?.[window.state?.ctx?.role]||[]).includes(route))window.go?.(route);
     else if(/^#(projects|tasks|updates|admin_activity|overview)(\/|$)/.test(link))window.location.hash=link;
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
     if(initialized && window.state?.ctx?.preferences?.feedNotifications!==false){
       incoming.reverse().slice(-3).forEach(show);
     }
     if(!initialized){
       initialized=true;
       // On login, surface only freshly generated alerts instead of flooding
       // the screen with an entire unread history.
       if(window.state?.ctx?.preferences?.feedNotifications!==false){
         rows.filter(n=>!n.read&&Date.now()-Date.parse(n.createdAt)<60000)
           .slice(0,1).forEach(show);
       }
     }
     lastIds=new Set(rows.map(n=>String(n.id)));
     if(window.state){
       const byId=new Map((window.state.notifications||[]).map(n=>[String(n.id),n]));
       rows.forEach(n=>byId.set(String(n.id),n));
       window.state.notifications=[...byId.values()].sort((a,b)=>Date.parse(b.createdAt)-Date.parse(a.createdAt)).slice(0,100);
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

/* Techfinitys Web Push: shows browser/OS notifications even with no CRM tab. */
'use strict';
self.addEventListener('push',event=>{
  let payload={};
  try{payload=event.data?event.data.json():{}}catch(_){payload={}}
  const title=String(payload.title||'Techfinitys CRM').slice(0,220);
  const link=String(payload.link||'#overview');
  const safeLink=/^#[a-z_]+(?:\/[a-zA-Z0-9-]+)*$/.test(link)?link:'#overview';
  event.waitUntil(self.registration.showNotification(title,{
    body:String(payload.body||'New CRM update').slice(0,150),
    icon:'/static/images/techfinitys-logo.png',
    tag:'tf-push-'+String(payload.id||Date.now()),
    data:{link:safeLink,id:payload.id||null},
    badge:'/static/images/techfinitys-logo.png',
    renotify:false
  }));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const link=event.notification.data?.link||'#overview';
  const url=new URL('/',self.location.origin);
  if(link.startsWith('#workchat/')){
    const id=link.slice('#workchat/'.length);
    if(/^[0-9a-f-]{36}$/i.test(id))url.searchParams.set('openChat',id);
    url.hash='overview';
  }else{url.hash=link.slice(1)}
  event.waitUntil((async()=>{
    const clients=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of clients){
      if(new URL(client.url).origin!==self.location.origin)continue;
      await client.focus();
      client.postMessage({type:'tf-push-open',link});
      return;
    }
    await self.clients.openWindow(url.href);
  })());
});

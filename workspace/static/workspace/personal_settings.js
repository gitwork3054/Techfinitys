/* Techfinitys personal preferences — per-account, saved in Django. */
(function(){
 'use strict';
 const defaults={fontSize:'normal',mode:'light',accent:'blue',panel:'aurora',landingPage:'overview',
   reduceMotion:false,highContrast:false,compactMode:false,feedNotifications:true,emailNotifications:true,activityReminders:true};
 const landing=[['overview','Home'],['projects','Projects'],['tasks','My tasks'],['updates','Updates']];
 const colors=[['blue','#2978eb'],['orange','#fb831c'],['teal','#05bcb4'],['red','#f44351'],['green','#0abf67'],['purple','#8069ed']];
 let prefs={...defaults},account=null,initial=false,saving=false;
 const root=document.documentElement;
 function clean(p){return {...defaults,...Object.fromEntries(Object.entries(p||{}).filter(([k,v])=>Object.hasOwn(defaults,k)&&typeof v===typeof defaults[k]))};}
 function activeMode(){return prefs.mode==='auto'?(window.matchMedia?.('(prefers-color-scheme: dark)').matches?'dark':'light'):prefs.mode;}
 function apply(){
   const mode=activeMode();
   root.dataset.theme=mode;
   root.dataset.fontSize=prefs.fontSize;
   root.dataset.panel=prefs.panel;
   root.dataset.accent=prefs.accent;
   root.dataset.highContrast=prefs.highContrast?'yes':'no';
   root.dataset.compact=prefs.compactMode?'yes':'no';
   root.dataset.reduceMotion=prefs.reduceMotion?'yes':'no';
   try{localStorage.setItem('techfinitys-theme',mode)}catch(_){}
   document.dispatchEvent(new CustomEvent('tf-theme-changed'));
 }
 function receive(serverPrefs,id){
   const switched=String(account)!==String(id);
   account=id;
   prefs=clean(serverPrefs);
   apply();
   if(!initial || switched){
     initial=true;
     if(!window.location.hash || window.location.hash==='#overview'){
       const allowed=(window.state?.ctx?.role==='client'?['overview','projects','tasks','updates']:['overview','projects','tasks','updates']);
       if(allowed.includes(prefs.landingPage)&&prefs.landingPage!=='overview'&&window.state){
         window.state.tab=prefs.landingPage;
       }
     }
   }
 }
 async function set(key,value){
   if(!(key in defaults)||typeof value!==typeof defaults[key])return;
   const previous={...prefs};
   prefs={...prefs,[key]:value};
   apply();
   if(window.state?.tab==='settings')window.render?.();
   if(!account)return;
   try{
     const csrf=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||'';
     const response=await fetch('/api/workspace/',{
       method:'POST',credentials:'same-origin',
       headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf)},
       body:JSON.stringify({action:'save_preferences',preferences:{[key]:value}})
     });
     const data=await response.json();
     if(!response.ok)throw Error(data.error||'Unable to save preference');
     if(window.state?.ctx)window.state.ctx.preferences={...window.state.ctx.preferences,[key]:value};
     const status=document.getElementById('tfPrefsStatus');
     if(status)status.textContent='Saved to your account';
   }catch(err){
     prefs=previous;apply();if(window.state?.tab==='settings')window.render?.();
     alert('Setting was not saved: '+err.message);
   }
 }
 const selected=(key,value)=>prefs[key]===value?' selected':'';
 const pressed=(key,value)=>prefs[key]===value?'true':'false';
 function choice(key,value,label,extra=''){
  return '<button type="button" class="tf-prefs-choice'+selected(key,value)+'" aria-pressed="'+pressed(key,value)+'" onclick="TFPreferences.set('+JSON.stringify(key)+','+JSON.stringify(value)+')">'+extra+label+'</button>';
 }
 function switcher(key,label,description){
  return '<label class="tf-prefs-switch"><span><strong>'+label+'</strong><small>'+description+'</small></span><input type="checkbox" '+(prefs[key]?'checked':'')+' onchange="TFPreferences.set('+JSON.stringify(key)+',this.checked)"></label>';
 }
 function renderSettings(){
  const person=window.state?.ctx||{};
  const name=String(person.name||'My profile').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const initials=name.trim().split(/\s+/).map(x=>x[0]).join('').slice(0,2).toUpperCase();
  return '<div class="tf-prefs-page"><div class="tf-prefs-heading"><div><span class="tf-prefs-kicker">PERSONAL PREFERENCES</span><h1>Settings</h1><p>Customize how Techfinitys looks and works for your account.</p></div><span class="tf-prefs-save" id="tfPrefsStatus">Automatically saved</span></div>'+
  '<div class="tf-prefs-tabs"><button type="button" class="active" onclick="document.getElementById(\'tfPersonalTheme\')?.scrollIntoView({behavior:\'smooth\',block:\'start\'})">User Personal</button><button type="button" onclick="document.getElementById(\'tfPersonalAccess\')?.scrollIntoView({behavior:\'smooth\',block:\'start\'})">Accessibility</button><button type="button" onclick="document.getElementById(\'tfPersonalNotifications\')?.scrollIntoView({behavior:\'smooth\',block:\'start\'})">Notifications</button></div>'+
  '<div class="tf-prefs-profile"><span class="tf-prefs-avatar">'+initials+'</span><div><h2>'+name+'</h2><p>'+String(person.roleLabel||'Workspace member')+'</p><button type="button" onclick="window.TFCollab?.openProfile?.()">Edit profile & photo ↗</button></div></div>'+
  '<section id="tfPersonalTheme" class="tf-prefs-section"><div class="tf-prefs-section-title"><h2>Themes</h2><p>Choose your workspace colour and background style.</p></div><div class="tf-prefs-row"><strong>Colour</strong><div class="tf-prefs-color-row">'+colors.map(([k,color])=>choice('accent',k,'<span class="tf-prefs-swatch" style="background:'+color+'"></span><span class="tf-prefs-color-name">'+k+'</span>')).join('')+'</div></div>'+
  '<div class="tf-prefs-row"><strong>Panel</strong><div class="tf-prefs-options">'+choice('panel','aurora','Aurora','<span class="tf-prefs-preview aurora"></span>')+choice('panel','glass','Glass','<span class="tf-prefs-preview glass"></span>')+choice('panel','solid','Solid','<span class="tf-prefs-preview solid"></span>')+choice('panel','minimal','Minimal','<span class="tf-prefs-preview minimal"></span>')+'</div></div></section>'+
  '<section class="tf-prefs-section"><div class="tf-prefs-row"><strong>Mode</strong><div class="tf-prefs-options">'+choice('mode','light','Day','<span class="tf-mode-preview light">☀</span>')+choice('mode','dark','Night','<span class="tf-mode-preview dark">☾</span>')+choice('mode','auto','Auto','<span class="tf-mode-preview auto">◐</span>')+'</div></div>'+
  '<div class="tf-prefs-row"><strong>Font size</strong><div class="tf-prefs-options">'+choice('fontSize','small','Small','<b class="tf-font-sample" style="font-size:13px">Aa</b>')+choice('fontSize','normal','Default','<b class="tf-font-sample" style="font-size:16px">Aa</b>')+choice('fontSize','large','Large','<b class="tf-font-sample" style="font-size:20px">Aa</b>')+choice('fontSize','extra','Extra large','<b class="tf-font-sample" style="font-size:24px">Aa</b>')+'</div></div></section>'+
  '<section class="tf-prefs-section"><div class="tf-prefs-row"><strong>Landing page</strong><div class="tf-prefs-options">'+landing.map(([key,value])=>choice('landingPage',key,'<span class="tf-landing-symbol">'+({overview:'▦',projects:'◇',tasks:'☑',updates:'↻'}[key])+'</span>'+value)).join('')+'</div></div></section>'+
  '<section id="tfPersonalAccess" class="tf-prefs-section"><h2>Accessibility</h2>'+switcher('highContrast','High contrast','Boost text and border visibility')+switcher('reduceMotion','Reduce motion','Turn off decorative background animations')+switcher('compactMode','Compact spacing','Display more information on each screen')+'</section>'+
  '<section class="tf-prefs-section"><h2>Notification preferences</h2><p>These are personal notification preferences; delivery channels require their corresponding service configuration.</p>'+switcher('feedNotifications','Feed notifications','Preference for activity feed updates')+switcher('emailNotifications','Personal email','Preference for email updates')+switcher('activityReminders','Activity reminders','Preference for upcoming activity reminders')+'</section>'+
  '</div>';
 }
 window.TFPreferences={receive,set,renderSettings};
 window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change',()=>{if(prefs.mode==='auto')apply()});
})();

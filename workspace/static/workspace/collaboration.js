/* Techfinitys WorkChat + Recent Projects + profile editor.
 * Stored in Django, not a mock, with server enforced membership and CSRF.
 */
(() => {
  'use strict';
  const BASE = '/api/collaboration/';
  const ui = {
    ready:false, loading:false, recent:[], people:[], chats:[], currentId:'',
    messages:[], panel:false, mode:'list', tab:'chats', query:'', recentQuery:'',
    profile:null, profilePhotoVersion:0, notice:'', busy:false,
  };
  const e = v => String(v == null ? '' : v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const initials = name => String(name||'TF').split(/\s+/).map(x=>x[0]||'').join('').slice(0,2).toUpperCase();
  const stamp = time => {
    if (!time) return '';
    const d=new Date(time);if(Number.isNaN(d.valueOf()))return '';
    const today=new Date();
    return d.toDateString()===today.toDateString() ? d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'}) : d.toLocaleDateString('en-IN',{day:'numeric',month:'short'});
  };
  const role = () => window.state?.ctx?.role || '';
  const isStaff = () => ['admin','manager','employee'].includes(role());
  const me = () => window.state?.ctx?.id;
  const token = () => decodeURIComponent((document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))||'').split('=')[1]||'');
  const photoMarkup = (url,name,extra='') => url ? `<img class="tf-chat-avatar ${extra}" src="${e(url)}" alt="${e(name)}" loading="lazy">` : `<span class="tf-chat-avatar ${extra}" aria-hidden="true">${e(initials(name))}</span>`;
  const xhr = async (url, body) => {
    const response = await fetch(url, body === undefined ? {cache:'no-store',credentials:'same-origin'} : {
      method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':token()},
      credentials:'same-origin',body:JSON.stringify(body)
    });
    const data = await response.json().catch(()=>({error:'Unexpected server response'}));
    if(!response.ok)throw new Error(data.error || 'Request failed.');
    return data;
  };
  const message = (text,bad=false) => {ui.notice=text;const node=document.getElementById('tfChatNotice');if(node){node.textContent=text;node.classList.toggle('error',bad)}};

  function drawRecent(){
    const shell=document.getElementById('tfRecentProjects'),list=document.getElementById('tfRecentList');
    if(!shell || !list)return;
    shell.hidden=!window.state?.ctx;
    const q=ui.recentQuery.toLowerCase();const rows=ui.recent.filter(p=>(p.name+' '+p.clientName).toLowerCase().includes(q));
    list.innerHTML=rows.length ? rows.map(p=>`<button type="button" class="tf-recent-item" title="${e(p.name)} · ${e(p.clientName)}" onclick="TFCollab.viewProject('${e(p.id)}')"><span class="tf-folder-icon" aria-hidden="true">▣</span><span>${e(p.name)}</span></button>`).join('') : `<div class="tf-recent-empty">${ui.ready?'No matching accessible projects':'Loading projects…'}</div>`;
  }
  function toggleRecentSearch(){
    const head=document.querySelector('.tf-recent-head'); if(!head)return;
    const before=head.querySelector('input'); if(before){before.remove();ui.recentQuery='';drawRecent();return;}
    const input=document.createElement('input');input.type='search';input.className='tf-recent-search';input.placeholder='Find project…';input.setAttribute('aria-label','Search recent projects');
    input.addEventListener('input',()=>{ui.recentQuery=input.value;drawRecent()});head.appendChild(input);input.focus();
  }
  async function viewProject(id){
    if(!ui.recent.some(p=>p.id===id) && !window.state?.projects?.some(p=>p.id===id))return;
    // The recent-project feed can finish after the main workspace request.
    // Refresh the permission-scoped workspace before navigating if its snapshot
    // is older. Never synthesize a project or bypass the backend access filter.
    if(!window.state?.projects?.some(p=>p.id===id) && typeof window.load==='function'){
      await window.load();
    }
    if(window.state?.projects?.some(p=>p.id===id) && window.TFPlus?.openProject){
      window.TFPlus.openProject(id);
    }else if(window.go){
      window.go('projects');
      if(window.state)window.state.notice='This project is not in your current project list. Ask an admin to check your active client assignment.';
      if(typeof window.render==='function')window.render();
    }
  }
  async function touchProject(id){
    if(!id || !window.state?.ctx)return;
    try{const data=await xhr(BASE,{action:'visit_project',projectId:id});ui.recent=data.recentProjects||ui.recent;drawRecent()}catch(_){/* Project navigation still works without history update. */}
  }
  function avatarTop(){
    const ctx=window.state?.ctx;if(!ctx)return;
    const avatar=document.getElementById('topAvatar');if(!avatar)return;
    const url=ui.profile?.photo || ctx.profilePhotoUrl || '';
    const markup=url ? `<img src="${e(url)}?v=${ui.profilePhotoVersion}" alt="${e(ctx.name||'Profile')}" class="tf-top-photo">` : e(initials(ctx.name));
    if(avatar.innerHTML!==markup)avatar.innerHTML=markup;
    avatar.setAttribute('aria-label','Edit profile and photo');avatar.onclick=openProfile;
    const workspaceAvatar=document.querySelector('#workspaceCard .avatar');
    if(workspaceAvatar && url){
      const inner=`<img src="${e(url)}?v=${ui.profilePhotoVersion}" alt="" class="tf-top-photo">`;
      if(workspaceAvatar.innerHTML!==inner)workspaceAvatar.innerHTML=inner;
    }
    const workspaceCard=document.getElementById('workspaceCard');
    if(workspaceCard){workspaceCard.title='Edit your profile';workspaceCard.style.cursor='pointer';workspaceCard.onclick=openProfile;}
    if(window.state?.tab==='settings'){
      const pane=document.getElementById('mainContent');
      if(pane&&!pane.querySelector('#tfProfileSettings'))pane.insertAdjacentHTML('beforeend',`<section id="tfProfileSettings" class="tf-profile-settings"><div><strong>Personal profile</strong><p>Set your display name, phone and photo. Your login email is controlled by the workspace administrator.</p></div><button class="tf-profile-action" type="button" onclick="TFCollab.openProfile()">Edit profile & photo ↗</button></section>`)
    }
  }
  function drawDock(){
    const dock=document.getElementById('tfChatDock');if(!dock)return;
    dock.hidden=!isStaff();
    const count=ui.chats.reduce((n,c)=>n+(c.unread||0),0);
    const mobile=document.getElementById('tfMobileChatTrigger');
    if(mobile){mobile.hidden=!isStaff()||ui.panel;const badge=mobile.querySelector('#tfMobileUnread');if(badge)badge.textContent=count>0?String(Math.min(99,count)):'';}
    if(!isStaff())return;
    dock.innerHTML=`<button type="button" class="tf-dock-btn ${ui.panel&&ui.tab==='chats'?'active':''}" aria-label="Open internal employee chats" onclick="TFCollab.show('chats')"><span>◉</span><small>Chats</small>${count?`<b>${count>99?'99+':count}</b>`:''}</button>
    <button type="button" class="tf-dock-btn ${ui.panel&&ui.tab==='people'?'active':''}" aria-label="Open employee directory" onclick="TFCollab.show('people')"><span>♙</span><small>People</small></button>
    <button type="button" class="tf-dock-compose" title="Quick actions" aria-label="Quick chat actions" onclick="TFCollab.quick()">＋</button>`;
  }
  function show(tab='chats'){
    if(!isStaff())return;
    if(ui.panel && ui.tab===tab && ui.mode==='list'){ui.panel=false;renderPanel();return;}
    ui.panel=true;ui.mode='list';ui.tab=tab;ui.currentId='';ui.query='';renderPanel();loadInbox();
  }
  function switchTab(tab='chats'){if(!isStaff())return;ui.panel=true;ui.mode='list';ui.tab=tab;ui.currentId='';ui.query='';renderPanel();loadInbox()}
  function quick(){if(!isStaff())return;ui.panel=true;ui.mode='quick';renderPanel()}
  function closePanel(){ui.panel=false;ui.mode='list';ui.currentId='';renderPanel()}
  function panelHeader(){
    return `<div class="tf-chat-head"><div class="tf-chat-heading"><span class="tf-chat-logo">✦</span><div><strong>WorkChat</strong><small>Private Techfinitys team messages</small></div></div><button type="button" aria-label="Close messages" class="tf-chat-close" onclick="TFCollab.close()">×</button></div>`;
  }
  function renderPanel(){
    const panel=document.getElementById('tfChatPanel');if(!panel)return;
    if(!ui.panel||!isStaff()){panel.hidden=true;drawDock();return;}
    panel.hidden=false;drawDock();
    let content='';
    if(ui.mode==='quick'){
      content=`<div class="tf-chat-section-title">Quick actions</div><div class="tf-chat-quick">
        <button onclick="TFCollab.show('people')"><span>✉</span><div><strong>Send a direct message</strong><small>Choose a teammate</small></div></button>
        <button onclick="TFCollab.composeGroup()"><span>♧</span><div><strong>Start a group conversation</strong><small>Chat with your project team</small></div></button>
        <button onclick="TFCollab.show('people')"><span>♙</span><div><strong>Employee directory</strong><small>Find teammates</small></div></button>
        <button onclick="TFCollab.invite()"><span>＋</span><div><strong>${['admin','manager'].includes(role())?'Invite people':'My team'}</strong><small>${['admin','manager'].includes(role())?'Manage employee accounts':'View your team'}</small></div></button>
      </div>`;
    } else if(ui.mode==='group'){
      content=`<div class="tf-chat-backline"><button onclick="TFCollab.show('chats')">‹ Back</button><strong>New group</strong></div>
      <form class="tf-chat-group-form" onsubmit="event.preventDefault();TFCollab.submitGroup(this)">
        <label>Group name<input name="title" maxlength="100" minlength="2" required placeholder="e.g. Design team"></label>
        <label>People <small>Select up to 19</small></label><div class="tf-chat-people-select">${ui.people.map(p=>`<label><input type="checkbox" name="memberId" value="${p.id}">${photoMarkup(p.photo,p.name,'tiny')}<span>${e(p.name)}</span></label>`).join('')||'<p>No teammates available.</p>'}</div>
        <button class="tf-chat-submit" type="submit">Create group conversation</button>
      </form>`;
    } else if(ui.mode==='add'){
      const current=ui.chats.find(c=>c.id===ui.currentId),ids=new Set(current?.people?.map(p=>p.id)||[]);
      content=`<div class="tf-chat-backline"><button onclick="TFCollab.openThread('${e(ui.currentId)}')">‹ Back</button><strong>Add members</strong></div>
        <form class="tf-chat-group-form" onsubmit="event.preventDefault();TFCollab.submitAdd(this)"><div class="tf-chat-people-select">${ui.people.filter(p=>!ids.has(p.id)).map(p=>`<label><input type="checkbox" name="memberId" value="${p.id}">${photoMarkup(p.photo,p.name,'tiny')}<span>${e(p.name)}</span></label>`).join('')||'<p>Everyone is already in this group.</p>'}</div><button class="tf-chat-submit">Add to group</button></form>`;
    } else if(ui.mode==='thread'){
      const current=ui.chats.find(c=>c.id===ui.currentId);
      content=`<div class="tf-chat-backline"><button onclick="TFCollab.show('chats')" aria-label="Back to conversations">‹</button>${photoMarkup(current?.photo,current?.title||'Chat','tiny')}<div class="tf-chat-thread-title"><strong>${e(current?.title||'Conversation')}</strong><small>${current?.kind==='group'?`${current.people.length} team members`:'Direct message · internal'}</small></div>${current?.kind==='group'?`<button class="tf-chat-add-person" onclick="TFCollab.addPeople()" title="Add team members">＋</button>`:''}</div>
      <div id="tfMessageList" class="tf-messages" aria-live="polite"></div><form id="tfMessageForm" class="tf-message-form" onsubmit="event.preventDefault();TFCollab.send(this)"><textarea id="tfMessageInput" rows="2" maxlength="4000" required aria-label="Type message" placeholder="Message your teammate…" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();this.form.requestSubmit()}"></textarea><button type="submit" title="Send message">➤</button></form>`;
    } else {
      content=`<div class="tf-chat-tabs"><button class="${ui.tab==='chats'?'active':''}" onclick="TFCollab.switchTab('chats')">Recent</button><button class="${ui.tab==='unread'?'active':''}" onclick="TFCollab.switchTab('unread')">Unread</button><button class="${ui.tab==='people'?'active':''}" onclick="TFCollab.switchTab('people')">People</button><button class="tf-chat-new" onclick="TFCollab.quick()">＋ New</button></div>
      <div class="tf-chat-search"><span>⌕</span><input id="tfChatQuery" type="search" aria-label="Search conversations or people" placeholder="Search team…" value="${e(ui.query)}" oninput="TFCollab.search(this.value)"></div>
      <div id="tfChatList" class="tf-chat-list"></div>`;
    }
    panel.innerHTML=panelHeader()+`<div class="tf-chat-body">${content}</div><div id="tfChatNotice" class="tf-chat-notice" role="status">${e(ui.notice)}</div>`;
    if(ui.mode==='thread'){drawMessages();const field=document.getElementById('tfMessageInput');field?.focus()}
    if(ui.mode==='list')drawList();
  }
  function drawList(){
    const list=document.getElementById('tfChatList');if(!list)return;
    const q=ui.query.toLowerCase().trim();
    const rows = ui.tab==='people' ? ui.people.filter(p=>(p.name+' '+p.department+' '+p.title).toLowerCase().includes(q)) : ui.chats.filter(c=>(ui.tab!=='unread'||c.unread>0)&&(c.title+' '+c.lastMessage).toLowerCase().includes(q));
    list.innerHTML=rows.length?rows.map(o=>{
      const person=ui.tab==='people',title=person?o.name:o.title,detail=person?(o.title||'Team member'):(o.lastMessage||((o.kind==='group'?'Group':'Direct')+' conversation'));
      return `<button class="tf-chat-item" type="button" onclick="${person?`TFCollab.direct(${o.id})`:`TFCollab.openThread('${e(o.id)}')`}">
        ${photoMarkup(person?o.photo:o.photo,title)}<span class="tf-chat-item-copy"><strong>${e(title)}</strong><small>${e(detail)}</small></span>
        <span class="tf-chat-item-end">${person?'':`<time>${stamp(o.lastAt)}</time>${o.unread?`<b>${o.unread>99?'99+':o.unread}</b>`:''}`}</span></button>`
    }).join('') : `<div class="tf-chat-empty">${ui.loading?'Loading…':ui.tab==='people'?'No teammates match this search.':'No conversations yet. Start a new message!'}</div>`;
  }
  function search(value){ui.query=value;drawList()}
  function drawMessages(){
    const list=document.getElementById('tfMessageList');if(!list)return;
    const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<120;
    list.innerHTML=ui.messages.length?ui.messages.map(m=>`<div class="tf-message ${String(m.senderId)===String(me())?'mine':'theirs'}">
      ${String(m.senderId)===String(me())?'':photoMarkup(m.photo,m.senderName,'tiny')}
      <div class="tf-message-bubble">${String(m.senderId)===String(me())?'':`<small class="tf-message-author">${e(m.senderName)}</small>`}<p>${e(m.body)}</p><time>${stamp(m.at)}</time></div></div>`).join('') : '<div class="tf-chat-empty">Start the conversation with a message.</div>';
    if(nearBottom)list.scrollTop=list.scrollHeight;
  }
  async function loadInbox(){
    if(!window.state?.ctx || ui.loading)return;
    ui.loading=true;
    try{
      const data=await xhr(BASE);
      ui.recent=data.recentProjects||[];ui.people=data.people||[];ui.chats=data.conversations||[];
      ui.ready=true;ui.notice='';drawRecent();drawDock();
      // Keep the project register in sync when a newly granted assignment
      // appears in Recent Projects before the main workspace data refreshes.
      if(!ui.projectSyncChecked && role()==='employee' && ui.recent.some(p=>!window.state?.projects?.some(x=>x.id===p.id))){
        ui.projectSyncChecked=true;
        if(typeof window.load==='function')await window.load();
      }
      if(ui.panel&&ui.mode==='list')drawList();
      if(ui.panel&&ui.mode==='thread')await loadThread(ui.currentId,true);
    }catch(error){if(ui.panel)message(error.message,true)}finally{ui.loading=false}
  }
  async function loadThread(id,silent=false){
    if(!id || !isStaff())return;
    try{
      const data=await xhr(BASE+'thread/'+encodeURIComponent(id)+'/');
      if(ui.currentId!==id || ui.mode!=='thread')return;
      ui.messages=data.messages||[];
      const convo=ui.chats.find(c=>c.id===id);
      if(convo){Object.assign(convo,data.conversation);convo.unread=0}
      drawMessages();drawDock();
      if(!silent){const field=document.getElementById('tfMessageInput');field?.focus()}
    }catch(error){message(error.message,true)}
  }
  function openThread(id){
    if(!ui.chats.some(c=>c.id===id))return;
    ui.currentId=id;ui.mode='thread';ui.panel=true;ui.messages=[];ui.notice='';renderPanel();loadThread(id);
  }
  async function direct(id){
    if(ui.busy)return;ui.busy=true;
    try{const r=await xhr(BASE,{action:'start_chat',kind:'direct',memberIds:[id]});
      if(!ui.chats.find(c=>c.id===r.conversation.id))ui.chats.unshift(r.conversation);
      openThread(r.conversation.id)
    }catch(error){message(error.message,true)}finally{ui.busy=false}
  }
  function composeGroup(){ui.mode='group';ui.panel=true;renderPanel()}
  async function submitGroup(form){
    const people=[...form.querySelectorAll('input[name="memberId"]:checked')].map(el=>Number(el.value));
    if(!people.length){message('Choose at least one teammate.',true);return;}
    if(ui.busy)return;ui.busy=true;
    try{const r=await xhr(BASE,{action:'start_chat',kind:'group',title:form.elements.title.value,memberIds:people});
      ui.chats.unshift(r.conversation);openThread(r.conversation.id)
    }catch(error){message(error.message,true)}finally{ui.busy=false}
  }
  async function send(form){
    const textarea=form.querySelector('textarea');const body=textarea?.value.trim();if(!body || ui.busy)return;
    const id=ui.currentId;ui.busy=true;textarea.disabled=true;
    try{const result=await xhr(BASE,{action:'send_chat',conversationId:id,body});
      if(ui.currentId!==id)return;
      ui.messages.push(result.message);textarea.value='';drawMessages();
      const row=ui.chats.find(c=>c.id===id);if(row){row.lastMessage=body;row.lastAt=result.message.at}
    }catch(error){message(error.message,true)}finally{textarea.disabled=false;textarea.focus();ui.busy=false}
  }
  function addPeople(){
    const c=ui.chats.find(c=>c.id===ui.currentId);if(!c||c.kind!=='group')return;
    if(!(['manager','admin'].includes(role())||Number(c.createdBy)===Number(me()))){message('Only group owners or managers may invite members.',true);return}
    ui.mode='add';renderPanel();
  }
  async function submitAdd(form){
    const ids=[...form.querySelectorAll('input[name="memberId"]:checked')].map(i=>Number(i.value));
    if(!ids.length){message('Select a teammate.',true);return}
    try{await xhr(BASE,{action:'add_chat_members',conversationId:ui.currentId,memberIds:ids});await loadInbox();ui.mode='thread';renderPanel();await loadThread(ui.currentId)}catch(error){message(error.message,true)}
  }
  function invite(){closePanel();if(['admin','manager'].includes(role()))window.go?.('team');else window.go?.('projects')}
  async function openProfile(){
    const overlay=document.getElementById('tfProfileDialog');if(!overlay)return;
    overlay.hidden=false;overlay.innerHTML=`<div class="tf-profile-scrim" onclick="TFCollab.closeProfile()"></div><div class="tf-profile-card" role="dialog" aria-modal="true" aria-labelledby="tfProfileTitle"><div class="tf-profile-head"><div><small>MY WORKSPACE</small><h2 id="tfProfileTitle">Edit profile</h2></div><button type="button" onclick="TFCollab.closeProfile()" aria-label="Close profile">×</button></div><div id="tfProfileBody" class="tf-profile-loading">Loading profile…</div></div>`;
    try{ui.profile=await xhr(BASE+'profile/');drawProfile()}catch(error){const node=document.getElementById('tfProfileBody');if(node)node.textContent=error.message}
  }
  function drawProfile(){
    const p=ui.profile,node=document.getElementById('tfProfileBody');if(!node||!p)return;
    node.innerHTML=`<form id="tfProfileForm" onsubmit="event.preventDefault();TFCollab.saveProfile(this)">
      <label class="tf-profile-photo-picker"><span id="tfProfilePreview">${photoMarkup(p.photo,p.name,'large')}</span><div><strong>Profile photo</strong><small>JPG, PNG or WebP · up to 2 MB<br>Automatically cropped to a square</small><input type="file" name="photo" accept="image/jpeg,image/png,image/webp" onchange="TFCollab.previewPhoto(this)" aria-label="Choose profile photo"></div></label>
      <div class="tf-profile-fields"><label>First name<input name="firstName" maxlength="150" value="${e(p.firstName)}" autocomplete="given-name"></label><label>Last name<input name="lastName" maxlength="150" value="${e(p.lastName)}" autocomplete="family-name"></label></div>
      <label>Phone number<input name="phone" maxlength="40" value="${e(p.phone)}" autocomplete="tel"></label>
      <label>Login email <span class="tf-profile-readonly">Managed by your administrator</span><input value="${e(p.email||'No email assigned')}" readonly tabindex="-1"></label>
      <div class="tf-profile-account">${p.googleLinked?'✓ Google account linked':'Google login can be linked after the administrator sets your verified email.'}</div>
      <div id="tfProfileStatus" role="status"></div><button type="submit" class="tf-profile-save">Save profile changes</button></form>`;
  }
  function previewPhoto(input){
    const file=input.files?.[0];if(!file)return;
    const node=document.getElementById('tfProfilePreview');if(!node)return;
    if(file.size>2*1024*1024){document.getElementById('tfProfileStatus').textContent='Photo must be smaller than 2 MB.';input.value='';return}
    const temp=URL.createObjectURL(file);node.innerHTML=`<img class="tf-chat-avatar large" alt="New profile photo" src="${e(temp)}">`;
    node.querySelector('img')?.addEventListener('load',()=>URL.revokeObjectURL(temp),{once:true});
  }
  async function saveProfile(form){
    const status=document.getElementById('tfProfileStatus');const submit=form.querySelector('button[type="submit"]');submit.disabled=true;
    try{
      const payload=new FormData(form);
      if(!payload.get('photo')?.size)payload.delete('photo');
      const result=await fetch(BASE+'profile/',{method:'POST',headers:{'X-CSRFToken':token()},body:payload,credentials:'same-origin'});
      const data=await result.json();if(!result.ok)throw new Error(data.error||'Unable to save profile');
      ui.profile=data;ui.profilePhotoVersion++;
      if(window.state?.ctx){window.state.ctx.name=data.name;window.state.ctx.profilePhotoUrl=data.photo}
      const current=window.state?.members?.find(m=>m.id===data.id);if(current){current.name=data.name;current.profilePhotoUrl=data.photo}
      avatarTop();if(status)status.textContent='Profile saved successfully.';
      drawProfile();const updated=document.getElementById('tfProfileStatus');if(updated)updated.textContent='Saved successfully.';
      await loadInbox();
    }catch(error){if(status){status.textContent=error.message;status.classList.add('error')}}finally{submit.disabled=false}
  }
  function closeProfile(){const overlay=document.getElementById('tfProfileDialog');if(overlay){overlay.hidden=true;overlay.innerHTML=''}}
  function init(){
    const search=document.getElementById('tfRecentSearchBtn');if(search)search.onclick=toggleRecentSearch;
    document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(document.getElementById('tfProfileDialog')?.hidden===false)closeProfile();else if(ui.panel)closePanel()}});
    // Wrap the already-installed CRM renderer so photo and profile actions stay
    // present when other modules redraw the sidebar/header.
    if(typeof render==='function'){
      const original=render;
      render=function(){const result=original();avatarTop();if(!ui.ready && !ui.loading && window.state?.ctx){queueMicrotask(()=>{if(!ui.ready&&!ui.loading)loadInbox()})}return result};
      window.render=render;
    }
    if(window.TFPlus?.openProject){
      const original=window.TFPlus.openProject;
      window.TFPlus.openProject=function(id,tab){const result=original.call(this,id,tab);touchProject(id);return result};
    }
    const wait=async()=>{
      if(!window.state?.ctx)return;
      avatarTop();await loadInbox();
      const matched=location.hash.match(/^#projects\/([0-9a-f-]{36})(?:\/|$)/i);
      if(matched)touchProject(matched[1]);
    };
    wait();
    setInterval(()=>{if(document.visibilityState==='visible' && window.state?.ctx)loadInbox()},30000);
    setInterval(()=>{if(document.visibilityState==='visible' && ui.panel && ui.mode==='thread' && ui.currentId)loadThread(ui.currentId,true)},6000);
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible' && window.state?.ctx)loadInbox()});
    // When the initial async workspace request completes, the render wrapper
    // will fire. Do not indefinitely poll while the page is being initialized.
    setTimeout(()=>{if(!ui.ready && window.state?.ctx)wait()},1500);
  }
  window.TFCollab={show,switchTab,quick,close:closePanel,closeProfile,openProfile,previewPhoto,saveProfile,
    viewProject,search,openThread,direct,composeGroup,submitGroup,send,addPeople,submitAdd,invite};
  init();
})();

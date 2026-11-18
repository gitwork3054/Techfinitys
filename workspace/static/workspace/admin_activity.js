/* Super Admin command inbox: company-wide audit trail and approval review. */
(function(){
  const ui={data:null,summary:null,loading:false,error:'',tab:'pending',filter:{q:'',category:'all',employeeId:'',from:'',to:''},cursor:'',next:null,seen:false,requestId:0,searchTimer:null};
  const escHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||'');
  const at=x=>x?new Date(x).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'—';
  const statusTime=x=>x?new Date(x).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'—';
  const card=(label,value,note,icon)=>`<article class="tf-ac-stat"><span>${icon} ${escHtml(label)}</span><strong>${Number(value||0).toLocaleString('en-IN')}</strong><small>${escHtml(note)}</small></article>`;
  const isAdmin=()=>window.state?.ctx?.role==='admin';
  const categories=[['all','All activity'],['attendance','Attendance & breaks'],['leave','Leave requests'],['tasks','Projects & tasks'],['time','Timesheets'],['approvals','Approvals'],['clients','Clients & support'],['billing','Invoices & payments'],['people','Team & users'],['chat','Chat metadata'],['other','Other']];
  if (typeof menus!=='undefined' && menus.admin && !menus.admin.includes('admin_activity')) menus.admin.splice(1,0,'admin_activity');
  if(typeof labels!=='undefined')labels.admin_activity='Admin activity';
  const statusDesc={attendance:'Attendance',leave:'Leave',tasks:'Projects & tasks',time:'Time tracking',approvals:'Approvals',clients:'Client service',billing:'Billing',people:'Team',chat:'Chat activity',other:'Operations'};
  function updateBadges(){
    if(!isAdmin())return;
    const n=ui.summary?.unread??window.state.notifications?.filter(x=>!x.read).length??0;
    const bell=document.getElementById('bellBtn');if(bell){bell.onclick=()=>window.go('admin_activity');bell.title=`Open Super Admin activity (${n} unread)`;bell.setAttribute('aria-label',bell.title);bell.innerHTML=`♧${n?`<span class="notification-dot">${n>99?'99+':n}</span>`:''}`;}
    const nav=document.querySelector('#nav [data-tab="admin_activity"]');if(nav){nav.querySelector('.tf-ac-nav-count')?.remove();if(n){const b=document.createElement('em');b.className='tf-ac-nav-count';b.textContent=n>99?'99+':String(n);nav.append(b);}}
  }
  async function summary(){if(!isAdmin())return;try{const r=await fetch('/api/admin-activity/?summary=1',{cache:'no-store'});if(!r.ok)return;const d=await r.json();ui.summary=d.summary;updateBadges();if(state.tab==='overview'||state.tab==='admin_activity')renderSummary();}catch(_){}}
  async function fetchEvents(append=false,quiet=false){
    if(!isAdmin()||(append&&ui.loading))return;ui.loading=true;ui.error='';if(!quiet)draw();
    const req=++ui.requestId;
    const params=new URLSearchParams({...ui.filter});if(append&&ui.next)params.set('before',ui.next);
    try{const response=await fetch('/api/admin-activity/?'+params.toString(),{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to load activity');if(req!==ui.requestId)return;
      if(append&&ui.data){data.events=[...ui.data.events,...data.events]}ui.data=data;ui.summary=data.summary;ui.next=data.nextBefore;ui.seen=true;updateBadges();
    }catch(err){ui.error=err.message;}finally{if(req===ui.requestId){ui.loading=false;if(state.tab==='admin_activity')draw();else if(state.tab==='overview')renderSummary();}}
  }
  function applyFilter(key,value){if(!(key in ui.filter))return;ui.filter[key]=value;ui.next=null;ui.data=null;fetchEvents();}
  function search(value){clearTimeout(ui.searchTimer);ui.searchTimer=setTimeout(()=>applyFilter('q',value),350);}
  function clearFilters(){ui.filter={q:'',category:'all',employeeId:'',from:'',to:''};ui.next=null;ui.data=null;fetchEvents();}
  function show(){if(!isAdmin())return;go('admin_activity');fetchEvents();}
  function switchTab(which){ui.tab=which==='history'?'history':'pending';draw();}
  function pendingRow(p,kind){
    const isLeave=kind==='leave',isTime=kind==='timesheet';
    const category=isLeave?'Leave request':isTime?'Timesheet submitted':'Internal sign-off';
    const title=isLeave?`${p.type} · ${statusTime(p.startDate)} – ${statusTime(p.endDate)}`:isTime?`${Math.round(p.minutes/6)/10} hours · ${statusTime(p.date)}`:p.title;
    const info=isLeave?p.reason||'No reason provided':isTime?[p.client,p.project,p.description].filter(Boolean).join(' · '):[p.client,p.description].filter(Boolean).join(' · ');
    const user=p.employee||p.requestedBy;
    return `<article class="tf-ac-request"><div class="tf-ac-request-icon">${isLeave?'☼':isTime?'◷':'✓'}</div><div class="tf-ac-request-main"><div class="tf-ac-request-meta"><span class="tf-ac-tag">${category}</span><span>${escHtml(user)}</span></div><h3>${escHtml(title)}</h3><p>${escHtml(info)}</p></div><div class="tf-ac-buttons"><button type="button" class="tf-ac-approve" onclick="TFAdminActivity.review('${kind}','${p.id}','approved')">✓ Approve</button><button type="button" class="tf-ac-decline" onclick="TFAdminActivity.review('${kind}','${p.id}','rejected')">Decline</button></div></article>`;
  }
  function pending(){const d=ui.data||{},rows=[...(d.leaves||[]).map(p=>pendingRow(p,'leave')),...(d.timesheets||[]).map(p=>pendingRow(p,'timesheet')),...(d.approvals||[]).map(p=>pendingRow(p,'approval'))];return `<div class="tf-ac-pending-head"><h2>Needs your decision</h2><p>Approving or declining updates the employee's real request, records the reviewer and notifies the requester.</p></div><div class="tf-ac-requests">${rows.join('')||`<div class="tf-ac-empty"><span>✓</span><strong>All caught up</strong><p>No outstanding leave, timesheet or internal approval requests.</p></div>`}</div>`;}
  function history(){
    const d=ui.data||{};const people=d.employees||[];
    return `<div class="tf-ac-filters"><label class="tf-ac-search">⌕ <input type="search" placeholder="Search actions, employees, projects…" aria-label="Search employee activity" value="${escHtml(ui.filter.q)}" oninput="TFAdminActivity.search(this.value)"></label>
      <select aria-label="Activity category" onchange="TFAdminActivity.applyFilter('category',this.value)">${categories.map(([id,label])=>`<option value="${id}" ${ui.filter.category===id?'selected':''}>${label}</option>`).join('')}</select>
      <select aria-label="Filter by employee" onchange="TFAdminActivity.applyFilter('employeeId',this.value)"><option value="">All employees</option>${people.map(p=>`<option value="${p.id}" ${String(ui.filter.employeeId)===String(p.id)?'selected':''}>${escHtml(p.name)}</option>`).join('')}</select>
      <label class="tf-ac-date">From <input type="date" value="${escHtml(ui.filter.from)}" onchange="TFAdminActivity.applyFilter('from',this.value)"></label><label class="tf-ac-date">To <input type="date" value="${escHtml(ui.filter.to)}" onchange="TFAdminActivity.applyFilter('to',this.value)"></label>
      <button type="button" onclick="TFAdminActivity.clearFilters()">Reset</button></div>
      <div class="tf-ac-timeline" aria-live="polite">${(d.events||[]).map(a=>`<article class="tf-ac-event"><span class="tf-ac-avatar">${escHtml(a.employee.split(/\s+/).map(n=>n.charAt(0)).join('').slice(0,2).toUpperCase())}</span><div class="tf-ac-event-body"><div class="tf-ac-event-title"><strong>${escHtml(a.employee)}</strong><span>${escHtml(a.action)}</span></div><div class="tf-ac-event-meta"><span class="tf-ac-tag ${escHtml(a.category)}">${escHtml(statusDesc[a.category]||a.category)}</span>${a.client?`<span>${escHtml(a.client)}</span>`:''}<time>${escHtml(at(a.at))}</time></div>${a.detail?`<p>${escHtml(a.detail)}</p>`:''}</div></article>`).join('')||`<div class="tf-ac-empty"><span>◌</span><strong>No matching activity</strong><p>Try another date, category or employee.</p></div>`}</div>
      ${ui.next?`<div class="tf-ac-more"><button type="button" onclick="TFAdminActivity.more()">Load older activity</button></div>`:''}`;
  }
  function view(){const s=ui.summary||{};const total=(s.pendingLeaves||0)+(s.pendingTimesheets||0)+(s.pendingApprovals||0);return `<div class="tf-ac-page">
    <header class="tf-ac-head"><div><span class="tf-ac-overline">SUPER ADMIN / OPERATIONS INTELLIGENCE</span><h1>Activity & approvals</h1><p>Every recorded employee action in one place—review requests, monitor shifts and follow progress.</p></div><div class="tf-ac-head-actions"><button type="button" onclick="notificationCenter()">All notifications</button><button type="button" onclick="TFAdminActivity.markAll()">✓ Mark alerts read</button><button type="button" class="tf-ac-refresh" onclick="TFAdminActivity.refresh()">↻ Refresh</button></div></header>
    <div class="tf-ac-stats">${card('Needs approval',total,'Pending team requests','◎')}${card('Currently on shift',s.onShift,'Active attendance sessions','◷')}${card('Actions today',s.todayActions,'Employee activity records','⌁')}${card('Unread alerts',s.unread,'New staff updates','♧')}</div>
    <div class="tf-ac-tabs"><button type="button" class="${ui.tab==='pending'?'active':''}" onclick="TFAdminActivity.switchTab('pending')">Approval queue <b>${total}</b></button><button type="button" class="${ui.tab==='history'?'active':''}" onclick="TFAdminActivity.switchTab('history')">All activity</button><span>${ui.loading?'Updating…':ui.data?'Updated just now':'Ready'}</span></div>
    ${ui.error?`<div class="tf-ac-error" role="alert">${escHtml(ui.error)} <button onclick="TFAdminActivity.refresh()">Retry</button></div>`:''}
    ${ui.tab==='pending'?pending():history()}
    ${ui.loading&&!ui.data?'<div class="tf-ac-loading">Loading team events…</div>':''}
    <div class="tf-ac-note">Activity is visible only to Super Admin. Entries reflect actions recorded by the CRM, not activity outside the application. Internal messages are shown as metadata, not private message contents.</div>
  </div>`;}
  function draw(){if(state.tab!=='admin_activity'||!isAdmin())return;const main=document.getElementById('mainContent');if(!main)return;main.innerHTML=view();}
  function renderSummary(){
    if(!isAdmin()||state.tab!=='overview')return;
    const main=document.getElementById('mainContent');if(!main)return;
    const s=ui.summary||{},total=(s.pendingLeaves||0)+(s.pendingTimesheets||0)+(s.pendingApprovals||0);
    document.getElementById('tfAdminOverviewStrip')?.remove();
    main.insertAdjacentHTML('afterbegin',`<button type="button" id="tfAdminOverviewStrip" class="tf-ac-overview" onclick="go('admin_activity')"><span class="tf-ac-overview-icon">◎</span><span><strong>Team activity & approvals</strong><small>${total} requests need review · ${s.onShift||0} employees on shift · ${s.unread||0} unread alerts</small></span><span class="tf-ac-overview-cta">Open activity center →</span></button>`);
  }
  async function markAll(){if(!isAdmin())return;try{const r=await fetch('/api/admin-activity/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({action:'mark_seen'})});const d=await r.json();if(!r.ok)throw Error(d.error||'Unable to mark alerts read');ui.summary={...(ui.summary||{}),unread:0};updateBadges();draw();}catch(e){ui.error=e.message;draw();}}
  function review(kind,id,status){if(!isAdmin())return;
    if(status==='approved'){
      if(!confirm('Approve this request? Your decision will be recorded and the employee notified.'))return;
      return submitDecision(kind,id,status,'');
    }
    openModal(`<div class="tf-ac-decision"><h2>Decline request</h2><p>The employee will see your decision and explanation.</p><form id="tfAdminDecisionForm"><label>Reason for declining<textarea name="note" rows="4" maxlength="2000" required placeholder="Give a clear reason for this decision"></textarea></label><div><button type="button" onclick="closeModal()">Cancel</button><button type="submit" class="tf-ac-decline">Decline request</button></div></form></div>`);
    document.getElementById('tfAdminDecisionForm').onsubmit=e=>{e.preventDefault();const note=e.target.elements.note.value.trim();if(!note)return;submitDecision(kind,id,status,note);};
  }
  async function submitDecision(kind,id,status,note){
    const action=kind==='leave'?'review_leave':kind==='timesheet'?'time_status':'decide_approval';
    if(!['leave','timesheet','approval'].includes(kind))return;
    try{const res=await fetch('/api/operations/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({action,id,status,note})});const data=await res.json();if(!res.ok)throw Error(data.error||'Could not submit decision');closeModal();await fetchEvents();await summary();
    }catch(err){ui.error=err.message;draw();alert(err.message);}
  }
  const previousRender=render;
  render=function(){previousRender();if(!isAdmin()||state.loading||state.error)return;updateBadges();if(state.tab==='admin_activity'){draw();if(!ui.data&&!ui.loading)queueMicrotask(()=>fetchEvents());}else if(state.tab==='overview')renderSummary();};
  window.render=render;
  window.TFAdminActivity={show,applyFilter,search,clearFilters,switchTab,refresh:()=>fetchEvents(),more:()=>fetchEvents(true),markAll,review};
  if(location.hash==='#admin_activity'){state.tab='admin_activity';if(!state.loading)render();}
  // In-app polling requires neither costly WebSockets nor a background worker.
  setInterval(()=>{if(document.visibilityState!=='visible'||!isAdmin())return;summary();if(state.tab==='admin_activity'&&!ui.loading&&!ui.next)fetchEvents(false,true);},30000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&isAdmin())summary();});
  if(isAdmin())summary();
})();

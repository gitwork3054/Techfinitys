/* Super Admin command inbox: company-wide audit trail and approval review. */
(function(){
  const ui={data:null,summary:null,loading:false,error:'',tab:'pending',filter:{q:'',category:'all',employeeId:'',from:'',to:''},cursor:'',next:null,seen:false,requestId:0,searchTimer:null,ledgerData:null,ledgerLoading:false,ledgerError:'',ledgerRequestId:0,ledgerStatus:'all',pendingData:null,pendingLoading:false,pendingError:'',pendingRequestId:0};
  const escHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||'');
  const at=x=>x?new Date(x).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'—';
  const statusTime=x=>x?new Date(x).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'—';
  const card=(label,value,note,icon,tab)=>`<button type="button" class="tf-ac-stat" onclick="TFAdminActivity.switchTab('${tab}')"><span>${icon} ${escHtml(label)}</span><strong>${Number(value||0).toLocaleString('en-IN')}</strong><small>${escHtml(note)}</small></button>`;
  const isAdmin=()=>window.state?.ctx?.role==='admin';
  const categories=[['all','All activity'],['attendance','Attendance & breaks'],['leave','Leave requests'],['tasks','Projects & tasks'],['time','Timesheets'],['approvals','Approvals'],['clients','Clients & support'],['billing','Invoices & payments'],['people','Team & users'],['access','Sign in / out'],['chat','Chat metadata'],['other','Other']];
  if (typeof menus!=='undefined' && menus.admin && !menus.admin.includes('admin_activity')) menus.admin.splice(1,0,'admin_activity');
  if(typeof labels!=='undefined')labels.admin_activity='Admin activity';
  const statusDesc={attendance:'Attendance',leave:'Leave',tasks:'Projects & tasks',time:'Time tracking',approvals:'Approvals',clients:'Client service',billing:'Billing',people:'Team',access:'Access',chat:'Chat activity',other:'Operations'};
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
  async function fetchPending(){
    if(!isAdmin()||ui.pendingLoading)return;
    const req=++ui.pendingRequestId;
    ui.pendingLoading=true;ui.pendingError='';
    if(state.tab==='admin_activity'&&ui.tab==='pending')draw();
    try{
      // Use the unfiltered server queue. Audit history filters never hide approvals.
      const response=await fetch('/api/admin-activity/',{cache:'no-store',credentials:'same-origin'});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'Could not load pending requests');
      if(req!==ui.pendingRequestId)return;
      ui.pendingData=data;
      ui.summary=data.summary;
      updateBadges();
    }catch(err){if(req===ui.pendingRequestId)ui.pendingError=err.message;}
    finally{if(req===ui.pendingRequestId){
      ui.pendingLoading=false;
      if(state.tab==='admin_activity'&&ui.tab==='pending')draw();
      else if(state.tab==='overview')renderSummary();
    }}
  }
  function applyFilter(key,value){if(!(key in ui.filter))return;ui.filter[key]=value;ui.next=null;if(isLedger()){fetchLedger(1);}else{ui.data=null;fetchEvents();}}
  function search(value){clearTimeout(ui.searchTimer);ui.searchTimer=setTimeout(()=>applyFilter('q',value),350);}
  function clearFilters(){ui.filter={q:'',category:'all',employeeId:'',from:'',to:''};ui.ledgerStatus='all';ui.next=null;if(isLedger()){fetchLedger(1);}else{ui.data=null;fetchEvents();}}
  function show(){if(!isAdmin())return;go('admin_activity');fetchPending();}
  function switchTab(which){const next=['pending','history','attendance','leaves','timesheets'].includes(which)?which:'pending';if(next!==ui.tab){ui.tab=next;ui.ledgerData=null;ui.ledgerError='';ui.ledgerRequestId++;ui.ledgerStatus='all';}draw();if(isLedger())fetchLedger(1);else if(ui.tab==='pending')fetchPending();else if(!ui.data)fetchEvents();}
  function pendingRow(p,kind){
    const isLeave=kind==='leave',isTime=kind==='timesheet';
    const category=isLeave?'Leave request':isTime?'Timesheet submitted':'Internal sign-off';
    const title=isLeave?`${p.type} · ${statusTime(p.startDate)} – ${statusTime(p.endDate)}`:isTime?`${Math.round(p.minutes/6)/10} hours · ${statusTime(p.date)}`:p.title;
    const info=isLeave?p.reason||'No reason provided':isTime?[p.client,p.project,p.description].filter(Boolean).join(' · '):[p.client,p.description].filter(Boolean).join(' · ');
    const user=p.employee||p.requestedBy;
    return `<article class="tf-ac-request"><div class="tf-ac-request-icon">${isLeave?'☼':isTime?'◷':'✓'}</div><div class="tf-ac-request-main"><div class="tf-ac-request-meta"><span class="tf-ac-tag">${category}</span><span>${escHtml(user)}</span></div><h3>${escHtml(title)}</h3><p>${escHtml(info)}</p></div><div class="tf-ac-buttons"><button type="button" class="tf-ac-approve" onclick="TFAdminActivity.review('${kind}','${p.id}','approved')">✓ Approve</button><button type="button" class="tf-ac-decline" onclick="TFAdminActivity.review('${kind}','${p.id}','rejected')">Decline</button></div></article>`;
  }
  function pending(){
    const d=ui.pendingData||{},rows=[
      ...(d.leaves||[]).map(p=>pendingRow(p,'leave')),
      ...(d.timesheets||[]).map(p=>pendingRow(p,'timesheet')),
      ...(d.approvals||[]).map(p=>pendingRow(p,'approval'))
    ];
    const totals=d.summary||{};
    const latest=ui.summary||{};
    const count=s=>(s.pendingLeaves||0)+(s.pendingTimesheets||0)+(s.pendingApprovals||0);
    const expected=Math.max(count(totals),count(latest));
    let fallback='';
    if(ui.pendingError)fallback=`<div class="tf-ac-error" role="alert">${escHtml(ui.pendingError)} <button type="button" onclick="TFAdminActivity.refresh()">Retry</button></div>`;
    else if(ui.pendingLoading||!ui.pendingData)fallback='<div class="tf-ac-loading" role="status">Loading pending leave, timesheet and approval requests…</div>';
    else if(!rows.length&&expected>0)fallback=`<div class="tf-ac-error" role="alert">${expected} pending request(s) were counted but their details could not be displayed. <button type="button" onclick="TFAdminActivity.refresh()">Reload requests</button></div>`;
    else if(!rows.length)fallback='<div class="tf-ac-empty"><span>✓</span><strong>All caught up</strong><p>No outstanding leave, timesheet or internal approval requests.</p></div>';
    return `<div class="tf-ac-pending-head"><h2>Needs your decision</h2><p>Approving or declining updates the employee's real request, records the reviewer and notifies the requester.</p></div><div class="tf-ac-requests">${rows.join('')}${fallback}</div>`;
  }
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
  // Dedicated paginated employee ledgers: separate from the infinite audit feed.
  function isLedger(){return ['attendance','leaves','timesheets'].includes(ui.tab);}
  const hours=x=>`${(Number(x||0)/60).toFixed(1)} h`;
  async function fetchLedger(page=1){
    if(!isAdmin()||!isLedger())return;
    const kind=ui.tab, filterKey=JSON.stringify(ui.filter)+'/'+ui.ledgerStatus;
    const request=++ui.ledgerRequestId;
    ui.ledgerLoading=true;ui.ledgerError='';if(page===1)ui.ledgerData=null;draw();
    const params=new URLSearchParams({...ui.filter,ledger:kind,page:String(page)});
    if(ui.ledgerStatus!=='all')params.set('status',ui.ledgerStatus);
    try{
      const response=await fetch('/api/admin-activity/?'+params.toString(),{cache:'no-store'});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'Could not load employee records');
      if(request!==ui.ledgerRequestId||ui.tab!==kind||JSON.stringify(ui.filter)+'/'+ui.ledgerStatus!==filterKey)return;
      if(page>1&&ui.ledgerData&&ui.ledgerData.ledger===kind)data.rows=[...ui.ledgerData.rows,...data.rows];
      ui.ledgerData=data;ui.summary=data.summary;updateBadges();
    }catch(err){if(request===ui.ledgerRequestId)ui.ledgerError=err.message;}
    finally{if(request===ui.ledgerRequestId){ui.ledgerLoading=false;draw();}}
  }
  function ledgerStatus(value){ui.ledgerStatus=value;fetchLedger(1);}
  function ledgerFilters(){
    const people=ui.data?.employees||[];
    const choices=ui.tab==='attendance'?[['all','All shift statuses'],['working','Working'],['on_break','On break'],['clocked_out','Clocked out']]:
      ui.tab==='leaves'?[['all','All leave decisions'],['pending','Pending'],['approved','Approved'],['rejected','Declined'],['cancelled','Cancelled']]:
      [['all','All timesheet statuses'],['draft','Draft'],['submitted','Submitted'],['approved','Approved'],['rejected','Rejected']];
    return `<div class="tf-ac-filters tf-ac-ledger-filters">
      <label class="tf-ac-search">⌕ <input type="search" placeholder="Search employees and records…" aria-label="Search employee records" value="${escHtml(ui.filter.q)}" oninput="TFAdminActivity.search(this.value)"></label>
      <select aria-label="Select employee" onchange="TFAdminActivity.applyFilter('employeeId',this.value)"><option value="">All employees</option>${people.map(p=>`<option value="${p.id}" ${String(ui.filter.employeeId)===String(p.id)?'selected':''}>${escHtml(p.name)}</option>`).join('')}</select>
      <select aria-label="Record status" onchange="TFAdminActivity.ledgerStatus(this.value)">${choices.map(([id,label])=>`<option value="${id}" ${ui.ledgerStatus===id?'selected':''}>${label}</option>`).join('')}</select>
      <label class="tf-ac-date">From <input type="date" value="${escHtml(ui.filter.from)}" onchange="TFAdminActivity.applyFilter('from',this.value)"></label>
      <label class="tf-ac-date">To <input type="date" value="${escHtml(ui.filter.to)}" onchange="TFAdminActivity.applyFilter('to',this.value)"></label>
      <button type="button" onclick="TFAdminActivity.clearFilters()">Reset</button>
    </div>`;
  }
  function ledgerContent(){
    const titles={attendance:'Employee attendance & break logs',leaves:'Employee leave history',timesheets:'Timesheet & work logs'};
    const d=ui.ledgerData,rows=d?.rows||[];
    const safe=x=>escHtml(x===undefined||x===null||x===''?'—':x);
    const pill=x=>`<span class="tf-ac-tag tf-ac-state">${safe(x)}</span>`;
    const person=r=>`<button type="button" class="tf-ac-person-link" onclick="TFAdminActivity.applyFilter('employeeId','${Number(r.employeeId)}')">${safe(r.employee)}</button>`;
    let headings=[],body=[];
    if(ui.tab==='attendance'){
      headings=['Employee','Date','Clock in','Clock out','Break time','Worked','Mode','Status'];
      body=rows.map(r=>`<tr><td>${person(r)}</td><td>${safe(statusTime(r.date))}</td><td>${safe(at(r.clockIn))}</td><td>${safe(at(r.clockOut))}</td><td>${safe(r.breakMinutes)} min${r.breakStartedAt?'<small>Live break</small>':''}</td><td>${hours(r.workedMinutes)}</td><td>${safe(r.mode)}</td><td>${pill(r.status)}${r.note?`<small>${safe(r.note)}</small>`:''}</td></tr>`);
    }else if(ui.tab==='leaves'){
      headings=['Employee','Leave type','Period','Days','Status','Submitted','Reviewed by','Reason / decision'];
      body=rows.map(r=>`<tr><td>${person(r)}</td><td>${safe(r.type)}</td><td>${safe(statusTime(r.startDate))} – ${safe(statusTime(r.endDate))}</td><td>${Number(r.days)}</td><td>${pill(r.status)}</td><td>${safe(at(r.submittedAt))}</td><td>${safe(r.reviewedBy)}<small>${safe(at(r.reviewedAt))}</small></td><td><div class="tf-ac-ledger-note">${safe(r.reason)}</div>${r.status==='pending'? `<div class="tf-ac-buttons"><button type="button" class="tf-ac-approve" onclick="TFAdminActivity.review('leave','${r.id}','approved')">✓ Approve</button><button type="button" class="tf-ac-decline" onclick="TFAdminActivity.review('leave','${r.id}','rejected')">Decline</button></div>`:''}${r.reviewNote?`<small>Decision: ${safe(r.reviewNote)}</small>`:''}</td></tr>`);
    }else{
      headings=['Employee','Work date','Client / project','Work details','Hours','Billing','Status','Reviewed by'];
      body=rows.map(r=>`<tr><td>${person(r)}</td><td>${safe(statusTime(r.date))}</td><td>${safe(r.client)}<small>${safe(r.project)}</small></td><td>${safe(r.task)}<small>${safe(r.description)}</small></td><td>${hours(r.minutes)}</td><td>${r.billable?'Billable':'Non-billable'}</td><td>${pill(r.status)}</td><td>${safe(r.reviewedBy)}<small>${safe(at(r.reviewedAt))}</small></td></tr>`);
    }
    return `<section class="tf-ac-ledger"><div class="tf-ac-pending-head"><h2>${titles[ui.tab]}</h2><p>Choose an employee, a status, or a date range. Records are paginated and limited to Super Admin.</p></div>
      ${ledgerFilters()}
      ${ui.ledgerError?`<div class="tf-ac-error" role="alert">${safe(ui.ledgerError)} <button type="button" onclick="TFAdminActivity.refresh()">Retry</button></div>`:''}
      ${!d&&ui.ledgerLoading?'<div class="tf-ac-loading">Loading employee records…</div>':
        `<div class="tf-ac-ledger-scroll"><table class="tf-ac-ledger-table"><thead><tr>${headings.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${body.join('')||`<tr><td colspan="8"><div class="tf-ac-empty"><strong>No matching records</strong><p>Try a different employee, date, or status.</p></div></td></tr>`}</tbody></table></div>
          <div class="tf-ac-ledger-foot"><span>${rows.length} records loaded${d?' · Page '+d.page:''}</span>${d?.hasMore?`<button type="button" onclick="TFAdminActivity.more()" ${ui.ledgerLoading?'disabled':''}>${ui.ledgerLoading?'Loading…':'Load more records'}</button>`:''}</div>`}
    </section>`;
  }
  function view(){const s=ui.summary||{};const total=(s.pendingLeaves||0)+(s.pendingTimesheets||0)+(s.pendingApprovals||0);return `<div class="tf-ac-page">
    <header class="tf-ac-head"><div><span class="tf-ac-overline">SUPER ADMIN / OPERATIONS INTELLIGENCE</span><h1>Employee activity & approvals</h1><p>Review employee requests, attendance, break time, work logs and recorded task activity in one place.</p></div><div class="tf-ac-head-actions"><button type="button" onclick="notificationCenter()">All notifications</button><button type="button" onclick="TFAdminActivity.markAll()">✓ Mark alerts read</button><button type="button" class="tf-ac-refresh" onclick="TFAdminActivity.refresh()">↻ Refresh</button></div></header>
    <div class="tf-ac-stats">${card('Needs approval',total,'Pending team requests','◎','pending')}${card('Currently on shift',s.onShift,(s.onBreak||0)+' on break now','◷','attendance')}${card('Actions today',s.todayActions,'Recorded employee actions','⌁','history')}${card('Unread alerts',s.unread,'New staff updates','♧','history')}</div>
    <div class="tf-ac-tabs"><button type="button" class="${ui.tab==='pending'?'active':''}" onclick="TFAdminActivity.switchTab('pending')">Approval queue <b>${total}</b></button><button type="button" class="${ui.tab==='history'?'active':''}" onclick="TFAdminActivity.switchTab('history')">All activity</button><button type="button" class="${ui.tab==='attendance'?'active':''}" onclick="TFAdminActivity.switchTab('attendance')">Attendance & breaks</button><button type="button" class="${ui.tab==='leaves'?'active':''}" onclick="TFAdminActivity.switchTab('leaves')">Leave history</button><button type="button" class="${ui.tab==='timesheets'?'active':''}" onclick="TFAdminActivity.switchTab('timesheets')">Timesheets</button><span>${ui.tab==='pending'?(ui.pendingLoading?'Loading requests…':ui.pendingData?'Requests updated':'Ready'):(ui.loading?'Updating…':ui.data?'Updated just now':'Ready')}</span></div>
    ${ui.error?`<div class="tf-ac-error" role="alert">${escHtml(ui.error)} <button onclick="TFAdminActivity.refresh()">Retry</button></div>`:''}
    ${ui.tab==='pending'?pending():ui.tab==='history'?history():ledgerContent()}
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
    try{const res=await fetch('/api/operations/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({action,id,status,note})});const data=await res.json();if(!res.ok)throw Error(data.error||'Could not submit decision');closeModal();ui.pendingData=null;await fetchPending();if(isLedger())await fetchLedger(1);await summary();
    }catch(err){ui.error=err.message;draw();alert(err.message);}
  }
  const previousRender=render;
  render=function(){previousRender();if(!isAdmin()||state.loading||state.error)return;updateBadges();if(state.tab==='admin_activity'){draw();if(ui.tab==='pending'&&!ui.pendingData&&!ui.pendingLoading&&!ui.pendingError)queueMicrotask(()=>fetchPending());else if(ui.tab==='history'&&!ui.data&&!ui.loading)queueMicrotask(()=>fetchEvents());}else if(state.tab==='overview')renderSummary();};
  window.render=render;
  window.TFAdminActivity={show,applyFilter,search,clearFilters,switchTab,ledgerStatus,refresh:()=>isLedger()?fetchLedger(1):ui.tab==='pending'?fetchPending():fetchEvents(),more:()=>isLedger()?fetchLedger((ui.ledgerData?.page||1)+1):fetchEvents(true),markAll,review};
  if(location.hash==='#admin_activity'){state.tab='admin_activity';if(!state.loading)render();}
  // In-app polling requires neither costly WebSockets nor a background worker.
  setInterval(()=>{if(document.visibilityState!=='visible'||!isAdmin())return;summary();if(state.tab==='admin_activity'&&ui.tab==='pending'&&!ui.pendingLoading)fetchPending();else if(state.tab==='admin_activity'&&ui.tab==='history'&&!ui.loading&&!ui.next)fetchEvents(false,true);},30000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&isAdmin())summary();});
  if(isAdmin())summary();
})();

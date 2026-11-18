/* Techfinitys OS — connected client and employee experiences.
   Vanilla JS, no runtime CDN/framework dependency. Django remains source of truth. */
(() => {
  const opApi = '/api/operations/';
  const opsUI = {attendancePerson:'', timeStatus:'all', ticketStatus:'all', leadStage:'all', approvalStatus:'all'};
  const manager = () => ['admin','manager'].includes(state.ctx?.role);
  const staff = () => state.ctx?.role !== 'client';
  const mine = arr => (arr || []).filter(x=>String(x.employeeId)===String(state.ctx?.id));
  const items = key => state[key] || [];
  const today = () => state.serverToday || new Date().toISOString().slice(0,10);
  const dateOnly = x => (x||'').slice(0,10);
  const num = x => new Intl.NumberFormat('en-IN').format(x||0);
  const hms = minutes => `${Math.floor((minutes||0)/60)}h ${Math.round((minutes||0)%60)}m`;
  const money = x => '₹'+new Intl.NumberFormat('en-IN',{maximumFractionDigits:0}).format(Number(x||0));
  const cls = v => ['approved','completed','resolved','won','active','clocked_out','paid'].includes(v)?'success':['rejected','urgent','blocked','lost'].includes(v)?'danger':['pending','review','submitted','waiting_client','on_break'].includes(v)?'warning':'neutral';
  const pill = v => `<span class="os-pill ${cls(v)}">${esc((v||'—').replaceAll('_',' '))}</span>`;
  const empty = (title,desc='Nothing here yet.') => `<div class="os-empty"><div class="os-empty-symbol">✦</div><strong>${esc(title)}</strong><p>${esc(desc)}</p></div>`;
  const sel = (values,value,placeholder='All') => `<option value="">${esc(placeholder)}</option>${values.map(x=>`<option value="${esc(x.value)}" ${String(x.value)===String(value)?'selected':''}>${esc(x.label)}</option>`).join('')}`;
  const people = () => state.members.filter(m=>['employee','manager','admin'].includes(m.role));
  const clientOptions = val => sel(state.clients.map(c=>({value:c.id,label:c.name})),val,'Select client');
  const projectOptions = val => sel(state.projects.map(p=>({value:p.id,label:`${p.clientName} · ${p.title}`})),val,'No project');
  const personOptions = val => sel(people().map(m=>({value:m.id,label:m.name})),val,'Select employee');
  const escAttr = esc;

  // Replace legacy JSON placeholders with structured operations views.
  Object.assign(labels, {
    attendance:'Attendance', leaves:'Leave & holidays', timesheets:'Time tracking',
    approvals:'Approvals',tickets:'Support tickets',milestones:'Milestones',leads:'Sales pipeline',
    timelogs:'Legacy time records',overview:'Command center',reports:'Insights & reports'
  });
  menus.client = ['overview','projects','milestones','tasks','updates','approvals','tickets','calendar','content','deliverables','files','invoices','notes','settings'];
  menus.employee = ['overview','tasks','projects','milestones','attendance','timesheets','leaves','approvals','clients','updates','calendar','tickets','files','notes','issues','collaboration','settings'];
  menus.manager = ['overview','leads','clients','team','assignments','projects','milestones','tasks','attendance','timesheets','leaves','approvals','tickets','updates','calendar','deliverables','content','campaigns','shoots','files','invoices','reports','audit','workflows','settings'];
  menus.admin = [...menus.manager];
  const coreShell = shell;
  shell = function(){
    coreShell();
    const role = state.ctx?.role;
    const roleNav = document.getElementById('nav');
    if (roleNav) {
      const category = k => ['overview','leads','clients','team','assignments'].includes(k)?'ORGANIZE':
         ['projects','milestones','tasks','updates','calendar','notes','content','deliverables','campaigns','shoots'].includes(k)?'DELIVER':
         ['attendance','timesheets','leaves'].includes(k)?'PEOPLE & TIME':
         ['approvals','tickets','files','invoices','collaboration','issues'].includes(k)?'CLIENT SERVICE':'CONTROL';
      const groups={}; for(const key of menus[role]||[]) (groups[category(key)]||=([])).push(key);
      roleNav.innerHTML=Object.entries(groups).map(([group,keys])=>`<div class="os-nav-group"><span>${group}</span>${keys.map(k=>`<button type="button" data-tab="${k}" class="${state.tab===k?'active':''}" title="${esc(labels[k]||k)}"><span class="nav-icon">${icon(k)}</span><span>${esc(labels[k]||k)}</span>${k==='approvals'&&items('approvalRequests').some(a=>a.status==='pending')?'<em>•</em>':''}</button>`).join('')}</div>`).join('');
      roleNav.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{go(b.dataset.tab);document.querySelector('.sidebar')?.classList.remove('mobile-open')}));
    }
    const dateEl=document.getElementById('todayTop'); if(dateEl) dateEl.textContent=new Date().toLocaleDateString('en-IN',{weekday:'short',day:'numeric',month:'short'});
    const bell=document.getElementById('bellBtn'); if(bell){const n=state.notifications.filter(n=>!n.read).length;bell.innerHTML=`♧${n?`<span class="notification-dot">${n}</span>`:''}`; bell.title=`Notifications (${n} unread)`}
  };

  const osHeading = (name,subtitle,actions='') => `<div class="os-heading"><div><span class="os-overline">TECHFINITYS / ${staff()?'OPERATIONS':'CLIENT PORTAL'}</span><h1>${esc(name)}</h1><p>${esc(subtitle)}</p></div><div class="os-heading-actions">${actions}</div></div>`;
  const numberCard = (name,value,detail,ico,nav,accent='violet') => `<button class="os-number-card ${accent}" onclick="go('${nav}')"><div class="os-number-header"><span>${esc(name)}</span><b>${ico}</b></div><strong>${esc(String(value))}</strong><small>${esc(detail)}</small><i class="number-deco"></i></button>`;
  const paneTitle = (title,extra='') => `<div class="os-pane-header"><div><span class="os-label">${esc(title)}</span></div>${extra}</div>`;
  const tableHead = arr => `<thead><tr>${arr.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead>`;
  const osTable = (heads,rows,cols) => `<div class="os-table-wrap"><table class="os-table">${tableHead(heads)}<tbody>${rows||`<tr><td colspan="${cols||heads.length}">No records found.</td></tr>`}</tbody></table></div>`;
  const action = (text,call,theme='') => `<button class="os-button ${theme}" onclick="${call}">${text}</button>`;
  const openAttendance = () => items('attendance').find(a=>String(a.employeeId)===String(state.ctx?.id) && !a.clockOut);
  const taskList = (rows,max=5)=>rows.slice(0,max).map(t=>`<button class="os-workrow" onclick="go('tasks')"><span class="os-work-icon">✓</span><span class="os-work-main"><strong>${esc(t.title)}</strong><small>${esc(t.clientName)} · ${esc(t.assignedName||'Unassigned')}</small></span>${pill(t.priority||t.status)}<time>${shortDate(t.dueAt)}</time></button>`).join('') || empty('All clear','No matching tasks right now.');
  const feed = (rows,max=5) => rows.slice(0,max).map(a=>`<div class="os-feedrow"><span class="avatar tiny">${initials(a.actorName)}</span><div><strong>${esc(a.action)}</strong><p>${esc(a.detail||a.clientName||'Workspace updated')}</p><small>${esc(a.actorName)} · ${shortDate(a.createdAt)}</small></div></div>`).join('')||empty('Activity starts here');
  const progress = (done,total) => `<div class="os-progress"><span style="width:${total?Math.round(done/total*100):0}%"></span></div>`;

  function commandCenter(){
    const role=state.ctx.role, isClient=role==='client';
    const personalTasks=isClient?state.tasks:role==='employee'?state.tasks.filter(t=>t.assignedTo===state.ctx.id):state.tasks;
    const outstanding=personalTasks.filter(t=>t.status!=='completed');
    const overdue=outstanding.filter(t=>t.dueAt && new Date(t.dueAt)<new Date());
    const pending=items('approvalRequests').filter(a=>a.status==='pending');
    const openTickets=items('supportTickets').filter(t=>!['resolved','closed'].includes(t.status));
    const active=state.projects.filter(p=>p.status==='active');
    const present=items('attendance').filter(a=>a.date===today()&&!a.clockOut).length;
    const displayName=(state.ctx.name||'there').split(' ')[0];
    let quick=isClient?`${action('Request support',"ticketModal()",'filled')}${action('Review approvals',"go('approvals')")}`:
      `${action('＋ New task',"taskModal()",'filled')}${action('＋ Log time',"timeModal()")}`;
    const metrics = isClient ? [
      ['Active projects',active.length,'In progress','◈','projects','violet'],
      ['Pending approvals',pending.length,'Need your decision','◎','approvals','amber'],
      ['Visible tasks',personalTasks.length,`${outstanding.length} in progress`,'☑','tasks','sky'],
      ['Open tickets',openTickets.length,'Support requests','✉','tickets','mint']
    ] : [
      ['Open work',outstanding.length,`${overdue.length} overdue`,'☑','tasks','violet'],
      ['Active projects',active.length,`${state.clients.length} client accounts`,'◈','projects','sky'],
      ['Pending sign-offs',pending.length,'Awaiting decisions','◎','approvals','amber'],
      manager()?['Team online',present,'Clocked in today','◉','attendance','mint']:['My timesheet',hms(mine(items('timeEntries')).filter(t=>t.date===today()).reduce((s,t)=>s+t.minutes,0)),'Logged today','◷','timesheets','mint']
    ];
    const greet=new Date().getHours()<12?'Good morning':new Date().getHours()<17?'Good afternoon':'Good evening';
    const list=outstanding.slice().sort((a,b)=>(a.dueAt||'9999').localeCompare(b.dueAt||'9999'));
    const newest=state.updates.slice(0,4);
    return `${osHeading('Command center',isClient?'Everything happening with your projects, in one clear view.':'A live operational picture of people, projects and client delivery.')}
      <section class="os-welcome"><div class="os-welcome-content"><div class="os-welcome-kicker"><span>✦</span> YOUR WORKSPACE, SIMPLIFIED</div><h2>${greet}, ${esc(displayName)} <span class="wave">✳</span></h2><p>${isClient?'See what is moving, review deliverables and reach your team without chasing updates.':`You have ${outstanding.length} open tasks, ${pending.length} approvals and ${openTickets.length} active support requests.`}</p><div class="os-welcome-actions">${quick}</div></div><div class="os-welcome-art" aria-hidden="true"><span class="art-orbit orbit-a"></span><span class="art-orbit orbit-b"></span><span class="art-core">TF</span><span class="art-float one">✓</span><span class="art-float two">✦</span></div></section>
      <div class="os-numbers">${metrics.map(m=>numberCard(...m)).join('')}</div>
      <div class="os-columns"><section class="os-pane">${paneTitle(isClient?'Your next steps':'Priority work',`<button class="os-text-btn" onclick="go('tasks')">View all →</button>`)}<div>${taskList(list,6)}</div></section>
      <section class="os-pane">${paneTitle(isClient?'Latest project updates':'Team activity',`<button class="os-text-btn" onclick="go('${isClient?'updates':'audit'}')">See all →</button>`)}${isClient?newest.map(u=>`<div class="os-feedrow"><span class="avatar tiny">${initials(u.authorName)}</span><div><strong>${esc(u.title)}</strong><p>${esc(u.body.slice(0,160))}</p><small>${esc(u.authorName)} · ${shortDate(u.createdAt)}</small></div></div>`).join('')||empty('No updates yet'):feed(state.activities)}</section></div>
      <section class="os-pane os-portfolio">${paneTitle(isClient?'Project health':'Delivery portfolio',`<button class="os-text-btn" onclick="go('projects')">Explore projects →</button>`)}<div class="os-portfolio-grid">${state.projects.slice(0,4).map(p=>`<button class="os-portfolio-item" onclick="go('projects')"><span class="os-project-symbol">◈</span><strong>${esc(p.title)}</strong><small>${esc(p.clientName)}</small>${progress(p.progress,100)}<div><b>${p.progress}%</b>${pill(p.status)}</div></button>`).join('')||empty('No projects assigned')}</div></section>`;
  }

  async function opsPost(data){
    const r=await fetch(opApi,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:JSON.stringify(data)});
    const d=await r.json().catch(()=>({error:`Server error (${r.status})`}));
    if(!r.ok)throw Error(d.error||'Unable to save changes');
    state.notice='Changes saved';await load();closeModal();return d;
  }
  async function execute(action,payload={}){try{await opsPost({action,...payload})}catch(e){showError(e.message)}}
  function showError(message){const h=document.getElementById('toastHost');if(h){h.innerHTML=`<div class="os-toast"><strong>Could not complete action</strong><span>${esc(message)}</span><button onclick="document.getElementById('toastHost').innerHTML=''">×</button></div>`}else alert(message)}
  function modal(title,subtitle,body,footer=''){openModal(`<div class="os-modal-label">TECHFINITYS / WORKFLOW</div><h2 class="os-modal-title">${esc(title)}</h2><p class="os-modal-subtitle">${esc(subtitle)}</p>${body}${footer}`)}
  const getForm=el=>Object.fromEntries(new FormData(el));
  function onForm(callback){const f=document.querySelector('#osForm'); f.onsubmit=async e=>{e.preventDefault();const payload=getForm(f); const checkboxes=f.querySelectorAll('input[type=checkbox]'); checkboxes.forEach(c=>payload[c.name]=c.checked); try{await callback(payload)}catch(ex){showError(ex.message)}}}
  const formButtons=(title='Save')=>`<div class="os-form-actions"><button type="button" onclick="closeModal()">Cancel</button><button class="primary" type="submit">${esc(title)}</button></div>`;
  // Keep foreign-key dropdowns restricted to the selected account, not an
  // arbitrary project/employee from another client (server validates too).
  function bindScopedForm(form){
    const clientField=form?.querySelector('[name="clientId"]');
    if(!clientField)return;
    const projectField=form.querySelector('[name="projectId"]');
    const taskField=form.querySelector('[name="taskId"]');
    const blockerField=form.querySelector('[name="blockedBy"]');
    const assigneeField=form.querySelector('[name="assignedTo"]')||form.querySelector('[name="reviewerId"]');
    function sync(){
      const cid=clientField.value;
      const set=(field,options,placeholder)=>{
        if(!field)return;
        const value=field.value;
        field.innerHTML='<option value="">'+esc(placeholder)+'</option>'+options.map(x=>`<option value="${esc(x.value)}">${esc(x.label)}</option>`).join('');
        if(options.some(x=>String(x.value)===String(value)))field.value=value;
      };
      set(projectField,state.projects.filter(p=>p.clientId===cid).map(p=>({value:p.id,label:p.title})),'No project');
      set(taskField,state.tasks.filter(t=>t.clientId===cid&&t.id!==form.dataset.editingTask).map(t=>({value:t.id,label:t.title})),'No task');
      set(blockerField,state.tasks.filter(t=>t.clientId===cid&&t.id!==form.dataset.editingTask).map(t=>({value:t.id,label:t.title})),'No dependency');
      const teamIds=new Set(state.assignments.filter(a=>a.clientId===cid&&a.active).map(a=>String(a.employeeId)));
      set(assigneeField,people().filter(p=>p.role!=='employee'||teamIds.has(String(p.id))).map(p=>({value:p.id,label:p.name})),'Select employee');
    }
    clientField.addEventListener('change',sync);
    sync();
  }


  function attendancePage(){
    const current=openAttendance();const recent=items('attendance');const rows=manager()?(opsUI.attendancePerson?recent.filter(a=>String(a.employeeId)===String(opsUI.attendancePerson)):recent):mine(recent);
    const mineToday=mine(recent).find(a=>a.date===today());const todayHours=mineToday?.workedMinutes||0;
    const actions=staff()?`<a class="os-button" href="/api/export/attendance/">↓ Export CSV</a>`:'';
    const filter=manager()?`<select class="os-select" onchange="opsUI.attendancePerson=this.value;render()">${sel(people().map(m=>({value:m.id,label:m.name})),opsUI.attendancePerson,'All employees')}</select>`:'';
    return `${osHeading('Attendance & shifts','Clock in, track breaks, review worked hours and maintain an accurate attendance record.',actions)}
      <div class="os-attendance-hero"><div><span class="os-label">LIVE ATTENDANCE</span><h2>${current?current.status==='on_break'?'You’re on a break':'Your shift is running':'Ready for your workday?'}</h2><p>${current?`Clocked in at ${fmtDate(current.clockIn)} · ${esc(current.mode)} mode`:'Choose your work mode and start your attendance timer.'}</p></div><div class="os-attendance-controls">${current?`${action(current.status==='on_break'?'Resume work':'Start break',`execute('${current.status==='on_break'?'end_break':'start_break'}')`)}${action('Clock out',"execute('clock_out')",'filled')}`:`<select id="workMode" class="os-select"><option value="office">In office</option><option value="remote">Working remotely</option><option value="field">Field work</option></select><button class="os-button filled" onclick="execute('clock_in',{mode:document.getElementById('workMode').value})">● Clock in</button>`}</div></div>
      <div class="os-three">${numberCard('Today’s worked time',hms(todayHours),'Breaks excluded','◷','attendance','violet')}${numberCard('Recorded days',mine(recent).length,'Last 45 days','▦','attendance','sky')}${numberCard('Currently on shift',manager()?recent.filter(a=>!a.clockOut).length:current?1:0,manager()?'Across the team':'Your attendance status','◉','attendance','mint')}</div>
      <section class="os-pane">${paneTitle('Attendance register',filter)}${osTable(['Team member','Date','Clock in','Clock out','Worked','Work mode','Status'],rows.map(a=>`<tr><td><strong>${esc(a.employeeName)}</strong></td><td>${shortDate(a.date)}</td><td>${fmtDate(a.clockIn)}</td><td>${a.clockOut?fmtDate(a.clockOut):'—'}</td><td><strong>${hms(a.workedMinutes)}</strong></td><td>${pill(a.mode)}</td><td>${pill(a.status)}</td></tr>`).join(''))}</section>`;
  }
  function leavePage(){
    const rows=items('leaves');const pending=rows.filter(a=>a.status==='pending');const userRows=mine(rows);
    return `${osHeading('Leave & holidays','Request time off, track decisions, and help the team plan around availability.',`${action('＋ Request leave',"leaveModal()",'filled')}<a class="os-button" href="/api/export/leaves/">↓ Export</a>`)}
      <div class="os-three">${numberCard('My requests',userRows.length,'All request types','▦','leaves','violet')}${numberCard('Waiting for review',manager()?pending.length:userRows.filter(x=>x.status==='pending').length,'Pending decisions','◷','leaves','amber')}${numberCard('Approved',userRows.filter(x=>x.status==='approved').length,'Your confirmed requests','✓','leaves','mint')}</div>
      <section class="os-pane">${paneTitle(manager()?'Team leave requests':'My leave requests')}${osTable(['Employee','Leave type','Dates','Days','Status','Reason / note','Action'],rows.map(r=>`<tr><td><strong>${esc(r.employeeName)}</strong></td><td>${esc(r.type)}</td><td>${shortDate(r.startDate)} – ${shortDate(r.endDate)}</td><td>${r.days}</td><td>${pill(r.status)}</td><td class="os-clamp">${esc(r.reason||r.reviewNote||'—')}</td><td><div class="os-row-actions">${manager()&&r.status==='pending'&&r.employeeId!==state.ctx.id?`${action('Approve',`execute('review_leave',{id:'${r.id}',status:'approved'})`,'mini accent')}${action('Reject',`decideLeave('${r.id}')`,'mini')}`:r.employeeId===state.ctx.id&&r.status==='pending'?action('Cancel',`execute('cancel_leave',{id:'${r.id}'})`,'mini'):'—'}</div></td></tr>`).join(''))}</section>`;
  }
  function leaveModal(){modal('Request time off','Your manager will receive a review notification.',`<form id="osForm"><div class="os-form-grid"><label>Type<select name="type"><option value="annual">Annual leave</option><option value="casual">Casual leave</option><option value="sick">Sick leave</option><option value="unpaid">Unpaid leave</option><option value="other">Other</option></select></label><label>Start date<input name="startDate" type="date" required min="${today()}"></label><label>End date<input name="endDate" type="date" required min="${today()}"></label></div><label>Reason<textarea name="reason" placeholder="Optional context for your manager" rows="3"></textarea></label>${formButtons('Submit leave request')}</form>`);onForm(p=>opsPost({action:'request_leave',...p}))}
  function decideLeave(id){modal('Reject leave','Add a reason the employee can act on.',`<form id="osForm"><label>Decision note<textarea name="note" required rows="3"></textarea></label>${formButtons('Reject request')}</form>`);onForm(p=>opsPost({action:'review_leave',id,status:'rejected',...p}))}

  function timesheetsPage(){
    const times=items('timeEntries').filter(t=>opsUI.timeStatus==='all'||t.status===opsUI.timeStatus);
    const minutes=times.reduce((s,t)=>s+t.minutes,0);const billable=times.filter(t=>t.billable).reduce((s,t)=>s+t.minutes,0);
    return `${osHeading('Time tracking','Real work logs against client projects and tasks, ready for manager review.',`${action('＋ Log time',"timeModal()",'filled')}<a href="/api/export/timesheets/" class="os-button">↓ Export</a>`)}
    <div class="os-three">${numberCard('Time recorded',hms(minutes),'From visible logs','◷','timesheets','violet')}${numberCard('Billable time',hms(billable),'Chargeable delivery','◈','timesheets','mint')}${numberCard('Awaiting review',times.filter(t=>t.status==='submitted').length,'Submitted entries','◎','timesheets','amber')}</div>
    <section class="os-pane">${paneTitle('Timesheet entries',`<select class="os-select" onchange="opsUI.timeStatus=this.value;render()">${['all','draft','submitted','approved','rejected'].map(s=>`<option ${opsUI.timeStatus===s?'selected':''} value="${s}">${s==='all'?'All statuses':s[0].toUpperCase()+s.slice(1)}</option>`).join('')}</select>`)}
    ${osTable(['Date','Team member','Client / project','Description','Hours','Billing','Status','Action'],times.map(t=>`<tr><td>${shortDate(t.date)}</td><td>${esc(t.employeeName)}</td><td><strong>${esc(t.clientName)}</strong><small>${esc(t.projectName||t.taskName||'General work')}</small></td><td class="os-clamp">${esc(t.description||'—')}</td><td><strong>${hms(t.minutes)}</strong></td><td>${t.billable?'Billable':'Non-billable'}</td><td>${pill(t.status)}</td><td><div class="os-row-actions">${t.employeeId===state.ctx.id&&['draft','rejected'].includes(t.status)?action('Submit',`execute('time_status',{id:'${t.id}',status:'submitted'})`,'mini accent'):manager()&&t.status==='submitted'&&t.employeeId!==state.ctx.id?`${action('Approve',`execute('time_status',{id:'${t.id}',status:'approved'})`,'mini accent')}${action('Reject',`execute('time_status',{id:'${t.id}',status:'rejected'})`,'mini')}`:'—'}</div></td></tr>`).join(''))}</section>`;
  }
  function timeModal(){modal('Log work hours','Track actual hours spent on a client project, task, or delivery.',`<form id="osForm"><div class="os-form-grid"><label>Client<select name="clientId" required>${clientOptions('')}</select></label><label>Project<select name="projectId">${projectOptions('')}</select></label><label>Related task<select name="taskId">${sel(state.tasks.map(t=>({value:t.id,label:t.title})),'','General work')}</select></label><label>Date<input name="date" type="date" value="${today()}" required></label><label>Hours<input name="hours" type="number" step="0.25" min="0.25" max="24" value="1" required></label></div><label>Work description<textarea name="description" rows="3" placeholder="What did you work on?"></textarea></label><label class="os-inline-check"><input name="billable" type="checkbox" checked> Billable time</label>${formButtons('Save time entry')}</form>`);onForm(p=>{const hours=Number(p.hours);if(!Number.isFinite(hours)||hours<=0)return Promise.reject(Error('Enter valid hours'));const minutes=Math.round(hours*60);delete p.hours;return opsPost({action:'add_time',...p,minutes})});bindScopedForm(document.getElementById('osForm'))}

  function approvalsPage(){
    const all=items('approvalRequests');const rows=all.filter(a=>opsUI.approvalStatus==='all'||a.status===opsUI.approvalStatus);
    return `${osHeading('Approvals','A dedicated sign-off lane for deliverables, milestones and client decisions.',staff()?action('＋ Request approval',"approvalModal()",'filled'):'')}
    <div class="os-three">${numberCard('Pending approval',all.filter(a=>a.status==='pending').length,'Needs a decision','◎','approvals','amber')}${numberCard('Approved',all.filter(a=>a.status==='approved').length,'Signed-off work','✓','approvals','mint')}${numberCard('Revisions',all.filter(a=>['changes','rejected'].includes(a.status)).length,'Needs attention','↻','approvals','sky')}</div>
    <section class="os-pane">${paneTitle('Review queue',`<select class="os-select" onchange="opsUI.approvalStatus=this.value;render()">${['all','pending','approved','changes','rejected'].map(s=>`<option value="${s}" ${opsUI.approvalStatus===s?'selected':''}>${s==='all'?'All decisions':s.replaceAll('_',' ')}</option>`).join('')}</select>`)}
    <div class="os-approval-grid">${rows.map(a=>`<article class="os-approval-card"><div class="os-card-top"><span class="os-overline">${esc(a.clientName)} · ${a.audience==='client'?'CLIENT SIGN-OFF':'INTERNAL'}</span>${pill(a.status)}</div><h3>${esc(a.title)}</h3><p>${esc(a.description||'No additional description')}</p><div class="os-card-meta"><span>Requested by <b>${esc(a.requestedBy)}</b></span><span>${a.dueAt?'Due '+shortDate(a.dueAt):shortDate(a.createdAt)}</span></div>${a.decisionNote?`<div class="os-note">${esc(a.decisionNote)}</div>`:''}${a.status==='pending'&&((state.ctx.role==='client'&&a.audience==='client')||(staff()&&a.audience==='internal'&&(manager()||String(a.reviewerId)===String(state.ctx.id))))?`<div class="os-card-actions">${action('Approve',`decideApproval('${a.id}','approved')`,'filled')}${action('Request changes',`decideApproval('${a.id}','changes')`)}${action('Reject',`decideApproval('${a.id}','rejected')`,'danger')}</div>`:''}</article>`).join('')||empty('No approval requests','Share a deliverable for review to start the process.')}</div></section>`;
  }
  function approvalModal(){modal('Request approval','Submit a client deliverable or internal work for an auditable decision.',`<form id="osForm"><label>Title<input name="title" required maxlength="220" placeholder="e.g. November creative campaign"></label><div class="os-form-grid"><label>Client<select name="clientId" required>${clientOptions('')}</select></label><label>Approval type<select name="audience" id="audienceInput" onchange="document.getElementById('reviewerBlock').hidden=this.value==='client'"><option value="client">Client sign-off</option><option value="internal">Internal approval</option></select></label><label id="reviewerBlock" hidden>Reviewer<select name="reviewerId">${personOptions('')}</select></label><label>Project<select name="projectId">${projectOptions('')}</select></label><label>Due date<input name="dueAt" type="datetime-local"></label></div><label>Brief / what needs sign-off<textarea name="description" rows="4" placeholder="Explain exactly what must be reviewed"></textarea></label>${formButtons('Send for review')}</form>`);onForm(p=>{if(p.dueAt)p.dueAt=new Date(p.dueAt).toISOString();return opsPost({action:'create_approval',...p})});bindScopedForm(document.getElementById('osForm'))}
  function decideApproval(id,status){if(status==='approved'){execute('decide_approval',{id,status});return}modal(status==='changes'?'Request changes':'Reject approval','Add clear, actionable feedback for the team.',`<form id="osForm"><label>Feedback<textarea name="note" rows="4" required placeholder="What needs to change?"></textarea></label>${formButtons('Submit decision')}</form>`);onForm(p=>opsPost({action:'decide_approval',id,status,...p}))}

  function supportPage(){
    const all=items('supportTickets'),rows=all.filter(t=>opsUI.ticketStatus==='all'||t.status===opsUI.ticketStatus);
    return `${osHeading('Support desk',state.ctx.role==='client'?'A direct line to your delivery team, with every request in one place.':'Manage incoming client requests with status, priority and threaded replies.',`${action('＋ New ticket',"ticketModal()",'filled')}<a href="/api/export/tickets/" class="os-button">↓ Export</a>`)}
    <div class="os-three">${numberCard('Open',all.filter(t=>t.status==='open').length,'New requests','✉','tickets','sky')}${numberCard('Being handled',all.filter(t=>t.status==='in_progress').length,'Team in progress','◷','tickets','violet')}${numberCard('Resolved',all.filter(t=>['resolved','closed'].includes(t.status)).length,'Completed requests','✓','tickets','mint')}</div>
    <section class="os-pane">${paneTitle('Support inbox',`<select class="os-select" onchange="opsUI.ticketStatus=this.value;render()">${['all','open','in_progress','waiting_client','resolved','closed'].map(s=>`<option value="${s}" ${opsUI.ticketStatus===s?'selected':''}>${s==='all'?'All tickets':s.replaceAll('_',' ')}</option>`).join('')}</select>`)}
    ${osTable(['Ticket','Client','Priority','Status','Last updated','Action'],rows.map(t=>`<tr><td><strong>${esc(t.title)}</strong><small>${esc(t.createdBy)}</small></td><td>${esc(t.clientName)}</td><td>${pill(t.priority)}</td><td>${pill(t.status)}</td><td>${shortDate(t.updatedAt)}</td><td>${action('Open conversation',`ticketThread('${t.id}')`,'mini accent')}</td></tr>`).join(''))}</section>`;
  }
  function ticketModal(){modal('Create support ticket','Send a structured request to the right client workspace.',`<form id="osForm"><label>Client<select name="clientId" required>${clientOptions(state.ctx.role==='client'?state.clients[0]?.id:'')}</select></label><label>Subject<input name="title" maxlength="220" required placeholder="What do you need help with?"></label><label>Description<textarea name="description" rows="4" required placeholder="Provide the brief, impact and any relevant details"></textarea></label><label>Priority<select name="priority"><option value="normal">Normal</option><option value="low">Low</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>${formButtons('Create ticket')}</form>`);onForm(p=>opsPost({action:'create_ticket',...p}))}
  function ticketThread(id){const t=items('supportTickets').find(t=>t.id===id);if(!t)return;const messages=t.messages.map(m=>`<div class="os-message ${m.internal?'internal':''}"><div><strong>${esc(m.author)}</strong>${m.internal?pill('internal'):''}<small>${fmtDate(m.createdAt)}</small></div><p>${esc(m.body)}</p></div>`).join('')||empty('No replies yet','Start the conversation below.');
    modal(t.title,`${t.clientName} · ${t.priority} priority · ${t.status}`,`<div class="os-thread">${messages}</div><form id="osForm"><label>Reply<textarea name="body" rows="3" required placeholder="Write an update..."></textarea></label>${staff()?'<label class="os-inline-check"><input name="internal" type="checkbox"> Internal note (hidden from client)</label>':''}${formButtons('Send reply')}</form>${staff()?`<div class="os-ticket-status"><span>Change status</span><select id="newTicketStatus" class="os-select">${['open','in_progress','waiting_client','resolved','closed'].map(s=>`<option value="${s}" ${t.status===s?'selected':''}>${s.replaceAll('_',' ')}</option>`).join('')}</select>${action('Update',`execute('ticket_status',{id:'${id}',status:document.getElementById('newTicketStatus').value})`,'mini')}</div>`:''}`);
    onForm(p=>opsPost({action:'ticket_message',id,...p}));
  }

  function milestonesPage(){
    const ms=items('milestones');return `${osHeading('Project milestones','Track important checkpoints and dependencies as projects move from brief to delivery.',staff()?action('＋ New milestone',"milestoneModal()",'filled'):'')}
    <section class="os-pane">${paneTitle('Delivery roadmap')}<div class="os-milestone-grid">${state.projects.map(p=>{const steps=ms.filter(m=>m.projectId===p.id);return `<article class="os-roadmap"><div class="os-card-top"><span class="os-overline">${esc(p.clientName)}</span>${pill(p.status)}</div><h3>${esc(p.title)}</h3>${progress(p.progress,100)}<div class="os-roadmap-steps">${steps.map(m=>`<div class="os-roadmap-step"><span class="os-step-dot ${m.status}"></span><div><strong>${esc(m.title)}</strong><small>${shortDate(m.dueDate)} · ${esc(m.ownerName||'Team')}</small></div>${staff()?`<select onchange="execute('milestone_status',{id:'${m.id}',status:this.value})">${['planned','active','completed'].map(s=>`<option value="${s}" ${m.status===s?'selected':''}>${s}</option>`).join('')}</select>`:pill(m.status)}</div>`).join('')||'<p class="os-faint">No milestones created for this project.</p>'}</div></article>`}).join('')||empty('No projects yet')}</div></section>`;
  }
  function milestoneModal(){modal('Create project milestone','Define a concrete delivery checkpoint.',`<form id="osForm"><label>Project<select name="projectId" required>${projectOptions('')}</select></label><label>Milestone title<input name="title" required></label><div class="os-form-grid"><label>Due date<input name="dueDate" type="date"></label><label>Owner<select name="ownerId">${personOptions('')}</select></label></div><label>Description<textarea name="description" rows="3"></textarea></label><label class="os-inline-check"><input type="checkbox" name="clientVisible" checked> Visible to client</label>${formButtons('Add milestone')}</form>`);onForm(p=>opsPost({action:'save_milestone',...p}))}

  function salesPage(){const ls=items('salesLeads').filter(x=>opsUI.leadStage==='all'||x.stage===opsUI.leadStage),groups=['new','contacted','qualified','proposal','negotiation','won','lost'];const total=items('salesLeads').filter(l=>!['lost','won'].includes(l.stage)).reduce((s,l)=>s+Number(l.value||0),0);
    return `${osHeading('Sales pipeline','Move prospects from first conversation to an onboarded client workspace.',`${action('＋ Add lead',"leadModal()",'filled')}<a href="/api/export/leads/" class="os-button">↓ Export</a>`)}
    <div class="os-three">${numberCard('Active opportunities',items('salesLeads').filter(l=>!['won','lost'].includes(l.stage)).length,'Across the pipeline','◈','leads','violet')}${numberCard('Pipeline value',money(total),'Estimated, not invoiced','₹','leads','sky')}${numberCard('Won deals',items('salesLeads').filter(l=>l.stage==='won').length,'Closed successfully','✓','leads','mint')}</div>
    <div class="os-pipeline">${groups.map(g=>`<section class="os-pipeline-lane"><div class="os-pipeline-header"><strong>${g.toUpperCase()}</strong><span>${ls.filter(l=>l.stage===g).length}</span></div>${ls.filter(l=>l.stage===g).map(l=>`<article class="os-lead"><span class="os-overline">${esc(l.source||'LEAD')}</span><h3>${esc(l.company||l.name)}</h3><p>${esc(l.name)}</p><strong class="os-lead-value">${money(l.value)}</strong><small>${esc(l.ownerName||'Unassigned')}</small><select aria-label="Move lead to stage" onchange="execute('lead_stage',{id:'${l.id}',stage:this.value})">${groups.map(x=>`<option value="${x}" ${x===l.stage?'selected':''}>${x}</option>`).join('')}</select>${!l.convertedClientId&&l.stage!=='lost'?action('Convert to client',`execute('convert_lead',{id:'${l.id}'})`,'mini accent'):l.convertedClientId?pill('converted'):''}</article>`).join('')}</section>`).join('')}</div>`;
  }
  function leadModal(){modal('New sales opportunity','Capture the contact, expected value and responsible owner.',`<form id="osForm"><div class="os-form-grid"><label>Contact name<input name="name" required></label><label>Company<input name="company"></label><label>Email<input type="email" name="email"></label><label>Phone<input name="phone"></label><label>Source<input name="source" placeholder="Referral, website, Instagram..."></label><label>Estimated value (INR)<input type="number" name="value" step="0.01" min="0" value="0"></label><label>Owner<select name="ownerId">${personOptions(state.ctx.id)}</select></label></div><label>Notes<textarea name="notes" rows="3"></textarea></label>${formButtons('Add opportunity')}</form>`);onForm(p=>opsPost({action:'save_lead',...p}))}

  function reportsPage(){
    const work=state.tasks.filter(t=>t.status!=='completed'),done=state.tasks.filter(t=>t.status==='completed');
    const grouped=state.clients.map(c=>{const tasks=state.tasks.filter(t=>t.clientId===c.id),logs=items('timeEntries').filter(t=>t.clientId===c.id);return {name:c.name,active:tasks.filter(t=>t.status!=='completed').length,done:tasks.filter(t=>t.status==='completed').length,logs:logs.reduce((s,l)=>s+l.minutes,0),progress:tasks.length?Math.round(tasks.filter(t=>t.status==='completed').length/tasks.length*100):0}});
    const overdue=work.filter(t=>t.dueAt&&new Date(t.dueAt)<new Date());
    return `${osHeading('Insights & reports','Operational performance by client, delivery, time, attendance and service health.',`<a class="os-button" href="/api/export/timesheets/">↓ Time CSV</a><a class="os-button" href="/api/export/attendance/">↓ Attendance CSV</a>`)}
    <div class="os-three">${numberCard('Delivery completion',state.tasks.length?Math.round(done.length/state.tasks.length*100)+'%':'—','All visible tasks','✓','tasks','mint')}${numberCard('Overdue tasks',overdue.length,'Requires follow-up','◷','tasks','amber')}${numberCard('Tracked hours',hms(items('timeEntries').reduce((s,t)=>s+t.minutes,0)),'Visible time entries','◈','timesheets','violet')}</div>
    <section class="os-pane">${paneTitle('Client delivery performance')}${osTable(['Client','Open tasks','Completed','Completion','Logged hours'],grouped.map(c=>`<tr><td><strong>${esc(c.name)}</strong></td><td>${c.active}</td><td>${c.done}</td><td><div class="os-report-bar"><span>${progress(c.progress,100)}</span>${c.progress}%</div></td><td>${hms(c.logs)}</td></tr>`).join(''))}</section>
    <div class="os-columns"><section class="os-pane">${paneTitle('Project status mix')}${['planned','active','on_hold','completed'].map(s=>`<div class="os-report-metric"><span>${s.replaceAll('_',' ')}</span>${progress(state.projects.filter(p=>p.status===s).length,state.projects.length)}<b>${state.projects.filter(p=>p.status===s).length}</b></div>`).join('')}</section><section class="os-pane">${paneTitle('Requests & approvals')}<div class="os-report-stack">${[['Pending approvals',items('approvalRequests').filter(a=>a.status==='pending').length],['Open service tickets',items('supportTickets').filter(t=>!['resolved','closed'].includes(t.status)).length],['Pending leave',items('leaves').filter(t=>t.status==='pending').length],['Submitted time entries',items('timeEntries').filter(t=>t.status==='submitted').length]].map(([k,v])=>`<div><span>${k}</span><strong>${v}</strong></div>`).join('')}</div></section></div><p class="os-disclaimer">Reports reflect accessible records. CSV exports support complete authorized histories; the dashboard feed is intentionally bounded for speed.</p>`;
  }
  const baseTasks=tasks;
  tasks=function(){const views=items('savedViews').filter(v=>v.module==='tasks');const strip=`<div class="os-savedbar"><strong>My saved views</strong>${views.map(v=>`<button onclick="applySavedView(${v.id})">${esc(v.name)}</button>`).join('')}${action('Save current filters',"saveCurrentView()",'mini accent')}</div>`;return baseTasks().replace('<div class="task-toolbar">',strip+'<div class="task-toolbar">')};
  function saveCurrentView(){modal('Save a task view','Keep your favourite filters one click away.',`<form id="osForm"><label>View name<input name="name" required maxlength="80" placeholder="e.g. My overdue tasks"></label>${formButtons('Save view')}</form>`);onForm(p=>opsPost({action:'save_view',...p,filters:{...taskUI}}))}
  function applySavedView(id){const v=items('savedViews').find(v=>v.id===id);if(!v)return;Object.assign(taskUI,{search:'',client:'',owner:'',status:'open',priority:'',timespan:'all',view:'list'},v.filters);render()}
  const oldTaskModal=taskModal;
  taskModal=function(id=''){oldTaskModal(id);const form=document.querySelector('#f');if(!form)return;form.dataset.editingTask=id;const t=state.tasks.find(x=>x.id===id)||{};const others=state.tasks.filter(x=>x.id!==id&&(!t.clientId||x.clientId===t.clientId));const button=form.querySelector('button.primary');if(button)button.insertAdjacentHTML('beforebegin',`<div class="os-form-grid"><label>Blocked by task<select name="blockedBy">${sel(others.map(x=>({value:x.id,label:x.title})),t.blockedBy||'','No dependency')}</select></label><label>Tags (comma separated)<input name="tags" value="${escAttr((t.tags||[]).join(', '))}" placeholder="design, urgent, social"></label></div>`);bindScopedForm(form)};
  const oldUpdateModal=updateModal;
  updateModal=function(){oldUpdateModal();bindScopedForm(document.getElementById('f'))};
  const oldClientModal=clientModal;
  clientModal=function(){oldClientModal();const p=document.querySelector('[name="portalPassword"]');if(p){p.minLength=12;p.placeholder='12+ character password'} };

  function settingsEnhanced(){return `${osHeading('Workspace settings','Account security, permissions and connected operations.')}
    <div class="os-columns"><section class="os-pane">${paneTitle('Security and access')}<h3>Change your password</h3><p>Use a unique password with at least 12 characters.</p><form id="osPasswordForm" class="os-settings-form"><label>Current password<input type="password" name="oldPassword" required></label><label>New password<input type="password" name="newPassword" minlength="12" required></label><button class="primary" type="submit">Update password</button></form></section><section class="os-pane">${paneTitle('Permission model')}<div class="os-settings-block"><span>1</span><div><strong>Identity and role</strong><p>Admin, manager, employee and client accounts each have their own workspace.</p></div></div><div class="os-settings-block"><span>2</span><div><strong>Client assignments</strong><p>Employees may only work inside explicitly assigned client workspaces.</p></div></div><div class="os-settings-block"><span>3</span><div><strong>Approval separation</strong><p>Clients sign off on client deliverables; managers approve HR and time entries.</p></div></div></section></div>`}
  const coreRender=render;
  render=function(){
    if(state.loading||state.error||!state.ctx){coreRender();return}
    const routes={overview:commandCenter,attendance:attendancePage,leaves:leavePage,timesheets:timesheetsPage,
      approvals:approvalsPage,tickets:supportPage,milestones:milestonesPage,leads:salesPage,reports:reportsPage,settings:settingsEnhanced};
    if(!routes[state.tab]){coreRender();return}
    shell();const note=state.notice?`<div class="notice">${esc(state.notice)}<button onclick="state.notice='';render()">×</button></div>`:'';
    document.getElementById('mainContent').innerHTML=note+routes[state.tab]();
    if(state.tab==='settings'){
      const f=document.getElementById('osPasswordForm');if(f)f.onsubmit=async e=>{e.preventDefault();try{await opsPost({action:'change_password',...getForm(f)});f.reset()}catch(err){showError(err.message)}}
    }
  };

  function notificationCenter(){modal('Notifications',`${state.notifications.filter(n=>!n.read).length} unread notifications`, `<div class="os-notifications">${state.notifications.slice(0,40).map(n=>`<button class="os-notification ${n.read?'read':''}" onclick="markRead(${n.id})"><b>${esc(n.title)}</b><small>${esc(n.body||'')} · ${shortDate(n.createdAt)}</small><em>${n.read?'Read':'Mark read'}</em></button>`).join('')||empty('All caught up','New client and task activity appears here.')}</div>`)}
  function markRead(id){post({action:'read_notification',id}).catch(e=>showError(e.message))}
  const searchData=()=>[
    ...(staff()?state.clients.map(c=>({title:c.name,detail:'Client workspace',tab:'clients'})):[]),
    ...state.projects.map(p=>({title:p.title,detail:p.clientName+' · Project',tab:'projects'})),
    ...state.tasks.map(t=>({title:t.title,detail:t.clientName+' · Task',tab:'tasks'})),
    ...items('approvalRequests').map(a=>({title:a.title,detail:a.clientName+' · Approval',tab:'approvals'})),
    ...items('supportTickets').map(t=>({title:t.title,detail:t.clientName+' · Ticket',tab:'tickets'})),
    ...items('salesLeads').map(l=>({title:l.name,detail:l.company+' · Lead',tab:'leads'})),
    ...(manager()?state.members.filter(m=>m.role!=='client').map(m=>({title:m.name,detail:m.roleLabel+' · Team',tab:'team'})):[])
  ];
  function palette(){modal('Search workspace','Quickly find clients, projects, tasks, tickets and people you can access.',`<input id="paletteSearch" class="os-palette-search" autocomplete="off" placeholder="Type to search... (or press Ctrl + K)"><div id="paletteResults" class="os-palette-results"></div>`);const input=document.getElementById('paletteSearch');input.oninput=()=>{const q=input.value.toLowerCase().trim();const rows=searchData().filter(x=>!q||`${x.title} ${x.detail}`.toLowerCase().includes(q)).slice(0,14);document.getElementById('paletteResults').innerHTML=rows.map(x=>`<button onclick="closeModal();go('${x.tab}')"><span>⌕</span><strong>${esc(x.title)}</strong><small>${esc(x.detail)}</small><em>↵</em></button>`).join('')||empty('No matches','Try a different search term.')};input.oninput();input.focus()}
  function quickCreate(){const opts=state.ctx.role==='client'?[['Support ticket','ticketModal()','✉'],['Client update','updateModal()','↻']]:[['Task','taskModal()','☑'],['Log hours','timeModal()','◷'],['Milestone','milestoneModal()','◈'],['Approval','approvalModal()','◎'],['Support ticket','ticketModal()','✉'],...(manager()?[['Sales lead','leadModal()','◇'],['Client','clientModal()','♟'],['Employee','memberModal()','♜']]:[])];modal('Quick create','Create a record without leaving your workspace.',`<div class="os-create-grid">${opts.map(x=>`<button onclick="closeModal();${x[1]}"><span>${x[2]}</span>${x[0]} <b>＋</b></button>`).join('')}</div>`)}
  // Bind all actions referenced by inline event handlers (all data is escaped).
  Object.assign(window,{execute,opsUI,leaveModal,decideLeave,timeModal,approvalModal,decideApproval,
    ticketModal,ticketThread,milestoneModal,leadModal,saveCurrentView,applySavedView,
    notificationCenter,palette,quickCreate,markRead});
  document.getElementById('bellBtn').onclick=notificationCenter;
  const command=document.getElementById('commandBtn');if(command) command.onclick=palette;
  const quick=document.getElementById('quickBtn');if(quick)quick.onclick=quickCreate;
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();palette()}});
  const oldGo=go;
  go=function(key){oldGo(key);try{history.replaceState(null,'','#'+key)}catch{}};
  window.go=go;window.render=render;window.taskModal=taskModal;window.clientModal=clientModal;
  if(location.hash){const tab=location.hash.slice(1);if((menus[state.ctx?.role]||[]).includes(tab))state.tab=tab;}
  if(!state.loading&&!state.error)render();
})();

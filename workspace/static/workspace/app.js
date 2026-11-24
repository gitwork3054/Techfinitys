const state={ctx:null,clients:[],members:[],assignments:[],projects:[],tasks:[],updates:[],notes:[],events:[],notifications:[],activities:[],records:[],taskLists:[],projectIssues:[],projectFeed:[],projectDocs:[],projectTeams:[],dashboardLayouts:[],defaultWidgets:{},projectGroups:[],tab:'overview',loading:true,error:'',notice:''};
const $=s=>document.querySelector(s); const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const cookie=n=>document.cookie.split('; ').find(x=>x.startsWith(n+'='))?.split('=')[1]||'';
const api='/api/workspace/';
const labels={overview:'Overview',clients:'Clients',team:'Team & hierarchy',assignments:'Client assignments',projects:'Projects',tasks:'Tasks',updates:'Updates',calendar:'Calendar',notes:'Notes',packages:'Packages',deliverables:'Deliverables',content:'Content',campaigns:'Analytics',shoots:'Shoots',files:'Files & assets',tickets:'Support desk',invoices:'Billing',workflows:'Workflows',reports:'Reports',audit:'Activity log',settings:'Settings'};
const menus={
 client:['overview','updates','projects','tasks','calendar','notes','packages','deliverables','content','campaigns','shoots','files','tickets','invoices'],
 employee:['overview','clients','projects','tasks','updates','calendar','notes','deliverables','content','campaigns','shoots','files','tickets'],
 manager:['overview','clients','team','assignments','projects','tasks','updates','calendar','notes','packages','deliverables','content','campaigns','shoots','files','tickets','invoices','workflows','reports','audit'],
 admin:['overview','clients','team','assignments','projects','tasks','updates','calendar','notes','packages','deliverables','content','campaigns','shoots','files','tickets','invoices','workflows','reports','audit','settings']
};
function roleName(){return state.ctx?.roleLabel||''}
function initials(name){return String(name||'TF').split(/\s+/).map(x=>x[0]).join('').slice(0,2).toUpperCase()}
function fmtDate(v){if(!v)return '—';try{return new Date(v).toLocaleString('en-IN',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}catch{return v}}
function shortDate(v){if(!v)return '—';try{return new Date(v).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})}catch{return v}}
function badge(v){let good=['active','completed','approved','published','resolved','paid'].some(x=>String(v).toLowerCase().includes(x)),warn=['review','blocked','onboarding','due','open','progress'].some(x=>String(v).toLowerCase().includes(x));return `<span class="badge ${good?'good':warn?'warn':''}">${esc(v||'—')}</span>`}
async function post(data){let r=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:JSON.stringify(data)});let text=await r.text(),d={};try{d=text?JSON.parse(text):{}}catch(_){throw Error(r.ok?'Server returned an invalid response':`Server error ${r.status}. Check the Django terminal for details.`)}if(!r.ok)throw Error(d.error||`Request failed (${r.status})`);state.notice='Saved successfully';await load();closeModal();return d}
async function load(){
  state.loading=true;render();
  try{
    const [r,opsr,plusr]=await Promise.all([
      fetch(api,{cache:'no-store'}),fetch('/api/operations/',{cache:'no-store'}),
      fetch('/api/projects-plus/',{cache:'no-store'})
    ]);
    const [d,ops,plus]=await Promise.all([r.json(),opsr.json(),plusr.json()]);
    if(!r.ok)throw Error(d.error||'Unable to load CRM');
    if(!opsr.ok)throw Error(ops.error||'Unable to load operations');
    if(!plusr.ok)throw Error(plus.error||'Unable to load project workspace');
    Object.assign(state,d,ops,plus);
    state.ctx=d.ctx||d.context||state.ctx;
    if(!state.ctx)throw Error('CRM account context is missing');
    state.error='';
    if(!(menus[state.ctx.role]||[]).includes(state.tab))state.tab='overview';
  }catch(e){state.error=e.message}
  finally{state.loading=false;render()}
}

// Employee-only full workspace refresh. Preserves the current page and
// re-fetches the same permission-scoped APIs used at sign-in.
let tfEmployeeRefreshBusy=false;
async function refreshEmployeeWorkspace(){
  const btn=document.getElementById('tfEmployeeRefresh');
  if(state.ctx?.role!=='employee'||tfEmployeeRefreshBusy)return;
  tfEmployeeRefreshBusy=true;
  if(btn){btn.disabled=true;btn.setAttribute('aria-busy','true');}
  try{
    await load();
    if(state.error)throw Error(state.error);
    if(window.TFCollab && typeof window.TFCollab.refresh==='function')await window.TFCollab.refresh();
    if(btn){btn.title='Workspace updated';}
  }catch(err){state.notice='Could not refresh your workspace. Please try again.';render();}
  finally{
    tfEmployeeRefreshBusy=false;
    if(btn){btn.disabled=false;btn.removeAttribute('aria-busy');}
  }
}
document.getElementById('tfEmployeeRefresh')?.addEventListener('click',refreshEmployeeWorkspace);
function go(t){if(state.ctx && !(menus[state.ctx.role]||[]).includes(t))return;state.tab=t;render()}
function shell(){if(!state.ctx)return;const refreshButton=document.getElementById('tfEmployeeRefresh');if(refreshButton)refreshButton.hidden=state.ctx.role!=='employee';$('#crumbTitle').textContent=labels[state.tab]||state.tab;$('#rolePill').textContent=roleName();$('#topAvatar').textContent=initials(state.ctx.name);$('#workspaceCard').innerHTML=`<span class="avatar">${initials(state.ctx.name)}</span><div><strong>${esc(state.ctx.name)}</strong><small>${esc(roleName())}</small></div>`;$('#nav').innerHTML=(menus[state.ctx.role]||[]).map(k=>`<button class="${state.tab===k?'active':''}" data-tab="${k}"><span>${icon(k)}</span>${labels[k]}${k==='updates'&&state.updates.length?`<em>${state.updates.length}</em>`:''}</button>`).join('');$('#nav').querySelectorAll('button').forEach(b=>b.onclick=()=>go(b.dataset.tab))}
function icon(k){return ({overview:'▦',clients:'♟',team:'♜',assignments:'⇄',projects:'◇',tasks:'☑',updates:'↻',calendar:'▣',notes:'≣',content:'◫',files:'▰',tickets:'▱',packages:'◇',deliverables:'☑',campaigns:'▥',shoots:'◉',workflows:'⌘',invoices:'▤',reports:'▥',audit:'⌘',settings:'⚙'})[k]||'•'}
function heading(sub='Keep every client, owner and next step clear.'){return `<div class="heading"><div><div class="eyebrow">TECHFINITYS / ${esc(roleName().toUpperCase())}</div><h1>${esc(labels[state.tab]||'CRM')}</h1><p>${esc(sub)}</p></div></div>`}
function stat(title,value,sub){return `<div class="stat"><span>${esc(title)}</span><div>${esc(value)}</div><small>${esc(sub)}</small></div>`}
function toolbar(button=''){return `<div class="toolbar"><div></div>${button}</div>`}
function clients(){
  const canManage=['admin','manager'].includes(state.ctx.role);
  const activeCount=state.clients.filter(c=>String(c.status||c.statusLabel||'').toLowerCase().includes('active')).length;
  const rows=state.clients.map(c=>{
    const members=(c.assignedNames||[]).filter(Boolean).join(', ');
    return `<tr>
      <td><span class="tf-client-code">${esc(c.code||'—')}</span></td>
      <td><div class="tf-client-identity"><span class="tf-client-avatar" aria-hidden="true">${esc(initials(c.name))}</span><div><strong>${esc(c.name||'Unnamed client')}</strong><small>${esc(c.email||'Client workspace')}</small></div></div></td>
      <td><span class="tf-client-company">${esc(c.company||'—')}</span></td>
      <td><strong class="tf-client-package">${esc(c.package||'—')}</strong></td>
      <td>${members?`<span class="tf-client-team" title="${esc(members)}">${esc(members)}</span>`:'<span class="tf-client-unassigned">Not assigned</span>'}</td>
      <td>${badge(c.statusLabel||c.status)}</td>
      <td>${canManage?`<button type="button" class="tf-client-assign" onclick="assignmentModal('${c.id}')">Assign employee</button>`:'<span class="tf-client-unassigned">View only</span>'}</td>
    </tr>`;
  }).join('');
  return `${heading('Manage client workspaces, package details and employee access in one place.')}
    <section class="tf-client-register" aria-label="Client directory">
      <header class="tf-client-register-header"><div><span class="tf-client-register-label">CLIENT DIRECTORY</span><h2>All clients <span>${state.clients.length}</span></h2></div><div class="tf-client-register-actions"><span class="tf-client-active"><i></i>${activeCount} active</span>${canManage?'<button type="button" class="tf-client-create" onclick="clientModal()">＋ New client</button>':''}</div></header>
      <div class="tf-client-table-wrap"><table class="tf-client-table"><thead><tr><th>Code</th><th>Client</th><th>Company</th><th>Package</th><th>Assigned team</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows||'<tr><td colspan="7" class="tf-client-empty"><strong>No clients yet</strong><span>Use New client to create your first workspace.</span></td></tr>'}</tbody></table></div>
    </section>`;
}
function team(){let members=state.members.filter(m=>m.role!=='client');return `${heading('Reporting lines and permissions are separate from client assignments.')}${toolbar(['admin','manager'].includes(state.ctx.role)?'<button class="primary" onclick="memberModal()">＋ New employee</button>':'')}<div class="hierarchy">${members.map(m=>`<button type="button" class="person tf-employee-card" onclick="employeeDetails(${Number(m.id)})" aria-label="View ${esc(m.name)} employee details"><span class="avatar">${initials(m.name)}</span><span class="tf-employee-card-info"><strong>${esc(m.name)}</strong><small>${esc(m.jobTitle||m.roleLabel)}${m.department?' · '+esc(m.department):''}</small><small>Reports to: ${esc(m.managerName||'Top level')}</small></span>${badge(m.active?'Active':'Inactive')}<span class="tf-employee-card-arrow">›</span></button>`).join('')}</div>`;}
function employeeDetails(id){
  const m=state.members.find(x=>Number(x.id)===Number(id));if(!m)return;
  const projects=state.projects.filter(p=>Number(p.ownerId)===Number(id));
  const assigned=state.tasks.filter(t=>Number(t.assignedTo)===Number(id)||(t.assigneeIds||[]).map(Number).includes(Number(id)));
  const clients=state.assignments.filter(a=>Number(a.employeeId)===Number(id)&&a.active).map(a=>state.clients.find(c=>String(c.id)===String(a.clientId))?.name).filter(Boolean);
  const admin=state.ctx?.role==='admin';
  openModal(`<div class="tf-employee-dialog"><span class="eyebrow">TEAM / EMPLOYEE PROFILE</span><div class="tf-employee-profile-top"><span class="avatar">${initials(m.name)}</span><div><h2>${esc(m.name)}</h2><p>${esc(m.roleLabel)} · ${esc(m.active?'Active':'Inactive')}</p></div></div><div class="tf-employee-details-grid">
    <div><small>Username</small><strong>${esc(m.username)}</strong></div><div><small>Email</small><strong>${esc(m.email||'Not set')}</strong></div>
    <div><small>Phone</small><strong>${esc(m.phone||'Not set')}</strong></div><div><small>Department</small><strong>${esc(m.department||'Not set')}</strong></div>
    <div><small>Job title</small><strong>${esc(m.jobTitle||'Not set')}</strong></div><div><small>Reports to</small><strong>${esc(m.managerName||'Top level')}</strong></div>
    <div><small>Assigned clients</small><strong>${esc(clients.join(', ')||'None')}</strong></div><div><small>Work</small><strong>${projects.length} owned projects · ${assigned.length} tasks</strong></div>
  </div><div class="tf-employee-profile-actions"><button type="button" onclick="closeModal()">Close</button><button type="button" class="primary" onclick="editEmployee(${Number(m.id)})">✎ Edit details</button>${admin&&m.role!=='admin'?`<button type="button" class="tf-employee-danger" onclick="deleteEmployee(${Number(m.id)})">Delete employee</button>`:''}</div></div>`);
}
function editEmployee(id){
  const m=state.members.find(x=>Number(x.id)===Number(id));if(!m)return;
  if(!['admin','manager'].includes(state.ctx?.role))return;
  const managerOptions=state.members.filter(p=>['manager','admin'].includes(p.role)&&Number(p.id)!==Number(id));
  const names=(m.name||'').split(' ');const first=m.name===m.username?'':names.shift()||'';const last=m.name===m.username?'':names.join(' ');
  const managerOnly=state.ctx.role==='admin';
  openModal(`<div class="tf-employee-dialog"><span class="eyebrow">TEAM / EDIT EMPLOYEE</span><h2>Edit ${esc(m.name)}</h2><form id="tfEditEmployeeForm"><div class="form-grid">
    <label>First name<input name="firstName" required value="${esc(first)}"></label><label>Last name<input name="lastName" value="${esc(last)}"></label>
    <label>Username<input name="username" required value="${esc(m.username)}"></label><label>Email<input type="email" name="email" value="${esc(m.email||'')}"></label>
    <label>Phone<input name="phone" value="${esc(m.phone||'')}"></label><label>Department<input name="department" value="${esc(m.department||'')}"></label>
    <label>Job title<input name="jobTitle" value="${esc(m.jobTitle||'')}"></label>
    <label>Reports to<select name="managerId"><option value="">Top level</option>${managerOptions.map(x=>`<option value="${x.id}" ${Number(m.managerId)===Number(x.id)?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>
    ${managerOnly?`<label>Role<select name="role">${[['employee','Employee'],['manager','Office Manager'],['admin','Super Admin']].map(([v,s])=>`<option value="${v}" ${m.role===v?'selected':''}>${s}</option>`).join('')}</select></label><label>New password (optional)<input type="password" name="password" minlength="4" autocomplete="new-password" placeholder="Leave blank to keep current"></label>`:''}
    <label>Status<select name="active"><option value="true" ${m.active?'selected':''}>Active</option><option value="false" ${!m.active?'selected':''}>Inactive</option></select></label>
  </div><div class="tf-employee-profile-actions"><button type="button" onclick="employeeDetails(${Number(id)})">Cancel</button><button type="submit" class="primary">Save changes</button></div></form></div>`);
  document.getElementById('tfEditEmployeeForm').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget;const button=form.querySelector('[type="submit"]');button.disabled=true;
    const values=Object.fromEntries(new FormData(form));values.active=values.active==='true';if(!values.password)delete values.password;
    try{await post({action:'update_member',memberId:id,...values});closeModal();}catch(error){alert(error.message);button.disabled=false;}
  };
}
async function deleteEmployee(id){
  if(state.ctx?.role!=='admin'||Number(state.ctx.id)===Number(id))return;
  const m=state.members.find(x=>Number(x.id)===Number(id));if(!m||m.role==='admin')return;
  if(!confirm(`Remove access for ${m.name}? The employee will be deactivated, their client assignments disabled, and task, attendance, leave and audit history preserved. This can be reversed by editing their status.`))return;
  try{await post({action:'delete_member',memberId:id});closeModal();}catch(error){alert(error.message)}
}
function assignments(){let rows=state.assignments.map(a=>{let c=state.clients.find(x=>x.id===a.clientId),m=state.members.find(x=>x.id===a.employeeId);return `<tr><td>${esc(c?.name||'')}</td><td>${esc(m?.name||'')}</td><td>${esc(a.roleTitle)}</td><td>${a.isPrimary?'Primary':'Member'}</td><td><button onclick="removeAssignment(${a.id})">Remove</button></td></tr>`}).join('');return `${heading('Employees only see client workspaces explicitly assigned to them.')}${toolbar('<button class="primary" onclick="assignmentModal()">＋ Assign employee</button>')}<div class="panel"><table><thead><tr><th>Client</th><th>Employee</th><th>Responsibility</th><th>Type</th><th></th></tr></thead><tbody>${rows||'<tr><td colspan="5">No assignments.</td></tr>'}</tbody></table></div>`}
function projects(){return `${heading('Projects group tasks, notes and client progress under one delivery stream.')}${toolbar(state.ctx.role!=='client'?'<button class="primary" onclick="projectModal()">＋ New project</button>':'')}<div class="cards">${state.projects.map(p=>`<article class="record-card"><div class="record-top"><span class="eyebrow">${esc(p.clientName)}</span>${badge(p.statusLabel)}</div><h3>${esc(p.title)}</h3><p>${esc(p.description||'')}</p><div class="progress"><i style="width:${p.progress}%"></i></div><div class="meta"><span>${p.progress}% complete</span><span>Owner: ${esc(p.ownerName||'Unassigned')}</span><span>Due: ${shortDate(p.dueDate)}</span></div>${state.ctx.role!=='client'?`<button onclick="projectModal('${p.id}')">Edit project</button>`:''}</article>`).join('')||'<div class="empty">No projects yet.</div>'}</div>`}
function taskRow(t){return `<div class="task-row"><div><strong>${esc(t.title)}</strong><small>${esc(t.clientName)} · ${esc(t.assignedName||'Unassigned')} · ${esc(t.priorityLabel)}</small></div>${badge(t.statusLabel)}${state.ctx.role!=='client'?`<select onchange="setTaskStatus('${t.id}',this.value)">${['todo','in_progress','review','blocked','completed'].map(x=>`<option value="${x}" ${x===t.status?'selected':''}>${({todo:'To do',in_progress:'In progress',review:'In review',blocked:'Blocked',completed:'Completed'})[x]}</option>`).join('')}</select>`:''}</div>`}
function tasks(){let groups=['todo','in_progress','review','blocked','completed'];return `${heading('Assign work to people who already belong to that client team; clients see only client-visible tasks.')}${toolbar(state.ctx.role!=='client'?'<button class="primary" onclick="taskModal()">＋ New task</button>':'')}<div class="board">${groups.map(g=>`<section class="lane"><h3>${({todo:'To do',in_progress:'In progress',review:'In review',blocked:'Blocked',completed:'Completed'})[g]} <span>${state.tasks.filter(t=>t.status===g).length}</span></h3>${state.tasks.filter(t=>t.status===g).map(t=>`<article class="task-card"><span class="eyebrow">${esc(t.clientName)}</span><h4>${esc(t.title)}</h4><p>${esc(t.description||'')}</p><small>${esc(t.assignedName||'Unassigned')} · due ${shortDate(t.dueAt)}</small>${state.ctx.role!=='client'?`<button onclick="taskModal('${t.id}')">Edit</button>`:''}</article>`).join('')||'<div class="empty compact">No tasks</div>'}</section>`).join('')}</div>`}
function updates(){return `${heading('Employees can publish client-facing progress or keep updates internal to the team.')}${toolbar('<button class="primary" onclick="updateModal()">＋ Post update</button>')}<div class="timeline">${state.updates.map(u=>`<article><span class="avatar">${initials(u.authorName)}</span><div><div class="record-top"><strong>${esc(u.authorName)}</strong><span>${fmtDate(u.createdAt)}</span></div><h3>${esc(u.title)}</h3><p>${esc(u.body)}</p><div class="meta"><span>${esc(u.clientName)}</span><span>${u.visibility==='client'?'Client + team':'Internal'}</span><span>${u.progress}% progress</span></div></div></article>`).join('')||'<div class="empty">No updates yet.</div>'}</div>`}
function notes(){return `${heading('Attach context to a client, project or task with client, team or private visibility.')}${toolbar('<button class="primary" onclick="noteModal()">＋ Add note</button>')}<div class="cards">${state.notes.map(n=>`<article class="record-card"><div class="record-top"><span class="eyebrow">${esc(n.clientName)}</span>${n.pinned?'<span class="badge good">Pinned</span>':''}</div><p>${esc(n.body)}</p><div class="meta"><span>${esc(n.authorName)}</span><span>${esc(n.visibility)}</span><span>${fmtDate(n.createdAt)}</span></div></article>`).join('')||'<div class="empty">No notes yet.</div>'}</div>`}
function calendar(){return `${heading('Meetings, deadlines, shoots, reviews and reminders across every assigned client.')}${toolbar(state.ctx.role!=='client'?'<button class="primary" onclick="eventModal()">＋ New event</button>':'')}<div class="panel"><div class="calendar-list">${state.events.map(e=>`<article><div class="datebox"><strong>${new Date(e.startAt).getDate()}</strong><span>${new Date(e.startAt).toLocaleString('en-IN',{month:'short'})}</span></div><div><span class="eyebrow">${esc(e.eventTypeLabel)} · ${esc(e.clientName)}</span><h3>${esc(e.title)}</h3><p>${esc(e.description||'')}</p><small>${fmtDate(e.startAt)} · ${esc(e.attendeeNames.join(', ')||e.ownerName||'')}</small></div></article>`).join('')||'<div class="empty">No events scheduled.</div>'}</div></div>`}
function legacy(kind){if(kind==='workflows')return workflows();let rs=state.records.filter(r=>r.kind===kind);return `${heading('This module retains the original Techfinitys CRM workflow while using the new client visibility rules.')}${toolbar(state.ctx.role!=='client' || ['tickets','content'].includes(kind)?`<button class="primary" onclick="legacyModal('${kind}')">＋ Add ${esc(labels[kind]||kind)}</button>`:'')}<div class="cards">${rs.map(r=>`<article class="record-card"><div class="record-top"><span class="eyebrow">${esc(r.client||'org')}</span>${badge(r.status)}</div><h3>${esc(r.title)}</h3><p>${esc(r.detail||r.body||'')}</p><div class="meta"><span>${esc(r.owner||'')}</span><span>${esc(r.date||'')}</span></div>${kind==='files'&&r.hasAttachment?`<button onclick="window.location='/api/file/${encodeURIComponent(r.id)}/'">Download</button>`:''}</article>`).join('')||'<div class="empty">No records in this module.</div>'}</div>`}

/* Task workflow automation designer. All rules execute in Django. */
const tfStatusOptions=[['any','Any'],['todo','To do'],['in_progress','In progress'],['review','In review'],['blocked','Blocked'],['completed','Completed']];
function tfOpts(options,chosen){return options.map(x=>'<option value="'+esc(x[0])+'" '+(x[0]===chosen?'selected':'')+'>'+esc(x[1])+'</option>').join('');}
function workflows(){
 const rows=state.records.filter(r=>r.kind==='workflows');
 const permitted=['admin','manager'].includes(state.ctx?.role);
 const html=rows.map(r=>'<article class="tf-flow-card"><div><h3>'+esc(r.title)+' '+badge(r.status)+'</h3><p>Task status: '+esc(r.fromStatus||'any')+' → '+esc(r.toStatus||'any')+'</p><small>'+esc((r.actions||[]).map(a=>({notify_assignee:'Notify assignee',set_priority:'Change priority',create_followup:'Create follow-up task'}[a.type]||a.type)).join(' · '))+'</small></div>'+(permitted?'<button onclick="workflowBuilder('+JSON.stringify(r.id).replace(/"/g,"'")+')">Edit</button><button onclick="workflowDelete('+JSON.stringify(r.id).replace(/"/g,"'")+')">Delete</button>':'')+'</article>').join('');
 return heading('Build automation rules with triggers, conditions, and real actions.')+toolbar(permitted?'<button class="primary" onclick="workflowBuilder()">＋ New workflow</button>':'')+'<div class="tf-flow-list">'+(html||'<div class="tf-flow-card">No workflows yet. Create a rule to automate task updates.</div>')+'</div>';
}
function tfFlowAction(a){
 a=a||{};const type=a.type||'notify_assignee';
 let extra=type==='set_priority'?'<select class="tf-flow-priority">'+tfOpts([['low','Low'],['normal','Normal'],['high','High'],['urgent','Urgent']],a.priority||'normal')+'</select>':type==='create_followup'?'<input class="tf-flow-title" placeholder="Follow-up task title" maxlength="180" required value="'+esc(a.title||'')+'">':'<small>Notify the currently assigned employee</small>';
 return '<div class="tf-flow-action"><select class="tf-flow-type" onchange="tfFlowChange(this)">'+tfOpts([['notify_assignee','Notify assignee'],['set_priority','Change task priority'],['create_followup','Create follow-up task']],type)+'</select>'+extra+'<button type="button" onclick="this.parentElement.remove()">×</button></div>';
}
function tfFlowChange(select){const wrapper=document.createElement('div');wrapper.innerHTML=tfFlowAction({type:select.value});select.closest('.tf-flow-action').replaceWith(wrapper.firstElementChild);}
function tfFlowAdd(){const list=document.getElementById('tfFlowActions');if(list.children.length>=4)return alert('Maximum 4 actions');list.insertAdjacentHTML('beforeend',tfFlowAction());}
function workflowBuilder(id){
 if(!['admin','manager'].includes(state.ctx?.role))return;
 const r=state.records.find(x=>x.kind==='workflows'&&x.id===id)||{};
 let clients='<option value="org">All clients</option>'+state.clients.map(x=>'<option value="'+esc(x.code)+'" '+(r.client===x.code?'selected':'')+'>'+esc(x.name)+'</option>').join('');
 let form='<div class="tf-flow-builder"><div class="eyebrow">AUTOMATION BUILDER</div><h2>'+(id?'Edit':'Create')+' workflow</h2><p>Rules execute automatically when task status changes.</p><form id="tfFlowForm">';
 form+='<label>Workflow name<input name="title" maxlength="160" required value="'+esc(r.title||'')+'" placeholder="e.g. Finished task follow-up"></label>';
 form+='<div class="form-grid"><label>Client scope<select name="client">'+clients+'</select></label><label>Status<select name="status">'+tfOpts([['Draft','Draft (off)'],['Active','Active (on)']],r.status||'Draft')+'</select></label></div>';
 form+='<div class="tf-flow-step"><h3>1. Trigger</h3><label>When<select name="trigger"><option value="task_status">Task status changes</option></select></label></div>';
 form+='<div class="tf-flow-step"><h3>2. Conditions</h3><div class="form-grid"><label>From status<select name="fromStatus">'+tfOpts(tfStatusOptions,r.fromStatus||'any')+'</select></label><label>To status<select name="toStatus">'+tfOpts(tfStatusOptions,r.toStatus||'completed')+'</select></label></div></div>';
 form+='<div class="tf-flow-step"><h3>3. Actions</h3><div id="tfFlowActions">'+(r.actions?.length?r.actions:[{type:'notify_assignee'}]).map(tfFlowAction).join('')+'</div><button type="button" onclick="tfFlowAdd()">＋ Add action</button></div>';
 form+='<div class="tf-flow-footer"><button type="button" onclick="closeModal()">Cancel</button><button type="submit" class="primary">Save workflow</button></div></form></div>';
 openModal(form);
 const el=document.getElementById('tfFlowForm');
 el.onsubmit=async e=>{
  e.preventDefault();
  const actions=Array.from(el.querySelectorAll('.tf-flow-action')).map(row=>{
   const type=row.querySelector('.tf-flow-type').value;
   if(type==='set_priority')return {type,priority:row.querySelector('.tf-flow-priority').value};
   if(type==='create_followup')return {type,title:row.querySelector('.tf-flow-title').value.trim()};
   return {type};
  });
  if(!actions.length||actions.some(a=>a.type==='create_followup'&&!a.title))return alert('Add a valid action.');
  const button=el.querySelector('[type=submit]');button.disabled=true;
  try{await post(Object.assign({kind:'workflows',id,actions},Object.fromEntries(new FormData(el))));}
  catch(err){alert(err.message);button.disabled=false;}
 };
}
async function workflowDelete(id){
 if(!['admin','manager'].includes(state.ctx?.role)||!confirm('Permanently delete this workflow?'))return;
 try{await post({action:'delete_workflow',kind:'workflows',id});}catch(e){alert(e.message);}
}

function audit(){return `${heading('Immutable-style operational trail of key hierarchy and workflow changes.')}<div class="panel">${state.activities.map(a=>`<div class="activity"><span class="avatar tiny">${initials(a.actorName)}</span><div><strong>${esc(a.action)}</strong><p>${esc(a.detail)}</p><small>${esc(a.actorName)} · ${esc(a.clientName)} · ${fmtDate(a.createdAt)}</small></div></div>`).join('')||'<div class="empty">No activity yet.</div>'}</div>`}
function reports(){let byClient=state.clients.map(c=>{let ts=state.tasks.filter(t=>t.clientId===c.id),done=ts.filter(t=>t.status==='completed').length;return `<tr><td>${esc(c.name)}</td><td>${ts.length}</td><td>${done}</td><td>${ts.length?Math.round(done/ts.length*100):0}%</td><td>${state.updates.filter(u=>u.clientId===c.id).length}</td></tr>`}).join('');return `${heading('Simple operational reporting across clients, tasks and communication.')}<div class="panel"><table><thead><tr><th>Client</th><th>Tasks</th><th>Completed</th><th>Completion</th><th>Updates</th></tr></thead><tbody>${byClient}</tbody></table></div>`}
function settings(){return `${heading('Organisation controls are managed by the Super Admin.')}<div class="cards"><article class="record-card"><span class="eyebrow">Security</span><h3>Role hierarchy</h3><p>Super Admin → Office Manager → Employee → assigned client workspaces. Clients are isolated to their own portal.</p></article><article class="record-card"><span class="eyebrow">Permissions</span><h3>Feature access</h3><p>Role hierarchy controls data visibility; permission grants control actions.</p></article><article class="record-card"><span class="eyebrow">Audit</span><h3>Activity history</h3><p>Client assignment, user creation, task changes and updates are recorded.</p></article></div>`}
function render(){if(state.loading){$('#mainContent').innerHTML='<div class="empty">Loading CRM…</div>';return}if(state.error){$('#mainContent').innerHTML=`<div class="empty"><h2>${esc(state.error)}</h2><a href="/login/">Sign in again</a></div>`;return}shell();let fn={overview,clients,team,assignments,projects,tasks,updates,calendar,notes,reports,audit,settings}[state.tab];$('#mainContent').innerHTML=(state.notice?`<div class="notice">${esc(state.notice)}<button onclick="state.notice='';render()">×</button></div>`:'')+(fn?fn():legacy(state.tab))}
function openModal(html){$('#modalRoot').innerHTML=`<div class="overlay" onclick="if(event.target===this)closeModal()"><section class="modal"><button class="close icon" onclick="closeModal()">×</button>${html}</section></div>`}
function closeModal(){$('#modalRoot').innerHTML=''}
function clientSelect(value=''){return `<select name="clientId" required><option value="">Select client</option>${state.clients.map(c=>`<option value="${c.id}" ${c.id===value?'selected':''}>${esc(c.name)}</option>`).join('')}</select>`}
function employeeSelect(value=''){let ms=state.members.filter(m=>['employee','manager'].includes(m.role));return `<select name="employeeId" required><option value="">Select employee</option>${ms.map(m=>`<option value="${m.id}" ${String(m.id)===String(value)?'selected':''}>${esc(m.name)} · ${esc(m.jobTitle||m.roleLabel)}</option>`).join('')}</select>`}
function clientModal(){let employees=state.members.filter(m=>m.role==='employee');openModal(`<div class="eyebrow">Client management</div><h2>Create client workspace</h2><form id="f"><div class="form-grid"><label>Client name<input name="name" required></label><label>Client code<input name="code" placeholder="acme-studio"></label><label>Company<input name="company"></label><label>Email<input type="email" name="email"></label><label>Phone<input name="phone"></label><label>Package<input name="package"></label><label>Status<select name="status"><option value="onboarding">Onboarding</option><option value="active">Active</option><option value="paused">Paused</option></select></label><label>Assign employee<select name="employeeId"><option value="">Assign later</option>${employees.map(m=>`<option value="${m.id}">${esc(m.name)} · ${esc(m.jobTitle||'Employee')}</option>`).join('')}</select></label></div><hr><h3>Optional client portal login</h3><div class="form-grid"><label>Username<input name="portalUsername"></label><label>Temporary password<input name="portalPassword" type="password" minlength="4" placeholder="4 or more characters"></label></div><button class="primary">Create client</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));try{await post({action:'create_client',...o})}catch(x){alert(x.message)}}}
function memberModal(){let managers=state.members.filter(m=>['manager','admin'].includes(m.role));openModal(`<div class="eyebrow">People</div><h2>Create employee</h2><form id="f"><div class="form-grid"><label>First name<input name="firstName" required></label><label>Last name<input name="lastName"></label><label>Username<input name="username" required></label><label>Temporary password<input name="password" type="password" minlength="4" required></label><label>Email<input name="email" type="email"></label><label>Phone<input name="phone"></label><label>Department<input name="department"></label><label>Job title<input name="jobTitle"></label><label>Reports to<select name="managerId"><option value="">Top level</option>${managers.map(m=>`<option value="${m.id}">${esc(m.name)}</option>`).join('')}</select></label><label>Role<select name="role"><option value="employee">Employee</option>${state.ctx.role==='admin'?'<option value="manager">Office Manager</option>':''}</select></label></div><button class="primary">Create user</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));try{await post({action:'create_member',...o})}catch(x){alert(x.message)}}}
function assignmentModal(clientId=''){openModal(`<div class="eyebrow">Access assignment</div><h2>Assign employee to client</h2><form id="f"><label>Client${clientSelect(clientId)}</label><label>Employee${employeeSelect()}</label><label>Responsibility<input name="roleTitle" value="Account team"></label><label class="check"><input type="checkbox" name="isPrimary"> Primary account owner</label><button class="primary">Assign</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target),o=Object.fromEntries(fd);o.isPrimary=fd.get('isPrimary')==='on';try{await post({action:'assign_client',...o})}catch(x){alert(x.message)}}}
async function removeAssignment(id){if(confirm('Remove this employee from the client workspace?'))try{await post({action:'unassign_client',assignmentId:id})}catch(x){alert(x.message)}}
function projectModal(id=''){let p=state.projects.find(x=>x.id===id)||{};let team=state.members.filter(m=>['employee','manager'].includes(m.role));openModal(`<div class="eyebrow">Projects</div><h2>${id?'Edit':'Create'} project</h2><form id="f"><label>Client${clientSelect(p.clientId||'')}</label><label>Title<input name="title" required value="${esc(p.title||'')}"></label><label>Description<textarea name="description">${esc(p.description||'')}</textarea></label><div class="form-grid"><label>Status<select name="status">${['planned','active','on_hold','completed'].map(x=>`<option value="${x}" ${x===p.status?'selected':''}>${x.replace('_',' ')}</option>`).join('')}</select></label><label>Progress %<input name="progress" type="number" min="0" max="100" value="${p.progress||0}"></label><label>Owner<select name="ownerId"><option value="">Unassigned</option>${team.map(m=>`<option value="${m.id}" ${m.id===p.ownerId?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label><label>Start<input name="startDate" type="date" value="${p.startDate||''}"></label><label>Due<input name="dueDate" type="date" value="${p.dueDate||''}"></label></div><button class="primary">Save project</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));try{await post({action:'save_project',id,...o})}catch(x){alert(x.message)}}}
function taskModal(id=''){let t=state.tasks.find(x=>x.id===id)||{};let team=state.members.filter(m=>['employee','manager'].includes(m.role));openModal(`<div class="eyebrow">Tasks</div><h2>${id?'Edit':'Create'} task</h2><form id="f"><label>Client${clientSelect(t.clientId||'')}</label><label>Title<input name="title" required value="${esc(t.title||'')}"></label><label>Description<textarea name="description">${esc(t.description||'')}</textarea></label><div class="form-grid"><label>Status<select name="status">${['todo','in_progress','review','blocked','completed'].map(x=>`<option value="${x}" ${x===t.status?'selected':''}>${x.replace('_',' ')}</option>`).join('')}</select></label><label>Priority<select name="priority">${['low','normal','high','urgent'].map(x=>`<option value="${x}" ${x===t.priority?'selected':''}>${x}</option>`).join('')}</select></label><label>Assigned to<select name="assignedTo"><option value="">Unassigned</option>${team.map(m=>`<option value="${m.id}" ${m.id===t.assignedTo?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label><label>Project<select name="projectId"><option value="">No project</option>${state.projects.map(p=>`<option value="${p.id}" ${p.id===t.projectId?'selected':''}>${esc(p.title)}</option>`).join('')}</select></label><label>Start<input name="startAt" type="datetime-local" value="${t.startAt?t.startAt.slice(0,16):''}"></label><label>Due<input name="dueAt" type="datetime-local" value="${t.dueAt?t.dueAt.slice(0,16):''}"></label><label>Estimated hours<input name="estimatedHours" type="number" step="0.25" min="0" value="${t.estimatedHours||0}"></label><label>Recurrence<input name="recurrence" placeholder="e.g. weekly" value="${esc(t.recurrence||'')}"></label></div><label class="check"><input name="clientVisible" type="checkbox" ${t.clientVisible!==false?'checked':''}> Visible in client portal</label><button class="primary">Save task</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target),o=Object.fromEntries(fd);o.clientVisible=fd.get('clientVisible')==='on';for(let k of ['startAt','dueAt'])if(o[k])o[k]=new Date(o[k]).toISOString();try{let payload={action:'save_task',...o};if(id)payload.id=id;await post(payload)}catch(x){alert(x.message)}}}
async function setTaskStatus(id,status){try{await post({action:'task_status',id,status})}catch(x){alert(x.message)}}
function updateModal(){openModal(`<div class="eyebrow">Progress</div><h2>Post update</h2><form id="f"><label>Client${clientSelect()}</label><label>Title<input name="title" required></label><label>Update<textarea name="body" required></textarea></label><div class="form-grid"><label>Progress %<input name="progress" type="number" min="0" max="100" value="0"></label>${state.ctx.role!=='client'?'<label>Visibility<select name="visibility"><option value="client">Client + team</option><option value="team">Internal team only</option></select></label>':''}<label>Related task<select name="taskId"><option value="">None</option>${state.tasks.map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('')}</select></label></div><button class="primary">Publish update</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let o=Object.fromEntries(new FormData(e.target));try{await post({action:'add_update',...o})}catch(x){alert(x.message)}}}
function noteModal(){openModal(`<div class="eyebrow">Notes</div><h2>Add note</h2><form id="f"><label>Client${clientSelect()}</label><label>Note<textarea name="body" required></textarea></label>${state.ctx.role!=='client'?'<label>Visibility<select name="visibility"><option value="team">Internal team</option><option value="client">Client + team</option><option value="private">Private</option></select></label>':''}<label class="check"><input name="pinned" type="checkbox"> Pin note</label><button class="primary">Save note</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target),o=Object.fromEntries(fd);o.pinned=fd.get('pinned')==='on';try{await post({action:'add_note',...o})}catch(x){alert(x.message)}}}
function eventModal(){let people=state.members.filter(m=>m.role!=='client');openModal(`<div class="eyebrow">Calendar</div><h2>Schedule event</h2><form id="f"><label>Client (optional)<select name="clientId"><option value="">Organisation-wide</option>${state.clients.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></label><label>Title<input name="title" required></label><div class="form-grid"><label>Type<select name="eventType"><option value="meeting">Meeting</option><option value="deadline">Deadline</option><option value="shoot">Shoot</option><option value="review">Review</option><option value="reminder">Reminder</option></select></label><label>Start<input name="startAt" type="datetime-local" required></label><label>End<input name="endAt" type="datetime-local"></label></div><label>Description<textarea name="description"></textarea></label><label>Attendees<select name="attendeeIds" multiple size="6">${people.map(m=>`<option value="${m.id}">${esc(m.name)}</option>`).join('')}</select></label><button class="primary">Save event</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target),o=Object.fromEntries(fd);o.attendeeIds=fd.getAll('attendeeIds').map(Number);if(o.startAt)o.startAt=new Date(o.startAt).toISOString();if(o.endAt)o.endAt=new Date(o.endAt).toISOString();try{await post({action:'save_event',...o})}catch(x){alert(x.message)}}}
function legacyModal(kind){if(kind==='workflows')return workflowBuilder();openModal(`<div class="eyebrow">${esc(kind)}</div><h2>Add ${esc(labels[kind]||kind)}</h2><form id="f"><label>Client code<select name="client"><option value="org">Organisation</option>${state.clients.map(c=>`<option value="${c.code}">${esc(c.name)}</option>`).join('')}</select></label><label>Title<input name="title" required></label><label>Status<input name="status" value="Draft"></label><label>Details<textarea name="detail"></textarea></label>${kind==='files'?'<label>Upload file (max 5 MB)<input name="file" type="file"></label>':''}<button class="primary">Save</button></form>`);$('#f').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.target),o=Object.fromEntries(fd);if(kind==='files'){let f=fd.get('file');delete o.file;if(f&&f.size){if(f.size>5000000){alert('Maximum file size is 5 MB');return}o.fileName=f.name;o.fileData=await new Promise((res,rej)=>{let r=new FileReader();r.onload=()=>res(String(r.result).split(',')[1]);r.onerror=rej;r.readAsDataURL(f)})}}try{await post({kind,...o})}catch(x){alert(x.message)}}}

// =========================================================
// Zoho-style advanced home + task management upgrade
// =========================================================
labels.issues='Issues'; labels.phases='Phases'; labels.timelogs='Time logs'; labels.timesheets='Timesheets';
labels.collaboration='Collaboration'; labels.approvals='My approvals';
for(const role of ['employee','manager','admin']){
  const a=menus[role]||[];
  const add=['issues','phases','timelogs','timesheets','collaboration','approvals'];
  for(const k of add) if(!a.includes(k)) a.push(k);
}
if(menus.client){ for(const k of ['issues','collaboration']) if(!menus.client.includes(k)) menus.client.push(k); }

const taskUI={search:'',client:'',owner:'',status:'open',priority:'',timespan:'all',view:'list'};
function taskStatusLabel(v){return ({todo:'Open',in_progress:'In progress',review:'Review',blocked:'Blocked',completed:'Completed'})[v]||v}
function sameDay(a,b=new Date()){if(!a)return false;let d=new Date(a);return d.getFullYear()===b.getFullYear()&&d.getMonth()===b.getMonth()&&d.getDate()===b.getDate()}
function filteredTasks(){
  let rows=[...state.tasks];
  const q=taskUI.search.trim().toLowerCase();
  if(q) rows=rows.filter(t=>[t.title,t.description,t.clientName,t.projectName,t.assignedName].some(v=>String(v||'').toLowerCase().includes(q)));
  if(taskUI.client) rows=rows.filter(t=>t.clientId===taskUI.client);
  if(taskUI.owner) rows=rows.filter(t=>String(t.assignedTo||'')===String(taskUI.owner));
  if(taskUI.status==='open') rows=rows.filter(t=>t.status!=='completed');
  else if(taskUI.status && taskUI.status!=='all') rows=rows.filter(t=>t.status===taskUI.status);
  if(taskUI.priority) rows=rows.filter(t=>t.priority===taskUI.priority);
  const now=new Date(), end=new Date(now); end.setDate(end.getDate()+7);
  if(taskUI.timespan==='today') rows=rows.filter(t=>sameDay(t.dueAt,now)||sameDay(t.startAt,now));
  if(taskUI.timespan==='week') rows=rows.filter(t=>t.dueAt&&new Date(t.dueAt)>=now&&new Date(t.dueAt)<=end);
  if(taskUI.timespan==='overdue') rows=rows.filter(t=>t.status!=='completed'&&t.dueAt&&new Date(t.dueAt)<now);
  return rows;
}
function setTaskFilter(k,v){taskUI[k]=v;render()}
function resetTaskFilters(){Object.assign(taskUI,{search:'',client:'',owner:'',status:'open',priority:'',timespan:'all'});render()}
function openTasksWith(filter,value){taskUI[filter]=value;state.tab='tasks';render()}

function icon(k){return ({overview:'⌂',clients:'♟',team:'♜',assignments:'⇄',projects:'◇',tasks:'☑',updates:'↻',calendar:'▣',notes:'≣',content:'◫',files:'▰',tickets:'▱',packages:'◇',deliverables:'☑',campaigns:'▥',shoots:'◉',workflows:'⌘',invoices:'▤',reports:'▥',audit:'⌘',settings:'⚙',issues:'⚠',phases:'◫',timelogs:'◷',timesheets:'▦',collaboration:'♧',approvals:'✓'})[k]||'•'}

function dashTile(title,value,sub,click=''){
 return `<button class="dash-tile" ${click?`onclick="${click}"`:''}><span>${esc(title)}</span><strong>${esc(value)}</strong><small>${esc(sub||'')}</small></button>`
}
function moduleShortcut(k,sub){return `<button class="module-shortcut" onclick="go('${k}')"><b>${icon(k)}</b><span><strong>${esc(labels[k]||k)}</strong><small>${esc(sub)}</small></span><em>→</em></button>`}
function overview(){
 const mine=state.ctx.role==='employee'?state.tasks.filter(t=>t.assignedTo===state.ctx.id):state.tasks;
 const open=mine.filter(t=>t.status!=='completed'), closed=mine.filter(t=>t.status==='completed');
 const activeProjects=state.projects.filter(p=>p.status==='active');
 const today=mine.filter(t=>t.status!=='completed'&&(sameDay(t.dueAt)||sameDay(t.startAt)));
 const overdue=open.filter(t=>t.dueAt&&new Date(t.dueAt)<new Date());
 const issues=state.records.filter(r=>r.kind==='issues'&&!['closed','resolved'].includes(String(r.status||'').toLowerCase()));
 const approvals=state.records.filter(r=>r.kind==='approvals'&&String(r.status||'').toLowerCase().includes('pending'));
 const upcoming=[...state.events].filter(e=>new Date(e.startAt)>=new Date()).slice(0,8);
 return `${heading(state.ctx.role==='client'?'Your work, deadlines and communication in one place.':'Global dashboard — clients, projects, tasks, people and deadlines at a glance.')}
 <div class="home-actions">${state.ctx.role!=='client'?'<button class="primary" onclick="taskModal()">＋ Add Task</button>':''}<button onclick="go('projects')">Projects</button><button onclick="go('calendar')">Calendar</button><button onclick="go('reports')">Reports</button></div>
 <div class="zoho-stats">${dashTile('Accessible Clients',state.clients.length,state.ctx.role==='employee'?'Assigned to you':'Visible in your hierarchy',`go('clients')`)}${dashTile('Open Tasks',open.length,overdue.length+' overdue',`openTasksWith('status','open')`)}${dashTile('Projects',state.projects.length,activeProjects.length+' active',`go('projects')`)}${dashTile("Today's Tasks",today.length,'Due or starting today',`openTasksWith('timespan','today')`)}${dashTile('Unread Notifications',state.notifications.filter(n=>!n.read).length,'Recent changes',`go('updates')`)}${dashTile('My Open Tasks',state.ctx.role==='employee'?open.length:state.tasks.filter(t=>t.assignedTo===state.ctx.id&&t.status!=='completed').length,'Assigned to me',`openTasksWith('owner','${state.ctx.id}')`)}${dashTile('Closed Tasks',closed.length,'Completed work',`openTasksWith('status','completed')`)}${dashTile('Open Issues',issues.length,'Needs attention',`go('issues')`)}${dashTile('Pending Approvals',approvals.length,'Waiting for action',`go('approvals')`)}</div>
 <div class="dashboard-columns"><section class="panel"><div class="section-title"><h2>Today's tasks</h2><div>${state.ctx.role!=='client'?'<button class="primary small-btn" onclick="taskModal()">＋ Add Task</button>':''}<button onclick="openTasksWith('timespan','today')">View all →</button></div></div>${today.slice(0,12).map(t=>`<button class="today-task" onclick="${state.ctx.role!=='client'?`taskModal('${t.id}')`:`go('tasks')`}"><span class="avatar tiny">${initials(t.assignedName||'TF')}</span><div><strong>${esc(t.title)}</strong><small>${esc(t.clientName)}${t.projectName?' · '+esc(t.projectName):''}</small></div>${badge(taskStatusLabel(t.status))}<time>${shortDate(t.dueAt||t.startAt)}</time></button>`).join('')||'<div class="empty compact">No tasks due today.</div>'}</section>
 <section class="panel"><div class="section-title"><h2>My work items due today</h2><button onclick="go('calendar')">Calendar →</button></div>${today.slice(0,10).map(t=>`<div class="work-item"><span>☑</span><div><strong>${esc(t.title)}</strong><small>${esc(t.clientName)}</small></div><time>${shortDate(t.dueAt||t.startAt)}</time></div>`).join('')||'<div class="empty compact">Nothing due today.</div>'}<div class="section-title dashboard-subtitle"><h2>Upcoming calendar</h2></div>${upcoming.slice(0,5).map(e=>`<button class="work-item" onclick="go('calendar')"><span>▣</span><div><strong>${esc(e.title)}</strong><small>${esc(e.clientName)} · ${esc(e.eventTypeLabel)}</small></div><time>${shortDate(e.startAt)}</time></button>`).join('')||'<div class="empty compact">No upcoming events.</div>'}</section></div>
 <div class="panel"><div class="section-title"><h2>Workspace</h2><span class="hint">Every module is clickable</span></div><div class="module-grid">${moduleShortcut('projects','Projects, owners and progress')}${moduleShortcut('tasks','Task lists, owners and deadlines')}${moduleShortcut('issues','Track blockers and issues')}${moduleShortcut('phases','Delivery phases and milestones')}${moduleShortcut('timelogs','Daily work logs')}${moduleShortcut('timesheets','Employee timesheets')}${moduleShortcut('collaboration','Team/client collaboration')}${moduleShortcut('approvals','Approval queue')}${moduleShortcut('updates','Client and internal updates')}${moduleShortcut('notes','Client/project/task notes')}${moduleShortcut('reports','Operational reports')}${['admin','manager'].includes(state.ctx.role)?moduleShortcut('team','Users and hierarchy'):''}</div></div>`;
}

function taskFilterBar(){
 const employees=state.members.filter(m=>['employee','manager'].includes(m.role));
 return `<div class="task-toolbar"><div class="task-filter-row"><input class="filter-search" value="${esc(taskUI.search)}" placeholder="Search task, client, project…" oninput="setTaskFilter('search',this.value)"><select onchange="setTaskFilter('client',this.value)"><option value="">All clients</option>${state.clients.map(c=>`<option value="${c.id}" ${taskUI.client===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select><select onchange="setTaskFilter('owner',this.value)"><option value="">All owners</option>${employees.map(m=>`<option value="${m.id}" ${String(taskUI.owner)===String(m.id)?'selected':''}>${esc(m.name)}</option>`).join('')}</select><select onchange="setTaskFilter('status',this.value)"><option value="all">All statuses</option><option value="open" ${taskUI.status==='open'?'selected':''}>Open</option>${['todo','in_progress','review','blocked','completed'].map(x=>`<option value="${x}" ${taskUI.status===x?'selected':''}>${taskStatusLabel(x)}</option>`).join('')}</select><select onchange="setTaskFilter('priority',this.value)"><option value="">All priorities</option>${['low','normal','high','urgent'].map(x=>`<option value="${x}" ${taskUI.priority===x?'selected':''}>${x[0].toUpperCase()+x.slice(1)}</option>`).join('')}</select><select onchange="setTaskFilter('timespan',this.value)"><option value="all">Any time</option><option value="today" ${taskUI.timespan==='today'?'selected':''}>Today</option><option value="week" ${taskUI.timespan==='week'?'selected':''}>Next 7 days</option><option value="overdue" ${taskUI.timespan==='overdue'?'selected':''}>Overdue</option></select><button onclick="resetTaskFilters()">Clear</button></div><div class="task-view-actions"><button class="${taskUI.view==='list'?'active':''}" onclick="taskUI.view='list';render()">☷ List</button><button class="${taskUI.view==='board'?'active':''}" onclick="taskUI.view='board';render()">▦ Board</button>${state.ctx.role!=='client'?'<button class="primary" onclick="taskModal()">＋ Add Task</button>':''}</div></div>`;
}
function tasks(){
 const rows=filteredTasks();
 let content='';
 if(taskUI.view==='board'){
   const groups=['todo','in_progress','review','blocked','completed'];
   content=`<div class="board">${groups.map(g=>`<section class="lane"><h3>${taskStatusLabel(g)} <span>${rows.filter(t=>t.status===g).length}</span></h3>${rows.filter(t=>t.status===g).map(t=>`<article class="task-card"><span class="eyebrow">${esc(t.clientName)}</span><h4>${esc(t.title)}</h4><p>${esc(t.description||'')}</p><small>${esc(t.assignedName||'Unassigned')} · ${shortDate(t.dueAt)}</small>${state.ctx.role!=='client'?`<button onclick="taskModal('${t.id}')">Open task</button>`:''}</article>`).join('')||'<div class="empty compact">No tasks</div>'}</section>`).join('')}</div>`;
 }else{
   content=`<div class="panel task-table-wrap"><table class="task-list-table"><thead><tr><th>Task</th><th>Project</th><th>Owner</th><th>Status</th><th>Priority</th><th>Start</th><th>Due</th><th>Duration</th></tr></thead><tbody>${rows.map(t=>{let hrs=Number(t.estimatedHours||0);return `<tr class="click-row" onclick="${state.ctx.role!=='client'?`taskModal('${t.id}')`:`void(0)`}"><td><strong>${esc(t.title)}</strong><small>${esc(t.clientName)}</small></td><td>${esc(t.projectName||'—')}</td><td><span class="owner-pill"><i>${initials(t.assignedName||'NA')}</i>${esc(t.assignedName||'Unassigned')}</span></td><td>${badge(taskStatusLabel(t.status))}</td><td>${badge(t.priorityLabel||t.priority)}</td><td>${shortDate(t.startAt)}</td><td class="${t.status!=='completed'&&t.dueAt&&new Date(t.dueAt)<new Date()?'overdue-text':''}">${shortDate(t.dueAt)}</td><td>${hrs?hrs+' h':'—'}</td></tr>`}).join('')||'<tr><td colspan="8"><div class="empty compact">No tasks match the selected filters.</div></td></tr>'}</tbody></table></div>`;
 }
 return `${heading('Zoho-style task workspace with list/board views, owners, dates, priority and advanced filters.')}${taskFilterBar()}${content}`;
}

function legacy(kind){
 let rs=state.records.filter(r=>r.kind===kind);
 return `${heading(({issues:'Track blockers, ownership and resolution status.',phases:'Manage delivery phases and milestones.',timelogs:'Record work performed against clients and projects.',timesheets:'Review employee time by date and client.',collaboration:'Keep structured team and client collaboration in one place.',approvals:'Manage pending, approved and rejected work.'})[kind]||'This module uses the same hierarchy-aware client visibility rules.')}${toolbar(state.ctx.role!=='client'||['tickets','content','collaboration'].includes(kind)?`<button class="primary" onclick="legacyModal('${kind}')">＋ Add ${esc(labels[kind]||kind)}</button>`:'')}<div class="cards">${rs.map(r=>`<article class="record-card clickable-card" onclick="legacyModal('${kind}')"><div class="record-top"><span class="eyebrow">${esc(r.client||'org')}</span>${badge(r.status)}</div><h3>${esc(r.title)}</h3><p>${esc(r.detail||r.body||'')}</p><div class="meta"><span>${esc(r.owner||'')}</span><span>${esc(r.date||'')}</span></div>${kind==='files'&&r.hasAttachment?`<button onclick="event.stopPropagation();window.location='/api/file/${encodeURIComponent(r.id)}/'">Download</button>`:''}</article>`).join('')||'<div class="empty">No records in this module yet. Use the Add button to create one.</div>'}</div>`;
}

window.setTaskFilter=setTaskFilter; window.resetTaskFilters=resetTaskFilters; window.openTasksWith=openTasksWith; window.taskUI=taskUI;

$('#bellBtn').onclick=()=>go('updates');window.go=go;window.state=state;window.render=render;window.closeModal=closeModal;window.clientModal=clientModal;window.memberModal=memberModal;window.assignmentModal=assignmentModal;window.removeAssignment=removeAssignment;window.projectModal=projectModal;window.taskModal=taskModal;window.setTaskStatus=setTaskStatus;window.updateModal=updateModal;window.noteModal=noteModal;window.eventModal=eventModal;window.legacyModal=legacyModal;load();


// Persistent Zoho-inspired light/dark theme.
(function initThemeToggle(){
  const root=document.documentElement;
  const button=document.getElementById('themeToggle');
  const label=document.getElementById('themeLabel');
  function current(){return root.dataset.theme==='light'?'light':'dark'}
  function sync(){
    const t=current();
    if(label) label.textContent=t==='dark'?'Dark':'Light';
    if(button){
      button.setAttribute('aria-pressed',String(t==='dark'));
      button.title=t==='dark'?'Switch to light mode':'Switch to dark mode';
    }
  }
  if(button) button.addEventListener('click',()=>{
    const next=current()==='dark'?'light':'dark';
    root.dataset.theme=next;
    try{localStorage.setItem('techfinitys-theme',next)}catch(e){}
    sync();
  });
  sync();
})();

// Premium interaction layer: keyboard shortcuts and refined feedback.
(function initPremiumUX(){
  // Escape closes open modal.
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape' && document.querySelector('.overlay')) closeModal();
    // Alt + T opens a new task from anywhere employees/managers/admins can create one.
    if(e.altKey && e.key.toLowerCase()==='t' && state.ctx && ['admin','manager'].includes(state.ctx.role)){
      e.preventDefault();
      taskModal();
    }
    // Alt + H returns to dashboard.
    if(e.altKey && e.key.toLowerCase()==='h'){
      e.preventDefault();
      go('overview');
    }
  });

  // Add descriptive tooltips without cluttering the UI.
  const enhance=()=>{
    const addTask=[...document.querySelectorAll('button')].find(b=>/add task|new task/i.test(b.textContent||''));
    if(addTask && !addTask.title) addTask.title='Add task (Alt + T)';
    const brand=document.querySelector('.brand');
    if(brand && !brand.title) brand.title='Go to dashboard (Alt + H)';
  };

  const observer=new MutationObserver(()=>enhance());
  observer.observe(document.body,{childList:true,subtree:true});
  enhance();
})();

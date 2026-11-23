/* Techfinitys Project Studio — a relational, Zoho-inspired delivery workspace.
 * No third-party browser dependencies. No mock business data. */
(() => {
  const apiPlus = '/api/projects-plus/';
  const ui = {
    project: '', projectTab: 'dashboard', projectQuery: '', projectStatus: 'all',
    projectGroup: '', projectSort: 'title', projectDesc: false, projectPage: 1,
    view: 'list', sort: 'dueAt', desc: false, page: 1, groupBy: 'taskList',
    drawer: false, selected: new Set(), collapsed: new Set(),
    filters: { status: 'open', search: '', logic: 'all' },
    homeTaskQuery: '', homeTaskStatus: 'all', homeTaskLimit: 15,
    issuesStatus: 'open', feedProject: '', taskProject: '', quickBusy: false,
  };
  const isStaff = () => state.ctx?.role !== 'client';
  const isManager = () => ['admin', 'manager'].includes(state.ctx?.role);
  const isEmployee = () => state.ctx?.role === 'employee';
  const isMyTask = t => String(t.assignedTo)===String(roleId()) || (t.assigneeIds||[]).some(id=>String(id)===String(roleId()));
  const canChangeTask = t => isManager() || (isEmployee() && isMyTask(t));
  const arr = key => state[key] || [];
  const safe = value => esc(value ?? '');
  const date = value => value ? new Date(value).toLocaleDateString('en-IN', {day:'2-digit',month:'short',year:'numeric'}) : '—';
  const fmt = value => value ? new Date(value).toLocaleString('en-IN', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
  const iso = value => (value || '').slice(0,10);
  const today = () => state.serverToday || new Date().toISOString().slice(0,10);
  const titleStatus = v => ({todo:'Open',in_progress:'In progress',review:'In review',blocked:'Blocked',completed:'Completed',planned:'Planned',active:'Active',on_hold:'On hold',open:'Open',resolved:'Resolved',closed:'Closed'})[v] || (v || '—');
  const statusPill = s => `<span class="tf-status tf-${safe(s)}">${safe(titleStatus(s))}</span>`;
  const empty = (heading,detail='') => `<div class="tf-empty"><span class="tf-empty-icon">✧</span><strong>${safe(heading)}</strong><p>${safe(detail)}</p></div>`;
  const teamName = x => x?.assignedName || 'Unassigned';
  const projectBy = id => state.projects.find(p => p.id === id);
  const projectTasks = id => state.tasks.filter(t => t.projectId === id);
  const projectIssues = id => arr('projectIssues').filter(i => i.projectId === id);
  const taskLists = id => arr('taskLists').filter(l => l.projectId === id).sort((a,b) => a.position - b.position);
  const roleId = () => state.ctx?.id;
  const memberOptions = (value, all=false, projectId='') => {
    const project=projectBy(projectId);
    const assigned=new Set(arr('assignments').filter(a=>a.clientId===project?.clientId).map(a=>String(a.employeeId)));
    return `<option value="">Unassigned</option>` + state.members.filter(m=>['employee','manager','admin'].includes(m.role) && (all || !project || m.role!=='employee' || assigned.has(String(m.id)))).map(m=>`<option value="${m.id}" ${String(m.id)===String(value)?'selected':''}>${safe(m.name)}</option>`).join('');
  };
  const select = (name, options, current='',placeholder='All') => `<select name="${safe(name)}"><option value="">${safe(placeholder)}</option>${options.map(o=>`<option value="${safe(o.value)}" ${String(o.value)===String(current)?'selected':''}>${safe(o.label)}</option>`).join('')}</select>`;
  const getProjectScope=()=>ui.project&&projectBy(ui.project)?ui.project:'';
  const hours = mins => `${Math.floor((mins||0)/60)}h ${Math.round((mins||0)%60)}m`;
  const minutes = entries => entries.reduce((sum,t)=>sum+(Number(t.minutes)||0),0);
  const fmtCount = value => new Intl.NumberFormat('en-IN').format(value||0);
  const percentBar = n => `<span class="tf-progress"><i style="width:${Math.max(0,Math.min(100,n||0))}%"></i></span>`;
  const header=(label,sub,actions='')=>`<div class="tf-header"><div><div class="tf-overline">TECHFINITYS / PROJECT STUDIO</div><h1>${safe(label)}</h1><p>${safe(sub)}</p></div><div class="tf-header-actions">${actions}</div></div>`;
  const button=(label,onclick,kind='')=>`<button type="button" class="tf-btn ${kind}" onclick="${onclick}">${label}</button>`;
  const boxTitle=(name,extra='')=>`<div class="tf-panel-header"><h3>${safe(name)}</h3><div class="tf-panel-actions">${extra}</div></div>`;

  async function fetchJSON(url,options={}){
    const r=await fetch(url,options);
    const data=await r.json().catch(()=>({error:'The server did not return JSON'}));
    if(!r.ok)throw Error(data.error||`Server error ${r.status}`);
    return data;
  }
  async function plusPost(data){
    const result=await fetchJSON(apiPlus,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:JSON.stringify(data)});
    state.notice='Changes saved successfully'; await load(); return result;
  }
  async function opsPost(data){
    const result=await fetchJSON('/api/operations/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:JSON.stringify(data)});
    state.notice='Changes saved successfully'; await load(); return result;
  }
  function error(err){const msg=document.getElementById('tfFormError');if(msg){msg.textContent=err.message||String(err);msg.hidden=false;}else alert(err.message||String(err));}
  function formModal(name,subtitle,inner,onSubmit,saveLabel='Save changes'){
    openModal(`<div class="tf-form-modal"><span class="tf-overline">TECHFINITYS / PROJECT STUDIO</span><h2>${safe(name)}</h2><p>${safe(subtitle)}</p><form id="tfModalForm">${inner}<p id="tfFormError" class="tf-form-error" role="alert" hidden></p><div class="tf-form-actions"><button type="button" onclick="closeModal()">Cancel</button><button type="submit" class="primary">${safe(saveLabel)}</button></div></form></div>`);
    const form=document.getElementById('tfModalForm');
    form.addEventListener('submit',async event=>{
      event.preventDefault();const submit=form.querySelector('[type="submit"]');submit.disabled=true;
      try { await onSubmit(form,new FormData(form)); closeModal(); }
      catch(ex){error(ex);submit.disabled=false;}
    });
  }
  function taskStat(tasks){const done=tasks.filter(t=>t.status==='completed').length;return {done,open:tasks.length-done,total:tasks.length,percent:tasks.length?Math.round(done/tasks.length*100):0};}
  function projectCounter(p){const tasks=projectTasks(p.id),st=taskStat(tasks);return {tasks, ...st, issues:projectIssues(p.id).filter(i=>!['resolved','closed'].includes(i.status)).length};}

  function projectList(){
    const q=ui.projectQuery.toLowerCase().trim();let rows=state.projects.filter(p=>
      (!q||[p.title,p.clientName,p.ownerName,p.code,p.groupName,(p.tags||[]).join(' ')].some(x=>String(x||'').toLowerCase().includes(q)))&&
      (ui.projectStatus==='all'||p.status===ui.projectStatus)&&(!ui.projectGroup||p.groupName===ui.projectGroup));
    const sorter={title:p=>p.title.toLowerCase(),code:p=>p.code,owner:p=>p.ownerName.toLowerCase(),progress:p=>p.progress,
      tasks:p=>projectTasks(p.id).length,issues:p=>projectCounter(p).issues,started:p=>p.startDate||'',due:p=>p.dueDate||'',status:p=>p.status};
    rows.sort((a,b)=>{const x=sorter[ui.projectSort](a),y=sorter[ui.projectSort](b);return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(ui.projectDesc?-1:1)});
    const pageSize=25,pageCount=Math.max(1,Math.ceil(rows.length/pageSize));ui.projectPage=Math.min(pageCount,Math.max(1,ui.projectPage));
    const page=rows.slice((ui.projectPage-1)*pageSize,ui.projectPage*pageSize);
    const col=(k,t)=>`<button class="tf-column" onclick="TFPlus.sortProjects('${k}')">${t}${ui.projectSort===k?(ui.projectDesc?' ↓':' ↑'):''}</button>`;
    return `${header('Projects','A complete view of projects, teams, delivery progress and deadlines.',`${isManager()?`${button('↓ Export CSV',"location.href='/api/project-export/projects/'")}${button('＋ New project',"projectModal()",'primary')}`:''}`)}
      <section class="tf-pane tf-project-summary"><div class="tf-sparkline"></div><div><span>Active projects</span><strong>${state.projects.filter(p=>p.status==='active').length}</strong></div><div><span>Completed projects</span><strong>${state.projects.filter(p=>p.status==='completed').length}</strong></div><div><span>All open tasks</span><strong>${state.tasks.filter(t=>t.status!=='completed'&&(!isEmployee()||isMyTask(t))).length}</strong></div><div><span>Issues to resolve</span><strong>${arr('projectIssues').filter(i=>!['resolved','closed'].includes(i.status)).length}</strong></div></section>
      <section class="tf-pane tf-list-pane"><div class="tf-toolbar">
        <div class="tf-field-search"><span>⌕</span><input aria-label="Search projects" placeholder="Search projects, clients, owners…" value="${safe(ui.projectQuery)}" oninput="TFPlus.setProjectFilter('projectQuery',this.value)"></div>
        <select aria-label="Project status" onchange="TFPlus.setProjectFilter('projectStatus',this.value)">${[['all','All projects'],['active','Active'],['planned','Planned'],['on_hold','On hold'],['completed','Completed']].map(([v,t])=>`<option value="${v}" ${ui.projectStatus===v?'selected':''}>${t}</option>`).join('')}</select>
        <select aria-label="Project group" onchange="TFPlus.setProjectFilter('projectGroup',this.value)">${select('group',arr('projectGroups').map(x=>({value:x,label:x})),ui.projectGroup,'All groups').replace(/^<select[^>]*>/,'').replace(/<\/select>$/,'')}</select>
        ${button('▦ List view',"TFPlus.setProjectFilter('projectPage',1)",'muted')}
      </div><div class="tf-table-scroll"><table class="tf-grid tf-projects-table"><thead><tr>
        <th>${col('code','ID')}</th><th>${col('title','Project name')}</th><th>${col('progress','%')}</th><th>${col('owner','Owner')}</th><th>${col('status','Status')}</th><th>${col('tasks','Tasks')}</th><th>Phases</th><th>${col('issues','Issues')}</th><th>${col('started','Start date')}</th><th>${col('due','End date')}</th><th>Tags</th>
      </tr></thead><tbody>${page.map(p=>{const stats=projectCounter(p),phases=arr('milestones').filter(m=>m.projectId===p.id);return `<tr class="tf-interactive" onclick="TFPlus.openProject('${p.id}')" tabindex="0" onkeydown="if(event.key==='Enter')TFPlus.openProject('${p.id}')">
        <td><span class="tf-id">${safe(p.code)}</span></td><td><strong>${safe(p.title)}</strong><small>${safe(p.clientName)}${p.groupName?' / '+safe(p.groupName):''}</small></td><td><b>${stats.total?stats.percent:p.progress}%</b></td><td><span class="tf-owner"><i>${initials(p.ownerName||'TF')}</i>${safe(p.ownerName||'Unassigned')}</span></td><td>${statusPill(p.status)}</td><td><span class="tf-task-progress">${stats.done}/${stats.total}${percentBar(stats.percent)}</span></td><td>${phases.length?phases.filter(m=>m.status==='completed').length+'/'+phases.length:'No phases'}</td><td>${stats.issues?`<span class="tf-issue-count">${stats.issues} open</span>`:'No issues'}</td><td>${date(p.startDate)}</td><td>${date(p.dueDate)}</td><td>${(p.tags||[]).slice(0,2).map(t=>`<span class="tf-tag">${safe(t)}</span>`).join('')||'—'}</td>
      </tr>`}).join('')||`<tr><td colspan="11">${empty('No matching projects','Try adjusting your filters, or create a new project.')}</td></tr>`}</tbody></table></div>
      <div class="tf-footer-row"><span>${fmtCount(rows.length)} projects · 25 per page</span><div>${button('‹ Previous',`TFPlus.changeProjectPage(-1)`)}<span>Page ${ui.projectPage} of ${pageCount}</span>${button('Next ›',`TFPlus.changeProjectPage(1)`)}</div></div></section>`;
  }

  function openProject(id,tab='dashboard'){
    if(!projectBy(id))return;
    if(isEmployee()&&!['dashboard','tasks','documents','issues','feed'].includes(tab))tab='dashboard';
    ui.project=id;ui.projectTab=tab;ui.page=1;ui.selected.clear();state.tab='projects';render();
    try{history.replaceState(null,'','#projects/'+id+'/'+tab)}catch(_){}
  }
  function backProjects(){ui.project='';ui.taskProject='';ui.page=1;render();try{history.replaceState(null,'','#projects')}catch(_){}}
  function projectDetail(){
    const p=projectBy(ui.project);if(!p)return projectList();
    if(isEmployee()&&!['dashboard','tasks','documents','issues','feed'].includes(ui.projectTab))ui.projectTab='dashboard';
    const tabs=isEmployee()?[['dashboard','Dashboard'],['tasks','Tasks'],['documents','Documents'],['issues','Issues'],['feed','Feed']]:[['dashboard','Dashboard'],['tasks','Tasks'],['users','Users'],['reports','Reports'],['documents','Documents'],['phases','Phases'],['timelogs','Time Logs'],['issues','Issues'],['feed','Feed'],['timesheets','Timesheets'],['approvals','Approvals']];
    const buttons=isManager()?`${button('✎ Edit',`projectModal('${p.id}')`)}${button('＋ Add task',`TFPlus.taskEditor('','${p.id}')`,'primary')}`:state.ctx.role==='client'?button('＋ Support ticket',"go('tickets')",'primary'):'';
    const tabHtml={dashboard:()=>dashboard('project:'+p.id,p),tasks:()=>taskWorkspace(p.id),users:()=>projectUsers(p),reports:()=>projectReports(p),documents:()=>projectDocuments(p),phases:()=>projectPhases(p),timelogs:()=>projectTimeLogs(p),issues:()=>issueWorkspace(p.id),feed:()=>projectFeed(p),timesheets:()=>projectTimeLogs(p,true),approvals:()=>projectApprovals(p)}[ui.projectTab] || (()=>dashboard('project:'+p.id,p));
    return `<div class="tf-breadcrumb"><button onclick="TFPlus.backProjects()">Projects</button><span>›</span><span>${safe(p.code)} · ${safe(p.title)}</span></div>
      <div class="tf-project-hero"><div><div class="tf-overline">${safe(p.clientName)} ${p.groupName?'/ '+safe(p.groupName):''}</div><div class="tf-project-title"><h1>${safe(p.title)}</h1>${statusPill(p.status)}</div><p>${safe(p.description||'Deliverables, people and progress in one shared project space.')}</p><div class="tf-hero-info"><span>◉ ${safe(p.ownerName||'No owner')}</span><span>▣ Due ${date(p.dueDate)}</span><span>◈ ${p.progress}% complete</span></div></div><div class="tf-hero-actions">${buttons}</div></div>
      <nav class="tf-tabs" aria-label="Project sections">${tabs.map(([key,label])=>`<button class="${ui.projectTab===key?'active':''}" onclick="TFPlus.switchProjectTab('${key}')">${label}</button>`).join('')}</nav>
      <div class="tf-project-body">${tabHtml()}</div>`;
  }
  function switchProjectTab(key){if(isEmployee()&&!['dashboard','tasks','documents','issues','feed'].includes(key))return;ui.projectTab=key;ui.selected.clear();ui.page=1;render();try{history.replaceState(null,'','#projects/'+ui.project+'/'+key)}catch(_){}}
  function projects(){return getProjectScope()?projectDetail():projectList()}

  const filterFields = [
    ['taskName','Task name','text'],['taskId','Task ID','text'],['client','Client','client'],
    ['projectId','Project','project'],['projectGroup','Project group','projectGroup'],
    ['projectStatus','Project status','projectStatus'],['status','Status','status'],
    ['completion','Completion percentage','completion'],['owner','Owner','owner'],
    ['teamMember','Associated team','owner'],['priority','Priority','priority'],
    ['startDate','Start date','date'],['dueDate','Due date','date'],
    ['timespan','Time span','timespan'],['recurrence','Recurrence','recurrence'],
    ['createdTime','Created time','date'],['completionDate','Completion date','date'],
    ['modifiedTime','Last modified time','date'],['createdBy','Created by','owner'],
    ['taskList','Task list','list'],['tags','Tags','text'],['billingType','Billing type','billing'],
  ];
  function optionList(values,current,placeholder='Any'){
    return `<option value="">${safe(placeholder)}</option>`+values.map(([value,label])=>`<option value="${safe(value)}" ${String(current)===String(value)?'selected':''}>${safe(label)}</option>`).join('');
  }
  function filterControl(key,type){
    const value=ui.filters[key]||'';
    if(type==='date'||type==='text')return `<input class="tf-filter-input" data-filter="${key}" ${type==='date'?'type="date"':'type="text"'} value="${safe(value)}" placeholder="Search or enter value">`;
    const choices={
      status:[['open','All open'],...TaskStatus],priority:[['low','Low'],['normal','Normal'],['high','High'],['urgent','Urgent']],
      projectStatus:[['planned','Planned'],['active','Active'],['on_hold','On hold'],['completed','Completed']],
      completion:[['0-25','0–25%'],['26-50','26–50%'],['51-75','51–75%'],['76-99','76–99%'],['100','100%']],
      billing:[['billable','Billable'],['nonbillable','Non-billable']],
      recurrence:[['yes','Repeating'],['no','One-off']],
      timespan:[['overdue','Overdue'],['today','Today'],['week','Next 7 days'],['month','Next 30 days']],
      client:state.clients.map(c=>[c.id,c.name]),project:state.projects.map(p=>[p.id,p.title]),
      projectGroup:arr('projectGroups').map(g=>[g,g]),
      owner:state.members.filter(m=>m.role!=='client').map(m=>[String(m.id),m.name]),
      list:arr('taskLists').map(l=>[l.id,l.title+' · '+(projectBy(l.projectId)?.title||'')]),
    };
    return `<select class="tf-filter-input" data-filter="${key}">${optionList(choices[type]||[],value)}</select>`;
  }
  const TaskStatus=[['todo','Open'],['in_progress','In progress'],['review','In review'],['blocked','Blocked'],['completed','Completed']];
  function fieldMatch(t,key,value){
    const string=x=>String(x||'').toLowerCase();const contains=(x,y)=>string(x).includes(string(y));
    const project=projectBy(t.projectId)||{};
    switch(key){
      case 'taskName':return contains(t.title,value);
      case 'taskId':return contains(t.code,value);
      case 'client':return t.clientId===value;
      case 'projectId':return t.projectId===value;
      case 'projectGroup':return project.groupName===value;
      case 'projectStatus':return project.status===value;
      case 'status':return value==='all'?true:value==='open'?t.status!=='completed':t.status===value;
      case 'completion':{const p=Number(t.percentComplete)||0;if(value==='100')return p===100;const [lo,hi]=value.split('-').map(Number);return p>=lo&&p<=hi;}
      case 'owner':return String(t.assignedTo)===value;
      case 'teamMember':return String(t.assignedTo)===value||(t.assigneeIds||[]).some(x=>String(x)===value);
      case 'priority':return t.priority===value;
      case 'startDate':return iso(t.startAt)===value;
      case 'dueDate':return iso(t.dueAt)===value;
      case 'createdTime':return iso(t.createdAt)===value;
      case 'completionDate':return iso(t.completedAt)===value;
      case 'modifiedTime':return iso(t.updatedAt)===value;
      case 'createdBy':return String(t.createdBy)===value;
      case 'taskList':return t.taskListId===value;
      case 'tags':return (t.tags||[]).some(tag=>contains(tag,value));
      case 'billingType':return t.billingType===value;
      case 'recurrence':return value==='yes'?!!t.recurrence:!t.recurrence;
      case 'timespan':{const d=iso(t.dueAt);const day=today();if(!d)return false;
        if(value==='overdue')return t.status!=='completed'&&d<day;
        if(value==='today')return d===day;
        const next=new Date(day+'T12:00:00');next.setDate(next.getDate()+(value==='week'?7:30));
        return d>=day&&d<=next.toISOString().slice(0,10);
      }
      default:return true;
    }
  }
  function getFilteredTasks(projectId=''){
    const filters=Object.entries(ui.filters).filter(([k,v])=>v&&k!=='logic'&&k!=='search'&&v!=='all');
    const q=stringValue(ui.filters.search);let rows=state.tasks.filter(t=>(!projectId||t.projectId===projectId)&&(!isEmployee()||isMyTask(t)));
    if(q)rows=rows.filter(t=>[t.title,t.description,t.code,t.clientName,t.projectName,t.assignedName,(t.tags||[]).join(' ')].some(v=>stringValue(v).includes(q)));
    if(filters.length)rows=rows.filter(t=>ui.filters.logic==='any'?filters.some(([k,v])=>fieldMatch(t,k,v)):filters.every(([k,v])=>fieldMatch(t,k,v)));
    const sorts={dueAt:t=>t.dueAt||'9999',title:t=>t.title.toLowerCase(),status:t=>t.status,owner:t=>t.assignedName.toLowerCase(),priority:t=>({low:1,normal:2,high:3,urgent:4})[t.priority]||0,percent:t=>Number(t.percentComplete)||0,created:t=>t.createdAt||''};
    const key=sorts[ui.sort]||sorts.dueAt;
    rows.sort((a,b)=>{const x=key(a),y=key(b);return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(ui.desc?-1:1)});
    return rows;
  }
  function stringValue(s){return String(s||'').toLowerCase().trim();}
  function changeFilter(key,value){ui.filters[key]=value;ui.page=1;render();if(key==='search'){const el=document.getElementById('tfTaskSearch');if(el){el.focus();el.setSelectionRange(value.length,value.length)}}}
  function resetFilters(){ui.filters={status:'open',search:'',logic:'all'};ui.page=1;render()}
  function filterDrawer(){
    if(!ui.drawer)return '';
    const applied=Object.entries(ui.filters).filter(([k,v])=>v&&k!=='logic'&&k!=='search'&&v!=='all').length;
    return `<div class="tf-filter-scrim" onclick="TFPlus.closeFilters()"></div><aside class="tf-filter-drawer" role="dialog" aria-modal="true" aria-label="Advanced task filters">
      <div class="tf-filter-title"><h2>Advanced filters</h2>${button('Reset','TFPlus.resetFilters()')}</div>
      <p>Combine filters across people, projects, schedules and billing.</p>
      <div class="tf-filter-logic"><span>Match</span><label><input type="radio" name="tfLogic" value="any" ${ui.filters.logic==='any'?'checked':''}> Any of these</label><label><input type="radio" name="tfLogic" value="all" ${ui.filters.logic!=='any'?'checked':''}> All of these</label></div>
      <div class="tf-filter-field-list">${filterFields.map(([key,label,type])=>`<details ${ui.filters[key]?'open':''}><summary><span>${safe(label)}</span>${ui.filters[key]?'<i class="tf-active-filter">●</i>':'<span>›</span>'}</summary>${filterControl(key,type)}</details>`).join('')}</div>
      <div class="tf-filter-bottom"><span>${applied>0?applied+' active criteria':'Choose one or more criteria'}</span><div>${button('Cancel','TFPlus.closeFilters()')}${button('Find tasks','TFPlus.applyFilters()','primary')}</div></div>
    </aside>`;
  }
  function applyFilters(){
    for(const el of document.querySelectorAll('[data-filter]'))ui.filters[el.dataset.filter]=el.value;
    ui.filters.logic=document.querySelector('input[name="tfLogic"]:checked')?.value||'all';ui.page=1;ui.drawer=false;render();
  }
  function taskToolbar(projectId=''){
    const saved=arr('savedViews').filter(v=>v.module==='tasks');
    const active=Object.entries(ui.filters).filter(([k,v])=>v&&k!=='search'&&k!=='logic'&&v!=='all').length;
    return `<div class="tf-task-toolbar"><div class="tf-task-tools">
      <div class="tf-field-search"><span>⌕</span><input id="tfTaskSearch" aria-label="Search tasks" placeholder="Find task name, ID, project, owner…" value="${safe(ui.filters.search||'')}" oninput="TFPlus.changeFilter('search',this.value)"></div>
      <select aria-label="Task status" onchange="TFPlus.changeFilter('status',this.value)">${optionList([['open','All open'],['all','All tasks'],...TaskStatus],ui.filters.status||'','Any status')}</select>
      ${isManager()?`${button(`⚑ Filters${active?' ('+active+')':''}`,'TFPlus.openFilters()','filter')}${button('Reset filters','TFPlus.resetFilters()')}${button('☆ Save view','TFPlus.saveTaskView()')}<select aria-label="Saved views" onchange="TFPlus.loadTaskView(this.value)">${optionList(saved.map(v=>[String(v.id),v.name]),'','Saved views…')}</select>`:''}
    </div><div class="tf-task-tools">
      ${isManager()?`<select aria-label="Group tasks" onchange="TFPlus.changeGroup(this.value)">${optionList([['none','No grouping'],['taskList','By task list'],['project','By project'],['status','By status'],['owner','By owner']],ui.groupBy,'Group by…')}</select>`:''}
      ${button('☷ List',"TFPlus.setView('list')",ui.view==='list'?'selected':'')}${button('▦ Board',"TFPlus.setView('board')",ui.view==='board'?'selected':'')}
      ${isManager()?button('＋ Add task',`TFPlus.taskEditor('','${projectId}')`,'primary'):''}
    </div></div>`;
  }
  // Draft entry lives *inside* the task table. Save on Enter or with the Add button;
  // leaving the field does not unexpectedly create a client-visible task.
  function quickTaskRow(projectId,taskListId='',listName='General'){
    return `<tr class="tf-quick-task-row"><td></td><td class="tf-quick-plus">＋</td>
      <td class="tf-quick-title"><div class="tf-quick-wrap">
        <input class="tf-quick-input" data-project-id="${safe(projectId)}" data-list-id="${safe(taskListId)}"
          type="text" maxlength="220" autocomplete="off" aria-label="Add task to ${safe(listName||'General')}"
          placeholder="Add task…" onkeydown="TFPlus.quickTaskKey(event,this)">
        <button type="button" class="tf-quick-save" onclick="TFPlus.quickTaskButton(this)" title="Save task" aria-label="Save new task">Add ↵</button>
      </div></td><td colspan="8"><span class="tf-quick-hint">${safe(listName||'General')} · Enter to add · Esc to clear</span></td></tr>`;
  }
  function taskDateControl(t,field){
    if(!isManager())return date(t[field]);
    const label=field==='startAt'?'start':'due';
    const value=iso(t[field]);
    return `<span class="tf-date-editor"><button type="button" class="tf-date-trigger" aria-label="Edit ${label} date for ${safe(t.title)}"
      onclick="TFPlus.openTaskDatePicker(this)"><span>${value?date(t[field]):'Set date'}</span><span class="tf-date-icon" aria-hidden="true">▦</span></button>
      <input class="tf-date-native" type="date" value="${safe(value)}" aria-label="${label} date for ${safe(t.title)}"
        onchange="TFPlus.saveTaskDate(this,'${t.id}','${field}')" onkeydown="if(event.key==='Escape')this.blur()" /></span>`;
  }
  function openTaskDatePicker(button){
    const input=button.closest('.tf-date-editor')?.querySelector('input[type="date"]');
    if(!input)return;
    try{if(typeof input.showPicker==='function')input.showPicker();else input.focus();}
    catch(_){input.focus();input.click();}
  }
  async function saveTaskDate(input,taskId,field){
    if(!isManager())return;
    const task=state.tasks.find(t=>t.id===taskId);if(!task)return;
    const value=input.value||'',previous=iso(task[field]);
    if(value===previous)return;
    input.disabled=true;
    try{await plusPost({action:'set_task_date',taskId,field,date:value});}
    catch(ex){input.value=previous;input.disabled=false;error(ex);}
  }
  async function quickCreateTask(input){
    if(!isManager()||!input||ui.quickBusy)return;
    const title=String(input.value||'').trim();
    if(!title){input.focus();return;}
    if(title.length>220){error(new Error('Task name must be 220 characters or fewer'));return;}
    const projectId=input.dataset.projectId||'',taskListId=input.dataset.listId||'';
    if(!projectId){error(new Error('Open a project before adding a task inline'));return;}
    ui.quickBusy=true;input.disabled=true;
    const addButton=input.closest('tr')?.querySelector('.tf-quick-save');if(addButton)addButton.disabled=true;
    try{
      await plusPost({action:'quick_create_task',projectId,taskListId,title});
      const next=[...document.querySelectorAll('.tf-quick-input')].find(el=>el.dataset.projectId===projectId&&el.dataset.listId===taskListId);
      if(next)next.focus();
    }catch(ex){input.disabled=false;if(addButton)addButton.disabled=false;error(ex);input.focus();}
    finally{ui.quickBusy=false;}
  }
  function quickTaskKey(event,input){
    if(event.key==='Enter'){event.preventDefault();event.stopPropagation();quickCreateTask(input);}
    else if(event.key==='Escape'){input.value='';input.blur();}
  }
  function quickTaskButton(button){quickCreateTask(button.closest('tr')?.querySelector('.tf-quick-input'));}

  function taskGrid(rows,projectId=''){
    const size=25,group=ui.groupBy||'none',groups=new Map();
    const groupKey=t=>group==='taskList'?(t.taskListId?(arr('taskLists').find(x=>x.id===t.taskListId)?.title||'General'):'General'):
        group==='project'?(t.projectName||'No project'):group==='status'?titleStatus(t.status):group==='owner'?teamName(t):'All tasks';
    rows.forEach(t=>{const key=groupKey(t);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(t)});
    const all=rows.length;const count=Math.max(1,Math.ceil(all/size));ui.page=Math.min(ui.page,count);
    const ordered=[...groups.values()].flat();const visible=ordered.slice((ui.page-1)*size,ui.page*size);
    const head=(field,label)=>`<button class="tf-column" onclick="TFPlus.sortTasks('${field}')">${label}${ui.sort===field?(ui.desc?' ↓':' ↑'):''}</button>`;
    let tr='';let previous='',previousListId='';
    for(const t of visible){const current=groupKey(t);if(group!=='none'&&current!==previous){
      if(previous&&projectId&&isManager()&&group==='taskList')tr+=quickTaskRow(projectId,previousListId,previous);
      previous=current;previousListId=t.taskListId||'';
      tr+=`<tr class="tf-group-row"><td colspan="11">⌄ <strong>${safe(current)}</strong> <small>${groups.get(current)?.length||0} tasks</small></td></tr>`;
    }

      const overdue=t.dueAt&&iso(t.dueAt)<today()&&t.status!=='completed';
      tr+=`<tr class="tf-interactive" onclick="TFPlus.taskEditor('${t.id}')"><td class="tf-check-td" onclick="event.stopPropagation()">${isManager()?`<input type="checkbox" aria-label="Select task ${safe(t.title)}" ${ui.selected.has(t.id)?'checked':''} onchange="TFPlus.toggleTask('${t.id}',this.checked)">`:''}</td>
        <td><span class="tf-id">${safe(t.code)}</span></td><td class="tf-task-name"><strong>${safe(t.title)}</strong><small>${safe(t.projectName||t.clientName)}${t.parentId?' · Subtask':''}</small></td>
        <td>${safe(t.projectName||'—')}</td><td><span class="tf-owner"><i>${initials(teamName(t))}</i><span>${safe(teamName(t))}</span>${t.assigneeIds?.length?`<small>+${t.assigneeIds.length}</small>`:''}</span></td>
        <td onclick="event.stopPropagation()">${canChangeTask(t)?`<select class="tf-status-select tf-${safe(t.status)}" aria-label="Task status" onchange="TFPlus.setTaskStatus('${t.id}',this.value)">${TaskStatus.map(([v,label])=>`<option value="${v}" ${v===t.status?'selected':''}>${label}</option>`).join('')}</select>`:statusPill(t.status)}</td>
        <td>${(t.tags||[]).slice(0,2).map(tag=>`<span class="tf-tag">${safe(tag)}</span>`).join('')||'—'}</td>
        <td onclick="event.stopPropagation()">${taskDateControl(t,'startAt')}</td><td onclick="event.stopPropagation()" class="${overdue?'tf-overdue':''}">${taskDateControl(t,'dueAt')}${overdue?'<small>Overdue</small>':''}</td>
        <td>${t.estimatedHours?`${t.estimatedHours}h`:'—'}</td><td>${statusPill(t.priority)}</td></tr>`;
    }
    // Keep one entry row at the end of each task list, as in spreadsheet-style project tools.
    if(projectId&&isManager())tr+=quickTaskRow(projectId,group==='taskList'?previousListId:'',group==='taskList'?previous:'General');
    return `<section class="tf-pane tf-list-pane"><div class="tf-list-title"><span>Group by: <b>${safe(group==='taskList'?'Task List':group==='none'?'None':group)}</b> · ${fmtCount(all)} tasks</span>${isManager()&&projectId?button('＋ Add task list',`TFPlus.taskListModal('${projectId}')`):''}</div>
      ${ui.selected.size&&isManager()?`<div class="tf-bulk-bar"><b>${ui.selected.size} selected</b>${button('Mark completed',"TFPlus.bulkStatus('completed')",'primary')}${button('In progress',"TFPlus.bulkStatus('in_progress')")}${button('Clear',"TFPlus.clearSelection()")}</div>`:''}
      <div class="tf-table-scroll"><table class="tf-grid tf-task-table"><thead><tr><th class="tf-check-td">${isManager()?`<input type="checkbox" aria-label="Select visible tasks" onchange="TFPlus.selectVisibleTasks(this.checked)">`:''}</th><th>ID</th><th>${head('title','Task name')}</th><th>Project</th><th>${head('owner','Owner')}</th><th>${head('status','Status')}</th><th>Tags</th><th>Start date</th><th>${head('dueAt','Due date')}</th><th>Duration</th><th>${head('priority','Priority')}</th></tr></thead><tbody>${tr||`<tr><td colspan="11">${empty('No tasks found','Change filters or create your first task.')}</td></tr>`}</tbody></table></div>
      <div class="tf-footer-row"><span>${fmtCount(all)} tasks · ${size} per page</span><div>${button('‹ Previous',"TFPlus.pageTasks(-1)")}<span>Page ${ui.page} of ${count}</span>${button('Next ›',"TFPlus.pageTasks(1)")}</div></div></section>`;
  }
  function boardView(rows){
    return `<div class="tf-kanban">${TaskStatus.map(([status,label])=>{const cards=rows.filter(t=>t.status===status);return `<section class="tf-kanban-lane"><h3>${label}<span>${cards.length}</span></h3>${cards.map(t=>`<button class="tf-kanban-card" onclick="TFPlus.taskEditor('${t.id}')"><span class="tf-id">${safe(t.code)}</span><strong>${safe(t.title)}</strong><small>${safe(t.projectName||t.clientName)}</small><div>${statusPill(t.priority)}<span>◷ ${date(t.dueAt)}</span></div><div class="tf-kanban-owner"><i>${initials(teamName(t))}</i>${safe(teamName(t))}</div></button>`).join('')||empty('Empty lane')}</section>`}).join('')}</div>`;
  }
  function taskWorkspace(projectId=''){
    const rows=getFilteredTasks(projectId);
    return `${taskToolbar(projectId)}${ui.view==='board'?boardView(rows):taskGrid(rows,projectId)}${!isEmployee()?filterDrawer():''}`;
  }
  function tasks(){return `${header(isEmployee()?'My tasks':'Tasks',isEmployee()?'Your assigned tasks, deadlines, and progress. Select any row to open its details.':'Plan, group, assign, filter and deliver every work item.',isManager()?`<a class="tf-btn" href="/api/project-export/tasks/">↓ Export tasks</a>`:'')}${taskWorkspace('')}`}

  function taskEditor(id='',fixedProject=''){
    const t=state.tasks.find(x=>x.id===id)||{};
    if(id&&!t.id)return;
    if(isEmployee()&&!id)return;
    if(!isManager()){
      openModal(`<div class="tf-form-modal"><span class="tf-overline">TASK / ${safe(t.code)}</span><h2>${safe(t.title)}</h2><p>${safe(t.description||'No description')}</p>
        <div class="tf-readonly"><div>Status ${statusPill(t.status)}</div><div>Priority ${statusPill(t.priority)}</div><div>Owner <b>${safe(teamName(t))}</b></div><div>Project <b>${safe(t.projectName||t.clientName)}</b></div><div>Due <b>${date(t.dueAt)}</b></div></div><div class="tf-task-detail-actions">${isEmployee()&&canChangeTask(t)?`${t.status!=='in_progress'?button('Start work',`closeModal();TFPlus.setTaskStatus('${t.id}','in_progress')`,'primary'):''}${t.status!=='completed'?button('Mark completed',`closeModal();TFPlus.setTaskStatus('${t.id}','completed')`,'primary'):''}`:''}${button('Close','closeModal()')}</div></div>`);
      return;
    }
    const p=projectBy(fixedProject||t.projectId);
    const client=p?.clientId||t.clientId||state.clients[0]?.id||'';
    const projects=state.projects.filter(x=>x.clientId===client);
    const lists=taskLists(p?.id||t.projectId);
    const members=state.members.filter(m=>['employee','manager','admin'].includes(m.role));
    const chosen=new Set((t.assigneeIds||[]).map(String));
    formModal(id?'Edit task':'New task','Changes are saved directly to the project and notify the assigned employee.',
      `<label>Task name<input name="title" maxlength="220" value="${safe(t.title)}" required></label>
      <div class="tf-form-grid"><label>Client<select name="clientId" ${p?'disabled':''}>${state.clients.map(c=>`<option value="${c.id}" ${c.id===client?'selected':''}>${safe(c.name)}</option>`).join('')}</select>${p?`<input type="hidden" name="clientId" value="${p.clientId}">`:''}</label>
      <label>Project<select name="projectId" id="tfTaskProjectSelect" ${fixedProject?'disabled':''}><option value="">General workspace</option>${projects.map(x=>`<option value="${x.id}" ${x.id===(p?.id||t.projectId)?'selected':''}>${safe(x.title)}</option>`).join('')}</select>${fixedProject?`<input type="hidden" name="projectId" value="${p.id}">`:''}</label>
      <label>Task list<select name="taskListId" id="tfTaskListSelect">${optionList(lists.map(l=>[l.id,l.title]),t.taskListId,'General')}</select></label>
      <label>Status<select name="status">${TaskStatus.map(([v,label])=>`<option value="${v}" ${t.status===v?'selected':''}>${label}</option>`).join('')}</select></label>
      <label>Primary owner<select name="assignedTo">${memberOptions(t.assignedTo,false,p?.id||t.projectId)}</select></label>
      <label>Priority<select name="priority">${[['low','Low'],['normal','Normal'],['high','High'],['urgent','Urgent']].map(([v,label])=>`<option value="${v}" ${(t.priority||'normal')===v?'selected':''}>${label}</option>`).join('')}</select></label>
      <label>Start date & time<input name="startAt" type="datetime-local" value="${safe((t.startAt||'').slice(0,16))}"></label>
      <label>Due date & time<input name="dueAt" type="datetime-local" value="${safe((t.dueAt||'').slice(0,16))}"></label>
      <label>Estimate (hours)<input name="estimatedHours" type="number" min="0" max="20000" step="0.25" value="${t.estimatedHours||0}"></label>
      <label>Completion %<input name="percentComplete" type="number" min="0" max="100" value="${t.percentComplete||0}"></label>
      <label>Billing type<select name="billingType"><option value="billable" ${t.billingType!=='nonbillable'?'selected':''}>Billable</option><option value="nonbillable" ${t.billingType==='nonbillable'?'selected':''}>Non-billable</option></select></label>
      <label>Repeat<select name="recurrence"><option value="">Does not repeat</option>${['daily','weekly','monthly'].map(v=>`<option value="${v}" ${t.recurrence===v?'selected':''}>${v}</option>`).join('')}</select></label></div>
      <label>Collaborators <small>Ctrl / Command-click to select multiple</small><select name="assigneeIds" multiple size="4">${members.filter(m=>m.role!=='employee'||!p||arr('assignments').some(a=>a.clientId===p.clientId&&a.employeeId===m.id)).map(m=>`<option value="${m.id}" ${chosen.has(String(m.id))?'selected':''}>${safe(m.name)}</option>`).join('')}</select></label>
      <label>Tags (comma separated)<input name="tags" value="${safe((t.tags||[]).join(', '))}" placeholder="design, urgent, social"></label>
      <label>Description<textarea name="description" rows="3">${safe(t.description)}</textarea></label>
      <label class="tf-inline"><input type="checkbox" name="clientVisible" ${t.clientVisible!==false?'checked':''}> Visible to client</label>`,
      async (form,fd)=>{
        const o=Object.fromEntries(fd);
        o.assigneeIds=fd.getAll('assigneeIds').map(Number);
        o.tags=String(o.tags||'').split(',').map(x=>x.trim()).filter(Boolean);
        o.clientVisible=fd.get('clientVisible')==='on';
        for(const k of ['startAt','dueAt'])if(o[k])o[k]=new Date(o[k]).toISOString();
        if(id)o.id=id;
        await post({action:'save_task',...o});
      },id?'Save task':'Create task');
    const f=document.getElementById('tfModalForm');
    if(!fixedProject){
      const c=f.querySelector('select[name="clientId"]');const projectEl=f.querySelector('#tfTaskProjectSelect');const listEl=f.querySelector('#tfTaskListSelect');
      const sync=()=>{
        if(c){const allowed=state.projects.filter(p=>p.clientId===c.value);projectEl.innerHTML=`<option value="">General workspace</option>${allowed.map(p=>`<option value="${p.id}" ${p.id===t.projectId?'selected':''}>${safe(p.title)}</option>`).join('')}`;}
        const list=taskLists(projectEl.value);listEl.innerHTML=optionList(list.map(x=>[x.id,x.title]),'','General');
      };
      if(c)c.addEventListener('change',sync);
      projectEl.addEventListener('change',()=>{listEl.innerHTML=optionList(taskLists(projectEl.value).map(x=>[x.id,x.title]),'','General')});
    }
  }
  function taskListModal(projectId){
    if(!isManager())return;
    formModal('Create task list','Group related tasks into delivery stages or content batches.',
      '<label>Task list name<input name="title" required maxlength="120" placeholder="e.g. Social media posts"></label>',
      async (f,fd)=>plusPost({action:'save_task_list',projectId,title:fd.get('title')}),'Create task list');
  }
  async function setTaskStatus(id,status){
    const task=state.tasks.find(t=>t.id===id);if(!task||!canChangeTask(task))return;
    try{await post({action:'task_status',id,status})}catch(ex){alert(ex.message);render()}
  }
  async function bulkStatus(status){
    if(!isManager())return;
    try{await plusPost({action:'bulk_task_status',taskIds:[...ui.selected],status});ui.selected.clear()}catch(ex){alert(ex.message)}
  }
  function saveTaskView(){
    if(!isManager())return;
    formModal('Save filtered task view','Save these exact filter criteria to your account so you can reuse them.',
      '<label>View name<input name="name" required maxlength="80" placeholder="e.g. High priority tasks due this week"></label>',
      async(f,fd)=>opsPost({action:'save_view',name:String(fd.get('name')||''),filters:{...ui.filters,view:ui.view,groupBy:ui.groupBy}}),'Save view');
  }
  function loadTaskView(id){
    const item=arr('savedViews').find(v=>String(v.id)===String(id));if(!item)return;
    ui.filters={status:'open',search:'',logic:'all'};
    for(const [key,v] of Object.entries(item.filters||{})){
      if(key==='view')ui.view=v;
      else if(key==='groupBy')ui.groupBy=v;
      else ui.filters[key]=v;
    }
    ui.page=1;render();
  }
  function smartSuggestions(projectId=''){
    const rows=getFilteredTasks(projectId),unassigned=rows.filter(t=>!t.assignedTo&&t.status!=='completed'),
      overdue=rows.filter(t=>iso(t.dueAt)&&iso(t.dueAt)<today()&&t.status!=='completed'),
      blocked=rows.filter(t=>t.status==='blocked'),missingDue=rows.filter(t=>!t.dueAt&&t.status!=='completed');
    openModal(`<div class="tf-form-modal"><span class="tf-overline">RULE-BASED / DELIVERY INSIGHTS</span><h2>Task suggestions</h2><p>These checks use your actual task records—no AI-generated assignments or fabricated results.</p>
      <div class="tf-suggestion"><b>${overdue.length}</b><div><strong>Overdue tasks</strong><p>Review dates and escalate blockers.</p></div></div>
      <div class="tf-suggestion"><b>${unassigned.length}</b><div><strong>Unassigned open tasks</strong><p>Assign a team member so each task has an owner.</p></div></div>
      <div class="tf-suggestion"><b>${blocked.length}</b><div><strong>Blocked tasks</strong><p>Check dependencies and issue resolutions.</p></div></div>
      <div class="tf-suggestion"><b>${missingDue.length}</b><div><strong>Missing deadlines</strong><p>Add due dates for more reliable scheduling.</p></div></div>
      <div class="tf-form-actions">${button('Close','closeModal()')}${button('View overdue',`closeModal();TFPlus.changeFilter('timespan','overdue')`,'primary')}</div></div>`);
  }

  function widgetList(scope){
    if(isEmployee())return scope==='global'?['stats','today','overdue']:['stats','today','progress'];
    const saved=arr('dashboardLayouts').find(x=>x.scope===scope)?.widgets;
    return saved?.length?saved:(scope==='global'?arr('defaultWidgets').global:arr('defaultWidgets').project)||
      (scope==='global'?['stats','today','overdue','projects','activity']:['stats','task_chart','overdue','issues','progress']);
  }
  const widgetNames={stats:'Key metrics',today:'Today’s tasks',overdue:'Overdue work items',task_chart:'Task status',team:'Team status',issues:'Issues',progress:'Project progress',activity:'Recent activity',approvals:'Approvals',timesheets:'Tracked time',projects:'Active projects',shortcuts:'Quick modules',calendar:'Upcoming calendar',updates:'Client updates'};
  // The home task register is always visible, even when dashboard widgets are customized.
  // Employee rows are limited to tasks explicitly assigned to that employee.
  function homeTasks(){
    const allowed=state.tasks.filter(t=>!isEmployee()||isMyTask(t));
    const query=String(ui.homeTaskQuery||'').toLowerCase().trim();
    const statuses=[['all','All statuses'],['open','Open'],['in_progress','In progress'],['review','In review'],['blocked','Blocked'],['completed','Completed'],['overdue','Overdue']];
    const list=allowed.filter(t=>{
      if(query&&![t.title,t.description,t.code,t.projectName,t.clientName,t.assignedName].some(v=>String(v||'').toLowerCase().includes(query)))return false;
      if(ui.homeTaskStatus==='all')return true;
      if(ui.homeTaskStatus==='overdue')return t.status!=='completed'&&!!iso(t.dueAt)&&iso(t.dueAt)<today();
      if(ui.homeTaskStatus==='open')return t.status!=='completed';
      return t.status===ui.homeTaskStatus;
    }).sort((a,b)=>Number(a.status==='completed')-Number(b.status==='completed') || (a.dueAt||'9999').localeCompare(b.dueAt||'9999') || a.title.localeCompare(b.title));
    const visible=list.slice(0,ui.homeTaskLimit);
    const rows=visible.map(t=>{
      const overdue=t.status!=='completed'&&!!iso(t.dueAt)&&iso(t.dueAt)<today();
      return `<button type="button" class="tf-home-task-row" aria-label="Open task ${safe(t.title)}" onclick="TFPlus.taskEditor('${t.id}')">
        <span class="tf-home-task-main"><span class="tf-home-task-name">${safe(t.title)}</span><small>${safe(t.projectName||t.clientName)} · ${safe(t.code||'Task')}</small></span>
        <span class="tf-home-task-owner">${safe(teamName(t))}</span>
        <span class="tf-home-task-priority">${statusPill(t.priority)}</span>
        <span class="tf-home-task-status">${statusPill(t.status)}</span>
        <time class="${overdue?'tf-overdue':''}">${date(t.dueAt)}</time><span class="tf-home-task-open" aria-hidden="true">↗</span></button>`;
    }).join('');
    return `<section class="tf-home-tasks tf-pane" aria-label="All tasks" id="tfHomeTasks">
      <header class="tf-home-tasks-head"><div><span class="tf-overline">MY WORKSPACE / TASK REGISTER</span><h2>${isEmployee()?'My assigned tasks':'All tasks'} <span>${fmtCount(list.length)}</span></h2><p>Every ${isEmployee()?'assigned':'accessible'} task in one place. Select a row to view details${isEmployee()?' or update its status':''}.</p></div><button type="button" class="tf-btn" onclick="TFPlus.viewTasks()">View task workspace ↗</button></header>
      <div class="tf-home-tasks-controls"><label class="tf-field-search"><span>⌕</span><input id="tfHomeTaskSearch" type="search" autocomplete="off" aria-label="Search home tasks" placeholder="Search tasks or projects…" value="${safe(ui.homeTaskQuery)}" oninput="TFPlus.homeTaskFilter('query',this.value)"></label><select aria-label="Filter home tasks by status" onchange="TFPlus.homeTaskFilter('status',this.value)">${statuses.map(([v,label])=>`<option value="${v}" ${ui.homeTaskStatus===v?'selected':''}>${label}</option>`).join('')}</select></div>
      <div class="tf-home-tasks-table"><div class="tf-home-tasks-thead"><span>Task / Project</span><span>Owner</span><span>Priority</span><span>Status</span><span>Due</span><span></span></div>${rows||empty('No matching tasks',allowed.length?'Try a different search or status filter.':'Assigned tasks will appear here as soon as work is allocated.')}</div>
      <footer class="tf-home-tasks-footer"><span>Showing ${fmtCount(visible.length)} of ${fmtCount(list.length)} tasks</span>${list.length>visible.length?button('Show more tasks', 'TFPlus.moreHomeTasks()',''):''}</footer>
    </section>`;
  }
  function homeTaskFilter(kind,value){
    if(kind==='query')ui.homeTaskQuery=value;
    else if(kind==='status')ui.homeTaskStatus=value;
    else return;
    ui.homeTaskLimit=15;
    render();
    if(kind==='query'){
      const input=document.getElementById('tfHomeTaskSearch');
      if(input){input.focus();input.setSelectionRange(value.length,value.length)}
    }
  }
  function moreHomeTasks(){ui.homeTaskLimit+=15;render();}
  function dashboard(scope='global',project=null){
    const selected=widgetList(scope),global=scope==='global';
    const tasksFor=(project?projectTasks(project.id):state.tasks).filter(t=>!isEmployee()||isMyTask(t));
    const rows=tasksFor.filter(t=>t.status!=='completed'),done=tasksFor.filter(t=>t.status==='completed');
    const overdue=rows.filter(t=>iso(t.dueAt)&&iso(t.dueAt)<today());
    const issues=project?projectIssues(project.id):arr('projectIssues');
    const time=project?arr('timeEntries').filter(t=>t.projectId===project.id):arr('timeEntries');
    const approvals=project?arr('approvalRequests').filter(a=>a.projectId===project.id):arr('approvalRequests');
    const current=project?project.title:'Home';
    const actions=`${isManager()?button('＋ Add widget',`TFPlus.configureWidgets('${scope}')`):''}${button('↻ Refresh',"load()")}`;
    const title=global?header('Home dashboard',isEmployee()?'Your assigned work, deadlines, and daily progress in one place.':'Your live operational snapshot, with customizable widgets and shortcuts.',actions):
      `<div class="tf-dashboard-header"><div><strong>Project dashboard</strong><small>Widgets reflect work for ${safe(current)}</small></div><div>${actions}</div></div>`;
    return `${title}${global?homeTasks():''}<div class="tf-widgets">${selected.map((key,index)=>{
      const content=renderWidget(key,project,{rows,tasksFor,done,overdue,issues,time,approvals});
      return `<section class="tf-widget tf-widget-${key}"><div class="tf-widget-header"><strong>${safe(widgetNames[key]||key)}</strong>${isManager()?`<div class="tf-widget-controls"><button title="Move widget left" onclick="TFPlus.moveWidget('${scope}',${index},-1)">←</button><button title="Move widget right" onclick="TFPlus.moveWidget('${scope}',${index},1)">→</button><button title="Customize dashboard" onclick="TFPlus.configureWidgets('${scope}')">⋯</button></div>`:''}</div>${content}</section>`;
    }).join('')}</div>`;
  }
  const taskCompact=(tasks,limit=7)=>tasks.slice(0,limit).map(t=>`<button class="tf-compact-row" onclick="TFPlus.taskEditor('${t.id}')"><span class="tf-mini-check">☑</span><span><strong>${safe(t.title)}</strong><small>${safe(t.projectName||t.clientName)} · ${safe(teamName(t))}</small></span><time class="${iso(t.dueAt)<today()&&t.status!=='completed'?'tf-overdue':''}">${date(t.dueAt||t.startAt)}</time></button>`).join('')||empty('Nothing pending','There is no work in this category.');
  function renderWidget(key,project,data){
    const {rows,tasksFor,done,overdue,issues,time,approvals}=data;
    const stats=taskStat(tasksFor);
    const openIssues=issues.filter(i=>!['resolved','closed'].includes(i.status));
    const activeProjects=project?[project]:state.projects.filter(p=>p.status==='active');
    if(key==='stats'){
      const metrics=isEmployee()?project?[
        ['My open tasks',rows.length,'Assigned in this project'],['Completed',done.length,'My finished tasks'],['Project progress',`${stats.percent}%`,'My task completion']]:[
        ['My open tasks',rows.length,'Awaiting completion'],['Completed',done.length,'My finished tasks'],
        ['Due today',rows.filter(t=>iso(t.dueAt)===today()).length,'My deadlines today'],['Overdue',rows.filter(t=>iso(t.dueAt)&&iso(t.dueAt)<today()).length,'My overdue tasks']]:project?[
        ['Open tasks',rows.length,'Tasks in progress'],['Completed',done.length,'Finished work'],['Project progress',`${stats.percent}%`,'Completion rate'],
        ['Active issues',openIssues.length,'Need attention'],['Phases',arr('milestones').filter(m=>m.projectId===project.id).length,'Delivery stages'],['Hours logged',hours(minutes(time)),'Recorded delivery']]:
        [['Open tasks',rows.length,'Across visible clients'],['Active projects',activeProjects.length,'Delivery in progress'],['Completed tasks',done.length,'Finished work'],
        ['My open tasks',rows.filter(t=>String(t.assignedTo)===String(roleId())).length,'Assigned to you'],['Closed phases',arr('milestones').filter(m=>m.status==='completed').length,'Completed milestones'],['Open issues',openIssues.length,'Awaiting resolution']];
      return `<div class="tf-metric-grid">${metrics.map(([name,count,description])=>`<div class="tf-metric"><span>${safe(name)}</span><strong>${safe(count)}</strong><small>${safe(description)}</small></div>`).join('')}</div>`;
    }
    if(key==='today')return `<div class="tf-widget-content">${taskCompact(rows.filter(t=>iso(t.dueAt)===today()||iso(t.startAt)===today()),8)}</div>`;
    if(key==='overdue')return `<div class="tf-widget-content">${taskCompact(overdue,8)}</div>`;
    if(key==='task_chart'){
      const open=tasksFor.filter(t=>t.status==='todo').length,progress=tasksFor.filter(t=>t.status==='in_progress').length,
        review=tasksFor.filter(t=>t.status==='review').length,blocked=tasksFor.filter(t=>t.status==='blocked').length;
      const total=stats.total||1,a=stats.done/total*360,b=(stats.done+open)/total*360,c=(stats.done+open+progress)/total*360,d=(stats.done+open+progress+review)/total*360;
      return `<div class="tf-donut-layout"><div class="tf-donut" style="background:conic-gradient(#50cbac 0deg ${a}deg,#5b83f7 ${a}deg ${b}deg,#febd69 ${b}deg ${c}deg,#9e8bff ${c}deg ${d}deg,#f2777d ${d}deg 360deg)"><div><strong>${stats.percent}%</strong><small>complete</small></div></div><div class="tf-chart-legend">${[['Completed',stats.done,'mint'],['Open',open,'blue'],['In progress',progress,'orange'],['In review',review,'purple'],['Blocked',blocked,'red']].map(([name,n,c])=>`<div><i class="tf-dot ${c}"></i>${name}<strong>${n}</strong></div>`).join('')}</div></div>`;
    }
    if(key==='team'){
      const taskMembers=project?arr('projectTeams').filter(x=>x.projectId===project.id).map(x=>x.memberId):state.members.filter(m=>m.role!=='client').map(x=>x.id);
      return `<div class="tf-widget-content">${state.members.filter(x=>taskMembers.includes(x.id)).slice(0,8).map(m=>{
        const x=tasksFor.filter(t=>t.assignedTo===m.id),over=x.filter(t=>t.status!=='completed'&&iso(t.dueAt)&&iso(t.dueAt)<today());
        return `<div class="tf-team-row"><i>${initials(m.name)}</i><strong>${safe(m.name)}</strong><span>${x.length} tasks</span><span class="${over.length?'tf-overdue':''}">${over.length} overdue</span></div>`;
      }).join('')||empty('Project team not assigned','Add people under the Users tab.')}</div>`;
    }
    if(key==='issues')return `<div class="tf-widget-content">${issues.filter(i=>!['resolved','closed'].includes(i.status)).slice(0,7).map(i=>`<button class="tf-compact-row" onclick="${project?`TFPlus.switchProjectTab('issues')`:`go('issues')`}"><span class="tf-mini-issue">!</span><span><strong>${safe(i.title)}</strong><small>${safe(i.projectName)} · ${safe(i.assignedName||'Unassigned')}</small></span>${statusPill(i.priority)}</button>`).join('')||empty('No open issues','Everything looks clear.')}</div>`;
    if(key==='progress')return `<div class="tf-widget-content">${activeProjects.slice(0,8).map(p=>`<button class="tf-progress-row" onclick="TFPlus.openProject('${p.id}')"><span>${safe(p.title)}</span><b>${p.progress}%</b>${percentBar(p.progress)}</button>`).join('')||empty('No active projects')}</div>`;
    if(key==='activity')return `<div class="tf-widget-content">${state.activities.filter(a=>!project||a.clientName===project.clientName).slice(0,7).map(a=>`<div class="tf-activity"><i>${initials(a.actorName)}</i><div><strong>${safe(a.action)}</strong><small>${safe(a.actorName)} · ${fmt(a.createdAt)}</small></div></div>`).join('')||empty('No recent activity')}</div>`;
    if(key==='approvals')return `<div class="tf-widget-content">${approvals.filter(a=>a.status==='pending').slice(0,6).map(a=>`<button class="tf-compact-row" onclick="${project?`TFPlus.switchProjectTab('approvals')`:`go('approvals')`}"><span class="tf-mini-check">◎</span><span><strong>${safe(a.title)}</strong><small>${safe(a.clientName)} · ${safe(a.requestedBy)}</small></span>${statusPill(a.status)}</button>`).join('')||empty('Nothing to approve')}</div>`;
    if(key==='timesheets'){
      const billable=time.filter(t=>t.billable),pending=time.filter(t=>t.status==='submitted');
      return `<div class="tf-time-stats"><div><strong>${hours(minutes(time))}</strong><span>Total time</span></div><div><strong>${hours(minutes(billable))}</strong><span>Billable</span></div><div><strong>${pending.length}</strong><span>Awaiting review</span></div></div>`;
    }
    if(key==='projects')return `<div class="tf-widget-content">${activeProjects.slice(0,8).map(p=>`<button class="tf-compact-row" onclick="TFPlus.openProject('${p.id}')"><span class="tf-mini-check">◈</span><span><strong>${safe(p.title)}</strong><small>${safe(p.clientName)} · ${safe(p.ownerName||'Unassigned')}</small></span><b>${p.progress}%</b></button>`).join('')||empty('No active projects')}</div>`;
    if(key==='shortcuts'){
      const links=isStaff()?['projects','tasks','issues','phases','timesheets','approvals']:['projects','tasks','approvals','tickets','files','calendar'];
      return `<div class="tf-shortcuts">${links.map(k=>`<button onclick="go('${k}')">${safe(labels[k]||k)} <span>↗</span></button>`).join('')}</div>`;
    }
    if(key==='calendar')return `<div class="tf-widget-content">${state.events.filter(e=>iso(e.startAt)>=today()&&(!project||e.clientId===project.clientId)).slice(0,6).map(e=>`<div class="tf-compact-row"><span class="tf-mini-check">▣</span><span><strong>${safe(e.title)}</strong><small>${safe(e.clientName)}</small></span><time>${date(e.startAt)}</time></div>`).join('')||empty('No upcoming events')}</div>`;
    if(key==='updates')return `<div class="tf-widget-content">${state.updates.filter(x=>!project||x.clientId===project.clientId).slice(0,6).map(x=>`<div class="tf-compact-row"><span class="tf-mini-check">↻</span><span><strong>${safe(x.title)}</strong><small>${safe(x.authorName)} · ${safe((x.body||'').slice(0,80))}</small></span><time>${date(x.createdAt)}</time></div>`).join('')||empty('No updates')}</div>`;
    return empty('Widget unavailable');
  }
  function configureWidgets(scope){
    if(!isManager())return;
    const selected=new Set(widgetList(scope));
    formModal('Customize dashboard','Choose the modules that matter most. Your widget choices are stored in your account.',
      `<div class="tf-widget-picker">${Object.entries(widgetNames).filter(([key])=>state.ctx.role!=='client'||!['team','timesheets'].includes(key)).map(([key,name])=>`<label><input type="checkbox" name="widgets" value="${key}" ${selected.has(key)?'checked':''}><span>${safe(name)}</span></label>`).join('')}</div>`,
      async(f,fd)=>{
        const chosen=fd.getAll('widgets');if(!chosen.length)throw Error('Choose at least one widget');
        await plusPost({action:'save_dashboard_layout',scope,widgets:chosen});
      },'Apply dashboard');
  }
  async function moveWidget(scope,index,by){
    if(!isManager())return;
    const layout=[...widgetList(scope)],next=index+by;if(next<0||next>=layout.length)return;
    [layout[index],layout[next]]=[layout[next],layout[index]];
    try{await plusPost({action:'save_dashboard_layout',scope,widgets:layout})}catch(ex){alert(ex.message)}
  }

  function projectUsers(p){
    const members=arr('projectTeams').filter(x=>x.projectId===p.id),clientStaff=arr('assignments').filter(a=>a.clientId===p.clientId).map(a=>a.employeeId);
    return `<section class="tf-pane">${boxTitle('Project users',isManager()?button('＋ Add person',`TFPlus.teamModal('${p.id}')`,'primary'):'')}
      <p class="tf-pane-sub">Project-specific team members and responsibilities. Client access remains controlled by client assignments.</p>
      <div class="tf-user-grid">${members.map(m=>{const data=state.members.find(x=>x.id===m.memberId);return `<div class="tf-user-card"><i>${initials(m.name)}</i><div><strong>${safe(m.name)}</strong><span>${safe(data?.jobTitle||data?.roleLabel||'Team member')}</span><small>${safe(m.role)}</small></div>${isManager()?`<button onclick="TFPlus.removeTeamMember('${p.id}',${m.memberId})" title="Remove from project team">×</button>`:''}</div>`}).join('')||empty('No project members yet','Choose people from this client’s assigned team.')}</div>
      <div class="tf-help-note">${clientStaff.length} people are currently assigned to this client. Project membership organizes participation; it does not override client permissions.</div></section>`;
  }
  function teamModal(projectId){
    const p=projectBy(projectId);if(!p)return;
    const assigned=new Set(arr('assignments').filter(a=>a.clientId===p.clientId).map(a=>String(a.employeeId)));
    const staff=state.members.filter(m=>['admin','manager'].includes(m.role)||(m.role==='employee'&&assigned.has(String(m.id))));
    formModal('Add project member','Choose from employees already assigned to this client.',
      `<label>Team member<select name="memberId" required>${optionList(staff.map(x=>[x.id,x.name]),'','Select member')}</select></label><label>Project role<select name="role"><option value="contributor">Contributor</option><option value="lead">Project lead</option><option value="observer">Observer</option></select></label>`,
      async(f,fd)=>plusPost({action:'save_project_member',projectId,memberId:fd.get('memberId'),role:fd.get('role')}),'Assign member');
  }
  async function removeTeamMember(projectId,memberId){
    if(!confirm('Remove this member from the project team? This will not revoke their client assignment.'))return;
    try{await plusPost({action:'remove_project_member',projectId,memberId})}catch(ex){alert(ex.message)}
  }
  function projectReports(p){
    const tasks=projectTasks(p.id),data=taskStat(tasks),issues=projectIssues(p.id),
      logged=arr('timeEntries').filter(t=>t.projectId===p.id),approved=logged.filter(t=>t.status==='approved'),
      phases=arr('milestones').filter(x=>x.projectId===p.id),byPriority=['low','normal','high','urgent'];
    const dateToday=today();
    return `<div class="tf-report-grid"><section class="tf-pane">${boxTitle('Delivery overview')}
      <div class="tf-report-numbers">${[['Tasks',tasks.length],['Completed',data.done],['Overdue',tasks.filter(t=>t.status!=='completed'&&iso(t.dueAt)&&iso(t.dueAt)<dateToday).length],['Open issues',issues.filter(i=>!['resolved','closed'].includes(i.status)).length]].map(([label,count])=>`<div><strong>${count}</strong><span>${label}</span></div>`).join('')}</div>
      <div class="tf-progress-card"><span>Task completion</span><b>${data.percent}%</b>${percentBar(data.percent)}</div>
    </section><section class="tf-pane">${boxTitle('Time and delivery')}
      <div class="tf-report-numbers"><div><strong>${hours(minutes(logged))}</strong><span>Total hours</span></div><div><strong>${hours(minutes(approved))}</strong><span>Approved hours</span></div><div><strong>${phases.length}</strong><span>Phases</span></div></div>
      <p class="tf-help-note">Based on authorized time logs recorded against this project.</p></section>
    <section class="tf-pane">${boxTitle('Task distribution')}
      ${TaskStatus.map(([v,label])=>{const count=tasks.filter(t=>t.status===v).length;return `<div class="tf-distribution"><span>${label}</span>${percentBar(tasks.length?count/tasks.length*100:0)}<b>${count}</b></div>`}).join('')}</section>
    <section class="tf-pane">${boxTitle('Work by priority')}${byPriority.map(v=>{const count=tasks.filter(t=>t.priority===v).length;return `<div class="tf-distribution"><span>${v}</span>${percentBar(tasks.length?count/tasks.length*100:0)}<b>${count}</b></div>`}).join('')}</section></div>`;
  }
  function projectPhases(p){
    const phases=arr('milestones').filter(x=>x.projectId===p.id);
    return `<section class="tf-pane">${boxTitle('Delivery phases',isStaff()?button('＋ Add phase',`TFPlus.phaseModal('${p.id}')`,'primary'):'')}<p class="tf-pane-sub">Define the work stages, milestones and completion checkpoints for this project.</p>
      ${phases.length?`<div class="tf-phase-timeline">${phases.map((m,index)=>`<article class="tf-phase-card"><div class="tf-phase-index">${index+1}</div><div><strong>${safe(m.title)}</strong><p>${safe(m.description||'Project milestone')}</p><small>◷ ${date(m.dueDate)} · ${safe(m.ownerName||'No owner')}</small></div><div>${statusPill(m.status)}${isStaff()?`<select aria-label="Phase status" onchange="TFPlus.phaseStatus('${m.id}',this.value)">${[['planned','Planned'],['active','In progress'],['completed','Completed']].map(([v,label])=>`<option value="${v}" ${m.status===v?'selected':''}>${label}</option>`).join('')}</select>`:''}</div></article>`).join('')}</div>`:empty('No phases configured','Create phases for content strategy, production, client approval and launch.')}</section>`;
  }
  function phaseModal(projectId){
    const p=projectBy(projectId);if(!p)return;
    formModal('Create project phase','Milestones help the team track progress through each delivery stage.',
      `<label>Phase title<input name="title" required maxlength="220" placeholder="e.g. Content production"></label>
       <label>Description<textarea name="description" maxlength="2000" rows="3"></textarea></label>
       <div class="tf-form-grid"><label>Target date<input type="date" name="dueDate"></label><label>Owner<select name="ownerId">${memberOptions('',false,projectId)}</select></label></div>
       <label class="tf-inline"><input type="checkbox" name="clientVisible" checked> Visible to client</label>`,
      async(f,fd)=>opsPost({action:'save_milestone',projectId,title:fd.get('title'),description:fd.get('description'),dueDate:fd.get('dueDate'),ownerId:fd.get('ownerId'),clientVisible:fd.has('clientVisible')}),'Create phase');
  }
  async function phaseStatus(id,status){try{await opsPost({action:'milestone_status',id,status})}catch(ex){alert(ex.message)}}

  function issueWorkspace(projectId=''){
    const all=arr('projectIssues').filter(x=>!projectId||x.projectId===projectId);
    const rows=all.filter(x=>ui.issuesStatus==='all'||(ui.issuesStatus==='open'?!['resolved','closed'].includes(x.status):x.status===ui.issuesStatus));
    return `<section class="tf-pane">${boxTitle('Issues & blockers',button('＋ Report issue',`TFPlus.issueModal('${projectId}')`,'primary'))}
      <div class="tf-inner-toolbar"><p>Report a blocker, assign an owner and track its resolution through to closure.</p>
      <select aria-label="Issue status" onchange="TFPlus.setIssueFilter(this.value)">${[['open','Open issues'],['all','All issues'],['in_progress','In progress'],['resolved','Resolved'],['closed','Closed']].map(([v,label])=>`<option value="${v}" ${ui.issuesStatus===v?'selected':''}>${label}</option>`).join('')}</select>
      <a class="tf-btn" href="/api/project-export/issues/">↓ Export</a></div>
      <div class="tf-table-scroll"><table class="tf-grid"><thead><tr><th>Issue</th><th>Project</th><th>Priority</th><th>Assigned to</th><th>Status</th><th>Created</th><th>Action</th></tr></thead><tbody>${rows.map(i=>`<tr><td><strong>${safe(i.title)}</strong><small>${safe((i.description||'').slice(0,90))}</small></td><td>${safe(i.projectName)}</td><td>${statusPill(i.priority)}</td><td>${safe(i.assignedName||'Unassigned')}</td><td>${statusPill(i.status)}</td><td>${date(i.createdAt)}</td><td>${isStaff()?`<select aria-label="Change issue status" onchange="TFPlus.issueStatus('${i.id}',this.value)">${[['open','Open'],['in_progress','In progress'],['resolved','Resolved'],['closed','Closed']].map(([v,label])=>`<option value="${v}" ${i.status===v?'selected':''}>${label}</option>`).join('')}</select>`:'Client reported'}</td></tr>`).join('')||`<tr><td colspan="7">${empty('No matching issues','There are no blockers matching this view.')}</td></tr>`}</tbody></table></div></section>`;
  }
  function issueModal(projectId=''){
    if(!projectId&&state.projects.length===1)projectId=state.projects[0].id;
    const p=projectBy(projectId),projects=p?[p]:state.projects;
    if(!projects.length){alert('Create or gain access to a project first');return}
    formModal('Report a project issue','Capture a blocker and keep its resolution visible to the relevant team.',
      `<label>Project<select name="projectId" required>${projects.map(p=>`<option value="${p.id}">${safe(p.title)}</option>`).join('')}</select></label>
      <label>Issue title<input name="title" required maxlength="220" placeholder="What needs attention?"></label>
      <label>Description<textarea name="description" maxlength="4000" rows="4" placeholder="Explain the issue, impact and reproduction steps"></textarea></label>
      <div class="tf-form-grid"><label>Priority<select name="priority"><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option><option value="low">Low</option></select></label>
      ${isStaff()?`<label>Assigned to<select name="assignedTo">${memberOptions('',false,projectId)}</select></label>`:''}<label>Due date<input name="dueAt" type="datetime-local"></label></div>
      ${isStaff()?'<label class="tf-inline"><input type="checkbox" name="clientVisible" checked> Client-visible issue</label>':''}`,
      async(f,fd)=>plusPost({action:'save_issue',projectId:fd.get('projectId'),title:fd.get('title'),description:fd.get('description'),priority:fd.get('priority'),assignedTo:fd.get('assignedTo')||'',dueAt:fd.get('dueAt')?new Date(fd.get('dueAt')).toISOString():'',clientVisible:fd.has('clientVisible')}),'Create issue');
  }
  async function issueStatus(id,status){try{await plusPost({action:'issue_status',id,status})}catch(ex){alert(ex.message)}}

  function projectFeed(p){
    const messages=arr('projectFeed').filter(x=>x.projectId===p.id).slice().sort((a,b)=>a.createdAt.localeCompare(b.createdAt));
    return `<section class="tf-pane">${boxTitle('Project collaboration',button('＋ Post update',`TFPlus.feedModal('${p.id}')`,'primary'))}
      <p class="tf-pane-sub">A threaded space for project discussion. Internal team notes stay hidden from the client portal.</p>
      <div class="tf-feed">${messages.map(m=>`<article class="tf-feed-post ${m.parentId?'reply':''}"><span class="tf-feed-avatar">${initials(m.author)}</span><div><div class="tf-feed-meta"><strong>${safe(m.author)}</strong>${statusPill(m.visibility)}<time>${fmt(m.createdAt)}</time></div><p>${safe(m.body)}</p><button onclick="TFPlus.feedModal('${p.id}','${m.id}')">↳ Reply</button></div></article>`).join('')||empty('No project discussions yet','Share an update, ask a question or collaborate on a task.')}</div></section>`;
  }
  function feedModal(projectId='',parentId=''){
    const p=projectBy(projectId)||state.projects[0];if(!p)return;
    formModal(parentId?'Reply to discussion':'Post project update','Messages are visible only to people who can access this project.',
      `${projectId?'':`<label>Project<select name="projectId">${state.projects.map(p=>`<option value="${p.id}">${safe(p.title)}</option>`).join('')}</select></label>`}
      <label>Message<textarea name="body" required maxlength="4000" rows="5" placeholder="Write your project update…"></textarea></label>
      ${isStaff()?`<label>Visibility<select name="visibility"><option value="client">Client + team</option><option value="team">Internal team only</option></select></label>`:''}`,
      async(f,fd)=>plusPost({action:'post_project_feed',projectId:projectId||fd.get('projectId')||p.id,parentId,body:fd.get('body'),visibility:fd.get('visibility')||'client'}),'Post message');
  }

  function projectDocuments(p){
    const docs=arr('projectDocs').filter(d=>d.projectId===p.id);
    return `<section class="tf-pane">${boxTitle('Project documents',button('↑ Upload document',`TFPlus.documentModal('${p.id}')`,'primary'))}
      <p class="tf-pane-sub">Share approved files, briefs and references securely with the team. Downloads require workspace permission.</p>
      <div class="tf-doc-list">${docs.map(d=>`<article class="tf-doc"><span>▤</span><div><strong>${safe(d.title)}</strong><small>${safe(d.uploadedBy)} · ${date(d.createdAt)} · ${(d.size/1024).toFixed(0)} KB ${d.clientVisible?'· Client visible':'· Internal'}</small></div><a class="tf-btn" href="${safe(d.downloadUrl)}">Download ↓</a></article>`).join('')||empty('No documents attached','Upload briefs, approvals and finished deliverables.')}</div>
      <p class="tf-storage-warning">Preview hosting uses temporary file storage. Files can be lost on restart or redeploy; use durable object storage before real projects.</p></section>`;
  }
  function documentModal(projectId){
    formModal('Upload project document','Upload a file up to 8 MB. For now, demonstration files only.',
      `<label>Document title<input name="title" maxlength="220" placeholder="Brief, deliverable or reference"></label>
      <label>Choose file<input type="file" name="file" required accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.txt,.zip"></label>
      ${isStaff()?'<label class="tf-inline"><input type="checkbox" name="clientVisible" checked> Allow client to download</label>':''}`,
      async(f,fd)=>{
        const file=fd.get('file');if(!file?.size||file.size>8_000_000)throw Error('Upload a file no larger than 8 MB');
        const payload=new FormData();payload.set('file',file);payload.set('projectId',projectId);
        payload.set('title',fd.get('title')||file.name);payload.set('clientVisible',fd.has('clientVisible')?'true':'false');
        await fetchJSON('/api/projects-plus/upload/',{method:'POST',headers:{'X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:payload});
        state.notice='Document uploaded';await load();
      },'Upload file');
  }

  function projectTimeLogs(p,timesheet=false){
    const logs=arr('timeEntries').filter(t=>t.projectId===p.id);
    const billable=logs.filter(t=>t.billable),approved=logs.filter(t=>t.status==='approved');
    if(state.ctx.role==='client')return `<section class="tf-pane">${empty('Internal time tracking','Your team’s detailed timesheets are available to authorized employees and managers.')}</section>`;
    return `<section class="tf-pane">${boxTitle(timesheet?'Project timesheets':'Project time logs',button('＋ Log time',`TFPlus.logTimeModal('${p.id}')`,'primary'))}
      <div class="tf-report-numbers tf-time-summary"><div><strong>${hours(minutes(logs))}</strong><span>Recorded hours</span></div><div><strong>${hours(minutes(billable))}</strong><span>Billable time</span></div><div><strong>${hours(minutes(approved))}</strong><span>Approved hours</span></div></div>
      <div class="tf-table-scroll"><table class="tf-grid"><thead><tr><th>Date</th><th>Team member</th><th>Task</th><th>Work description</th><th>Hours</th><th>Billing</th><th>Status</th><th>Action</th></tr></thead><tbody>
      ${logs.map(t=>`<tr><td>${date(t.date)}</td><td>${safe(t.employeeName)}</td><td>${safe(t.taskName||'General')}</td><td>${safe(t.description)}</td><td>${hours(t.minutes)}</td><td>${t.billable?'Billable':'Non-billable'}</td><td>${statusPill(t.status)}</td><td>${t.employeeId===roleId()&&['draft','rejected'].includes(t.status)?button('Submit',`TFPlus.timeStatus('${t.id}','submitted')`):isManager()&&t.employeeId!==roleId()&&t.status==='submitted'?`${button('Approve',`TFPlus.timeStatus('${t.id}','approved')`)} ${button('Reject',`TFPlus.timeStatus('${t.id}','rejected')`)}`:'—'}</td></tr>`).join('')||`<tr><td colspan="8">${empty('No time logged','Start a time entry against this project.')}</td></tr>`}</tbody></table></div></section>`;
  }
  function logTimeModal(projectId){
    const p=projectBy(projectId);if(!p)return;
    formModal('Log project time','Record actual work against this project. Submit the entry for manager approval.',
      `<label>Related task<select name="taskId">${optionList(projectTasks(p.id).map(t=>[t.id,t.title]),'','General project work')}</select></label>
      <div class="tf-form-grid"><label>Work date<input type="date" name="date" value="${today()}" max="${today()}" required></label>
      <label>Hours<input type="number" name="hours" min="0.25" max="24" step="0.25" value="1" required></label></div>
      <label>Description<textarea name="description" rows="3" maxlength="500" placeholder="What did you work on?"></textarea></label>
      <label class="tf-inline"><input type="checkbox" name="billable" checked> Billable work</label>`,
      async(f,fd)=>opsPost({action:'add_time',clientId:p.clientId,projectId:p.id,taskId:fd.get('taskId'),date:fd.get('date'),minutes:Math.round(Number(fd.get('hours'))*60),description:fd.get('description'),billable:fd.has('billable')}),'Log hours');
  }
  async function timeStatus(id,status){try{await opsPost({action:'time_status',id,status})}catch(ex){alert(ex.message)}}

  function projectApprovals(p){
    const approvals=arr('approvalRequests').filter(a=>a.projectId===p.id);
    return `<section class="tf-pane">${boxTitle('Project approvals',isStaff()?button('＋ Request sign-off',`TFPlus.approvalModal('${p.id}')`,'primary'):'')}
      <p class="tf-pane-sub">Create a review request and track approval, rejection or revisions before final delivery.</p>
      <div class="tf-approval-list">${approvals.map(a=>`<article class="tf-approval"><div><strong>${safe(a.title)}</strong><p>${safe(a.description||'Approval requested for this project')}</p><small>Requested by ${safe(a.requestedBy)} · ${date(a.createdAt)}</small></div>${statusPill(a.status)}${a.status==='pending'&&state.ctx.role==='client'&&a.audience==='client'?button('Review',`TFPlus.decideApproval('${a.id}')`,'primary'):a.status==='pending'&&isManager()&&a.audience==='internal'&&a.reviewerId!==roleId()?button('Review',`TFPlus.decideApproval('${a.id}')`,'primary'):''}</article>`).join('')||empty('No approval requests','Create a deliverable sign-off to receive a client decision.')}</div></section>`;
  }
  function approvalModal(projectId){
    const p=projectBy(projectId);if(!p)return;
    formModal('Request project approval','Ask the client or an internal reviewer to sign off on work.',
      `<label>Approval title<input name="title" required maxlength="220" placeholder="e.g. November content calendar"></label>
      <label>Description<textarea name="description" maxlength="4000" rows="3"></textarea></label>
      <div class="tf-form-grid"><label>Audience<select name="audience" id="tfApprovalAudience"><option value="client">Client approval</option><option value="internal">Internal team review</option></select></label><label>Reviewer <small>(for internal requests)</small><select name="reviewerId">${memberOptions('',false,p.id)}</select></label>
      <label>Due date<input name="dueAt" type="datetime-local"></label><label>Related task<select name="taskId">${optionList(projectTasks(p.id).filter(t=>t.clientVisible).map(t=>[t.id,t.title]),'','Project sign-off')}</select></label></div>`,
      async(f,fd)=>opsPost({action:'create_approval',clientId:p.clientId,projectId:p.id,title:fd.get('title'),description:fd.get('description'),audience:fd.get('audience'),reviewerId:fd.get('reviewerId'),taskId:fd.get('taskId'),dueAt:fd.get('dueAt')?new Date(fd.get('dueAt')).toISOString():''}),'Send approval request');
  }
  function decideApproval(id){
    formModal('Review deliverable','Approve, reject or request changes. Rejections require a reason.',
      `<label>Decision<select name="status"><option value="approved">Approve</option><option value="changes">Request changes</option><option value="rejected">Reject</option></select></label>
      <label>Decision note<textarea name="note" maxlength="4000" rows="3" placeholder="Explain revisions if requested"></textarea></label>`,
      async(f,fd)=>opsPost({action:'decide_approval',id,status:fd.get('status'),note:fd.get('note')}),'Submit decision');
  }

  function globalPhases(){
    return `${header('Phases','Milestones and delivery checkpoints across the project portfolio.')}
      <section class="tf-pane">${boxTitle('Phases',isStaff()&&state.projects.length?button('＋ Add phase',`TFPlus.phaseModal('${state.projects[0].id}')`,'primary'):'')}
      <div class="tf-table-scroll"><table class="tf-grid"><thead><tr><th>Phase</th><th>Project</th><th>Owner</th><th>Target date</th><th>Status</th></tr></thead><tbody>${arr('milestones').map(m=>`<tr><td><strong>${safe(m.title)}</strong></td><td><button onclick="TFPlus.openProject('${m.projectId}','phases')">${safe(m.projectName)}</button></td><td>${safe(m.ownerName||'Unassigned')}</td><td>${date(m.dueDate)}</td><td>${statusPill(m.status)}</td></tr>`).join('')||`<tr><td colspan="5">${empty('No phases yet')}</td></tr>`}</tbody></table></div></section>`;
  }
  function globalDiscussions(){
    const projects=state.projects;
    return `${header('Collaboration','Client-friendly and internal discussions, organized by project.',projects.length?button('＋ New message',`TFPlus.feedModal('${projects[0].id}')`,'primary'):'')}
      <section class="tf-pane">${arr('projectFeed').slice().sort((a,b)=>b.createdAt.localeCompare(a.createdAt)).map(m=>`<button class="tf-conversation-row" onclick="TFPlus.openProject('${m.projectId}','feed')"><span class="tf-feed-avatar">${initials(m.author)}</span><span><strong>${safe(m.author)} · ${safe(projectBy(m.projectId)?.title||'Project')}</strong><small>${safe((m.body||'').slice(0,180))}</small></span><time>${fmt(m.createdAt)}</time>${statusPill(m.visibility)}</button>`).join('')||empty('No discussions','Open a project and use its Feed tab to start the conversation.')}</section>`;
  }
  function globalDocuments(){
    return `${header('Documents & assets','Project briefs, deliverables and shared files in one permission-controlled library.')}
      <section class="tf-pane">${arr('projectDocs').map(d=>`<div class="tf-doc"><span>▤</span><div><strong>${safe(d.title)}</strong><small>${safe(projectBy(d.projectId)?.title||'Project')} · ${safe(d.uploadedBy)} · ${date(d.createdAt)}</small></div><a class="tf-btn" href="${safe(d.downloadUrl)}">Download ↓</a></div>`).join('')||empty('No project documents','Open a project and upload files under Documents.')}</section>`;
  }

  const oldLegacy = legacy;
  function legacyPlus(kind){
    if(kind==='issues')return `${header('Issue tracker','Track bugs, blockers and resolutions across client projects.')}${issueWorkspace()}`;
    if(kind==='phases')return globalPhases();
    if(kind==='collaboration')return globalDiscussions();
    if(kind==='files')return globalDocuments();
    if(kind==='timelogs')return `${header('Time logs','Tracked work against client projects.')}${state.projects.length?projectTimeLogs(state.projects[0]):empty('No projects yet')}`;
    return oldLegacy(kind);
  }

  const publicAPI={projects,tasks,dashboard,legacy:legacyPlus,openProject,backProjects,switchProjectTab,
    sortProjects(key){ui.projectDesc=ui.projectSort===key?!ui.projectDesc:false;ui.projectSort=key;render()},
    changeProjectPage(delta){ui.projectPage=Math.max(1,ui.projectPage+delta);render()},
    setProjectFilter(key,value){ui[key]=value;if(key!=='projectPage')ui.projectPage=1;render();if(key==='projectQuery'){const el=document.querySelector('input[aria-label="Search projects"]');el?.focus();el?.setSelectionRange(value.length,value.length)}},
    setView(view){ui.view=view;render()},changeGroup(group){ui.groupBy=group;ui.page=1;render()},
    sortTasks(key){ui.desc=ui.sort===key?!ui.desc:false;ui.sort=key;render()},
    pageTasks(delta){ui.page=Math.max(1,ui.page+delta);render()},
    toggleTask(id,checked){if(checked)ui.selected.add(id);else ui.selected.delete(id);render()},
    selectVisibleTasks(checked){const rows=getFilteredTasks(getProjectScope());const groups=new Map();const key=t=>ui.groupBy==='taskList'?(arr('taskLists').find(x=>x.id===t.taskListId)?.title||'General'):ui.groupBy==='project'?(t.projectName||'No project'):ui.groupBy==='status'?titleStatus(t.status):ui.groupBy==='owner'?teamName(t):'All tasks';for(const t of rows){const k=key(t);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(t)}for(const t of [...groups.values()].flat().slice((ui.page-1)*25,ui.page*25)){if(checked)ui.selected.add(t.id);else ui.selected.delete(t.id)}render()},
    clearSelection(){ui.selected.clear();render()},bulkStatus,taskEditor,taskListModal,setTaskStatus,
    quickTaskKey,quickTaskButton,openTaskDatePicker,saveTaskDate,
    changeFilter,resetFilters,openFilters(){ui.drawer=true;render()},closeFilters(){ui.drawer=false;render()},applyFilters,
    saveTaskView,loadTaskView,smartSuggestions,configureWidgets,moveWidget,homeTaskFilter,moreHomeTasks,teamModal,removeTeamMember,
    phaseModal,phaseStatus,issueModal,issueStatus,setIssueFilter(v){ui.issuesStatus=v;render()},
    feedModal,documentModal,logTimeModal,timeStatus,approvalModal,decideApproval,
    viewTasks(projectId=''){ui.project=projectId;ui.projectTab='tasks';state.tab=projectId?'projects':'tasks';ui.page=1;if(isEmployee())ui.filters.status='all';render()}
  };
  window.TFPlus=publicAPI;
  Object.assign(labels,{issues:'Issues',phases:'Phases',collaboration:'Collaboration',files:'Documents & assets',projects:'Projects',tasks:'Tasks'});
  for(const role of ['manager','admin']){
    for(const key of ['issues','phases','collaboration'])if(!menus[role].includes(key))menus[role].push(key);
  }
  // Reuse the existing route and role-based shell instead of creating a second SPA.
  projects=publicAPI.projects;tasks=publicAPI.tasks;legacy=publicAPI.legacy;
  window.projects=projects;window.tasks=tasks;window.legacy=legacy;
  window.applySavedView=publicAPI.loadTaskView;
  window.openTasksWith=(key,value)=>{ui.filters[key]=value;ui.page=1;ui.project='';state.tab='tasks';render()};
  window.resetTaskFilters=resetFilters;
  if(location.hash.startsWith('#projects/')){
    const [,id,tab]=location.hash.slice(1).split('/');
    if(projectBy(id)){ui.project=id;ui.projectTab=tab||'dashboard';state.tab='projects';}
  }
  if(!state.loading&&!state.error)render();
})();

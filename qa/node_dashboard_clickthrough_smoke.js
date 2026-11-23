// No DOM / network package required. Exercises the actual CRM JavaScript with
// an in-memory DOM and authorized employee/admin API fixtures.
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..');
function mockUI(role){
 const elements=new Map();
 class Element{
  constructor(){this.innerHTML='';this.textContent='';this.dataset={};this.classList={add(){},remove(){},toggle(){}};this.style={};this.listeners={};this.value='';}
  querySelectorAll(){return [];} querySelector(){return null;} addEventListener(t,h){this.listeners[t]=h;}
  setAttribute(){} removeAttribute(){} focus(){} setSelectionRange(){} reset(){} append(){} closest(){return this;}
 }
 function el(name){name=String(name).replace(/^#/, '');if(!elements.has(name))elements.set(name,new Element());return elements.get(name)}
 const doc={body:el('body'),documentElement:el('html'),cookie:'',querySelector:el,getElementById:el,querySelectorAll:()=>[],addEventListener:()=>{},createElement:()=>new Element()};
 doc.documentElement.dataset.theme='light';
 const clientId='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa', projectId='bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb';
 const mkTask=(id,title,owner,status)=>({id,code:'T-'+id.slice(0,4),title,description:'A design task',clientId,clientName:'Studio Client',projectId,projectName:'Website relaunch',assignedTo:owner,assignedName:owner===2?'Maya':'Other',assigneeIds:[owner],status,priority:'high',dueAt:'2026-11-20T10:00:00+05:30',tags:[]});
 const tasks=[mkTask('11111111-1111-4111-8111-111111111111','Design the hero',2,'in_progress'),mkTask('22222222-2222-4222-8222-222222222222','Publish landing page',2,'completed'),mkTask('33333333-3333-4333-8333-333333333333','Other person secret task',3,'todo')];
 const ctx={id:role==='employee'?2:1,name:role==='employee'?'Maya Dev':'Administrator',role,roleLabel:role==='employee'?'Employee':'Super Admin'};
 const work={ctx, clients:[{id:clientId,name:'Studio Client',code:'client'}],members:[{id:1,role:'admin',name:'Administrator'},{id:2,role:'employee',name:'Maya Dev'},{id:3,role:'employee',name:'Other'}],assignments:[],projects:[{id:projectId,clientId,clientName:'Studio Client',title:'Website relaunch',status:'active',code:'TF-01',progress:40,ownerName:'Maya Dev',groupName:'',tags:[]}],tasks,updates:[],notes:[],events:[],notifications:[],activities:[],records:[]};
 const operations={attendance:[],leaves:[],timeEntries:[],approvalRequests:[],supportTickets:[],milestones:[],salesLeads:[],savedViews:[],serverToday:'2026-11-19'};
 const plus={projectIssues:[],projectFeed:[],projectDocs:[],projectTeams:[],taskLists:[],dashboardLayouts:[],defaultWidgets:{global:['stats','today','overdue'],project:['stats','progress']},projectGroups:[]};
 const requests=[];
 const env={__requests:requests,window:null,document:doc,console,Promise,Date,Intl,Math,Number,String,Object,Array,Set,Map,JSON,Error,URLSearchParams,FormData:class{},location:{hash:''},history:{replaceState(){}},localStorage:{getItem(){return null},setItem(){}},MutationObserver:class{observe(){}},setInterval(){},setTimeout(fn){fn()},clearTimeout(){},alert(){},confirm(){return true},navigator:{},fetch:async(url,opts={})=>{
    if(opts.method==='POST')requests.push({url,body:JSON.parse(opts.body)});
    let data=url.startsWith('/api/workspace/')?work:url.startsWith('/api/operations/')?operations:url.startsWith('/api/projects-plus/')?plus:{};
    return {ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)};
  }};
 env.window=env;
 return {env,el,taskIds:tasks.map(t=>t.id),projectId};
}

async function initialize(role){
  const {env,el,projectId,taskIds}=mockUI(role);
  const fetchOriginal=env.fetch;
  env.fetch=async (url,opts={})=>{
    const reply=await fetchOriginal(url,opts);
    if(!opts.method && url==='/api/workspace/'){
      const data=await reply.json();
      data.tasks[0].startAt='2026-11-19T09:00:00+05:30';
      data.tasks[0].dueAt='2026-11-18T17:00:00+05:30';
      data.tasks[1].dueAt='2026-11-19T17:00:00+05:30';
      return {...reply,json:async()=>data,text:async()=>JSON.stringify(data)};
    }
    if(!opts.method && url==='/api/operations/'){
      const data=await reply.json();
      data.milestones=[{id:51,title:'Published phase',projectId,projectName:'Website relaunch',status:'completed',dueDate:'2026-11-19'}, {id:52,title:'Drafting phase',projectId,projectName:'Website relaunch',status:'active',dueDate:'2026-11-25'}];
      return {...reply,json:async()=>data,text:async()=>JSON.stringify(data)};
    }
    return reply;
  };
  const ctx=vm.createContext(env);
  for(const filename of ['app.js','enterprise.js','projects_plus.js'])vm.runInContext(fs.readFileSync(path.join(root,'workspace/static/workspace',filename),'utf8'),ctx,{filename,timeout:5000});
  for(let i=0;i<40&&!el('#mainContent').innerHTML.includes('tfHomeTasks');i++)await new Promise(resolve=>setImmediate(resolve));
  assert(ctx.state.ctx&&el('#mainContent').innerHTML.includes('tfHomeTasks'),`CRM did not load for ${role}`);
  return {ctx,el,projectId,taskIds,home:()=>el('#mainContent').innerHTML};
}
async function admin(){
  const {ctx,el,projectId,taskIds,home}=await initialize('admin');
  assert(home().includes('class="tf-metric tf-metric-link"')&&home().includes("dashboardDrilldown('open_tasks'"),'Metrics must be buttons with linked actions');
  assert(home().includes('tf-widget-view-all'),'Widget headers must offer full-list navigation');
  const originalTasks=ctx.state.tasks;ctx.state.tasks=[];ctx.render();
  assert(home().includes('tf-widget-empty-action'),'Empty task widgets must link to their full list');
  ctx.state.tasks=originalTasks;ctx.render();
  assert(home().includes('tf-home-task-sort')&&home().includes('sortHomeTasks'),'Task register columns must be sortable');
  assert(home().includes('TFPlus.openTaskDrawer('),'Task rows must open a detail drawer');
  ctx.TFPlus.sortHomeTasks('title');let h=home();
  assert(h.indexOf('Design the hero')<h.indexOf('Publish landing page'),'Ascending sort failed');
  ctx.TFPlus.sortHomeTasks('title');h=home();
  assert(h.indexOf('Design the hero')>h.indexOf('Publish landing page'),'Descending sort failed');
  const action=(key,p='',m='')=>ctx.TFPlus.dashboardDrilldown(key,p,m);
  action('open_tasks');assert(ctx.state.tab==='tasks'&&home().includes('Design the hero')&&!home().includes('Publish landing page'),'Open tasks drilldown failed');
  action('completed_tasks');assert(ctx.state.tab==='tasks'&&home().includes('Publish landing page')&&!home().includes('Design the hero'),'Completed tasks drilldown failed');
  action('overdue_tasks');assert(ctx.state.tab==='tasks'&&home().includes('Design the hero')&&!home().includes('Publish landing page'),'Overdue tasks drilldown failed');
  action('due_today');assert(ctx.state.tab==='tasks'&&home().includes('Design the hero'),'Today drilldown failed to include tasks starting today');
  action('active_projects');assert(ctx.state.tab==='projects'&&home().includes('Website relaunch')&&home().includes('option value="active" selected'),'Active projects drilldown failed');
  action('open_issues');assert(ctx.state.tab==='issues','Issues metric did not go to issue tracker');
  action('closed_phases');assert(ctx.state.tab==='phases'&&home().includes('Published phase')&&!home().includes('Drafting phase'),'Closed phases should filter to completed');
  action('all_tasks',projectId);assert(ctx.state.tab==='projects'&&home().includes('Website relaunch')&&home().includes('tf-task-toolbar'),'Project task drilldown failed');
  action('member_tasks',projectId,2);assert(!home().includes('Other person secret task'),'Member drilldown did not filter tasks');
  ctx.go('overview');
  await ctx.TFPlus.openTaskDrawer(taskIds[0]);
  assert(el('#tfTaskDrawerHost').innerHTML.includes('PROJECTS / TASK DETAILS'),'Task drawer did not open');
  console.log('Admin dashboard clickthrough: metrics, task drilldowns, phase filters, date filters, sorting, task drawer PASSED');
}
async function employee(){
  const {ctx,home,taskIds}=await initialize('employee');
  assert(home().includes('tf-metric-link')&&home().includes('tf-home-task-sort'),'Employee click targets missing');
  assert(!home().includes('Other person secret task'),'Employee home exposes coworker task');
  ctx.TFPlus.dashboardDrilldown('my_open_tasks');
  assert(ctx.state.tab==='tasks'&&home().includes('Design the hero')&&!home().includes('Other person secret task'),'Employee own-task drilldown not restricted');
  ctx.TFPlus.dashboardDrilldown('due_today');
  assert(ctx.state.tab==='tasks'&&home().includes('Design the hero'),'Employee due today drilldown failed');
  ctx.TFPlus.dashboardDrilldown('closed_phases');
  assert(ctx.state.tab==='projects','Employee should not see staff-only phase register');
  console.log('Employee dashboard clickthrough: assigned task isolation and navigation PASSED');
}
(async()=>{await admin();await employee();})().catch(e=>{console.error(e.stack);process.exitCode=1});

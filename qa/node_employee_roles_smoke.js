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
 const env={window:null,document:doc,console,Promise,Date,Intl,Math,Number,String,Object,Array,Set,Map,JSON,Error,URLSearchParams,FormData:class{},location:{hash:''},history:{replaceState(){}},localStorage:{getItem(){return null},setItem(){}},MutationObserver:class{observe(){}},setInterval(){},setTimeout(fn){fn()},clearTimeout(){},alert(){},confirm(){return true},navigator:{},fetch:async(url)=>{
    let data=url.startsWith('/api/workspace/')?work:url.startsWith('/api/operations/')?operations:url.startsWith('/api/projects-plus/')?plus:{};
    return {ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data)};
  }};
 env.window=env;
 return {env,el,taskIds:tasks.map(t=>t.id),projectId};
}
async function run(role){
 const {env,el,projectId}=mockUI(role);const ctx=vm.createContext(env);
 for(const filename of ['app.js','enterprise.js','projects_plus.js'])vm.runInContext(fs.readFileSync(path.join(root,'workspace/static/workspace',filename),'utf8'),ctx,{filename,timeout:5000});
 for(let i=0;i<24&&!el('#mainContent').innerHTML.includes('tfHomeTasks');i++)await new Promise(resolve=>setImmediate(resolve));
 assert(ctx.state.ctx,`${role} load did not finish`);
 // dashboard html and navigation are the actual DOM string painted by shell/render.
 const home=()=>el('#mainContent').innerHTML,nav=()=>el('#nav').innerHTML;
 assert(home().includes('id="tfHomeTasks"'),`${role}: home task register missing (tab=${ctx.state.tab}, loading=${ctx.state.loading}, error=${ctx.state.error}, html=${home().slice(0,1800)})`);
 if(role==='employee'){
  assert(vm.runInContext('menus.employee.length',ctx)===9,`${role}: ${nav()}`);
  assert(nav().includes('My tasks')&&nav().includes('Attendance'), 'Employee task/attendance nav missing');
  assert(!nav().includes('Admin activity')&&!nav().includes('Invoices')&&!nav().includes('Team &amp; hierarchy'),'Employee got manager nav');
  assert(home().includes('Design the hero')&&home().includes('Publish landing page'),'Employee missing assigned tasks');
  assert(!home().includes('Other person secret task'),'Employee home task register includes unassigned coworker task');
  assert(!home().includes('Customize dashboard'),'Employee got dashboard management');
  ctx.TFPlus.taskEditor('11111111-1111-4111-8111-111111111111');
  assert(el('#modalRoot').innerHTML.includes('Mark completed'),'Employee task detail missing completion action');
  assert(!el('#modalRoot').innerHTML.includes('name="assignedTo"'),'Employee task detail has manager edit field');
  ctx.closeModal();
  ctx.go('team');assert(ctx.state.tab==='overview','Employee can navigate to hidden team page');
  ctx.TFPlus.homeTaskFilter('query','Publish');
  assert(home().includes('Publish landing page')&&!home().includes('Design the hero'),'Search did not filter tasks');
  ctx.TFPlus.homeTaskFilter('query','');
  ctx.TFPlus.homeTaskFilter('status','completed');
  assert(home().includes('Publish landing page')&&!home().includes('Design the hero'),'Status filter broken');
  ctx.TFPlus.homeTaskFilter('status','all');
  ctx.TFPlus.openProject(projectId);
  assert(home().includes('Documents')&&!home().includes('>Users</button>')&&!home().includes('>Reports</button>'),'Employee has management project tabs');
  ctx.go('tasks');assert(!home().includes('＋ Add task'),'Employee can create new tasks from list');
 }else{
  assert(nav().includes('Team &amp; hierarchy')&&nav().includes('Workflows'),'Admin menu changed: '+nav().slice(0,950));
  assert(home().includes('Other person secret task'),'Admin lacks access to team tasks');
  assert(home().includes('Customize dashboard'),'Admin customization missing');
 }
 console.log(`${role} UI smoke test passed: ${vm.runInContext('menus[state.ctx.role].length',ctx)} navigation items, task register + role controls`);
}
(async()=>{await run('employee');await run('admin')})().catch(e=>{console.error(e.stack);process.exitCode=1});

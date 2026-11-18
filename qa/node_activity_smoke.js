const vm=require('vm'),fs=require('fs');
const apiData={summary:{unread:3,pendingLeaves:1,pendingTimesheets:1,pendingApprovals:1,onShift:2,todayActions:8},
 events:[{id:5,employee:'Ayesha Singh',employeeId:2,category:'tasks',action:'Changed task status',detail:'Campaign: To do -> In progress',client:'Sample Client',at:'2026-11-18T11:02:00+05:30'}],nextBefore:null,
 employees:[{id:2,name:'Ayesha Singh'}],leaves:[{id:'00000000-0000-0000-0000-000000000001',employee:'Ayesha Singh',type:'Annual',startDate:'2026-11-21',endDate:'2026-11-22',reason:'Personal leave'}],
 timesheets:[{id:'00000000-0000-0000-0000-000000000002',employee:'Ayesha Singh',minutes:60,date:'2026-11-18',client:'Sample Client'}],
 approvals:[{id:'00000000-0000-0000-0000-000000000003',requestedBy:'Ayesha Singh',title:'Approve designs',client:'Sample Client'}]};
const main={innerHTML:'',insertAdjacentHTML(where,html){this.innerHTML+=html}};
const bell={innerHTML:'',title:'',onclick:null,setAttribute(){}};
const nav={append(){},querySelector(){return null}};
const doc={cookie:'csrftoken=demo',visibilityState:'visible',getElementById(id){if(id==='mainContent')return main;if(id==='bellBtn')return bell;if(id==='tfAdminOverviewStrip')return null;return null},querySelector(){return nav},addEventListener(){},createElement(){return {className:'',textContent:''}}};
const ctx={state:{ctx:{role:'admin'},tab:'overview',loading:false,error:'',notifications:[]},menus:{admin:['overview']},labels:{overview:'Home'},window:{},document:doc,location:{hash:''},setInterval(){},clearTimeout, setTimeout,queueMicrotask, fetch:async(url,opts)=>({ok:true,json:async()=>opts?.method==='POST'?{ok:true}:String(url).includes('summary=1')?{summary:apiData.summary}:apiData}),console,confirm:()=>true,closeModal(){},openModal(){},alert(){},Date,Intl,URLSearchParams,Number,Math};
ctx.window.state=ctx.state;ctx.window.go=(x)=>{ctx.state.tab=x;ctx.render()};ctx.render=()=>{main.innerHTML='base view';};ctx.go=ctx.window.go;
vm.createContext(ctx);vm.runInContext(fs.readFileSync('workspace/static/workspace/admin_activity.js','utf8'),ctx);
if(!ctx.menus.admin.includes('admin_activity'))throw Error('Admin nav was not registered');
ctx.window.TFAdminActivity.show();
setTimeout(()=>{
 if(!main.innerHTML.includes('Needs your decision'))throw Error('Approval tab missing');
 if(!main.innerHTML.includes('Personal leave'))throw Error('Leave request missing');
 if(!main.innerHTML.includes('Decline'))throw Error('Decline action missing');
 ctx.window.TFAdminActivity.switchTab('history');
 if(!main.innerHTML.includes('Ayesha Singh')||!main.innerHTML.includes('Changed task status'))throw Error('Activity feed missing');
 if(!main.innerHTML.includes('Search actions'))throw Error('Activity filters missing');
 console.log('ADMIN ACTIVITY UI SMOKE: PASS');
},50);

const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.resolve(__dirname,'../workspace/static/workspace/app.js'),'utf8');
const begin=source.indexOf('function clients(){'),end=source.indexOf('\nfunction team(){',begin);
assert(begin>=0&&end>begin,'Client renderer missing');
const renderer=source.slice(begin,end);
const baseClients=[{id:'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa',code:'ST-01',name:'Studio <Partners>',company:'Creative Group',email:'team@example.test',status:'active',statusLabel:'Active',package:'10000',assignedNames:['Maya','Ravi']},{id:'bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb',name:'Second workspace',company:'',status:'inactive',statusLabel:'Inactive',assignedNames:[]}];
function make(role,clients=baseClients){const context={state:{ctx:{role},clients},initials:s=>String(s).split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase(),esc:s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])),badge:s=>`<span class="badge">${s}</span>`,heading:s=>`<h1>Clients</h1><p>${s}</p>`};vm.createContext(context);vm.runInContext(renderer,context);return context.clients()}
const admin=make('admin');const staff=make('employee');const empty=make('admin',[]);
assert(admin.includes('tf-client-register')&&admin.includes('<table class="tf-client-table">'),'Client table missing');
assert(admin.includes('Studio &lt;Partners&gt;')&&!admin.includes('Studio <Partners>'),'Client escaping broken');
assert(admin.includes('10000')&&admin.includes('Maya, Ravi'),'Package/team missing');
assert(admin.includes('＋ New client')&&admin.includes('Assign employee'),'Admin management actions missing');
assert(staff.includes('Studio &lt;Partners&gt;')&&!staff.includes('Assign employee')&&!staff.includes('New client'),'Employee has manager-only controls');
assert(empty.includes('No clients yet'),'Empty state missing');
console.log('CLIENTS UI SMOKE: PASS; styled table, company/package/team, no cross-role controls, XSS-safe rendering');

const fs=require('fs');const vm=require('vm');
const output={innerHTML:''};let didRender=0;const clients=[{id:'c123',name:'Acme Digital',company:'Acme Digital',email:'billing@acme.example',package:'Premium Package'}];
const data={invoices:[{id:'inv1',number:'TF-2026-00001',clientId:'c123',clientName:'Acme Digital',packageName:'Premium Package',status:'issued',total:'10000.00',paidTotal:'0.00',balanceDue:'10000.00',subtotal:'10000',discount:'0',taxAmount:'0',taxRate:'0',taxLabel:'Tax',issueDate:'2026-11-18',dueDate:'2026-11-25',items:[]}],canManage:true,seller:{company_name:'Techfinitys'},schedules:[]};
let modal=''; const form={onsubmit:null,addEventListener(){},querySelectorAll(){return[]},elements:{clientId:{value:''},amount:{value:''},quantity:{value:1},taxRate:{value:0},discount:{value:0}}};const ctx={
 state:{tab:'overview',ctx:{id:1,role:'manager'},clients,loading:false,error:'',records:[]},
 render(){didRender++}, shell(){}, window:{},document:{getElementById(id){if(id==='mainContent')return output;if(id==='tfBillForm')return form;if(id==='tfBillExtras')return {insertAdjacentHTML(){}};if(id==='tfBillEstimate')return {innerHTML:''};return null}},
 esc(s){return String(s).replace(/[&<>"']/g,(m)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))},
 cookie(){return 'csrftoken'},fetch:async (url,opts)=>({ok:true,json:async()=>opts?.method==='POST'?{invoice:data.invoices[0]}:data}),
 queueMicrotask,openModal(html){modal=html},closeModal(){modal=''},alert(){},confirm(){return true},prompt(){return 'Testing'},
 console,Date,Intl,Number,encodeURIComponent,decodeURIComponent,String,Object,Array,Math};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('workspace/static/workspace/billing.js','utf8'),ctx,{filename:'billing.js'});
ctx.state.tab='invoices';ctx.render();
setTimeout(()=>{
 if(!output.innerHTML.includes('Invoice register'))throw Error('Invoice table not rendered');
 if(!output.innerHTML.includes('TF-2026-00001'))throw Error('Invoice number missing');
 if(!output.innerHTML.includes('New invoice'))throw Error('Manager create action missing');
 if(!output.innerHTML.includes('Download invoice PDF'))throw Error('PDF link missing');
 ctx.window.TFBilling.newInvoice();
 if(!modal.includes('Create client invoice')||!modal.includes('Tax %'))throw Error('Invoice form missing fields');
 console.log('BILLING UI VM smoke: PASS; render hooks:',didRender,'HTML length:',output.innerHTML.length,'form:',modal.length);
},50);

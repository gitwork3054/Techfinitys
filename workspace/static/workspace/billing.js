/* Techfinitys Billing Studio - server-side invoices, payment ledger and branded PDFs. */
(() => {
  'use strict';
  const API='/api/billing/';
  const ui={data:null,loading:false,error:'',tab:'invoices',search:'',client:'',status:'all',message:''};
  const money=n=>'₹'+new Intl.NumberFormat('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(n)||0);
  const e=x=>esc(String(x ?? ''));
  const day=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'});
  const plusDays=(d,n)=>{const dt=new Date((d||day())+'T12:00:00Z');dt.setUTCDate(dt.getUTCDate()+n);return dt.toISOString().slice(0,10)};
  const icon=(name)=>({paid:'✓',partially_paid:'◐',issued:'↗',draft:'◌',void:'×'})[name]||'•';
  const label=s=>({draft:'Draft',issued:'Issued',partially_paid:'Partially paid',paid:'Paid',void:'Voided'})[s]||s;
  const choice=(v,label,sel)=>`<option value="${e(v)}" ${String(v)===String(sel)?'selected':''}>${e(label)}</option>`;
  const clientOptions=id=>`<option value="">Select client</option>${(state.clients||[]).map(c=>choice(c.id,c.name,id)).join('')}`;
  const canManage=()=>Boolean(ui.data?.canManage);
  const profile=()=>ui.data?.seller||{};
  const records=()=>ui.data?.invoices||[];
  const schedules=()=>ui.data?.schedules||[];
  const badge=status=>`<span class="tf-bill-status ${e(status)}">${icon(status)} ${e(label(status))}</span>`;
  const primary=(name,action)=>`<button class="tf-bill-btn primary" type="button" onclick="TFBilling.${action}">${name}</button>`;
  const secondary=(name,action)=>`<button class="tf-bill-btn" type="button" onclick="TFBilling.${action}">${name}</button>`;

  async function api(data){
    const response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},credentials:'same-origin',body:JSON.stringify(data)});
    const payload=await response.json().catch(()=>({error:'Server did not return JSON'}));
    if(!response.ok)throw Error(payload.error||`Error ${response.status}`);
    return payload;
  }
  async function reload(){
    ui.loading=true;ui.error='';draw();
    try{
      const response=await fetch(API,{cache:'no-store',credentials:'same-origin'});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'Unable to fetch billing data');
      ui.data=data;
    }catch(err){ui.error=err.message||String(err)}
    finally{ui.loading=false;draw()}
  }
  const dateFmt=x=>x||'—';
  const lines=i=>i.items||[];
  const subtotal=i=>Number(i.subtotal||0);
  const paid=i=>Number(i.paidTotal||0);
  const sum=(list,key)=>list.reduce((acc,r)=>acc+Number(r[key]||0),0);
  function heading(){
    return `<div class="tf-bill-heading"><div><span class="tf-bill-eyebrow">TECHFINITYS / CLIENT BILLING</span><h1>Invoices & billing</h1><p>Client packages, accurate totals, payments and stamped invoice PDFs.</p></div><div class="tf-bill-actions">${canManage()?`${primary('＋ New invoice','newInvoice()')}<a class="tf-bill-btn" href="/api/billing/export/">↓ Export CSV</a>`:''}${secondary('⟳ Refresh','refresh()')}</div></div>`;
  }
  function tabs(){return `<div class="tf-bill-tabs">${[['invoices','Invoices'],...(canManage()?[['schedules','Recurring plans'],...(state.ctx?.role==='admin'?[['profile','Letterhead & stamp']]:[])]:[])].map(([k,n])=>`<button type="button" class="${ui.tab===k?'active':''}" onclick="TFBilling.tab('${k}')">${n}</button>`).join('')}</div>`;}
  function metrics(){
    const invoices=records().filter(i=>i.status!=='draft'&&i.status!=='void');
    const outstanding=invoices.filter(i=>i.status!=='paid');
    return `<div class="tf-bill-metrics"><div class="tf-bill-metric"><span>Total invoiced</span><strong>${money(sum(invoices,'total'))}</strong><small>${invoices.length} issued invoices</small></div>
      <div class="tf-bill-metric"><span>Outstanding</span><strong>${money(sum(outstanding,'balanceDue'))}</strong><small>Awaiting payment</small></div>
      <div class="tf-bill-metric"><span>Payments received</span><strong>${money(sum(invoices,'paidTotal'))}</strong><small>Recorded transactions</small></div>
      <div class="tf-bill-metric"><span>Overdue</span><strong>${invoices.filter(i=>i.overdue).length}</strong><small>Past the due date</small></div></div>`;
  }
  function invoices(){
    const query=ui.search.trim().toLowerCase();
    let rows=records().filter(i=>
      (!query||[i.number,i.packageName,i.clientName,i.billToName].some(v=>String(v||'').toLowerCase().includes(query)))&&
      (!ui.client||i.clientId===ui.client)&&
      (ui.status==='all'||(ui.status==='overdue'?i.overdue:i.status===ui.status)));
    return `${metrics()}<section class="tf-bill-pane"><div class="tf-bill-pane-head"><div><h3>Invoice register</h3><p>Click any invoice to inspect charges and payments.</p></div><span>${rows.length} records</span></div>
      <div class="tf-bill-filters"><label class="tf-bill-search"><span>⌕</span><input aria-label="Search invoices" placeholder="Search number, client, package…" value="${e(ui.search)}" oninput="TFBilling.filter('search',this.value)"></label>
      ${canManage()?`<select aria-label="Filter by client" onchange="TFBilling.filter('client',this.value)"><option value="">All clients</option>${state.clients.map(c=>choice(c.id,c.name,ui.client)).join('')}</select>`:''}
      <select aria-label="Filter by status" onchange="TFBilling.filter('status',this.value)">${['all','draft','issued','partially_paid','paid','overdue','void'].filter(x=>canManage()||!['draft'].includes(x)).map(s=>choice(s,s==='all'?'All statuses':label(s),ui.status)).join('')}</select></div>
      <div class="tf-bill-table-wrap"><table class="tf-bill-table"><thead><tr><th>Invoice</th><th>Client / package</th><th>Issued</th><th>Due</th><th>Amount</th><th>Balance</th><th>Status</th><th>PDF</th></tr></thead>
      <tbody>${rows.map(i=>`<tr><td><button class="tf-bill-link" type="button" onclick="TFBilling.details('${i.id}')">${e(i.number)}</button></td><td><strong>${e(i.clientName)}</strong><small>${e(i.packageName)}</small></td><td>${e(i.issueDate)}</td><td>${e(i.dueDate)}${i.overdue?'<span class="tf-bill-overdue">OVERDUE</span>':''}</td><td>${money(i.total)}</td><td><strong>${money(i.balanceDue)}</strong></td><td>${badge(i.status)}</td><td><a class="tf-bill-download" href="/api/billing/pdf/${encodeURIComponent(i.id)}/" title="Download A4 invoice PDF" aria-label="Download invoice PDF">↓ PDF</a></td></tr>`).join('')||`<tr><td colspan="8" class="tf-bill-empty">No invoices found. ${canManage()?'Create a draft to start billing a client.':'Your issued invoices will appear here.'}</td></tr>`}</tbody></table></div></section>`;
  }
  function recurring(){
    return `<section class="tf-bill-pane"><div class="tf-bill-pane-head"><div><h3>Automatic billing plans</h3><p>Generate monthly, quarterly or yearly invoices without re-entering packages.</p></div>${primary('＋ Create recurring plan','newSchedule()')}</div><div class="tf-bill-advice">Plans generate new drafts when the daily <code>generate_invoices</code> job runs. Switch on “Auto-issue” only when you approve automatic invoice issuing. A job scheduler and persistent database are required for unattended operation.</div>
      <div class="tf-bill-table-wrap"><table class="tf-bill-table"><thead><tr><th>Client</th><th>Package</th><th>Cycle</th><th>Next run</th><th>Amount</th><th>State</th><th>Automation</th><th></th></tr></thead><tbody>
      ${schedules().map(s=>`<tr><td>${e(s.clientName)}</td><td><strong>${e(s.packageName)}</strong></td><td>${{1:'Monthly',3:'Quarterly',12:'Yearly'}[s.months]}</td><td>${e(s.nextRunOn)}</td><td>${money(Number(s.amount)*Number(s.quantity))}</td><td>${s.active?'<span class="tf-bill-status issued">Active</span>':'<span class="tf-bill-status draft">Paused</span>'}</td><td>${s.autoIssue?'Auto-issue':'Save drafts'}</td><td><button class="tf-bill-btn mini" onclick="TFBilling.toggleSchedule('${s.id}',${!s.active})">${s.active?'Pause':'Resume'}</button></td></tr>`).join('')||'<tr><td colspan="8" class="tf-bill-empty">No recurring billing plans created yet.</td></tr>'}</tbody></table></div></section>`;
  }
  function stationery(){const p=profile();return `<section class="tf-bill-pane tf-bill-stationery"><div class="tf-bill-pane-head"><div><h3>Branded invoice stationery</h3><p>These details appear in your header, payment section, footer and authorized stamp.</p></div>${primary('Edit business details','editProfile()')}</div>
      <div class="tf-bill-stationery-preview"><div class="tf-bill-preview-head"><img alt="Techfinitys" src="/static/images/techfinitys-logo.png"><div><strong>${e(p.company_name||'Techfinitys')}</strong><small>${e(p.legal_name||p.address||'Configure your official business details')}</small></div><span>INVOICE</span></div><div class="tf-bill-preview-body"><div><small>CONTACT</small><strong>${e(p.email||'Add an invoicing email')}</strong><p>${e(p.phone||'')}${p.gstin?` · GSTIN ${e(p.gstin)}`:''}</p></div><div class="tf-bill-stamp-preview"><span>${e(p.stamp_text||'AUTHORISED')}</span><small>TECHFINITYS</small></div></div><div class="tf-bill-preview-foot">${e(p.footer_text||'Thank you for your business.')}</div></div>
      <div class="tf-bill-actions">${secondary('Upload company stamp','uploadStamp()')}${p.hasStamp?'<span class="tf-bill-hint">Custom stamp uploaded</span>':'<span class="tf-bill-hint">Using default vector stamp</span>'}</div></section>`;}
  function draw(){
    if(!state.ctx||state.tab!=='invoices'||state.loading||state.error)return;
    shell();
    const content=document.getElementById('mainContent');if(!content)return;
    content.innerHTML=`<div class="tf-billing">${heading()}${ui.error?`<div class="tf-bill-error" role="alert">${e(ui.error)}</div>`:''}${ui.message?`<div class="tf-bill-success" role="status">${e(ui.message)}</div>`:''}
    ${ui.data?`${tabs()}${ui.tab==='invoices'?invoices():ui.tab==='schedules'?recurring():stationery()}`:ui.loading?'<div class="tf-bill-pane tf-bill-empty">Loading client billing...</div>':'<div class="tf-bill-pane tf-bill-empty">Billing could not be loaded. Use Refresh to try again.</div>'}</div>`;
  }
  function showModal(title,description,body,onSubmit,submit='Save'){
    openModal(`<div class="tf-bill-form"><div class="tf-bill-eyebrow">TECHFINITYS / BILLING STUDIO</div><h2>${e(title)}</h2><p class="tf-bill-form-sub">${e(description)}</p><form id="tfBillForm">${body}<div class="tf-bill-form-error" id="tfBillError" role="alert" hidden></div><div class="tf-bill-form-actions"><button type="button" class="tf-bill-btn" onclick="closeModal()">Cancel</button><button class="tf-bill-btn primary" type="submit">${e(submit)}</button></div></form></div>`);
    const form=document.getElementById('tfBillForm');form.onsubmit=async(event)=>{
      event.preventDefault();const button=form.querySelector('button[type="submit"]');button.disabled=true;
      try{await onSubmit(form,new FormData(form));closeModal();ui.message='Invoice changes saved successfully.';await reload();}
      catch(err){document.getElementById('tfBillError').textContent=err.message;document.getElementById('tfBillError').hidden=false;button.disabled=false;}
    };
  }
  function getClient(id){return state.clients.find(c=>String(c.id)===String(id))||{};}
  function clientChanged(){const form=document.getElementById('tfBillForm');if(!form)return;const c=getClient(form.elements.clientId.value);for(const [field,v] of Object.entries({billToName:c.company||c.name||'',billToEmail:c.email||'',packageName:c.package||''})){const inp=form.elements[field];if(inp&&(!inp.value||inp.dataset.autofill==='yes')){inp.value=v;inp.dataset.autofill='yes';}}}
  function itemRow(desc='',qty=1,price=''){return `<div class="tf-bill-item-row"><input name="itemDescription" aria-label="Item description" maxlength="320" value="${e(desc)}" placeholder="Additional service or deliverable"><input type="number" aria-label="Quantity" name="itemQuantity" min="0.01" step="0.01" value="${e(qty)}"><input type="number" aria-label="Unit price" name="itemPrice" min="0.01" step="0.01" value="${e(price)}" placeholder="Amount"><button type="button" title="Remove item" class="tf-bill-remove" onclick="this.closest('.tf-bill-item-row').remove();TFBilling.previewTotals()">×</button></div>`;}
  function addItem(){const rows=document.getElementById('tfBillExtras');if(!rows)return;rows.insertAdjacentHTML('beforeend',itemRow());}
  function previewTotals(){const form=document.getElementById('tfBillForm');if(!form)return;const n=k=>Number(form.elements[k]?.value||0);
    let sub=n('amount')*n('quantity');
    form.querySelectorAll('.tf-bill-item-row').forEach(row=>{sub+=Number(row.querySelector('[name="itemPrice"]').value||0)*Number(row.querySelector('[name="itemQuantity"]').value||0)});
    const discount=n('discount');const tax=Math.max(0,sub-discount)*n('taxRate')/100;
    const block=document.getElementById('tfBillEstimate');if(block)block.innerHTML=`Subtotal <b>${money(sub)}</b> · Tax <b>${money(tax)}</b> · Total <strong>${money(Math.max(0,sub-discount+tax))}</strong>`;
  }
  const textInput=(title,name,value='',more='')=>`<label>${title}<input name="${name}" value="${e(value)}" ${more}></label>`;
  function newInvoice(id=''){
    const v=records().find(x=>x.id===id)||{};
    const seller=profile();
    const isEdit=Boolean(v.id);
    const initial=v.issueDate||day();const due=v.dueDate||plusDays(initial,7);
    const opts=state.clients||[];
    if(!opts.length){alert('Create a client account first.');return;}
    const body=`<div class="tf-bill-form-grid"><label>Client<select name="clientId" required onchange="TFBilling.clientChanged()">${clientOptions(v.clientId||'')}</select></label>${textInput('Bill to / legal name','billToName',v.billToName||'', 'maxlength="180"')}
      ${textInput('Billing email','billToEmail',v.billToEmail||'', 'type="email"')}${textInput('Customer GSTIN (optional)','billToGstin',v.billToGstin||'', 'maxlength="25"')}
      <label class="full">Billing address<textarea name="billToAddress" rows="2" maxlength="1200">${e(v.billToAddress||'')}</textarea></label>
      ${textInput('Package / service name','packageName',v.packageName||'', 'maxlength="240" required')}${textInput('Package amount (INR)','amount',v.items?.[0]?.unitPrice||'','type="number" min="0.01" step="0.01" required')}
      ${textInput('Quantity','quantity',v.items?.[0]?.quantity||'1','type="number" min="0.01" step="0.01" required')}${textInput('Invoice date','issueDate',initial,'type="date" required')}
      ${textInput('Due date','dueDate',due,'type="date" required')}${textInput('Tax label','taxLabel',v.taxLabel||'Tax','maxlength="45"')}
      ${textInput('Tax %','taxRate',v.taxRate||'0','type="number" step="0.01" min="0" max="100"')}${textInput('Discount (INR)','discount',v.discount||'0','type="number" step="0.01" min="0"')}
      ${textInput('Service from','periodStart',v.periodStart||'','type="date"')}${textInput('Service until','periodEnd',v.periodEnd||'','type="date"')}
      <label class="full">Description<textarea name="description" rows="2" maxlength="1500">${e(v.description||'')}</textarea></label>
      <label class="full">Notes<textarea name="notes" rows="2" maxlength="3000">${e(v.notes||'')}</textarea></label>
      <label class="full">Payment terms<textarea name="terms" rows="2" maxlength="3000">${e(v.terms||seller.terms||'')}</textarea></label></div>
      <div class="tf-bill-extra-title"><strong>Extra invoice lines</strong><button type="button" class="tf-bill-btn mini" onclick="TFBilling.addItem()">＋ Add line</button></div>
      <div id="tfBillExtras">${(v.items||[]).slice(1).map(l=>itemRow(l.description,l.quantity,l.unitPrice)).join('')}</div>
      <div class="tf-bill-preview-total" id="tfBillEstimate">Totals calculated automatically.</div>`;
    showModal(isEdit?'Edit draft invoice':'Create client invoice','Save a draft first. The invoice number is assigned when it is issued.',body,async(form,fd)=>{
      const d=Object.fromEntries(fd);const extra=[];
      form.querySelectorAll('.tf-bill-item-row').forEach(row=>{
        const name=row.querySelector('[name="itemDescription"]').value.trim();
        if(name)extra.push({description:name,quantity:row.querySelector('[name="itemQuantity"]').value,unitPrice:row.querySelector('[name="itemPrice"]').value});
      });
      const payload={action:'save_draft',...(isEdit?{id}:{}),clientId:d.clientId,billToName:d.billToName,billToEmail:d.billToEmail,
        billToAddress:d.billToAddress,billToGstin:d.billToGstin,packageName:d.packageName,description:d.description,
        issueDate:d.issueDate,dueDate:d.dueDate,taxLabel:d.taxLabel,taxRate:d.taxRate,discount:d.discount,
        periodStart:d.periodStart,periodEnd:d.periodEnd,notes:d.notes,terms:d.terms,
        items:[{description:d.packageName,quantity:d.quantity,unitPrice:d.amount},...extra]};
      await api(payload);
    },isEdit?'Save draft':'Create draft');
    if(!isEdit)clientChanged();
    document.getElementById('tfBillForm').addEventListener('input',previewTotals);previewTotals();
  }
  function details(id){
    const i=records().find(x=>x.id===id);if(!i)return;
    const paymentRows=(i.payments||[]).map(p=>`<div class="tf-bill-payment-row"><span>${e(p.paidOn)} · ${e(p.method)}${p.reference?` · ${e(p.reference)}`:''}</span><strong>${money(p.amount)}</strong></div>`).join('');
    openModal(`<div class="tf-bill-detail"><div class="tf-bill-eyebrow">CLIENT INVOICE / ${e(i.number)}</div><h2>${e(i.packageName)}</h2><p>${e(i.clientName)} · ${e(i.issueDate)} → ${e(i.dueDate)}</p><div class="tf-bill-detail-metrics"><div><small>Invoiced</small><strong>${money(i.total)}</strong></div><div><small>Paid</small><strong>${money(i.paidTotal)}</strong></div><div><small>Balance</small><strong>${money(i.balanceDue)}</strong></div></div>
      <div class="tf-bill-detail-lines">${lines(i).map(l=>`<div><span>${e(l.description)}<small>${e(l.quantity)} × ${money(l.unitPrice)}</small></span><b>${money(l.amount)}</b></div>`).join('')}</div>
      <div class="tf-bill-detail-totals">Subtotal ${money(i.subtotal)} · Discount ${money(i.discount)} · ${e(i.taxLabel)} ${e(i.taxRate)}%: ${money(i.taxAmount)}</div>
      ${paymentRows?`<h3>Payment history</h3>${paymentRows}`:''}
      <div class="tf-bill-form-actions"><button type="button" class="tf-bill-btn" onclick="closeModal()">Close</button><a class="tf-bill-btn" href="/api/billing/pdf/${encodeURIComponent(i.id)}/">↓ Download PDF</a>
      ${canManage()&&i.status==='draft'?`${secondary('Edit draft',`edit('${i.id}')`)}${primary('Issue invoice',`issue('${i.id}')`)}`:''}
      ${canManage()&&['issued','partially_paid'].includes(i.status)?`${secondary('Record payment',`pay('${i.id}')`)}${i.status==='issued'?secondary('Void',`voidInvoice('${i.id}')`):''}`:''}</div></div>`);
  }
  function edit(id){closeModal();newInvoice(id)}
  async function run(data,confirmText=''){
    if(confirmText&&!confirm(confirmText))return;
    try{await api(data);closeModal();ui.message='Action completed successfully.';await reload();}
    catch(err){alert(err.message||String(err))}
  }
  function issue(id){return run({action:'issue',id},'Issue this invoice? Its number and billing details will be locked.');}
  function voidInvoice(id){const reason=prompt('Reason for voiding this invoice (required):');if(!reason)return;return run({action:'void',id,reason},'Void this invoice? It remains in the audit history.');}
  function pay(id){const i=records().find(i=>i.id===id);if(!i)return;showModal('Record client payment',`Invoice ${i.number} · ${i.clientName}`,`<div class="tf-bill-form-grid">${textInput('Payment amount (INR)','amount',i.balanceDue,'type="number" step="0.01" min="0.01" required')}${textInput('Payment date','paidOn',day(),'type="date" required')}
    <label>Method<select name="method">${[['bank_transfer','Bank transfer'],['upi','UPI'],['cash','Cash'],['cheque','Cheque'],['card','Card'],['other','Other']].map(([a,b])=>choice(a,b,'bank_transfer')).join('')}</select></label>${textInput('Transaction reference','reference','','maxlength="120"')}
    <label class="full">Note<input name="note" maxlength="300" placeholder="Optional payment note"></label></div>`,async(form,fd)=>api({action:'payment',id,...Object.fromEntries(fd)}),'Record payment');}
  function newSchedule(){
    showModal('Create recurring billing plan','Each cycle creates an invoice draft. Auto-issue is optional and must be enabled intentionally.',`<div class="tf-bill-form-grid"><label>Client<select name="clientId" required>${clientOptions('')}</select></label>${textInput('Package','packageName','','required maxlength="240"')}
    ${textInput('Package amount (INR)','amount','','type="number" step="0.01" min="0.01" required')}${textInput('Quantity','quantity','1','type="number" step="0.01" min="0.01" required')}
    <label>Cycle<select name="months"><option value="1">Monthly</option><option value="3">Quarterly</option><option value="12">Yearly</option></select></label>${textInput('Next billing date','nextRunOn',day(),'type="date" required')}
    ${textInput('Payment terms (days)','dueDays','7','type="number" min="0" max="180"')}${textInput('Tax rate %','taxRate','0','type="number" step="0.01" min="0" max="100"')}
    ${textInput('Tax label','taxLabel','Tax','maxlength="45"')}${textInput('Discount','discount','0','type="number" min="0" step="0.01"')}
    <label class="full">Description<input name="description" maxlength="500"></label><label class="tf-bill-check full"><input type="checkbox" name="autoIssue"> Automatically issue each generated invoice instead of keeping it as a draft</label></div>`,async(form,fd)=>{
      const data=Object.fromEntries(fd);return api({action:'schedule',...data,autoIssue:fd.has('autoIssue')});
    },'Create recurring plan');
  }
  function toggleSchedule(id,active){return run({action:'schedule',id,active},active?'Resume this billing schedule?':'Pause future invoices for this schedule?');}
  function editProfile(){const p=profile();const fields=[['company_name','Company display name','180'],['legal_name','Legal business name','180'],['address','Full business address','1200'],['email','Invoice contact email','254'],['phone','Phone','55'],['website','Website','160'],['gstin','Seller GSTIN','25'],['pan','PAN','20'],['bank_name','Bank name','140'],['account_name','Account holder','180'],['account_number','Account number','70'],['ifsc','IFSC','20'],['upi_id','UPI ID','90'],['footer_text','Footer text','220'],['stamp_text','Stamp wording','65']];const form=fields.map(([key,n,max])=>textInput(n,key,p[key]||'',`maxlength="${max}" ${key==='company_name'?'required':''}`)).join('')+`<label class="full">Terms<textarea name="terms" rows="3" maxlength="3000">${e(p.terms||'')}</textarea></label>`;showModal('Company letterhead & footer','Used for future invoices. Previously issued invoices retain their seller information.',`<div class="tf-bill-form-grid">${form}</div>`,(el,fd)=>api({action:'profile',...Object.fromEntries(fd)}));}
  function uploadStamp(){showModal('Upload authorized stamp','PNG or JPG, maximum 450 KB. Use only a stamp you are authorized to represent.',`<label>Company stamp image<input type="file" name="stamp" accept="image/png,image/jpeg" required></label>`,async(form,fd)=>{
    const photo=fd.get('stamp');if(!photo||!photo.size||photo.size>450000)throw Error('Select a PNG or JPG image smaller than 450 KB');
    const r=await fetch('/api/billing/stamp/',{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':decodeURIComponent(cookie('csrftoken'))},body:fd});
    const res=await r.json().catch(()=>({error:'Upload failed'}));if(!r.ok)throw Error(res.error||'Upload failed');
  },'Upload stamp');}
  function filter(which,value){ui[which]=value;draw();}
  function tab(value){ui.tab=value;ui.message='';draw();}
  const originalRender=render;
  render=function(){
    if(state.tab!=='invoices'||!state.ctx||state.loading||state.error)return originalRender();
    // Retain Project Studio/WorkChat render hooks for nav and user photos.
    originalRender();
    if(!ui.data&&!ui.loading){ui.loading=true;queueMicrotask(reload);}
    draw();
  };
  window.render=render;
  window.TFBilling={refresh:reload,newInvoice,clientChanged,addItem,previewTotals,details,edit,issue,voidInvoice,pay,
    newSchedule,toggleSchedule,editProfile,uploadStamp,filter,tab};
})();

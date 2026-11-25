/* Zoho Projects direct import: account-bound OAuth, preview, user-approved one-way copy. */
(function(){
'use strict';
const base='/api/zoho/';
let connected=false,portals=[],projects=[],clientOptions=[],portalId='',selected=new Set(),loading=false;
function el(name,cls,text){
  const item=document.createElement(name);if(cls)item.className=cls;
  if(text!==undefined)item.textContent=text;
  return item;
}
function root(){
  let modal=document.getElementById('tfZohoImport');
  if(!modal){
    modal=el('div','tf-zoho-modal');modal.id='tfZohoImport';modal.hidden=true;
    const panel=el('section','tf-zoho-panel');
    panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');
    panel.setAttribute('aria-labelledby','tfZohoTitle');
    modal.append(panel);document.body.append(modal);
    modal.addEventListener('click',event=>{if(event.target===modal)close()});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!modal.hidden)close()});
  }
  return modal;
}
function close(){root().hidden=true;}
function button(text,fn,cls=''){
  const b=el('button','tf-zoho-btn '+cls,text);b.type='button';b.onclick=fn;return b;
}
function line(tag,cls,text){return el(tag,cls,text);}
function statusText(value){const p=document.querySelector('#tfZohoMessage');if(p)p.textContent=value;}
async function json(url,options){
  const res=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});
  const data=await res.json().catch(()=>({error:'The CRM returned an unexpected response'}));
  if(!res.ok)throw Error(data.error||'Request failed');
  return data;
}
function csrf(){const t=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='));return decodeURIComponent(t?.split('=').slice(1).join('=')||'');}
function post(url,data){
  return json(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(data)});
}
function drawFrame(){
 const modal=root(),panel=modal.firstElementChild;
 panel.replaceChildren();
 const header=el('div','tf-zoho-header');
 const names=el('div');names.append(el('span','tf-zoho-eyebrow','PROJECTS / IMPORT'),el('h2','', 'Import from Zoho Projects'));
 names.lastElementChild.id='tfZohoTitle';
 const dismiss=button('×',close,'tf-zoho-close');dismiss.setAttribute('aria-label','Close import');
 header.append(names,dismiss);panel.append(header);
 panel.append(el('p','tf-zoho-intro','Copy selected projects securely from your Zoho account. Your Zoho projects are never modified.'));
 const msg=el('p','tf-zoho-message','');msg.id='tfZohoMessage';panel.append(msg);
 const content=el('div','tf-zoho-content');content.id='tfZohoContent';panel.append(content);
 return content;
}
function select(label,opts,change){
 const row=el('label','tf-zoho-field');
 row.append(el('span','',label));
 const input=el('select');
 opts.forEach(([value,text])=>{const opt=el('option','',text);opt.value=String(value);input.append(opt);});
 input.onchange=()=>change(input.value);
 row.append(input);return row;
}
function connectionView(config){
 const c=drawFrame();
 if(!config.configured){
  c.append(el('p','tf-zoho-warning','Zoho OAuth is not configured for this CRM yet. Super Admin must add ZOHO_PROJECTS_CLIENT_ID and ZOHO_PROJECTS_CLIENT_SECRET to Render and register the redirect URL below in Zoho API Console.'));
  c.append(el('code','tf-zoho-code','https://techfinitys-crm-8wp1.onrender.com/api/zoho/callback/'));
  c.append(el('p','tf-zoho-hint','Use a Server-based Zoho OAuth application with read-only Projects and Portals scopes. No Zoho password is entered into Techfinitys.'));
  return;
 }
 c.append(el('p','tf-zoho-hint','Choose the same data centre as your Zoho account. For projects.zoho.in use India.'));
 const region=select('Zoho data centre',[['in','India (.in)'],['com','Global (.com)'],['eu','Europe (.eu)'],['com.au','Australia (.com.au)']],()=>{});
 c.append(region);
 c.append(button('Connect Zoho Projects',()=>{window.location.assign(base+'connect/?region='+encodeURIComponent(region.querySelector('select').value));},'primary'));
}
async function showConnected(){
 const c=drawFrame();
 if(!portals.length){
  c.append(el('p','tf-zoho-warning','No Zoho Projects portals were returned for this account.'));
  return;
 }
 const client=select('Import projects under this CRM client',[
  ['','Select destination client…'],...clientOptions.map(x=>[x.id,x.name])
 ],()=>{});
 client.id='tfZohoClient';c.append(client);
 const selector=select('Zoho Projects portal',portals.map(x=>[x.id,x.name]),async id=>{
  portalId=id;await loadPreview();
 });
 c.append(selector);
 c.append(el('div','tf-zoho-preview','Loading projects…')).lastElementChild.id='tfZohoPreview';
 const footer=el('div','tf-zoho-footer');
 footer.append(button('Disconnect',async()=>{await post(base+'disconnect/',{});connected=false;portals=[];projects=[];drawFrame();connectionView({configured:true});},'secondary'));
 footer.append(button('Import selected projects',importSelected,'primary')).lastElementChild.id='tfZohoImportSelected';
 c.append(footer);
 portalId=portals[0].id;
 await loadPreview();
}
async function loadPreview(){
 const box=document.getElementById('tfZohoPreview');if(!box)return;
 box.replaceChildren(el('p','tf-zoho-hint','Loading Zoho projects…'));
 try{
  const result=await json(base+'preview/?portal_id='+encodeURIComponent(portalId));
  projects=result.projects||[];selected.clear();drawPreview(result.limitReached);
 }catch(e){box.replaceChildren(el('p','tf-zoho-warning',e.message));}
}
function drawPreview(limited){
 const box=document.getElementById('tfZohoPreview');if(!box)return;
 box.replaceChildren();
 const summary=el('div','tf-zoho-summary');
 const count=el('span','',projects.length+' projects found'+(limited?' (first 500)':''));
 const all=button('Select available',()=>{projects.filter(p=>!p.imported).slice(0,100).forEach(p=>selected.add(p.id));drawPreview(limited);},'secondary');
 summary.append(count,all);box.append(summary);
 if(!projects.length){box.append(el('p','tf-zoho-hint','No projects found in this portal.'));return}
 const list=el('div','tf-zoho-list');
 projects.forEach(project=>{
  const label=el('label','tf-zoho-item'+(project.imported?' is-imported':''));
  const check=el('input');check.type='checkbox';check.disabled=!!project.imported;check.checked=selected.has(project.id);
  check.onchange=()=>{if(check.checked)selected.add(project.id);else selected.delete(project.id);const action=document.getElementById('tfZohoImportSelected');if(action)action.textContent='Import '+selected.size+' selected';};
  const text=el('span','tf-zoho-item-text');text.append(el('strong','',project.name),el('small','',project.imported?'Already imported':('Zoho ID: '+project.id+' · '+project.status)));
  label.append(check,text);list.append(label);
 });
 box.append(list);
 const action=document.getElementById('tfZohoImportSelected');if(action)action.textContent='Import '+selected.size+' selected';
}
async function importSelected(){
 if(loading)return;
 const dest=document.querySelector('#tfZohoClient select')?.value;
 if(!dest){statusText('Choose the destination client.');return}
 if(!selected.size){statusText('Select at least one project.');return}
 if(selected.size>100){statusText('Import up to 100 projects at a time.');return}
 const target=clientOptions.find(c=>String(c.id)===dest)?.name||'this client';
 if(!window.confirm('Import '+selected.size+' project(s) into '+target+'? Zoho will remain unchanged.'))return;
 loading=true;statusText('Importing projects…');
 try{
  const result=await post(base+'import/',{client_id:dest,portal_id:portalId,project_ids:[...selected]});
  statusText('Imported '+result.created.length+' projects. '+result.skipped+' duplicates skipped.');
  result.created.forEach(row=>{const p=projects.find(x=>x.id===row.id);if(p)p.imported=true;});
  selected.clear();
  await loadPreview();
  statusText('Imported '+result.created.length+' projects. '+result.skipped+' duplicates skipped. Refresh Projects to see the new records.');
 }catch(e){statusText(e.message);}
 finally{loading=false;}
}
async function open(){
 root().hidden=false;drawFrame();statusText('Checking Zoho connection…');
 try{
  const config=await json(base+'status/');
  connected=config.connected;clientOptions=config.clients||[];
  if(!connected){connectionView(config);return}
  const result=await json(base+'portals/');
  portals=result.portals||[];
  await showConnected();
 }catch(e){const content=document.getElementById('tfZohoContent');if(content)content.replaceChildren(el('p','tf-zoho-warning',e.message));statusText('');}
}
window.TFZohoImport={open,close};
})();

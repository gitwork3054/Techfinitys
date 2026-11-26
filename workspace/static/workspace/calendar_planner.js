/* Techfinitys Projects calendar: month/week planner using existing CRM events and tasks. */
(function(){
'use strict';
let shownMonth=new Date(new Date().getFullYear(),new Date().getMonth(),1);
let weekAnchor=new Date();
let mode='month',lastState=null;
const days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const names={meeting:'Meeting',shoot:'Shoot',deadline:'Deadline',review:'Review',reminder:'Reminder',other:'Event',task:'Task due'};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function parse(v){
 if(!v)return null;
 let m=String(v).match(/^(\d{4})-(\d{2})-(\d{2})$/);
 const d=m?new Date(+m[1],+m[2]-1,+m[3]):new Date(v);
 return Number.isFinite(d.valueOf())?d:null;
}
function key(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
function list(state){
 const entries=[];
 (state.events||[]).forEach(e=>{
  const date=parse(e.startAt);
  if(date)entries.push({date,key:key(date),type:(e.eventType||'other').toLowerCase(),kind:'event',id:String(e.id),title:e.title||'Event',client:e.clientName||'',time:date.toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit'}),record:e});
 });
 (state.tasks||[]).forEach(t=>{
  const date=parse(t.dueAt);
  if(date)entries.push({date,key:key(date),type:'task',kind:'task',id:String(t.id),title:t.title||'Task due',client:t.clientName||t.projectName||'',time:'',record:t});
 });
 return entries.sort((a,b)=>a.date-b.date||a.title.localeCompare(b.title));
}
function changeMonth(delta){
 if(mode==='week'){
   weekAnchor=new Date(weekAnchor.getFullYear(),weekAnchor.getMonth(),weekAnchor.getDate()+7*delta);
   shownMonth=new Date(weekAnchor.getFullYear(),weekAnchor.getMonth(),1);
 }else shownMonth=new Date(shownMonth.getFullYear(),shownMonth.getMonth()+delta,1);
 window.render?.();
}
function today(){
 const n=new Date();shownMonth=new Date(n.getFullYear(),n.getMonth(),1);weekAnchor=n;window.render?.();
}
function changeMode(value){
 if(!['month','week'].includes(value))return;
 if(value==='week'&&mode!=='week'){
   const now=new Date();
   weekAnchor=now.getMonth()===shownMonth.getMonth()&&now.getFullYear()===shownMonth.getFullYear()
     ?now:new Date(shownMonth.getFullYear(),shownMonth.getMonth(),1);
 }
 if(value==='month'&&mode==='week')shownMonth=new Date(weekAnchor.getFullYear(),weekAnchor.getMonth(),1);
 mode=value;window.render?.();
}
function schedule(day){
 if(lastState?.ctx?.role==='client')return;
 window.eventModal?.();
 if(!day)return;
 const input=document.querySelector('#modalRoot input[name="startAt"]');
 if(input)input.value=day+'T09:00';
}
function open(kind,id){
 const item=list(lastState||{}).find(x=>x.kind===kind&&x.id===String(id));if(!item)return;
 if(item.kind==='task'){
   if(lastState?.ctx?.role!=='client'&&window.taskModal)window.taskModal(item.id);
   else details('Task deadline',item.title,item.client,item.record.status||'Open');
   return;
 }
 const e=item.record;
 const detailsText=[e.clientName||'Organisation',e.startAt?'Starts: '+new Date(e.startAt).toLocaleString('en-IN'):'',e.endAt?'Ends: '+new Date(e.endAt).toLocaleString('en-IN'):'',e.description||'',(e.attendeeNames||[]).join(', ')].filter(Boolean).join('\n');
 details(e.eventTypeLabel||'Scheduled event',e.title,detailsText,'');
}
function details(type,title,description,status){
 const root=document.getElementById('modalRoot');if(!root)return;
 const cover=document.createElement('div');cover.className='overlay';cover.addEventListener('click',e=>{if(e.target===cover)root.replaceChildren();});
 const card=document.createElement('section');card.className='modal';
 const close=document.createElement('button');close.className='close icon';close.textContent='×';close.setAttribute('aria-label','Close event');close.onclick=()=>root.replaceChildren();
 const heading=document.createElement('div');heading.className='eyebrow';heading.textContent=type;
 const name=document.createElement('h2');name.textContent=title;
 const desc=document.createElement('p');desc.style.whiteSpace='pre-line';desc.textContent=description+(status?'\n'+status:'');
 card.append(close,heading,name,desc);cover.append(card);root.replaceChildren(cover);
}
function render(state){
 lastState=state;
 const rows=list(state),lookup=new Map();
 for(const entry of rows){if(!lookup.has(entry.key))lookup.set(entry.key,[]);lookup.get(entry.key).push(entry);}
 const start=mode==='week'
  ?new Date(weekAnchor.getFullYear(),weekAnchor.getMonth(),weekAnchor.getDate()-weekAnchor.getDay())
  :new Date(shownMonth.getFullYear(),shownMonth.getMonth(),1-new Date(shownMonth.getFullYear(),shownMonth.getMonth(),1).getDay());
 const title=mode==='week'
  ?start.toLocaleDateString('en-IN',{month:'long',year:'numeric'})+' · Week of '+start.getDate()
  :shownMonth.toLocaleDateString('en-IN',{month:'long',year:'numeric'});
 const nowKey=key(new Date());
 const count=mode==='week'?7:42;
 const cells=[];
 for(let i=0;i<count;i++){
  const date=new Date(start.getFullYear(),start.getMonth(),start.getDate()+i),day=key(date);
  const out=mode==='month'&&date.getMonth()!==shownMonth.getMonth();
  const items=lookup.get(day)||[],max=mode==='month'?3:8;
  const body=items.slice(0,max).map(entry=>{
   const cls=['meeting','shoot','deadline','review','reminder','task','other'].includes(entry.type)?entry.type:'other';
   const content=(entry.time?'<span class="tf-plan-time">'+esc(entry.time)+'</span>':'<span class="tf-plan-time">◆</span>')+'<span class="tf-plan-title">'+esc(entry.title)+'</span>';
   return '<button type="button" class="tf-plan-event tf-plan-'+cls+'" title="'+esc(entry.title+' · '+entry.client)+'" onclick="TFCalendarPlanner.open('+JSON.stringify(entry.kind)+','+JSON.stringify(entry.id)+')">'+content+'</button>';
  }).join('');
  cells.push('<div class="tf-plan-day'+(out?' is-outside':'')+(day===nowKey?' is-today':'')+'">'+
    '<div class="tf-plan-day-head"><span class="tf-plan-day-number">'+date.getDate()+'</span>'+
    (state.ctx?.role==='client'?'':'<button type="button" class="tf-plan-add" aria-label="Schedule on '+day+'" title="Add event" onclick="TFCalendarPlanner.schedule('+JSON.stringify(day)+')">+</button>')+
    '</div><div class="tf-plan-events">'+body+'</div>'+
    (items.length>max?'<span class="tf-plan-more">+'+(items.length-max)+' more</span>':'')+'</div>');
 }
 const heading='<div class="heading"><div><div class="eyebrow">TECHFINITYS / PLANNER</div><h1>Calendar</h1><p>Schedule shoots, meetings, reviews and tasks across your projects.</p></div></div>';
 const tools='<div class="tf-plan-toolbar"><div class="tf-plan-navigation">'+
 '<button type="button" class="tf-plan-today" onclick="TFCalendarPlanner.today()">Today</button>'+
 '<button type="button" class="tf-plan-arrow" aria-label="Previous '+mode+'" onclick="TFCalendarPlanner.changeMonth(-1)">‹</button>'+
 '<button type="button" class="tf-plan-arrow" aria-label="Next '+mode+'" onclick="TFCalendarPlanner.changeMonth(1)">›</button>'+
 '<h2>'+esc(title)+'</h2></div><div class="tf-plan-actions">'+
 '<div class="tf-plan-view"><button type="button" class="'+(mode==='month'?'active':'')+'" onclick="TFCalendarPlanner.changeMode(&quot;month&quot;)">Month</button>'+
 '<button type="button" class="'+(mode==='week'?'active':'')+'" onclick="TFCalendarPlanner.changeMode(&quot;week&quot;)">Week</button></div>'+
 (state.ctx?.role==='client'?'':'<button type="button" class="primary" onclick="TFCalendarPlanner.schedule()">＋ New event</button>')+
 '</div></div>';
 const legend=['shoot','meeting','deadline','review','reminder','task'].map(t=>'<span class="tf-plan-legend-'+t+'"><i></i>'+names[t]+'</span>').join('');
 return heading+'<section class="tf-planner" aria-label="Calendar planner">'+tools+
 '<div class="tf-plan-legends">'+legend+'</div>'+
 '<div class="tf-plan-scroll"><div class="tf-plan-grid">'+
 days.map(d=>'<div class="tf-plan-weekday">'+d+'</div>').join('')+cells.join('')+
 '</div></div></section>';
}
window.TFCalendarPlanner={render,changeMonth,today,changeMode,schedule,open};
})();
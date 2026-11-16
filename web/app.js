"use strict";
/* BMS web admin — three-panel layout: menu (left) · working panel (centre) · reference panel (right) */
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const ICONS={
 dashboard:'<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
 car:'<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
 route:'<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
 fuel:'<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
 building:'<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4M10 10h4M10 14h4M10 18h4"/>',
 users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
 file:'<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
 bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
 search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',plus:'<path d="M5 12h14M12 5v14"/>',x:'<path d="M18 6 6 18M6 6l12 12"/>',
 download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
 logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
 pl:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',pr:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/>',
 alert:'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3zM12 9v4M12 17h.01"/>',
 chev:'<path d="m9 18 6-6-6-6"/>',clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
 shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
 check:'<path d="M20 6 9 17l-5-5"/>',inbox:'<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
 phone:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>'};
Object.assign(ICONS,{plug:'<path d="M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',box:'<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>',
 ticket:'<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M12 11h4M12 16h4M8 11h.01M8 16h.01"/>',
 upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',wrench:'<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>'});
const I=(n,c="")=>`<svg class="ic ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${ICONS[n]||""}</svg>`;

let TOKEN=localStorage.bms_token,ME=null,PL=[],COMP=[],NOTE=null,PREM=localStorage.bms_prem||"",view="dashboard",recent=[],SUM=null,NOTI=[],TSUM=null;
const can=p=>ME&&(ME.perms.includes("*")||ME.perms.includes(p));

/* ---------- api ---------- */
async function api(p,o={}){const h={Authorization:"Bearer "+TOKEN};let b=o.body;
 if(b&&!(b instanceof FormData)){h["Content-Type"]="application/json";b=JSON.stringify(b)}
 const r=await fetch("/api"+p,{method:o.method||(b?"POST":"GET"),headers:h,body:b});
 if(r.status==401){signOut(false);throw Error("Signed out")}
 const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(typeof j.detail=="string"?j.detail:"Request failed");return j}
function signOut(reload=true){localStorage.removeItem("bms_token");TOKEN=null;ME=null;if(reload)location.hash="",location.reload();else showLogin()}
function toast(m,ok=true){const t=$("#toast");t.innerHTML=(ok?I("check"):I("alert"))+esc(m);t.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("show"),3200)}

/* ---------- formatting ---------- */
const dObj=d=>new Date(/Z|[+-]\d\d:\d\d$/.test(d)||d.length<=10?d:d+"Z");
const fmtD=d=>d?dObj(d).toLocaleDateString([],{day:"numeric",month:"short",year:"numeric"}):"–";
const fmtDT=d=>d?dObj(d).toLocaleString([],{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}):"–";
const n0=x=>x==null?"–":Number(x).toLocaleString();
const chip=(t,c="")=>`<span class="chip ${c}"><i></i>${esc(t)}</span>`;
const VS={available:["Available","ok"],on_trip:["On trip","gold"],maintenance:["Maintenance","bad"],retired:["Retired",""]};
const TS={requested:["Needs driver","warn"],assigned:["Assigned","gold"],started:["In progress","gold"],completed:["Completed","ok"],cancelled:["Cancelled",""]};
const sc=(m,k)=>chip(...(m[k]||[k,""]));
const daysTo=d=>Math.floor((dObj(d)-new Date(new Date().toDateString()))/864e5);
const expChip=d=>{if(!d)return chip("No date");const n=daysTo(d);return n<0?chip(`Expired ${-n}d ago`,"bad"):n<=30?chip(`Due in ${n} days`,"warn"):chip("Valid","ok")};
const ROLES={group_admin:"Group Admin",corporate_admin_head:"Corporate Admin Head",premises_admin:"Admin In-charge",maintenance_head:"Maintenance Head",finance:"Finance",hr:"HR",driver:"Driver",employee:"Employee"};
const init=n=>String(n).replace(/\(.*\)/,"").trim().split(/\s+/).slice(0,2).map(w=>w[0]).join("").toUpperCase();
const route2=r=>r.pickup?`${esc(r.pickup)} → ${esc(r.destination)}`:`To ${esc(r.destination)}`;
const tripNo=id=>"TR-"+String(id).padStart(4,"0");
const fileLink=(n,l="View")=>n?`<a href="/api/files/${n}?t=${TOKEN}" target="_blank" rel="noopener">${l}</a>`:`<span class="muted">–</span>`;
const thumb=n=>n?`<a href="/api/files/${n}?t=${TOKEN}" target="_blank" rel="noopener"><img class="thumb" alt="" src="/api/files/${n}?t=${TOKEN}" onerror="this.replaceWith(document.createTextNode('file'))"></a>`:"";

/* premises helpers */
const pById=id=>PL.find(p=>p.id==id),cName=id=>COMP.find(c=>c.id==id)?.name||"";
const desc=id=>{const o=new Set,st=[+id];while(st.length){const x=st.pop();o.add(x);PL.filter(p=>p.parent_id==x).forEach(p=>st.push(p.id))}return o};
const inPrem=pid=>!PREM||desc(PREM).has(pid);
const premName=id=>pById(id)?.name||"–";
const premScope=()=>PREM?premName(PREM):"All premises";

/* ---------- reusable UI ---------- */
const head=(t,s,a="")=>`<div class="ph"><div><h1>${t}</h1>${s?`<p>${s}</p>`:""}</div><div class="acts">${a}</div></div>`;
const emptyState=(t,s,ic="inbox")=>`<div class="empty">${I(ic)}<b>${t}</b>${s||""}</div>`;
const skeleton=()=>`<div class="page"><div class="skel" style="width:220px;height:26px"></div><div class="skel" style="width:340px"></div><div class="grid g4" style="margin-top:22px">${"<div class='panel' style='height:104px;padding:16px'><div class='skel' style='width:50%'></div><div class='skel' style='width:30%;height:26px'></div></div>".repeat(4)}</div></div>`;
function crumbs(list){$("#crumbs").innerHTML=list.map((c,i)=>i==list.length-1?`<b>${esc(c[0])}</b>`:`<a href="#/${c[1]}">${esc(c[0])}</a>${I("chev")}`).join("")}
function addRecent(label,path,icon){recent=[{label,path,icon},...recent.filter(r=>r.path!=path)].slice(0,6)}

function table(id,cols,rows,o={}){
 const tabs=o.tabs?`<div class="seg" id="${id}_tabs">${o.tabs.map((t,i)=>`<button type="button" data-t="${t[0]}" class="${i?"":"on"}">${t[1]}<span class="ct">${rows.filter(t[2]).length}</span></button>`).join("")}</div>`:"";
 const bar=`${tabs}<div class="search">${I("search")}<input id="${id}_q" placeholder="${o.ph||"Search"}…" autocomplete="off"></div><span class="sp"></span>${o.extra||""}${o.csv?`<button class="btn ghost sm" type="button" id="${id}_csv">${I("download")}Export</button>`:""}`;
 return `<div class="panel" id="${id}"><div class="tbar">${o.noBar?"":bar}</div><div class="tscroll"><table class="dt"><thead><tr>${cols.map(c=>`<th class="${c.cls||""}">${c.h||""}</th>`).join("")}</tr></thead><tbody>${rows.map((r,i)=>`<tr class="${o.click?"click":""}" data-q="${esc((o.q?o.q(r):"").toLowerCase())}">${cols.map(c=>`<td class="${c.cls||""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table>${rows.length?"":emptyState(o.empty||"Nothing here yet",o.emptySub||"")}</div><div class="tfoot" id="${id}_n"></div></div>`}
function wire(id,rows,cols,o={}){
 const root=$("#"+id);if(!root)return;let tab=o.tabs?o.tabs[0][0]:null,sel=null;
 const apply=()=>{const q=($("#"+id+"_q")?.value||"").toLowerCase().trim();let n=0;const f=o.tabs?o.tabs.find(t=>t[0]==tab)[2]:()=>true;
  $$("tbody tr",root).forEach((tr,i)=>{const ok=(!q||tr.dataset.q.includes(q))&&f(rows[i]);tr.classList.toggle("hidden",!ok);ok&&n++});
  $("#"+id+"_n").textContent=rows.length?`Showing ${n} of ${rows.length}`:""};
 $("#"+id+"_q")?.addEventListener("input",apply);
 $$("#"+id+"_tabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;$$("#"+id+"_tabs button").forEach(x=>x.classList.toggle("on",x==b));apply()});
 if(o.click)$$("tbody tr",root).forEach((tr,i)=>tr.onclick=e=>{if(e.target.closest("button,a,input,select"))return;$$("tbody tr.sel",root).forEach(x=>x.classList.remove("sel"));tr.classList.add("sel");o.click(rows[i])});
 $("#"+id+"_csv")?.addEventListener("click",()=>{const cs=cols.filter(c=>c.t),q=v=>`"${String(v??"").replace(/"/g,'""')}"`;
  const csv=[cs.map(c=>q(c.h)).join(","),...rows.map(r=>cs.map(c=>q(c.t(r))).join(","))].join("\n");
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download=(o.csv||id)+".csv";a.click()});
 apply()}

/* slide-over form */
const val=id=>$("#f_"+id)?.value;
function F(label,id,o={}){const a=`id="f_${id}" ${o.ph?`placeholder="${esc(o.ph)}"`:""} ${o.req?"required":""}`;let el;
 if(o.opts)el=`<select ${a}>${o.opts.map(([v,l])=>`<option value="${esc(v)}" ${String(o.val)==String(v)?"selected":""}>${esc(l)}</option>`).join("")}</select>`;
 else if(o.rows)el=`<textarea ${a} rows="${o.rows}"></textarea>`;
 else el=`<input ${a} type="${o.type||"text"}" ${o.val!=null?`value="${esc(o.val)}"`:""} ${o.step?`step="${o.step}"`:""} ${o.accept?`accept="${o.accept}"`:""}>`;
 return `<label class="f">${label}${el}${o.hint?`<span class="hint">${o.hint}</span>`:""}</label>`}
function drawer({title,sub,body,label="Save",onSave,onOpen}){closeDrawer();
 const d=document.createElement("div");d.id="drawer";
 d.innerHTML=`<div class="scrim" data-x></div><aside class="sheet" role="dialog" aria-label="${esc(title)}"><header><div><h3>${esc(title)}</h3>${sub?`<p>${esc(sub)}</p>`:""}</div><button class="icon" data-x type="button" aria-label="Close">${I("x")}</button></header><form class="sbody" id="dform">${body}<p class="ferr" id="ferr"></p></form><footer><button class="btn ghost" type="button" data-x>Cancel</button><button class="btn" type="button" id="fsave">${esc(label)}</button></footer></aside>`;
 $("#drawerRoot").appendChild(d);$$("[data-x]",d).forEach(x=>x.onclick=closeDrawer);
 const save=async()=>{const b=$("#fsave");b.disabled=true;$("#ferr").textContent="";
  try{await onSave();closeDrawer()}catch(e){$("#ferr").textContent=e.message;b.disabled=false}};
 $("#fsave").onclick=save;$("#dform").onsubmit=e=>{e.preventDefault();save()};onOpen&&onOpen();$("#dform input,#dform select")?.focus()}
const closeDrawer=()=>{$("#drawerRoot").innerHTML=""};
document.addEventListener("keydown",e=>{if(e.key=="Escape"){closeDrawer();$("#pop").classList.add("hidden")}});

/* ---------- reference panel (right) ---------- */
async function refPanel(o={}){
 const rec=recent.map(r=>`<a href="#/${r.path}">${I(r.icon||"file")}<span>${esc(r.label)}</span></a>`).join("");
 let h=`<div class="rp">`;
 if(o.title)h+=`<div class="sec"><h4>${esc(o.kind||"Selected record")}</h4><div class="title">${esc(o.title)}</div>${o.sub||""}${(o.kv||[]).map(([k,v])=>`<div class="kv"><span>${k}</span><span style="text-align:right">${v}</span></div>`).join("")}${o.extra||""}</div>`;
 else h+=`<div class="sec"><h4>Reference</h4><p class="muted">Select a record to see its details, linked documents and audit history here.</p></div>`;
 h+=`<div class="sec" id="hist" ${o.entity&&can("audit.read")?"":"hidden"}><h4>History</h4><div class="skel"></div></div>`;
 h+=`<div class="sec" id="mine"><h4>My recent activity</h4><div class="skel"></div></div>`;
 h+=`<div class="sec recent"><h4>Recently opened</h4>${rec||`<span class="muted small">Nothing yet</span>`}</div></div>`;
 $("#ref").innerHTML=h;MINE?paintMine():loadMine();
 if(o.entity&&can("audit.read")){try{const a=await api(`/audit?entity=${o.entity}&entity_id=${o.id}`);
  $("#hist").innerHTML=`<h4>History</h4>`+(a.length?`<div class="tl">${a.slice(0,12).map(x=>`<div class="ev"><b>${esc(x.action.replace(/_/g," "))}</b><small>${esc(x.user_name)} · ${fmtDT(x.at)}</small></div>`).join("")}</div>`:`<p class="muted small">No changes recorded yet.</p>`)}catch{}}}

/* ---------- notifications ---------- */
function renderBell(){const items=[];if(NOTE&&NOTE.expiring){NOTE.expiring.forEach(e=>items.push({ic:"alert",c:e.days<0?"var(--bad)":"var(--warn)",t:`${e.vehicle} · ${e.doc_type}`,s:e.days<0?`Expired ${-e.days} days ago`:`Due in ${e.days} days`,p:"vehicles/"+e.vehicle_id}));
  if(NOTE.trips_unassigned)items.push({ic:"route",c:"var(--warn)",t:`${NOTE.trips_unassigned} trip request(s) need a driver`,s:"Open trips",p:"trips"});
  if(NOTE.fuel_flagged)items.push({ic:"fuel",c:"var(--bad)",t:`${NOTE.fuel_flagged} fuel entr${NOTE.fuel_flagged>1?"ies":"y"} flagged for review`,s:"Fuel log",p:"fuel"})}
 if(SUM?.tickets){const t=SUM.tickets;if(t.overdue)items.push({ic:"alert",c:"var(--bad)",t:`${t.overdue} ticket${t.overdue>1?"s":""} overdue`,s:"Open tickets",p:"tickets"});if(t.unassigned)items.push({ic:"ticket",c:"var(--warn)",t:`${t.unassigned} ticket${t.unassigned>1?"s":""} not assigned yet`,s:"Open tickets",p:"tickets"})}
 (NOTI||[]).forEach(n=>items.push({ic:n.kind=="leaver"?"users":n.kind=="incident"?"alert":"wrench",c:"var(--bad)",t:n.title,s:n.body||"",p:n.link||"dashboard",n:n.id}));
 if(SUM?.docs?.count)items.push({ic:"file",c:SUM.docs.expired?"var(--bad)":"var(--warn)",t:`${SUM.docs.count} premises document${SUM.docs.count>1?"s":""} expiring (${SUM.docs.expired} expired)`,s:"Premises documents",p:"premises"});
 if(SUM?.utilities?.overdue)items.push({ic:"plug",c:"var(--bad)",t:`${SUM.utilities.overdue} utility bill${SUM.utilities.overdue>1?"s":""} overdue`,s:"Utilities",p:"utilities"});
 if(SUM?.hrms){const h=SUM.hrms;if(h.state=="error")items.push({ic:"alert",c:"var(--bad)",t:"HRMS integration is not reachable",s:h.last_error||"Check the settings",p:can("integrations.manage")?"integrations":"advances"});if(h.advances_waiting)items.push({ic:"route",c:"var(--warn)",t:`${h.advances_waiting} travel advance${h.advances_waiting>1?"s":""} not yet in the HRMS`,s:"Travel advances",p:"advances"})}
 if(SUM?.assets){const a=SUM.assets;if(a.service_overdue)items.push({ic:"box",c:"var(--bad)",t:`${a.service_overdue} asset${a.service_overdue>1?"s":""} overdue for service`,s:"Asset register",p:"assets"});if(a.warranty_expiring)items.push({ic:"box",c:"var(--warn)",t:`${a.warranty_expiring} warranty ending within 30 days`,s:"Asset register",p:"assets"})}
 $("#bell").innerHTML=I("bell")+(items.length?'<span class="dot"></span>':"");
 $("#pop").innerHTML=`<header><span>Notifications</span><span class="muted small">${items.length}</span></header>`+(items.length?items.map(i=>`<div class="it" data-p="${i.p}" data-n="${i.n||""}"><span style="color:${i.c}">${I(i.ic)}</span><div><b>${esc(i.t)}</b><div class="muted small">${esc(i.s)}</div></div></div>`).join(""):`<div class="none">You're all caught up</div>`);
 $$("#pop .it").forEach(el=>el.onclick=()=>{$("#pop").classList.add("hidden");if(el.dataset.n)api("/notifications/"+el.dataset.n+"/read",{method:"POST"}).then(refreshNotes).catch(()=>{});location.hash="#/"+el.dataset.p})}
async function refreshNotes(){try{SUM=await api("/summary"+(PREM?"?premises_id="+PREM:""));NOTI=await api("/notifications").catch(()=>[]);TSUM=can("travel.read")?await api("/travel/summary").catch(()=>null):null;if(can("dashboard"))NOTE=await api("/dashboard");renderBell();renderMenu();renderActionBar()}catch{}}

/* ---------- shell ---------- */
const NAV=[["Overview",[["dashboard","Dashboard","dashboard","dashboard"]]],
 ["Fleet",[["vehicles","Vehicles","car","vehicles.read"],["handovers","Handovers & returns","users","vehicles.read"],["trips","Trips","route","trips.read"],["fuel","Fuel log","fuel","fuel.read"],["vservices","Service & repairs","wrench","vehicles.read"],["compliance","Insurance & compliance","shield","vehicles.read"],["incidents","Incidents","alert","vehicles.read"]]],
 ["People",[["employees","Employees","users","employees.read"],["advances","Travel advances","route","employees.write"]]],
 ["Facilities",[["utilities","Utilities","plug","utilities.read"]]],
 ["Travel",[["travel","Travel requests","route","travel.read"],["visas","Visa & permits","shield","travel.read"],["refunds","Refunds & reconciliation","file","travel.read"]]],
 ["Maintenance",[["assets","Asset register","box","assets.read"],["tickets","Tickets","ticket","tickets.read"]]],
 ["Administration",[["onboarding","Onboarding","upload","onboarding"],["integrations","HRMS integration","plug","integrations.manage"],["travelpolicy","Travel policy","file","travel.read"],["premises","Premises","building","premises.view"],["guesthouses","Guest houses","building","employees.read"],["users","Users & roles","users","users.admin"],["audit","Audit trail","file","audit.read"]]]];
function renderMenu(){
 const badge={trips:NOTE?.trips_unassigned,fuel:NOTE?.fuel_flagged,tickets:SUM?.tickets?.open,travel:TSUM?.awaiting_me,assets:SUM?.assets?.service_overdue};
 const opts=PL.map(p=>`<option value="${p.id}" ${p.id==PREM?"selected":""}>${p.parent_id?"\u00A0\u00A0↳ ":""}${esc(p.name)}</option>`).join("");
 const nav=NAV.map(([sec,items])=>{const v=items.filter(i=>can(i[3]));return v.length?`<h6>${sec}</h6>`+v.map(i=>`<a href="#/${i[0]}" class="${view==i[0]||(i[0]=="vehicles"&&view=="vehicle")||(i[0]=="assets"&&view=="asset")||(i[0]=="tickets"&&view=="ticket")||(i[0]=="guesthouses"&&view=="guesthouse")||(i[0]=="premises"&&view=="premise")||(i[0]=="travel"&&view=="trequest")?"on":""}" title="${i[1]}">${I(i[2])}<span class="lbl">${i[1]}</span>${badge[i[0]]?`<span class="badge">${badge[i[0]]}</span>`:""}</a>`).join(""):""}).join("");
 $("#menu").innerHTML=`<div class="brand"><div class="logo" title="Company logo slot">B</div><div><b>Building Management</b><small>${esc(COMP.length==1?COMP[0].name:"Group Administration")}</small></div></div>
 ${can("vehicles.read")||can("premises.write")||can("tickets.read")||can("assets.read")?`<div class="psw"><label>Premises</label><select id="psw"><option value="">All premises</option>${opts}</select></div>`:""}
 <nav class="nav">${nav}</nav>
 <div class="ucard"><div class="av">${esc(init(ME.name))}</div><div class="who"><b>${esc(ME.name)}</b><small>${esc(ME.grants.map(g=>ROLES[g.role]||g.role)[0]||"")}</small></div><button class="icon" id="so" title="Sign out">${I("logout")}</button></div>`;
 $("#psw")?.addEventListener("change",e=>{PREM=e.target.value;localStorage.bms_prem=PREM;route()});
 $("#so").onclick=()=>signOut()}

const DETV=["vehicle","asset","ticket","guesthouse","premise","trequest"];const ROUTES={};Object.assign(ROUTES,P1,P2);
async function route(){if(!ME)return;closeDrawer();
 const [v="dashboard",id]=location.hash.replace(/^#\//,"").split("?")[0].split("/");const DET={vehicles:"vehicle",assets:"asset",tickets:"ticket",guesthouses:"guesthouse",premises:"premise",travel:"trequest"};view=id&&DET[v]?DET[v]:(ROUTES[v]?v:"dashboard");
 MINE=null;renderMenu();renderActionBar();$("#main").innerHTML=skeleton();$("#gsearch").value="";
 const perm={dashboard:"dashboard",vehicles:"vehicles.read",vehicle:"vehicles.read",trips:"trips.read",fuel:"fuel.read",premises:"premises.view",premise:"premises.view",travel:"travel.read",trequest:"travel.read",visas:"travel.read",refunds:"travel.read",travelpolicy:"travel.read",handovers:"vehicles.read",compliance:"vehicles.read",vservices:"vehicles.read",incidents:"vehicles.read",utilities:"utilities.read",users:"users.admin",audit:"audit.read",assets:"assets.read",asset:"assets.read",tickets:"tickets.read",ticket:"tickets.read",onboarding:"onboarding",employees:"employees.read",guesthouses:"employees.read",guesthouse:"employees.read",advances:"employees.write",integrations:"integrations.manage"}[view];
 try{ if(!can(perm)){const it=NAV.flatMap(x=>x[1]).filter(i=>can(i[3])),f=can("tickets.manage")?it.find(i=>i[0]=="tickets"):it[0];
   if(view=="dashboard"&&f){location.hash="#/"+f[0];return}
   if(!f)welcome();else $("#main").innerHTML=`<div class="page">${emptyState("You don't have access to this page","Ask a Group Admin to grant a role with this permission.","shield")}</div>`}
  else if(DETV.includes(view)) await ROUTES[view](+id); else await ROUTES[view]();
 }catch(e){if(e.message!="Signed out")$("#main").innerHTML=`<div class="page">${emptyState("Something went wrong",esc(e.message),"alert")}</div>`}
 $("#main").scrollTop=0}
function welcome(){crumbs([["Home"]]);refPanel();$("#main").innerHTML=`<div class="page">${head(`Welcome, ${esc(ME.name.split(" ")[0])}`,"Your role works through the mobile apps.")}<div class="panel"><div class="bd" style="padding:22px">${can("driver.app")?`<p><b>Driver?</b> Open the driver app on your phone: <a href="/driver/">/driver/</a>. Start and end trips with meter photos and log fuel.</p>`:`<p>No web modules are assigned to your role yet.</p>`}</div></div></div>`}

/* ================= pages ================= */
ROUTES.dashboard=async function(){
 const q=PREM?"?premises_id="+PREM:"";const [d,trips,sm]=await Promise.all([api("/dashboard"+q),can("trips.read")?api("/trips?status=requested"):[],api("/summary"+q)]);if(!PREM)SUM=sm;
 if(!PREM){NOTE=d;renderBell();renderMenu()}crumbs([["Dashboard"]]);refPanel();
 const open=trips.filter(t=>inPrem(t.premises_id));
 const other=d.vehicles-d.available-d.on_trip-d.maintenance,tot=d.vehicles||1;
 const seg=[[d.available,"#15803D"],[d.on_trip,"#C9A227"],[d.maintenance,"#B91C1C"],[other,"#D1D5DB"]];let a=0;
 const grad=d.vehicles?seg.map(([n,c])=>{const s=a;a+=n/tot*100;return `${c} ${s}% ${a}%`}).join(","):"#EBE0B5 0 100%";
 const hr=new Date().getHours(),g=hr<12?"Good morning":hr<17?"Good afternoon":"Good evening";
 $("#main").innerHTML=`<div class="page">${head(`${g}, ${esc(ME.name.replace(/\(.*\)/,"").trim())}`,`${new Date().toLocaleDateString([],{weekday:"long",day:"numeric",month:"long",year:"numeric"})} · ${esc(premScope())}`,
  can("vehicles.write")?`<button class="btn" id="addv">${I("plus")}Add vehicle</button>`:"")}
 <div class="grid g4" style="margin-bottom:16px">
  <div class="kpi link" data-go="vehicles"><div class="k">${I("car")}Fleet</div><div class="v">${d.vehicles}</div><div class="s">${d.available} available · ${d.on_trip} on trip</div></div>
  <div class="kpi link ${d.trips_unassigned?"warn":""}" data-go="trips"><div class="k">${I("route")}Open trips</div><div class="v">${d.trips_open}</div><div class="s">${d.trips_unassigned} awaiting a driver</div></div>
  <div class="kpi link ${d.fuel_flagged?"bad":""}" data-go="fuel"><div class="k">${I("alert")}Fuel to review</div><div class="v">${d.fuel_flagged}</div><div class="s">Flagged entries</div></div>
  <div class="kpi"><div class="k">${I("fuel")}Fuel spend · month</div><div class="v">${n0(d.fuel_cost_month)}</div><div class="s">${d.cost_per_km?`${d.cost_per_km} per km · ${n0(d.km_month)} km`:"No completed trips yet"}</div></div></div>
 ${sm.assets||sm.tickets?`<div class="grid g4" style="margin-bottom:16px">
  ${sm.assets?`<div class="kpi link" data-go="assets"><div class="k">${I("box")}Admin assets</div><div class="v">${sm.assets.total}</div><div class="s">${sm.assets.under_maintenance} under maintenance</div></div>
  <div class="kpi link ${sm.assets.service_overdue?"bad":sm.assets.service_soon?"warn":""}" data-go="assets"><div class="k">${I("wrench")}Service due</div><div class="v">${sm.assets.service_overdue+sm.assets.service_soon}</div><div class="s">${sm.assets.service_overdue} overdue · ${sm.assets.warranty_expiring} warranties ending</div></div>`:""}
  ${sm.tickets?`<div class="kpi link ${sm.tickets.unassigned?"warn":""}" data-go="tickets"><div class="k">${I("ticket")}Open tickets</div><div class="v">${sm.tickets.open}</div><div class="s">${sm.tickets.unassigned} not assigned</div></div>
  <div class="kpi link ${sm.tickets.overdue?"bad":""}" data-go="tickets"><div class="k">${I("alert")}Tickets overdue</div><div class="v">${sm.tickets.overdue}</div><div class="s">${sm.tickets.critical} high or critical</div></div>`:""}</div>`:""}
 ${sm.people||sm.hrms?`<div class="grid g3" style="margin-bottom:16px">
  ${sm.people?`<div class="kpi link" data-go="employees"><div class="k">${I("users")}Employees</div><div class="v">${sm.people.total}</div><div class="s">${sm.people.active} active · ${sm.people.on_leave} on leave · ${sm.people.notice} on notice</div></div>
  <div class="kpi link" data-go="guesthouses"><div class="k">${I("building")}Guest house beds</div><div class="v">${sm.people.occupied}<span style="font-size:15px;color:var(--ink2)"> / ${sm.people.beds||"?"}</span></div><div class="s">${sm.people.guest_houses} guest house${sm.people.guest_houses==1?"":"es"}</div></div>`:""}
  ${sm.hrms?`<div class="kpi ${can("integrations.manage")?"link":""} ${sm.hrms.state=="error"?"bad":["ok"].includes(sm.hrms.state)?"":"warn"}" ${can("integrations.manage")?'data-go="integrations"':""}><div class="k">${I("plug")}HRMS integration</div><div class="v" style="font-size:20px;margin:6px 0">${chip(...(HS[sm.hrms.state]||[sm.hrms.state,""]))}</div><div class="s">${sm.hrms.last_ok?"Last success "+fmtDT(sm.hrms.last_ok):"No successful call yet"}${sm.hrms.failed_24h?` · ${sm.hrms.failed_24h} failed today`:""}${sm.hrms.advances_waiting?` · ${sm.hrms.advances_waiting} advance(s) waiting`:""}</div></div>`:""}</div>`:""}
 ${sm.docs||sm.utilities||sm.fleet?`<div class="grid g4" style="margin-bottom:16px">
  ${sm.docs?`<div class="kpi link ${sm.docs.expired?"bad":sm.docs.count?"warn":""}" data-go="premises"><div class="k">${I("file")}Premises documents</div><div class="v">${sm.docs.count}</div><div class="s">${sm.docs.expired} expired · reminders at 90, 30, 7 days</div></div>`:""}
  ${sm.utilities?`<div class="kpi link ${sm.utilities.overdue?"bad":sm.utilities.due_soon?"warn":""}" data-go="utilities"><div class="k">${I("plug")}Utility bills</div><div class="v">${sm.utilities.overdue+sm.utilities.due_soon}</div><div class="s">${sm.utilities.overdue} overdue · ${sm.utilities.due_soon} due in 7 days</div></div>`:""}
  ${sm.fleet?`<div class="kpi link ${sm.fleet.returns_pending?"bad":""}" data-go="handovers"><div class="k">${I("users")}Vehicle returns</div><div class="v">${sm.fleet.returns_pending}</div><div class="s">leavers holding a vehicle</div></div>
  <div class="kpi link ${sm.fleet.open_incidents||sm.fleet.services_pending_approval?"warn":""}" data-go="${sm.fleet.services_pending_approval?"vservices":"incidents"}"><div class="k">${I("wrench")}Fleet to action</div><div class="v">${sm.fleet.open_incidents+sm.fleet.services_pending_approval}</div><div class="s">${sm.fleet.open_incidents} incidents · ${sm.fleet.services_pending_approval} quotations to approve</div></div>`:""}</div>`:""}
 ${typeof TSUM!="undefined"&&TSUM?`<div class="grid g4" style="margin-bottom:16px"><div class="kpi link ${TSUM.awaiting_me?"warn":""}" data-go="travel"><div class="k">${I("route")}Travel approvals</div><div class="v">${TSUM.awaiting_me}</div><div class="s">${TSUM.awaiting} awaiting in all</div></div><div class="kpi link" data-go="travel"><div class="k">Trips to book</div><div class="v">${TSUM.approved_to_book}</div><div class="s">${TSUM.upcoming} upcoming</div></div><div class="kpi link ${TSUM.refunds_pending?"warn":""}" data-go="refunds"><div class="k">Refunds pending</div><div class="v">${TSUM.refunds_pending}</div></div><div class="kpi link ${TSUM.visas_expiring?"warn":""}" data-go="visas"><div class="k">${I("shield")}Visas expiring</div><div class="v">${TSUM.visas_expiring}</div><div class="s">within 60 days</div></div></div>`:""}
 <div class="grid g2-1">
  <div>${table("t_exp",[{h:"Vehicle",f:r=>`<span class="primary">${esc(r.vehicle)}</span>`},{h:"Document",f:r=>esc(r.doc_type)},{h:"Valid to",f:r=>fmtD(r.valid_to)},{h:"Status",f:r=>expChip(r.valid_to)}],d.expiring,{noBar:true,click:true,empty:"No renewals due",emptySub:"Nothing expired or due in the next 30 days."}).replace('<div class="tbar"></div>',`<div class="hd" style="display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--gold-l)"><h2 style="margin:0;font-size:14px">Document renewals</h2><span class="muted small">Expired or due within 30 days</span></div>`)}</div>
  <div style="display:grid;gap:16px;align-content:start">
   <div class="panel"><div class="hd"><h2>Fleet status</h2></div><div class="bd"><div class="donut" style="background:conic-gradient(${grad})"><div><span><b>${d.vehicles}</b><small>vehicles</small></span></div></div>
    <div class="lg"><i style="background:#15803D"></i><span>Available</span><span>${d.available}</span></div><div class="lg"><i style="background:#C9A227"></i><span>On trip</span><span>${d.on_trip}</span></div><div class="lg"><i style="background:#B91C1C"></i><span>Maintenance</span><span>${d.maintenance}</span></div></div></div>
   <div class="panel"><div class="hd"><h2>Needs a driver</h2><div class="acts"><a href="#/trips" class="small">View all</a></div></div>${open.length?open.slice(0,4).map(t=>`<div class="row click" data-go="trips"><div class="grow"><b>${esc(t.destination)}</b><div class="muted small">${esc(t.requester)} · ${fmtDT(t.needed_at)}</div></div>${chip("Unassigned","warn")}</div>`).join(""):emptyState("All trips are covered")}</div></div></div></div>`;
 $$("[data-go]").forEach(e=>e.onclick=()=>location.hash="#/"+e.dataset.go);
 wire("t_exp",d.expiring,[],{click:r=>location.hash="#/vehicles/"+r.vehicle_id});
 $("#addv")&&($("#addv").onclick=addVehicleDrawer)};

function addVehicleDrawer(){drawer({title:"Add vehicle",sub:"Register a vehicle against a premises.",label:"Add vehicle",
 body:F("Premises","p",{opts:PL.map(p=>[p.id,(p.parent_id?"↳ ":"")+p.name]),val:PREM})+F("Registration number","r",{ph:"KA01AB1234",req:1})+F("Make & model","m",{ph:"Toyota Innova Crysta"})+F("Year","y",{type:"number"})+F("Current odometer (km)","o",{type:"number",val:0}),
 onSave:async()=>{if(!val("r")||!val("m"))throw Error("Registration and model are required.");await api("/vehicles",{body:{premises_id:+val("p"),reg_no:val("r"),make_model:val("m"),year:+val("y")||null,odometer:+val("o")||0}});toast("Vehicle added");route()}})}

ROUTES.vehicles=async function(){
 const v=(await api("/vehicles")).filter(x=>inPrem(x.premises_id));const HM={};try{(await api("/handovers")).filter(a=>a.status!="returned").forEach(a=>HM[a.vehicle_id]=a)}catch{}crumbs([["Fleet","vehicles"],["Vehicles"]]);refPanel();
 const cols=[{h:"Vehicle",f:r=>`<div class="primary">${esc(r.reg_no)}</div><div class="sec">${esc(r.make_model)}${r.year?" · "+r.year:""}</div>`,t:r=>r.reg_no},{h:"Premises",f:r=>esc(premName(r.premises_id)),t:r=>premName(r.premises_id)},
  {h:"Assigned to",f:r=>HM[r.id]?`<div>${esc(HM[r.id].employee)}</div>${HM[r.id].status=="return_pending"?chip("Return pending","warn"):""}`:`<span class="muted">Common pool</span>`,t:r=>HM[r.id]?.employee||"Common pool"},{h:"Status",f:r=>sc(VS,r.status),t:r=>VS[r.status]?.[0]},{h:"Odometer",cls:"num right",f:r=>n0(r.odometer)+" km",t:r=>r.odometer},
  {h:"Next renewal",f:r=>r.next_expiry?`${expChip(r.next_expiry)} <span class="sec">${fmtD(r.next_expiry)}</span>`:`<span class="muted">–</span>`,t:r=>r.next_expiry},{h:"",cls:"right",f:()=>`<span class="muted">${I("chev")}</span>`}];
 const o={tabs:[["all","All",()=>true],["available","Available",r=>r.status=="available"],["on_trip","On trip",r=>r.status=="on_trip"],["renew","Renewals due",r=>r.expiry_state&&r.expiry_state!="ok"]],
  q:r=>`${r.reg_no} ${r.make_model} ${premName(r.premises_id)}`,csv:"vehicles",ph:"Search vehicles",empty:"No vehicles yet",emptySub:"Add your first vehicle to start tracking trips, fuel and renewals.",click:r=>location.hash="#/vehicles/"+r.id};
 $("#main").innerHTML=`<div class="page">${head("Vehicles",`${v.length} vehicles · ${esc(premScope())}`,can("vehicles.write")?bulkBtns("vehicles")+`<button class="btn" id="addv">${I("plus")}Add vehicle</button>`:"")}${table("t_v",cols,v,o)}</div>`;
 wire("t_v",v,cols,o);$("#addv")&&($("#addv").onclick=addVehicleDrawer)};

ROUTES.vehicle=async function(id){
 const d=await api("/vehicles/"+id),v=d.vehicle;crumbs([["Fleet","vehicles"],["Vehicles","vehicles"],[v.reg_no]]);addRecent(v.reg_no,"vehicles/"+id,"car");
 const latest={};d.documents.forEach(x=>{if(!latest[x.doc_type]||x.version>latest[x.doc_type].version)latest[x.doc_type]=x});const cur=Object.values(latest);
 const bad=cur.filter(x=>x.valid_to&&daysTo(x.valid_to)<0).length,soon=cur.filter(x=>x.valid_to&&daysTo(x.valid_to)>=0&&daysTo(x.valid_to)<=30).length;
 refPanel({title:v.reg_no,kind:"Vehicle",sub:`<div class="muted" style="margin-bottom:8px">${esc(v.make_model)}</div>`,entity:"vehicle",id,kv:[["Status",sc(VS,v.status)],["Odometer",n0(v.odometer)+" km"],["Premises",esc(premName(v.premises_id))]]});
 let tab="overview";
 const docCols=[{h:"Document",f:r=>`<span class="primary" style="text-transform:capitalize">${esc(r.doc_type)}</span>`},{h:"Number",f:r=>esc(r.number||"–")},{h:"Valid to",f:r=>fmtD(r.valid_to)},{h:"Status",f:r=>expChip(r.valid_to)},{h:"Version",f:r=>"v"+r.version},{h:"File",f:r=>fileLink(r.file)}];
 const paint=()=>{const c=$("#tabc");
  if(tab=="overview")c.innerHTML=`<div class="grid g2-1"><div class="panel"><div class="hd"><h2>Vehicle details</h2></div><div class="bd"><dl class="dl"><dt>Registration</dt><dd>${esc(v.reg_no)}</dd><dt>Make & model</dt><dd>${esc(v.make_model)}</dd><dt>Year</dt><dd>${v.year||"–"}</dd><dt>Premises</dt><dd>${esc(premName(v.premises_id))}</dd><dt>Use</dt><dd>${v.pool?"Common pool vehicle":"Assigned vehicle"}</dd><dt>Purchase</dt><dd>${fmtD(v.purchase_date)} · ${n0(v.purchase_value)}</dd><dt>Current value</dt><dd>${n0(v.current_value)}</dd><dt>Odometer</dt><dd>${n0(v.odometer)} km</dd></dl></div></div>
   <div class="panel"><div class="hd"><h2>Compliance</h2></div>${cur.length?cur.map(x=>`<div class="row"><div class="grow"><b style="text-transform:capitalize">${esc(x.doc_type)}</b><div class="muted small">Valid to ${fmtD(x.valid_to)}</div></div>${expChip(x.valid_to)}</div>`).join(""):emptyState("No documents","Upload registration and insurance.","file")}</div></div>`;
  else if(tab=="docs"){c.innerHTML=table("t_d",docCols,d.documents,{noBar:true,empty:"No documents uploaded"}).replace('<div class="tbar"></div>',`<div class="hd" style="display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--gold-l)"><h2 style="margin:0;font-size:14px">Documents</h2><span style="margin-left:auto">${can("vehicles.write")?`<button class="btn sm" id="addd">${I("plus")}Add or renew</button>`:""}</span></div>`);wire("t_d",d.documents,[],{});$("#addd")&&($("#addd").onclick=()=>docDrawer(id))}
  else if(tab=="asg")V5.assign(c,v,()=>paint());else if(tab=="svc")V5.service(c,v,()=>paint());else if(tab=="inc")V5.incidents(c,v,()=>paint());
  else if(tab=="trips"){c.innerHTML=table("t_t",[{h:"Trip",f:r=>`<span class="primary">${tripNo(r.id)}</span>`},{h:"Destination",f:r=>esc(r.destination)},{h:"Status",f:r=>sc(TS,r.status)},{h:"Distance",cls:"num",f:r=>r.end_meter!=null?n0(r.end_meter-r.start_meter)+" km":"–"}],d.trips,{noBar:true,empty:"No trips yet"});wire("t_t",d.trips,[],{})}
  else{c.innerHTML=table("t_f",[{h:"Date",f:r=>fmtDT(r.at)},{h:"Litres",cls:"num",f:r=>r.litres},{h:"Cost",cls:"num",f:r=>n0(r.cost)},{h:"Meter",cls:"num",f:r=>n0(r.meter_reading)},{h:"km/l",cls:"num",f:r=>r.mileage_kmpl??"–"},{h:"Flag",f:r=>r.flag?chip(r.flag.replace(/_/g," "),"bad"):""}],d.fuel,{noBar:true,empty:"No fuel entries yet"});wire("t_f",d.fuel,[],{})}};
 $("#main").innerHTML=`<div class="page"><div class="rh"><div class="big">${I("car")}</div><div><h1>${esc(v.reg_no)}</h1><p>${esc(v.make_model)}${v.year?" · "+v.year:""} · ${esc(premName(v.premises_id))}</p></div><div>${sc(VS,v.status)}</div><div class="acts">${can("vehicles.write")?`<button class="btn ghost" id="bved">Edit</button>`:""}${can("vehicles.write")?`<button class="btn ghost" id="addd2">${I("file")}Add document</button>`:""}</div></div>
  <div class="grid g4"><div class="kpi"><div class="k">Odometer</div><div class="v">${n0(v.odometer)}</div><div class="s">kilometres</div></div><div class="kpi ${bad?"bad":soon?"warn":""}"><div class="k">Documents</div><div class="v">${cur.length}</div><div class="s">${bad?bad+" expired":soon?soon+" due soon":"All valid"}</div></div><div class="kpi"><div class="k">Trips</div><div class="v">${d.trips.length}</div><div class="s">recent</div></div><div class="kpi"><div class="k">Fuel entries</div><div class="v">${d.fuel.length}</div><div class="s">recent</div></div></div>
  <div class="tabs" id="vtabs">${[["overview","Overview"],["asg","Assignment"],["docs","Documents"],["svc","Service & repairs"],["inc","Incidents"],["trips","Trips"],["fuel","Fuel"]].map(([k,l])=>`<button data-t="${k}" class="${k==tab?"on":""}">${l}</button>`).join("")}</div><div id="tabc"></div></div>`;
 $$("#vtabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;$$("#vtabs button").forEach(x=>x.classList.toggle("on",x==b));paint()});
 $("#addd2")&&($("#addd2").onclick=()=>docDrawer(id));$("#bved")&&($("#bved").onclick=()=>vehicleForm(v,()=>route()));paint()};

function docDrawer(id){drawer({title:"Add or renew document",sub:"Uploading a new document of the same type creates the next version.",label:"Upload",
 body:F("Document type","t",{opts:Object.entries(VDOC)})+F("Number","n")+F("Insurer / issuing authority","a")+F("Valid to","v",{type:"date"})+F("Renewal cost","rc",{type:"number",step:"0.01"})+F("File (PDF or image)","f",{type:"file",accept:".pdf,image/*"}),
 onSave:async()=>{const f=new FormData();f.append("doc_type",val("t"));f.append("number",val("n"));f.append("authority",val("a"));f.append("valid_to",val("v"));f.append("renewal_cost",val("rc")||"");const fl=$("#f_f").files[0];if(fl)f.append("file",fl);
  await api(`/vehicles/${id}/documents`,{body:f});toast("Document saved");route()}})}

ROUTES.trips=async function(){
 const [all,dr,veh]=await Promise.all([api("/trips"),can("trips.assign")?api("/drivers"):[],can("vehicles.read")?api("/vehicles"):[]]);
 const t=all.filter(x=>inPrem(x.premises_id));crumbs([["Fleet","vehicles"],["Trips"]]);refPanel();
 const cols=[{h:"Trip",f:r=>`<span class="primary">${tripNo(r.id)}</span>`,t:r=>tripNo(r.id)},{h:"Route",f:r=>`<div class="primary">${route2(r)}</div><div class="sec">${esc(r.purpose||"")}</div>`,t:r=>`${r.pickup||""} → ${r.destination}`},
  {h:"Requested by",f:r=>`<div>${esc(r.requester)}</div>`,t:r=>r.requester},{h:"Needed by",f:r=>fmtDT(r.needed_at),t:r=>r.needed_at},
  {h:"Vehicle & driver",f:r=>r.vehicle?`<div class="primary">${esc(r.vehicle)}</div><div class="sec">${esc(r.driver||"No driver")}</div>`:`<span class="muted">Not assigned</span>`,t:r=>`${r.vehicle||""} ${r.driver||""}`},
  {h:"Status",f:r=>sc(TS,r.status),t:r=>TS[r.status]?.[0]},{h:"Distance",cls:"num right",f:r=>r.distance!=null?n0(r.distance)+" km":"–",t:r=>r.distance},
  {h:"",cls:"right",f:r=>can("trips.assign")&&["requested","assigned"].includes(r.status)?`<button class="btn sm ${r.status=="requested"?"":"ghost"}" data-a="${r.id}">${r.status=="requested"?"Assign":"Reassign"}</button>`:""}];
 const o={tabs:[["all","All",()=>true],["requested","Needs driver",r=>r.status=="requested"],["assigned","Assigned",r=>r.status=="assigned"],["started","In progress",r=>r.status=="started"],["completed","Completed",r=>r.status=="completed"]],
  q:r=>`${tripNo(r.id)} ${r.pickup} ${r.destination} ${r.requester} ${r.vehicle} ${r.driver}`,csv:"trips",ph:"Search trips",empty:"No trips yet",emptySub:"Trip requests from employees appear here.",
  click:r=>refPanel({title:tripNo(r.id),kind:"Trip",entity:"trip",id:r.id,kv:[["Status",sc(TS,r.status)],["Route",route2(r)],["Requested by",esc(r.requester)],["Vehicle",esc(r.vehicle||"–")],["Driver",esc(r.driver||"–")],["Start meter",n0(r.start_meter)],["End meter",n0(r.end_meter)],["Started",fmtDT(r.start_at)],["Ended",fmtDT(r.end_at)]],
   extra:(r.start_photo||r.end_photo?`<div style="margin-top:10px"><h4>Meter photos</h4>${thumb(r.start_photo)}${thumb(r.end_photo)}</div>`:"")+(r.notes?`<p class="muted" style="margin-top:10px">${esc(r.notes)}</p>`:"")})};
 $("#main").innerHTML=`<div class="page">${head("Trips",`Requests, assignments and completed journeys · ${esc(premScope())}`)}${table("t_tr",cols,t,o)}</div>`;
 wire("t_tr",t,cols,o);
 $$("[data-a]").forEach(b=>b.onclick=()=>{const tr=t.find(x=>x.id==b.dataset.a);
  drawer({title:`Assign ${tripNo(tr.id)}`,sub:tr.pickup?`${tr.pickup} → ${tr.destination}`:`To ${tr.destination}`,label:"Confirm assignment",
   body:F("Vehicle","v",{opts:[["","Select a vehicle"],...veh.filter(x=>x.status!="maintenance"&&x.status!="retired"&&inPrem(x.premises_id)||x.id==tr.vehicle_id).map(x=>[x.id,`${x.reg_no} · ${x.make_model}`])],val:tr.vehicle_id||""})+F("Driver","d",{opts:[["","Select a driver"],...dr.map(x=>[x.id,x.name])],val:tr.driver_id||""}),
   onSave:async()=>{if(!val("v")||!val("d"))throw Error("Choose both a vehicle and a driver.");await api(`/trips/${tr.id}/assign`,{body:{vehicle_id:+val("v"),driver_id:+val("d")}});toast("Trip assigned");route()}})})};

ROUTES.fuel=async function(){
 const f=await api("/fuel"+(PREM?"?premises_id="+PREM:""));crumbs([["Fleet","vehicles"],["Fuel log"]]);refPanel();
 const L=f.reduce((a,x)=>a+x.litres,0),C=f.reduce((a,x)=>a+x.cost,0),km=f.filter(x=>x.mileage_kmpl),avg=km.length?km.reduce((a,x)=>a+x.mileage_kmpl,0)/km.length:null;
 const cols=[{h:"Date",f:r=>fmtDT(r.at),t:r=>r.at},{h:"Vehicle",f:r=>`<span class="primary">${esc(r.vehicle)}</span>`,t:r=>r.vehicle},{h:"Driver",f:r=>esc(r.driver),t:r=>r.driver},{h:"Litres",cls:"num right",f:r=>r.litres,t:r=>r.litres},{h:"Cost",cls:"num right",f:r=>n0(r.cost),t:r=>r.cost},
  {h:"Start meter",cls:"num right",f:r=>r.start_meter!=null?n0(r.start_meter):"–",t:r=>r.start_meter},{h:"Closing meter",cls:"num right",f:r=>n0(r.meter_reading),t:r=>r.meter_reading},{h:"Run km",cls:"num right",f:r=>r.start_meter!=null?n0(r.meter_reading-r.start_meter):"–"},{h:"km/l",cls:"num right",f:r=>r.mileage_kmpl??"–",t:r=>r.mileage_kmpl},{h:"Evidence",f:r=>thumb(r.start_photo)+thumb(r.meter_photo)+thumb(r.receipt)||`<span class="muted small">None</span>`},
  {h:"Review",f:r=>r.flag&&!r.reviewed?`<div>${chip(r.flag.replace(/_/g," ").replace(",",", "),"bad")}</div>${can("fuel.review")?`<button class="btn sm ghost" style="margin-top:6px" data-r="${r.id}">Mark reviewed</button>`:""}`:r.flag?chip("Reviewed","ok"):`<span class="muted">–</span>`}];
 const o={tabs:[["all","All",()=>true],["flag","Needs review",r=>r.flag&&!r.reviewed]],q:r=>`${r.vehicle} ${r.driver}`,csv:"fuel-log",ph:"Search vehicle or driver",empty:"No fuel entries yet",emptySub:"Entries logged in the driver app appear here."};
 $("#main").innerHTML=`<div class="page">${head("Fuel log","Entries from the driver app, with mileage and review flags")}<div class="grid g3" style="margin-bottom:16px">
  <div class="kpi"><div class="k">Total litres</div><div class="v">${n0(Math.round(L*10)/10)}</div></div><div class="kpi"><div class="k">Total cost</div><div class="v">${n0(C)}</div></div><div class="kpi"><div class="k">Average mileage</div><div class="v">${avg?avg.toFixed(1):"–"}</div><div class="s">km per litre</div></div></div>${table("t_f",cols,f,o)}</div>`;
 wire("t_f",f,cols,o);$$("[data-r]").forEach(b=>b.onclick=async()=>{try{await api(`/fuel/${b.dataset.r}/review`,{method:"POST"});toast("Marked as reviewed");route()}catch(e){toast(e.message,false)}})};

ROUTES.premises=async function(){
 await loadRef();crumbs([["Administration"],["Premises"]]);refPanel();
 let EM=[],GH=[];if(can("employees.read")){try{[EM,GH]=await Promise.all([api("/employees"),api("/guesthouses")])}catch{}}
 const roots=PL.filter(p=>!p.parent_id||!pById(p.parent_id)),TY={office:"Office",guest_house:"Guest house",branch:"Branch",hospital:"Hospital office"};
 $("#main").innerHTML=`<div class="page">${head("Premises","Corporate premises and the sub-premises beneath them",can("premises.write")?bulkBtns("premises")+`<button class="btn" id="addp">${I("plus")}Add premises</button>`:"")}
 <div class="grid g3">${roots.map(p=>{const kids=PL.filter(k=>k.parent_id==p.id);return `<div class="panel pcard"><div class="top"><div class="big" title="Premises photo slot">${I("building")}</div><div><h3>${esc(p.name)}</h3><div class="muted small">${esc(cName(p.company_id))} · ${esc(TY[p.type]||p.type)}</div></div></div>
  <p class="muted" style="margin:12px 0 0">${esc(p.address||"No address recorded")}</p>${can("employees.read")?`<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">${chip(EM.filter(e=>e.premises_id==p.id).length+" employees","gold")}${chip(EM.filter(e=>e.premises_id==p.id&&e.status=="active").length+" active","ok")}</div>`:""}<div class="subs"><h4 style="margin:0 0 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2)">Sub-premises (${kids.length})</h4>${kids.length?kids.map(k=>`<div class="sub">${I("building")}<div><b>${esc(k.name)}</b><div class="muted small">${esc(TY[k.type]||k.type)}${(g=>g?` · ${g.occupied}/${g.beds||"?"} beds`:"")(GH.find(x=>x.id==k.id))}</div></div></div>`).join(""):`<div class="muted small" style="padding:6px 0">None yet</div>`}</div></div>`}).join("")||emptyState("No premises","","building")}</div></div>`;
 $("#addp")&&($("#addp").onclick=addPremisesDrawer)};

function addPremisesDrawer(){const top=can("onboarding");
 drawer({title:"Add premises",sub:"A guest house or sub-premises inherits menu, roles and ticket types from its parent.",label:"Create",
  body:F("Parent premises","p",{opts:[...(top?[["","None: new top-level site"]]:[]),...PL.map(p=>[p.id,(p.parent_id?"↳ ":"")+p.name])],val:PREM})+(top?F("Company (for a top-level site)","co",{opts:COMP.map(c=>[c.id,c.name])}):"")+F("Name","n",{req:1,ph:"Guest House 2"})+F("Type","t",{opts:[["guest_house","Guest house"],["branch","Branch"],["hospital","Hospital office"],["office","Office"]]})+F("Address","a"),
  onSave:async()=>{if(!val("n"))throw Error("Name is required.");await api("/premises",{body:{parent_id:+val("p")||null,company_id:+val("co")||null,name:val("n"),type:val("t"),address:val("a")}});toast("Premises created");await loadRef();route()}})}

ROUTES.users=async function(){
 const u=await api("/users");crumbs([["Administration"],["Users & roles"]]);refPanel();
 const scope=g=>g.scope_level=="group"?"All companies":g.scope_level=="company"?cName(g.scope_id):premName(g.scope_id);
 const cols=[{h:"User",f:r=>`<div style="display:flex;gap:12px;align-items:center"><div class="av">${esc(init(r.name))}</div><div><div class="primary">${esc(r.name)}</div><div class="sec">${esc(r.email)}</div></div></div>`,t:r=>r.name},
  {h:"Role",f:r=>r.grants.map(g=>`<div>${esc(ROLES[g.role]||g.role)}</div>`).join(""),t:r=>r.grants.map(g=>ROLES[g.role]).join("; ")},{h:"Scope",f:r=>r.grants.map(g=>`<div>${chip(scope(g),"gold")}</div>`).join(""),t:r=>r.grants.map(scope).join("; ")},{h:"Status",f:r=>chip(r.active?"Active":"Inactive",r.active?"ok":""),t:r=>r.active?"Active":"Inactive"}];
 const o={q:r=>`${r.name} ${r.email} ${r.grants.map(g=>ROLES[g.role]).join(" ")}`,csv:"users",ph:"Search users",empty:"No users"};
 $("#main").innerHTML=`<div class="page">${head("Users & roles","Access is decided by role and scope together",`<button class="btn" id="addu">${I("plus")}Add user</button>`)}${table("t_u",cols,u,o)}</div>`;wire("t_u",u,cols,o);
 $("#addu").onclick=()=>{const tgt=lvl=>lvl=="company"?COMP.map(c=>[c.id,c.name]):lvl=="premises"?PL.map(p=>[p.id,p.name]):[["","All companies"]];
  drawer({title:"Add user",sub:"Create an account and grant a role over a scope.",label:"Create user",
  body:F("Full name","n",{req:1})+F("Email","e",{type:"email",req:1})+F("Initial password","p",{type:"password",hint:"The user should change it after first sign-in."})+F("Role","r",{opts:Object.entries(ROLES).map(([k,l])=>[k,l]),val:"driver"})+F("Scope level","l",{opts:[["company","Company"],["premises","Premises"],["group","Group (all)"]]})+`<div id="stgt">${F("Scope","s",{opts:tgt("company")})}</div>`,
  onOpen:()=>$("#f_l").onchange=e=>{$("#stgt").innerHTML=F("Scope","s",{opts:tgt(e.target.value)})},
  onSave:async()=>{if(!val("n")||!val("e")||!val("p"))throw Error("Name, email and password are required.");await api("/users",{body:{name:val("n"),email:val("e"),password:val("p"),role:val("r"),scope_level:val("l"),scope_id:+val("s")||null}});toast("User created");route()}})}};

const diff=(p,n)=>{try{const a=p?JSON.parse(p):{},b=n?JSON.parse(n):{},ks=Object.keys(b).filter(k=>!["id","password_hash"].includes(k)).slice(0,4);
 const out=ks.map(k=>a[k]!==undefined&&a[k]!==b[k]?`${k}: <span class="muted">${esc(a[k])}</span> → <b>${esc(b[k])}</b>`:`${k}: <b>${esc(b[k])}</b>`);return out.join("<br>")||"–"}catch{return "–"}};
ROUTES.audit=async function(){
 const a=await api("/audit");crumbs([["Administration"],["Audit trail"]]);refPanel();
 const cols=[{h:"When",cls:"nowrap",f:r=>fmtDT(r.at),t:r=>r.at},{h:"User",f:r=>esc(r.user_name),t:r=>r.user_name},{h:"Record",f:r=>`<span class="primary" style="text-transform:capitalize">${esc(r.entity)}</span> <span class="muted">#${r.entity_id}</span>`,t:r=>`${r.entity} #${r.entity_id}`},{h:"Action",f:r=>chip(r.action.replace(/_/g," "),"gold"),t:r=>r.action},{h:"Change",f:r=>`<div class="small">${diff(r.prev,r.new)}</div>`,t:r=>r.new}];
 const ents=[...new Set(a.map(x=>x.entity))];
 const o={tabs:[["all","All",()=>true],...ents.map(e=>[e,e[0].toUpperCase()+e.slice(1),r=>r.entity==e])],q:r=>`${r.user_name} ${r.entity} ${r.action} ${r.new}`,csv:"audit-trail",ph:"Search audit trail",empty:"No activity yet"};
 $("#main").innerHTML=`<div class="page">${head("Audit trail","Every change with user, time, previous and new value. Entries cannot be edited.")}${table("t_a",cols,a,o)}</div>`;wire("t_a",a,cols,o)};

Object.assign(ROUTES,P4,P5,P6,P7);
/* ---------- auth & boot ---------- */
async function loadRef(){[PL,COMP]=await Promise.all([api("/premises"),api("/companies")])}
function showLogin(){$("#shell").classList.add("hidden");$("#login").classList.remove("hidden");
 $("#heroList").innerHTML=[["shield","Role and scope based access on every request"],["file","A complete audit trail for each change"],["phone","Driver app for trips, meter photos and fuel"]].map(([i,t])=>`<li>${I(i)}${t}</li>`).join("");
 fetch("/api/auth/demo").then(r=>r.json()).then(a=>{if(!a.length)return;$("#demo").classList.remove("hidden");$("#demoList").innerHTML=a.map((x,i)=>`<button type="button" class="btn ghost sm" data-i="${i}"><span>${esc(x.label)}</span><span class="muted">${esc(x.email)}</span></button>`).join("");
  $$("#demoList button").forEach(b=>b.onclick=()=>login(a[b.dataset.i].email,a[b.dataset.i].password))}).catch(()=>{})}
async function login(email,password){$("#lerr").textContent="";const b=$("#go");b.disabled=true;
 try{const r=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const j=await r.json();if(!r.ok)throw Error(j.detail||"Sign-in failed");TOKEN=j.token;localStorage.bms_token=TOKEN;location.hash="#/dashboard";await boot()}
 catch(e){$("#lerr").textContent=e.message}finally{b.disabled=false}}
$("#lform").onsubmit=e=>{e.preventDefault();login($("#em").value.trim(),$("#pw").value)};
$("#showpw").onchange=e=>$("#pw").type=e.target.checked?"text":"password";
$("#gsearch").oninput=e=>{const i=$(".search input",$("#main"));if(i){i.value=e.target.value;i.dispatchEvent(new Event("input"))}};
$("#bell").onclick=e=>{e.stopPropagation();$("#pop").classList.toggle("hidden")};document.addEventListener("click",e=>{if(!e.target.closest("#pop"))$("#pop").classList.add("hidden")});
$("#tNav").innerHTML=I("pl");$("#tRef").innerHTML=I("pr");
if(localStorage.bms_navc=="1")document.body.classList.add("nav-c");if(localStorage.bms_refc=="1")document.body.classList.add("ref-c");
$("#tNav").onclick=()=>localStorage.bms_navc=document.body.classList.toggle("nav-c")?"1":"0";
$("#tRef").onclick=()=>localStorage.bms_refc=document.body.classList.toggle("ref-c")?"1":"0";
window.addEventListener("hashchange",route);
async function boot(){if(!TOKEN)return showLogin();
 try{ME=await api("/me");await loadRef()}catch{return showLogin()}
 $("#login").classList.add("hidden");$("#shell").classList.remove("hidden");renderBell();refreshNotes();if(!location.hash)location.hash="#/dashboard";route()}
boot();

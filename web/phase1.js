"use strict";
/* Phase 1 pages: Asset register, Tickets, Group Admin onboarding. Registered into ROUTES by app.js (Object.assign(ROUTES,P1)). */
const P1={};
const AS={in_service:["In service","ok"],under_maintenance:["Under maintenance","warn"],retired:["Retired",""]};
const CS={good:["Good","ok"],fair:["Fair","warn"],poor:["Poor","bad"]};
const PS={critical:["Critical","bad"],high:["High","warn"],medium:["Medium","gold"],low:["Low",""]};
const KS={open:["Open","warn"],assigned:["Assigned","gold"],in_progress:["In progress","gold"],on_hold:["On hold",""],resolved:["Resolved","ok"],closed:["Closed",""]};
const ACTIVE=["open","assigned","in_progress","on_hold"];
const CATS=["furniture","electrical","hvac","it","plumbing","fire_safety","appliance","security","building","housekeeping","vehicle","utilities","other"];
const catL=c=>({hvac:"HVAC",it:"IT",fire_safety:"Fire & safety"}[c]||String(c||"other").replace(/_/g," ").replace(/^./,x=>x.toUpperCase()));
const catOpts=(only)=>CATS.filter(c=>only||!["housekeeping","vehicle"].includes(c)).map(c=>[c,catL(c)]);
const premOpts=()=>PL.map(p=>[p.id,(p.parent_id?"↳ ":"")+p.name]);
const svcChip=a=>a.service_state=="overdue"?chip(`Overdue ${-daysTo(a.next_service_due)}d`,"bad"):a.service_state=="due_soon"?chip(`Due in ${daysTo(a.next_service_due)}d`,"warn"):a.next_service_due?chip("On schedule","ok"):`<span class="muted">No schedule</span>`;
const warChip=a=>a.warranty_state=="expired"?chip("Expired","bad"):a.warranty_state=="expiring"?chip(`Ends in ${daysTo(a.warranty_to)}d`,"warn"):a.warranty_to?chip("In warranty","ok"):`<span class="muted">–</span>`;
const isOverdue=t=>t.due_at&&ACTIVE.includes(t.status)&&dObj(t.due_at)<new Date();
const dueChip=t=>!ACTIVE.includes(t.status)?`<span class="muted">–</span>`:isOverdue(t)?chip("Overdue","bad")+`<div class="sec">${fmtDT(t.due_at)}</div>`:`<div>${fmtDT(t.due_at)}</div>`;
const subHead=(t,s)=>`<div class="hd" style="display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--gold-l)"><h2 style="margin:0;font-size:14px">${t}</h2>${s||""}</div>`;
const csvDownload=(name,rows)=>{const q=v=>`"${String(v??"").replace(/"/g,'""')}"`,a=document.createElement("a");a.href=URL.createObjectURL(new Blob([rows.map(r=>r.map(q).join(",")).join("\n")],{type:"text/csv"}));a.download=name;a.click()};
function parseCSV(t){t=t.replace(/^﻿/,"");const rows=[];let r=[],c="",q=false;
 for(let i=0;i<t.length;i++){const ch=t[i];
  if(q){if(ch=='"'){if(t[i+1]=='"'){c+='"';i++}else q=false}else c+=ch}
  else if(ch=='"')q=true;else if(ch==","){r.push(c);c=""}
  else if(ch=="\n"||ch=="\r"){if(ch=="\r"&&t[i+1]=="\n")i++;r.push(c);rows.push(r);r=[];c=""}else c+=ch}
 if(c||r.length){r.push(c);rows.push(r)}
 if(!rows.length)return[];const h=rows.shift().map(x=>x.trim().toLowerCase().replace(/\s+/g,"_"));
 return rows.filter(r=>r.some(x=>x.trim())).map(r=>Object.fromEntries(h.map((k,i)=>[k,(r[i]||"").trim()])))}


/* ======================= BULK UPLOAD (Excel template) ======================= */
const bulkBtns=sheet=>`<a class="btn ghost" href="/api/templates/workbook.xlsx?sheet=${sheet}&t=${TOKEN}" title="Excel file to fill in and send back">${I("download")}Template</a><button class="btn ghost" type="button" data-bulk="${sheet}">${I("upload")}Bulk upload</button>`;
document.addEventListener("click",e=>{const b=e.target.closest("[data-bulk]");if(b)bulkDrawer(b.dataset.bulk)});
const SHEETL={premises:"Premises",employees:"Employees",vehicles:"Vehicles",assets:"Assets",travel_policy:"Travel policy",visas:"Visas"};
function bulkDrawer(sheet){let file=null,changed=false;const what=sheet=="all"?"premises, employees, vehicles and assets":SHEETL[sheet].toLowerCase();
 drawer({title:"Bulk upload",sub:`Add ${what} from the Excel template. Nothing is saved until you confirm.`,label:"Close",
  body:`<ol style="margin:0 0 14px;padding-left:18px;line-height:1.7"><li>Download the template and fill it in (or send it to the person who has the details).</li><li>Choose the completed file below. It is checked first.</li><li>Fix any errors shown, or confirm the import.</li></ol>
   <a class="btn ghost sm" href="/api/templates/workbook.xlsx?sheet=${sheet}&t=${TOKEN}">${I("download")}Download template (.xlsx)</a>
   <label class="f" style="margin-top:16px">Completed file<input type="file" id="bfile" accept=".xlsx,.xlsm,.csv"></label><div id="bres"></div>`,
  onSave:async()=>{if(changed){await loadRef();route()}},
  onOpen:()=>{const send=async commit=>{const f=new FormData();f.append("file",file);f.append("commit",commit?"1":"");if(sheet!="all")f.append("kind",sheet);return api("/bulk/upload",{body:f})};
   const show=r=>{const el=$("#bres"),ks=Object.keys(r.sheets);
    el.innerHTML=`<div class="obsum">${chip(r.created+(r.committed?" imported":" ready to import"),r.created&&!r.errors?"ok":"")}${r.errors?chip(r.errors+" with errors","bad"):""}</div>`
     +ks.map(k=>{const x=r.sheets[k];return `<div style="margin:10px 0"><b>${SHEETL[k]}</b> <span class="muted small">· ${x.rows} rows · ${x.created} ${r.committed?"imported":"new"}${x.skipped.length?` · ${x.skipped.length} already exist`:""}</span>
      ${x.errors.length?`<ul class="obl bad">${x.errors.slice(0,15).map(e=>`<li><b>Row ${e.row}</b> · ${esc(e.msg)}</li>`).join("")}${x.errors.length>15?`<li>…and ${x.errors.length-15} more</li>`:""}</ul>`:""}
      ${x.notes.length?`<ul class="obl warn">${[...new Set(x.notes)].map(n=>`<li>${esc(n)}</li>`).join("")}</ul>`:""}</div>`}).join("")
     +(r.errors?`<p class="muted small">Nothing was imported. Correct these rows in your file and choose it again.</p>`:"")
     +(!r.errors&&!r.committed&&r.created?`<button class="btn" type="button" id="bgo">${I("check")}Import ${r.created} record${r.created>1?"s":""}</button>`:"")
     +(!r.errors&&!r.committed&&!r.created?`<p class="muted">Everything in the file already exists. Nothing to import.</p>`:"")
     +(r.committed?`<p style="color:var(--ok);font-weight:600">Imported. Close this panel to see the new records.</p>`:"");
    $("#bgo")&&($("#bgo").onclick=async()=>{$("#bgo").disabled=true;try{const x=await send(true);changed=true;show(x);toast(`Imported ${x.created} records`)}catch(e){toast(e.message,false);$("#bgo").disabled=false}})};
   $("#bfile").onchange=async e=>{file=e.target.files[0];if(!file)return;$("#bres").innerHTML=`<div class="skel" style="width:60%"></div>`;try{show(await send(false))}catch(x){$("#bres").innerHTML=`<p class="ferr">${esc(x.message)}</p>`}}}})}

/* ======================= ASSET REGISTER ======================= */
function assetForm(a,pre){const E=!!a,v=k=>a?a[k]:undefined;
 drawer({title:E?`Edit ${a.asset_tag}`:"Add asset",sub:E?"Changes are recorded in the audit trail.":"Register an asset against a premises. It gets a tag automatically.",label:E?"Save changes":"Add asset",
  body:(E?"":F("Premises","p",{opts:premOpts(),val:pre||PREM}))+F("Asset name","n",{req:1,val:v("name"),ph:"Diesel generator 125 kVA"})+F("Category","c",{opts:catOpts(),val:v("category")||"other"})+F("Make & model","m",{val:v("make_model")})+F("Serial number","s",{val:v("serial_no")})+F("Location (floor / room)","l",{val:v("location")})
   +F("Purchase date","pd",{type:"date",val:v("purchase_date")})+F("Purchase value","pv",{type:"number",val:v("purchase_value")})+F("Warranty valid to","w",{type:"date",val:v("warranty_to")})+F("Vendor / AMC","vn",{val:v("vendor")})
   +F("Service every (days)","si",{type:"number",val:v("service_interval_days"),hint:"For example 90 for quarterly. Leave empty if there is no routine service."})+(E?"":F("Last serviced on","ls",{type:"date"}))
   +F("Condition","cd",{opts:[["good","Good"],["fair","Fair"],["poor","Poor"]],val:v("condition")||"good"})+(E?F("Status","st",{opts:[["in_service","In service"],["under_maintenance","Under maintenance"],["retired","Retired"]],val:v("status")}):""),
  onSave:async()=>{if(!val("n"))throw Error("Asset name is required.");
   const b={name:val("n"),category:val("c"),make_model:val("m"),serial_no:val("s"),location:val("l"),purchase_date:val("pd")||null,purchase_value:val("pv")||null,warranty_to:val("w")||null,vendor:val("vn"),service_interval_days:val("si")||null,condition:val("cd")};
   if(E){b.status=val("st");await api(`/assets/${a.id}/update`,{body:b});toast("Asset updated")}else{b.premises_id=+val("p");b.last_service_date=val("ls")||null;await api("/assets",{body:b});toast("Asset added")}route()}})}

P1.assets=async function(){
 const all=(await api("/assets")).filter(x=>inPrem(x.premises_id));crumbs([["Maintenance"],["Asset register"]]);refPanel();
 const cols=[{h:"Asset",f:r=>`<div class="primary">${esc(r.name)}</div><div class="sec">${esc(r.asset_tag)}${r.make_model?" · "+esc(r.make_model):""}</div>`,t:r=>r.asset_tag},{h:"Premises",f:r=>`<div>${esc(premName(r.premises_id))}</div><div class="sec">${esc(r.location||"")}</div>`,t:r=>premName(r.premises_id)},{h:"Category",f:r=>esc(catL(r.category)),t:r=>catL(r.category)},
  {h:"Condition",f:r=>sc(CS,r.condition),t:r=>r.condition},{h:"Next service",f:r=>svcChip(r)+(r.next_service_due?`<div class="sec">${fmtD(r.next_service_due)}</div>`:""),t:r=>r.next_service_due},
  {h:"Warranty",f:r=>warChip(r),t:r=>r.warranty_to},{h:"Status",f:r=>sc(AS,r.status),t:r=>AS[r.status]?.[0]},{h:"",cls:"right",f:()=>`<span class="muted">${I("chev")}</span>`}];

 const o={tabs:[["all","All",()=>true],["svc","Service due",r=>["overdue","due_soon"].includes(r.service_state)&&r.status!="retired"],["maint","Under maintenance",r=>r.status=="under_maintenance"],["war","Warranty ending",r=>["expired","expiring"].includes(r.warranty_state)],["poor","Poor condition",r=>r.condition=="poor"],["ret","Retired",r=>r.status=="retired"]],
  q:r=>`${r.asset_tag} ${r.name} ${r.make_model} ${r.serial_no} ${r.location} ${premName(r.premises_id)} ${catL(r.category)}`,csv:"assets",ph:"Search assets",empty:"No assets yet",emptySub:can("onboarding")?"Import them in bulk from Onboarding, or add one here.":"Add an asset to start tracking it.",click:r=>location.hash="#/assets/"+r.id};
 $("#main").innerHTML=`<div class="page">${head("Asset register",`${all.length} assets · ${esc(premScope())}`,(can("assets.write")?bulkBtns("assets"):"")+(can("assets.write")?`<button class="btn" id="adda">${I("plus")}Add asset</button>`:""))}${table("t_as",cols,all,o)}</div>`;
 wire("t_as",all,cols,o);$("#adda")&&($("#adda").onclick=()=>assetForm())};

P1.asset=async function(id){
 const d=await api("/assets/"+id),a=d.asset;crumbs([["Maintenance"],["Asset register","assets"],[a.asset_tag]]);addRecent(a.asset_tag+" "+a.name,"assets/"+id,"box");
 refPanel({title:a.name,kind:"Asset · "+a.asset_tag,entity:"asset",id,kv:[["Premises",esc(premName(a.premises_id))],["Condition",sc(CS,a.condition)],["Status",sc(AS,a.status)],["Next service",svcChip(a)]]});
 const openT=d.tickets.filter(t=>ACTIVE.includes(t.status)).length;let tab="overview";
 const svcCols=[{h:"Date",f:r=>fmtD(r.on)},{h:"Type",f:r=>`<span style="text-transform:capitalize">${esc(r.kind)}</span>`},{h:"Vendor",f:r=>esc(r.vendor||"–")},{h:"Cost",cls:"num right",f:r=>n0(r.cost)},{h:"Notes",f:r=>esc(r.notes||"")},{h:"By",f:r=>esc(r.by_name||"")}];
 const tkCols=[{h:"Ticket",f:r=>`<span class="primary">TK-${String(r.id).padStart(4,"0")}</span>`},{h:"Issue",f:r=>esc(r.title)},{h:"Priority",f:r=>sc(PS,r.priority)},{h:"Status",f:r=>sc(KS,r.status)},{h:"Raised",f:r=>fmtDT(r.raised_at)}];
 const paint=()=>{const c=$("#tabc");
  if(tab=="overview")c.innerHTML=`<div class="grid g2-1"><div class="panel"><div class="hd"><h2>Asset details</h2></div><div class="bd"><dl class="dl"><dt>Tag</dt><dd>${esc(a.asset_tag)}</dd><dt>Category</dt><dd>${esc(catL(a.category))}</dd><dt>Make & model</dt><dd>${esc(a.make_model||"–")}</dd><dt>Serial number</dt><dd>${esc(a.serial_no||"–")}</dd><dt>Premises</dt><dd>${esc(premName(a.premises_id))}</dd><dt>Location</dt><dd>${esc(a.location||"–")}</dd><dt>Vendor / AMC</dt><dd>${esc(a.vendor||"–")}</dd><dt>Purchased</dt><dd>${fmtD(a.purchase_date)} · ${n0(a.purchase_value)}</dd>${a.external_source?`<dt>External ref</dt><dd>${esc(a.external_source)} · ${esc(a.external_id)}</dd>`:""}</dl></div></div>
   <div class="panel"><div class="hd"><h2>Maintenance</h2></div><div class="bd"><dl class="dl"><dt>Service every</dt><dd>${a.service_interval_days?a.service_interval_days+" days":"No routine service"}</dd><dt>Last serviced</dt><dd>${fmtD(a.last_service_date)}</dd><dt>Next due</dt><dd>${fmtD(a.next_service_due)} ${a.next_service_due?svcChip(a):""}</dd><dt>Warranty</dt><dd>${fmtD(a.warranty_to)} ${warChip(a)}</dd></dl>${a.notes?`<p class="muted" style="margin-top:10px">${esc(a.notes)}</p>`:""}</div></div></div>`;
  else if(tab=="svc"){c.innerHTML=table("t_sv",svcCols,d.services,{noBar:true,empty:"No service recorded",emptySub:"Log each preventive service or repair here."});wire("t_sv",d.services,[],{})}
  else{c.innerHTML=table("t_tk",tkCols,d.tickets,{noBar:true,click:true,empty:"No tickets for this asset"});wire("t_tk",d.tickets,[],{click:r=>location.hash="#/tickets/"+r.id})}};
 $("#main").innerHTML=`<div class="page"><div class="rh"><div class="big">${I("box")}</div><div><h1>${esc(a.name)}</h1><p>${esc(a.asset_tag)} · ${esc(catL(a.category))} · ${esc(premName(a.premises_id))}${a.location?" · "+esc(a.location):""}</p></div><div>${sc(AS,a.status)}</div>
  <div class="acts">${can("assets.service")?`<button class="btn ghost" id="bsv">${I("clock")}Log service</button>`:""}${can("assets.write")?`<button class="btn ghost" id="bed">Edit</button>`:""}${can("tickets.raise")?`<button class="btn" id="btk">${I("plus")}Raise ticket</button>`:""}</div></div>
  <div class="grid g4"><div class="kpi ${a.condition=="poor"?"bad":a.condition=="fair"?"warn":""}"><div class="k">Condition</div><div class="v" style="text-transform:capitalize">${a.condition}</div></div><div class="kpi ${a.service_state=="overdue"?"bad":a.service_state=="due_soon"?"warn":""}"><div class="k">Next service</div><div class="v" style="font-size:20px">${a.next_service_due?fmtD(a.next_service_due):"–"}</div><div class="s">${a.service_state=="overdue"?"Overdue":a.service_state=="due_soon"?"Due soon":"&nbsp;"}</div></div><div class="kpi"><div class="k">Services logged</div><div class="v">${d.services.length}</div></div><div class="kpi ${openT?"warn":""}"><div class="k">Open tickets</div><div class="v">${openT}</div></div></div>
  <div class="tabs" id="atabs">${[["overview","Overview"],["svc","Service history"],["tk","Tickets"]].map(([k,l])=>`<button data-t="${k}" class="${k==tab?"on":""}">${l}</button>`).join("")}</div><div id="tabc"></div></div>`;
 $$("#atabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;$$("#atabs button").forEach(x=>x.classList.toggle("on",x==b));paint()});
 $("#bed")&&($("#bed").onclick=()=>assetForm(a));$("#btk")&&($("#btk").onclick=()=>raiseTicket({asset:a}));
 $("#bsv")&&($("#bsv").onclick=()=>drawer({title:"Log service",sub:`${a.asset_tag} · ${a.name}`,label:"Save service",
  body:F("Type","k",{opts:[["preventive","Preventive service"],["repair","Repair"],["inspection","Inspection"]]})+F("Date","d",{type:"date",val:new Date().toISOString().slice(0,10)})+F("Cost","c",{type:"number",step:"0.01"})+F("Vendor / technician","v",{val:a.vendor})+F("Condition after service","cd",{opts:[["good","Good"],["fair","Fair"],["poor","Poor"]],val:a.condition})+F("Notes","n",{rows:3}),
  onSave:async()=>{await api(`/assets/${id}/service`,{body:{kind:val("k"),on:val("d"),cost:val("c")||null,vendor:val("v"),condition:val("cd"),notes:val("n")}});toast("Service logged");route()}}));
 paint()};

/* ======================= TICKETS ======================= */
async function raiseTicket(pre={}){
 let A=[];try{A=can("assets.read")?await api("/assets"):[]}catch{}
 const a0=pre.asset,ut=pre.utility,pid=a0?a0.premises_id:(ut?ut.premises_id:(pre.premises_id||PREM||PL[0]?.id));
 const aopts=p=>[["","No specific asset"],...A.filter(x=>x.premises_id==p&&x.status!="retired").map(x=>[x.id,`${x.asset_tag} · ${x.name}`])];
 drawer({title:"Raise a ticket",sub:"The maintenance team will see it immediately.",label:"Raise ticket",
  body:F("Premises","p",{opts:premOpts(),val:pid})+`<div id="asel">${F("Related asset","a",{opts:aopts(pid),val:a0?a0.id:""})}</div>`+F("What is the problem?","t",{req:1,val:ut?`${({electricity:"Electricity",water:"Water",internet:"Internet",gas:"Gas",telephone:"Telephone",waste:"Waste"}[ut.kind]||"Utility")} (${ut.provider}): `:undefined,ph:"Short title, e.g. Chiller tripping"})+F("Details","d",{rows:3,hint:"Where it is, what you noticed, since when."})
   +F("Category","c",{opts:catOpts(true),val:ut?"utilities":(a0?a0.category:"other")})+F("Priority","pr",{opts:[["low","Low · within 7 days"],["medium","Medium · within 3 days"],["high","High · within 24 hours"],["critical","Critical · within 4 hours"]],val:"medium"})+F("Is the asset out of use?","m",{opts:[["","No"],["1","Yes, mark it under maintenance"]]}),
  onOpen:()=>{if(a0||ut)$("#f_p").disabled=true;$("#f_p").onchange=e=>{$("#asel").innerHTML=F("Related asset","a",{opts:aopts(e.target.value)})}},
  onSave:async()=>{if(!val("t"))throw Error("Add a short title.");const t=await api("/tickets",{body:{premises_id:+val("p"),asset_id:val("a")?+val("a"):null,utility_id:ut?ut.id:null,title:val("t"),description:val("d"),category:val("c"),priority:val("pr"),mark_under_maintenance:!!val("m")}});toast("Ticket "+t.ticket_no+" raised");location.hash="#/tickets/"+t.id;route()}})}

P1.tickets=async function(){
 const all=(await api("/tickets")).filter(x=>inPrem(x.premises_id));crumbs([["Maintenance"],["Tickets"]]);refPanel();
 const act=all.filter(t=>ACTIVE.includes(t.status));
 const cols=[{h:"Ticket",f:r=>`<div class="primary">${esc(r.title)}</div><div class="sec">${r.ticket_no}${r.asset_tag?" · "+esc(r.asset_tag)+" "+esc(r.asset_name):""}</div>`,t:r=>r.ticket_no+" "+r.title},
  {h:"Premises",f:r=>esc(premName(r.premises_id)),t:r=>premName(r.premises_id)},{h:"Priority",f:r=>sc(PS,r.priority),t:r=>r.priority},
  {h:"Raised by",f:r=>`<div>${esc((r.raised_by_name||"").replace(/\(.*\)/,"").trim())}</div><div class="sec">${fmtDT(r.raised_at)}</div>`,t:r=>r.raised_by_name},
  {h:"Assigned to",f:r=>r.assigned_to?esc(r.assigned_to):`<span class="muted">Not assigned</span>`,t:r=>r.assigned_to},{h:"Due",f:r=>dueChip(r),t:r=>r.due_at},{h:"Status",f:r=>sc(KS,r.status),t:r=>KS[r.status]?.[0]},{h:"",cls:"right",f:()=>`<span class="muted">${I("chev")}</span>`}];
 const o={tabs:[["act","Active",r=>ACTIVE.includes(r.status)],["new","Unassigned",r=>r.status=="open"],["prog","In progress",r=>r.status=="in_progress"],["over","Overdue",r=>isOverdue(r)],["res","Resolved",r=>r.status=="resolved"],["closed","Closed",r=>r.status=="closed"],["all","All",()=>true]],
  q:r=>`${r.ticket_no} ${r.title} ${r.asset_name} ${r.asset_tag} ${premName(r.premises_id)} ${r.raised_by_name} ${r.assigned_to}`,csv:"tickets",ph:"Search tickets",empty:"No tickets",emptySub:"Tickets are raised by HR, Admin or the Maintenance team.",click:r=>location.hash="#/tickets/"+r.id};
 const un=act.filter(t=>t.status=="open").length,hi=act.filter(t=>["critical","high"].includes(t.priority)).length,ov=act.filter(isOverdue).length,rs=all.filter(t=>t.status=="resolved").length;
 $("#main").innerHTML=`<div class="page">${head("Tickets",`${can("tickets.manage")?"All tickets in your scope":"Tickets for your premises"} · ${esc(premScope())}`,can("tickets.raise")?`<button class="btn" id="rt">${I("plus")}Raise ticket</button>`:"")}
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">${I("ticket")}Active</div><div class="v">${act.length}</div><div class="s">open, assigned or in progress</div></div><div class="kpi ${un?"warn":""}"><div class="k">Unassigned</div><div class="v">${un}</div><div class="s">waiting for the team</div></div><div class="kpi ${hi?"warn":""}"><div class="k">High & critical</div><div class="v">${hi}</div><div class="s">active</div></div><div class="kpi ${ov?"bad":""}"><div class="k">Overdue</div><div class="v">${ov}</div><div class="s">${rs} resolved, awaiting closure</div></div></div>${table("t_tk",cols,all,o)}</div>`;
 wire("t_tk",all,cols,o);$("#rt")&&($("#rt").onclick=()=>raiseTicket())};

P1.ticket=async function(id){
 const d=await api("/tickets/"+id),t=d.ticket,ev=d.events;crumbs([["Maintenance"],["Tickets","tickets"],[t.ticket_no]]);addRecent(t.ticket_no+" "+t.title,"tickets/"+id,"ticket");
 refPanel({title:t.ticket_no,kind:"Ticket",entity:"ticket",id,kv:[["Status",sc(KS,t.status)],["Priority",sc(PS,t.priority)],["Premises",esc(premName(t.premises_id))],["Assigned to",esc(t.assigned_to||"–")]]});
 const upd=async b=>{try{await api(`/tickets/${id}/update`,{body:b});toast("Ticket updated");route()}catch(e){toast(e.message,false)}};
 let act="";
 if(d.can_manage)act=`<div class="panel"><div class="hd"><h2>Update ticket</h2></div><div class="bd">${F("Status","s",{opts:Object.entries(KS).map(([k,v])=>[k,v[0]]),val:t.status})}${F("Assigned to","as",{val:t.assigned_to,ph:"Technician or vendor name"})}<div id="rs">${F("Resolution","r",{rows:3,hint:"Required when resolving. Say what was done."})}</div>${F("Add a note","c",{rows:2})}<button class="btn" id="usave" style="width:100%;justify-content:center">Save update</button></div></div>`;
 else act=`<div class="panel"><div class="hd"><h2>Actions</h2></div><div class="bd">${d.can_raise&&["resolved","closed"].includes(t.status)?`<p class="muted" style="margin:0 0 10px">${t.status=="resolved"?"Check the work and confirm.":"Closed. Reopen if the problem is back."}</p><div style="display:grid;gap:8px">${t.status=="resolved"?`<button class="btn" id="bclose">${I("check")}Confirm fixed &amp; close</button>`:""}<button class="btn ghost" id="breopen">Reopen ticket</button></div><hr style="border:0;border-top:1px solid var(--gold-l);margin:14px 0">`:""}${F("Add a note","c",{rows:2})}<button class="btn ghost" id="bnote" style="width:100%;justify-content:center">Post note</button></div></div>`;
 const evIc={created:"plus",comment:"file",status:"check",assign:"users"};
 $("#main").innerHTML=`<div class="page"><div class="rh"><div class="big">${I("ticket")}</div><div><h1>${esc(t.title)}</h1><p>${t.ticket_no} · ${esc(catL(t.category))} · ${esc(premName(t.premises_id))}</p></div><div style="display:flex;gap:8px">${sc(PS,t.priority)}${sc(KS,t.status)}</div></div>
  <div class="grid g2-1"><div style="display:grid;gap:16px;align-content:start">
   <div class="panel"><div class="hd"><h2>Details</h2></div><div class="bd"><p style="margin:0 0 14px;white-space:pre-wrap">${esc(t.description||"No description given.")}</p><dl class="dl">${d.utility?`<dt>Utility</dt><dd>${esc(d.utility.kind)} · ${esc(d.utility.provider)}${d.utility.account_ref?" · "+esc(d.utility.account_ref):""}</dd>`:""}<dt>Asset</dt><dd>${t.asset_id?`<a href="#/assets/${t.asset_id}">${esc(t.asset_tag)} · ${esc(t.asset_name)}</a>`:"–"}</dd><dt>Raised by</dt><dd>${esc(t.raised_by_name||"–")} · ${fmtDT(t.raised_at)}</dd><dt>Due</dt><dd>${fmtDT(t.due_at)} ${isOverdue(t)?chip("Overdue","bad"):""}</dd><dt>Assigned to</dt><dd>${esc(t.assigned_to||"Not assigned")}</dd>${t.resolution?`<dt>Resolution</dt><dd>${esc(t.resolution)}</dd>`:""}${t.source!="bms"?`<dt>Source</dt><dd>${esc(t.source)} · ${esc(t.external_id||"")}</dd>`:""}</dl></div></div>
   <div class="panel"><div class="hd"><h2>Activity</h2></div><div class="bd"><div class="tl">${ev.map(e=>`<div class="ev"><b>${esc(e.kind=="comment"?"Note":e.kind=="created"?"Raised":e.kind=="assign"?"Assignment":"Status")}</b><div>${esc(e.text||"")}</div><small>${esc(e.user_name)} · ${fmtDT(e.at)}</small></div>`).join("")}</div></div></div></div>
   <div style="align-content:start;display:grid;gap:16px">${act}</div></div></div>`;
 const note=()=>({comment:val("c")});
 if(d.can_manage){const tog=()=>$("#rs").style.display=val("s")=="resolved"?"":"none";tog();$("#f_s").onchange=tog;
  $("#usave").onclick=()=>{const b={comment:val("c")};if(val("s")!=t.status)b.status=val("s");if((val("as")||"")!=(t.assigned_to||""))b.assigned_to=val("as");if(val("s")=="resolved")b.resolution=val("r");
   if(!b.comment&&!b.status&&!b.assigned_to)return toast("Nothing to update.",false);upd(b)}}
 $("#bclose")&&($("#bclose").onclick=()=>upd({status:"closed",comment:val("c")}));$("#breopen")&&($("#breopen").onclick=()=>upd({status:"open",comment:val("c")||"Reopened"}));
 $("#bnote")&&($("#bnote").onclick=()=>val("c")?upd(note()):toast("Write a note first.",false))};

/* ======================= ONBOARDING (Group Admin) ======================= */
const OB={
 premises:{n:1,title:"Premises & guest houses",desc:"Top-level sites, then the guest houses or sub-premises beneath them. List a parent above its children. Re-running is safe: names that already exist are skipped.",
  tpl:[["company","name","type","parent","address","country","currency"],["Jiva Technologies","Corporate Office, Bengaluru","office","","MG Road, Bengaluru","India","INR"],["","Guest House 1","guest house","Corporate Office, Bengaluru","Indiranagar, Bengaluru","",""]]},
 employees:{n:2,title:"Employees",desc:"Employees mapped to a building, with grade. This is the manual route until the HRMS is connected. Status: active, on_leave, notice, resigned, inactive.",
  tpl:[["premises","emp_code","name","grade","designation","department","email","phone","status","join_date"],["Corporate Office, Bengaluru","JT2001","Priya Sharma","M2","Manager","HR","priya@example.org","","active","2021-07-01"]]},
 vehicles:{n:3,title:"Vehicles",desc:"Each vehicle is mapped to a premises by name. Documents (insurance, fitness…) are added on the vehicle afterwards.",
  tpl:[["premises","reg_no","make_model","year","odometer","purchase_date","purchase_value"],["Corporate Office, Bengaluru","KA01AB1234","Toyota Innova Crysta","2023","18250","2023-04-01","2400000"]]},
 assets:{n:4,title:"Admin assets",desc:"Generators, lifts, AC, fire systems, appliances and so on. Set service_interval_days to schedule routine maintenance. Categories: furniture, electrical, hvac, it, plumbing, fire_safety, appliance, security, building, other.",
  tpl:[["premises","name","category","make_model","serial_no","location","purchase_date","purchase_value","warranty_to","vendor","service_interval_days","last_service_date","condition"],["Guest House 1","Solar water heater","plumbing","Racold 200L","RC-2231","Terrace","2023-02-10","54000","2026-02-10","Racold AMC","180","2026-08-01","good"]]}};
const OBROWS={};
function obShow(kind,r){const el=$("#res_"+kind),bad=r.errors.length;
 el.innerHTML=`<div class="obsum">${chip(r.rows+" rows read","")}${chip(r.created+(r.committed?" imported":" ready to import"),r.created&&!bad?"ok":"")}${r.skipped.length?chip(r.skipped.length+" already exist","warn"):""}${bad?chip(bad+" with errors","bad"):""}</div>`
  +(r.notes.length?`<ul class="obl warn">${[...new Set(r.notes)].map(n=>`<li>${esc(n)}</li>`).join("")}</ul>`:"")
  +(bad?`<ul class="obl bad">${r.errors.slice(0,12).map(e=>`<li><b>Row ${e.row}</b> · ${esc(e.msg)}</li>`).join("")}${bad>12?`<li>…and ${bad-12} more</li>`:""}</ul><p class="muted small">Nothing was imported. Fix the file and choose it again.</p>`:"")
  +(r.skipped.length?`<ul class="obl">${r.skipped.slice(0,4).map(e=>`<li>Row ${e.row} · ${esc(e.msg)}, skipped</li>`).join("")}</ul>`:"")
  +(!bad&&!r.committed&&r.created?`<button class="btn" id="go_${kind}">${I("check")}Import ${r.created} record${r.created>1?"s":""}</button>`:"")
  +(r.committed?`<p style="color:var(--ok);font-weight:600;margin:8px 0 0">Imported ${r.created}.</p>`:"");
 $("#go_"+kind)&&($("#go_"+kind).onclick=async()=>{try{const x=await api("/onboarding/"+kind,{body:{rows:OBROWS[kind],commit:true}});obShow(kind,x);toast(`Imported ${x.created} ${kind}`);await loadRef();setTimeout(route,900)}catch(e){toast(e.message,false)}})}
async function obFile(kind,file){const el=$("#res_"+kind);el.innerHTML=`<div class="skel" style="width:50%"></div>`;
 try{const rows=parseCSV(await file.text());if(!rows.length)throw Error("The file has no data rows. Use the template.");OBROWS[kind]=rows;obShow(kind,await api("/onboarding/"+kind,{body:{rows,commit:false}}))}catch(e){el.innerHTML=`<p class="ferr">${esc(e.message)}</p>`}}

P1.onboarding=async function(){
 const st=await api("/onboarding/status");await loadRef();crumbs([["Administration"],["Onboarding"]]);refPanel();
 const P=st.premises,tot=st.totals,roots=P.filter(p=>!p.parent_id||!P.find(x=>x.id==p.parent_id)),TY={office:"Office",guest_house:"Guest house",branch:"Branch",hospital:"Hospital office"};
 const ordered=[];roots.forEach(r=>{ordered.push({...r,lvl:0});P.filter(k=>k.parent_id==r.id).forEach(k=>ordered.push({...k,lvl:1}))});
 const noAssets=P.filter(p=>!p.assets).length,noInch=P.filter(p=>!p.incharge.length).length;
 const cols=[{h:"Premises",f:r=>`<div style="padding-left:${r.lvl*22}px" class="primary">${r.lvl?"↳ ":""}${esc(r.name)}</div><div class="sec" style="padding-left:${r.lvl*22}px">${esc(cName(r.company_id))} · ${esc(TY[r.type]||r.type)}</div>`,t:r=>r.name},
  {h:"Admin in-charge",f:r=>r.incharge.length?esc(r.incharge.join(", ")):`<span class="muted">Not assigned</span>`,t:r=>r.incharge.join("; ")},{h:"Employees",cls:"num right",f:r=>r.employees,t:r=>r.employees},{h:"Vehicles",cls:"num right",f:r=>r.vehicles,t:r=>r.vehicles},{h:"Assets",cls:"num right",f:r=>r.assets,t:r=>r.assets},
  {h:"Setup",f:r=>!r.incharge.length?chip("No in-charge","warn"):!r.assets?chip("No assets","warn"):chip("Mapped","ok"),t:r=>!r.incharge.length?"No in-charge":!r.assets?"No assets":"Mapped"}];
 const o={noBar:true,empty:"No premises yet",emptySub:"Start with step 1."};
 $("#main").innerHTML=`<div class="page">${head("Onboarding","One-time setup by the Group Administrator: premises, guest houses, vehicles and assets, each mapped to a premises.",bulkBtns("all")+`<button class="btn ghost" id="obp">${I("plus")}Add one premises</button>`)}
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">${I("building")}Premises</div><div class="v">${tot.premises}</div><div class="s">${tot.employees} employees mapped</div></div><div class="kpi"><div class="k">${I("car")}Vehicles</div><div class="v">${tot.vehicles}</div></div><div class="kpi"><div class="k">${I("box")}Assets</div><div class="v">${tot.assets}</div></div><div class="kpi ${noAssets||noInch?"warn":""}"><div class="k">${I("alert")}Needs attention</div><div class="v">${Math.max(noAssets,noInch)}</div><div class="s">${noAssets} without assets · ${noInch} without an in-charge</div></div></div>
  <div class="grid g2-1"><div style="display:grid;gap:16px;align-content:start">${Object.entries(OB).map(([k,x])=>`<div class="panel"><div class="hd"><span class="stepno">${x.n}</span><h2>${x.title}</h2><div class="acts"><button class="btn ghost sm" data-tpl="${k}">${I("download")}Template</button><label class="btn sm" style="cursor:pointer">${I("upload")}Choose CSV<input type="file" accept=".csv,text/csv" data-up="${k}" hidden></label></div></div><div class="bd"><p class="muted" style="margin:0 0 8px">${x.desc}</p><div id="res_${k}"></div></div></div>`).join("")}</div>
   <div style="display:grid;gap:16px;align-content:start"><div class="panel"><div class="hd"><h2>Logins to create</h2></div><div class="bd"><p class="muted" style="margin:0 0 10px">After premises exist, create the people who work with them in <a href="#/users">Users &amp; roles</a>.</p>
    <div class="row"><div class="grow"><b>Admin In-charge</b><div class="muted small">Role "Admin In-charge", scope = their premises. Raises tickets and manages that premises' assets.</div></div></div>
    <div class="row"><div class="grow"><b>Maintenance Head</b><div class="muted small">Role "Maintenance Head", scope = Group. Sees and works every ticket, and can raise them.</div></div></div>
    <div class="row"><div class="grow"><b>HR</b><div class="muted small">Role "HR", scope = Group or company. Manages employees and guest house allocation, can raise tickets.</div></div></div>
    <div class="row"><div class="grow"><b>Drivers</b><div class="muted small">Role "Driver", scope = company.</div></div></div></div></div>
    <div class="panel"><div class="hd"><h2>Integration API</h2></div><div class="bd"><p class="muted" style="margin:0 0 8px">Assets and tickets carry a source and external ID, so an asset-management or ticketing system can read and write them later. Authenticate with the <code>X-API-Key</code> header (set <code>INTEGRATION_API_KEY</code> on the server).</p>
    <div class="small" style="line-height:1.9"><code>GET  /api/integration/assets?updated_since=</code><br><code>POST /api/integration/assets</code><br><code>GET  /api/integration/tickets?updated_since=</code><br><code>POST /api/integration/tickets</code><br><a href="/docs" target="_blank" rel="noopener">Full API reference</a></div></div></div></div></div>
  <div style="margin-top:16px">${table("t_ob",cols,ordered,o).replace('<div class="tbar"></div>',subHead("Coverage by premises",`<span class="muted small">Every premises needs an in-charge and its assets</span>`))}</div></div>`;
 wire("t_ob",ordered,cols,{});
 $$("[data-tpl]").forEach(b=>b.onclick=()=>csvDownload(`bms-${b.dataset.tpl}-template.csv`,OB[b.dataset.tpl].tpl));
 $$("[data-up]").forEach(i=>i.onchange=()=>{if(i.files[0])obFile(i.dataset.up,i.files[0]);i.value=""});
 $("#obp").onclick=()=>addPremisesDrawer()};

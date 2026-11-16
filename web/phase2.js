"use strict";
/* Phase 2 pages: Employees per building, Guest houses, Travel advances, HRMS integration. Registered by app.js. */
const P2={};
const ES={active:["Active","ok"],on_leave:["On leave","warn"],notice:["Notice period","warn"],resigned:["Resigned","bad"],inactive:["Inactive",""]};
const HS={ok:["Connected","ok"],error:["Not reachable","bad"],untested:["Not tested yet","warn"],off:["Switched off",""],not_configured:["Not configured","warn"]};
const AD={pending:["Waiting","warn"],pushed:["Sent to HR","ok"],failed:["Failed","bad"]};
const GRADE=g=>g?`<span class="chip gold" style="font-weight:600"><i></i>${esc(g)}</span>`:`<span class="muted">–</span>`;
const buildings=()=>PL.filter(p=>p.type!="guest_house");
const bldOpts=()=>buildings().map(p=>[p.id,p.name]);
const dayN=d=>d?Math.floor((dObj(d)-new Date(new Date().toDateString()))/864e5):null;

/* ---------- employee form ---------- */
function employeeForm(e){const E=!!e,v=k=>e?e[k]:undefined;
 drawer({title:E?`Edit ${e.name}`:"Add employee",sub:E?e.emp_code+" · changes are recorded in the audit trail":"Map the employee to a building. The HRMS will take this over once it is connected.",label:E?"Save changes":"Add employee",
  body:F("Building","p",{opts:bldOpts(),val:E?e.premises_id:PREM})+(E?"":F("Employee code","c",{req:1,ph:"JT1010"}))+F("Full name","n",{req:1,val:v("name")})+F("Grade","g",{val:v("grade"),ph:"M2"})+F("Designation","d",{val:v("designation")})+F("Department","dp",{val:v("department")})
   +F("Email","e",{type:"email",val:v("email")})+F("Phone","ph",{val:v("phone")})+F("Status","s",{opts:Object.entries(ES).map(([k,x])=>[k,x[0]]),val:v("status")||"active"})+F("Joined on","j",{type:"date",val:v("join_date")}),
  onSave:async()=>{if(!val("n"))throw Error("Name is required.");if(!E&&!val("c"))throw Error("Employee code is required.");
   const b={premises_id:+val("p"),name:val("n"),grade:val("g"),designation:val("d"),department:val("dp"),email:val("e"),phone:val("ph"),status:val("s"),join_date:val("j")||null};
   if(E)await api(`/employees/${e.id}/update`,{body:b});else{b.emp_code=val("c");await api("/employees",{body:b})}toast(E?"Employee updated":"Employee added");route()}})}

/* ---------- HRMS lookup (HR -> Admin) ---------- */
function hrmsLookup(){
 drawer({title:"Find an employee in the HRMS",sub:"Search by name, username or employee code. Details come from HR.",label:"Done",
  body:`<label class="f">Search<input id="hq" placeholder="e.g. Kiran, JT1003" autocomplete="off"></label><button type="button" class="btn sm" id="hgo" style="margin-bottom:14px">${I("search")}Search HRMS</button><div id="hres"></div>`,
  onSave:async()=>{route()},
  onOpen:()=>{const go=async()=>{const q=$("#hq").value.trim(),el=$("#hres");if(q.length<2){el.innerHTML=`<p class="muted small">Type at least 2 characters.</p>`;return}
    el.innerHTML=`<div class="skel" style="width:60%"></div>`;
    try{const r=(await api("/hrms/search?q="+encodeURIComponent(q))).results;
     el.innerHTML=r.length?r.map((m,i)=>{const guess=buildings().find(p=>m.location&&p.name.toLowerCase().includes(m.location.toLowerCase()))||buildings().find(p=>p.id==PREM)||buildings()[0];
      return `<div class="row" style="align-items:flex-start;flex-wrap:wrap;gap:8px"><div class="grow"><b>${esc(m.name)}</b> ${GRADE(m.grade)}<div class="muted small">${esc(m.emp_code)} · ${esc(m.designation||"")} · ${esc(m.department||"")}${m.location?" · "+esc(m.location):""}</div><div class="muted small">${esc(m.email||"")}</div></div>
       <div style="display:grid;gap:6px;min-width:190px"><select data-b="${i}" style="height:32px">${bldOpts().map(([id,n])=>`<option value="${id}" ${id==guess?.id?"selected":""}>${esc(n)}</option>`).join("")}</select><button type="button" class="btn ${m.exists?"ghost":""} sm" data-i="${i}">${m.exists?"Refresh from HRMS":"Add to this portal"}</button></div></div>`}).join(""):`<p class="muted">No match in the HRMS.</p>`;
     $$("#hres [data-i]").forEach(b=>b.onclick=async()=>{try{const x=await api("/hrms/import",{body:{employee:r[b.dataset.i],premises_id:+$(`#hres [data-b="${b.dataset.i}"]`).value}});toast(x.action=="created"?"Employee added":"Employee refreshed");b.textContent="Done";b.disabled=true}catch(e){toast(e.message,false)}})}
    catch(e){el.innerHTML=`<p class="ferr">${esc(e.message)}</p><p class="muted small">You can still add the employee manually.</p>`}};
   $("#hgo").onclick=go;$("#hq").onkeydown=e=>{if(e.key=="Enter"){e.preventDefault();go()}}}})}

/* ======================= EMPLOYEES ======================= */
P2.employees=async function(){
 const [all0,gh]=await Promise.all([api("/employees"),api("/guesthouses")]);await loadRef();
 const all=all0.filter(x=>inPrem(x.premises_id));crumbs([["People"],["Employees"]]);refPanel();
 const bl=buildings().filter(b=>inPrem(b.id)),cnt=(b,st)=>all.filter(e=>e.premises_id==b.id&&(Array.isArray(st)?st.includes(e.status):e.status==st)).length;
 const bcols=[{h:"Building",f:r=>`<div class="primary">${esc(r.name)}</div><div class="sec">${esc(cName(r.company_id))}</div>`},{h:"Active",cls:"num right",f:r=>cnt(r,"active")},{h:"On leave",cls:"num right",f:r=>cnt(r,"on_leave")},{h:"Notice",cls:"num right",f:r=>cnt(r,"notice")},{h:"Exited",cls:"num right",f:r=>cnt(r,["resigned","inactive"])},
  {h:"Total",cls:"num right",f:r=>`<b>${all.filter(e=>e.premises_id==r.id).length}</b>`},{h:"Guest house beds",cls:"right",f:r=>{const g=gh.filter(x=>x.parent_id==r.id);const o=g.reduce((a,x)=>a+x.occupied,0),b=g.reduce((a,x)=>a+(x.beds||0),0);return g.length?`${o} of ${b||"?"} used`:`<span class="muted">No guest house</span>`}}];
 const cols=[{h:"Employee",f:r=>`<div class="primary">${esc(r.name)}</div><div class="sec">${esc(r.emp_code)}${r.email?" · "+esc(r.email):""}</div>`,t:r=>r.emp_code+" "+r.name},{h:"Building",f:r=>esc(premName(r.premises_id)),t:r=>premName(r.premises_id)},
  {h:"Role",f:r=>`<div>${esc(r.designation||"–")}</div><div class="sec">${esc(r.department||"")}</div>`,t:r=>`${r.designation||""} ${r.department||""}`},{h:"Grade",f:r=>GRADE(r.grade),t:r=>r.grade},{h:"Status",f:r=>sc(ES,r.status),t:r=>ES[r.status]?.[0]},
  {h:"Guest house",f:r=>r.guest_house?`<a href="#/guesthouses/${r.guest_house_id}">${esc(r.guest_house)}</a>`:`<span class="muted">–</span>`,t:r=>r.guest_house},{h:"Source",f:r=>r.source=="hrms"?chip("HRMS","gold"):chip(r.source=="import"?"Imported":"Manual",""),t:r=>r.source},
  {h:"",cls:"right",f:r=>can("employees.write")?`<button class="btn sm ghost" data-e="${r.id}">Edit</button>`:""}];
 const o={tabs:[["act","Active",r=>r.status=="active"],["lv","On leave",r=>r.status=="on_leave"],["nt","Notice period",r=>r.status=="notice"],["ex","Exited",r=>["resigned","inactive"].includes(r.status)],["gh","In guest house",r=>!!r.guest_house],["all","All",()=>true]],
  q:r=>`${r.emp_code} ${r.name} ${r.email} ${r.grade} ${r.designation} ${r.department} ${premName(r.premises_id)}`,csv:"employees",ph:"Search name, code, grade",empty:"No employees yet",emptySub:can("onboarding")?"Import them in bulk from Onboarding, add one, or find them in the HRMS.":"Add an employee or find one in the HRMS.",
  click:r=>refPanel({title:r.name,kind:"Employee · "+r.emp_code,entity:"employee",id:r.id,kv:[["Building",esc(premName(r.premises_id))],["Grade",GRADE(r.grade)],["Status",sc(ES,r.status)],["Department",esc(r.department||"–")],["Guest house",esc(r.guest_house||"–")],["Source",esc(r.source)]]})};
 $("#main").innerHTML=`<div class="page">${head("Employees",`${all.length} employees mapped to buildings · ${esc(premScope())}`,(can("employees.write")?bulkBtns("employees")+`<button class="btn ghost" id="hl">${I("search")}Find in HRMS</button><button class="btn" id="ae">${I("plus")}Add employee</button>`:""))}
  <div style="margin-bottom:16px">${table("t_bh",bcols,bl,{noBar:true,empty:"No buildings"}).replace('<div class="tbar"></div>',subHead("Headcount by building",`<span class="muted small">Status of employees mapped to each building</span>`))}</div>${table("t_em",cols,all,o)}</div>`;
 wire("t_bh",bl,[],{});wire("t_em",all,cols,o);
 $("#ae")&&($("#ae").onclick=()=>employeeForm());$("#hl")&&($("#hl").onclick=hrmsLookup);
 $$("[data-e]").forEach(b=>b.onclick=ev=>{ev.stopPropagation();employeeForm(all.find(x=>x.id==b.dataset.e))})};

/* ======================= GUEST HOUSES ======================= */
const mapUrl=h=>h.maps_url||(h.lat!=null&&h.lng!=null?`https://www.google.com/maps?q=${h.lat},${h.lng}`:h.address?`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(h.address)}`:"");
const bedBar=(occ,beds,big)=>{const n=beds||0;if(!n)return `<div class="bedbar none ${big?"big":""}"><span>Capacity not set</span></div>`;return `<div class="bedbar ${big?"big":""}" title="${occ} of ${n} beds occupied">${Array.from({length:Math.max(n,occ)},(_,i)=>`<i class="${i<occ?(i>=n?"over":"on"):""}"></i>`).join("")}</div>`};
const featChips=f=>(Array.isArray(f)?f:String(f||"").split(",")).map(x=>x.trim()).filter(Boolean).map(x=>`<span class="ft">${esc(x)}</span>`).join("");
const spaces=h=>[[h.floors,"floor"],[h.bedrooms,"bedroom"],[h.halls,"hall"],[h.balconies,"balcony","balconies"],[h.kitchens,"kitchen"]].filter(x=>x[0]).map(([n,w,pl])=>`<span class="ft">${n} ${n==1?w:(pl||w+"s")}</span>`).join("");

function addGuestHouse(){drawer({title:"Add guest house",sub:"Create it under a building, then add its rooms and details on the next screen.",label:"Create",
 body:F("Building","p",{opts:bldOpts(),val:PREM})+F("Guest house name","n",{req:1,ph:"Kilimani Guest House"})+F("Address","a"),
 onSave:async()=>{if(!val("n"))throw Error("Name is required.");const p=await api("/premises",{body:{parent_id:+val("p"),name:val("n"),type:"guest_house",address:val("a")}});toast("Guest house created. Add its rooms now.");await loadRef();location.hash="#/guesthouses/"+p.id}})}

P2.guesthouses=async function(){
 const g=(await api("/guesthouses")).filter(x=>inPrem(x.id));await loadRef();crumbs([["Administration"],["Guest houses"]]);refPanel();
 const beds=g.reduce((a,x)=>a+(x.beds||0),0),occ=g.reduce((a,x)=>a+x.occupied,0),att=g.reduce((a,x)=>a+x.assets_attention,0);
 const card=h=>{const free=h.beds!=null?h.beds-h.occupied:null;return `<div class="panel ghc" data-id="${h.id}" data-q="${esc((h.name+" "+premName(h.parent_id)+" "+(h.address||"")+" "+(h.location||"")).toLowerCase())}">
  <div class="top"><div class="big">${I("building")}</div><div style="min-width:0"><h3>${esc(h.name)}</h3><div class="muted small">${esc(premName(h.parent_id))} · ${esc(cName(h.company_id))}</div></div></div>
  <div class="ghaddr">${esc(h.address||"No address recorded")}${h.location?`<div class="muted small">${esc(h.location)}</div>`:""}${mapUrl(h)?`<a href="${esc(mapUrl(h))}" target="_blank" rel="noopener" class="small">${I("route")} Open in Google Maps</a>`:""}</div>
  <div class="fts">${spaces(h)||`<span class="muted small">Add rooms and details</span>`}</div>
  <div class="occ"><div class="occh"><b>${h.occupied}</b><span class="muted"> of ${h.beds??"?"} beds occupied</span><span class="sp"></span>${free==null?chip("Capacity not set","warn"):free<=0?chip("Full","bad"):chip(free+" free","ok")}</div>${bedBar(h.occupied,h.beds)}</div>
  <div class="ghfoot"><span class="muted small">${I("box")} ${h.assets} asset${h.assets==1?"":"s"}</span>${h.assets_attention?chip(h.assets_attention+" need attention","warn"):h.assets?chip("Assets OK","ok"):""}<span class="sp"></span>${can("premises.write")?`<button class="btn sm ghost" data-ed="${h.id}">Edit</button>`:""}<a class="btn sm" href="#/guesthouses/${h.id}">Open</a></div></div>`};
 $("#main").innerHTML=`<div class="page">${head("Guest houses",`Each guest house sits under a building · ${esc(premScope())}`,can("premises.write")?`<button class="btn" id="agh">${I("plus")}Add guest house</button>`:"")}
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">${I("building")}Guest houses</div><div class="v">${g.length}</div></div><div class="kpi"><div class="k">Beds</div><div class="v">${beds}</div></div><div class="kpi"><div class="k">Occupied</div><div class="v">${occ}</div><div class="s">${beds-occ} free</div></div><div class="kpi ${att?"warn":""}"><div class="k">${I("box")}Assets needing attention</div><div class="v">${att}</div></div></div>
  <div class="tbar" style="margin-bottom:12px;padding:0"><div class="search">${I("search")}<input id="ghq" placeholder="Search guest house, building, area…" autocomplete="off"></div><span class="sp"></span><span class="muted small" id="ghn"></span></div>
  <div class="ghgrid" id="ghgrid">${g.map(card).join("")||emptyState("No guest houses yet","Add one under a building.","building")}</div></div>`;
 const apply=()=>{const q=$("#ghq").value.toLowerCase().trim();let n=0;$$(".ghc").forEach(c=>{const ok=!q||c.dataset.q.includes(q);c.classList.toggle("hidden",!ok);ok&&n++});$("#ghn").textContent=g.length?`Showing ${n} of ${g.length}`:""};
 $("#ghq").oninput=apply;apply();
 $$(".ghc").forEach(c=>c.onclick=e=>{if(e.target.closest("a,button"))return;location.hash="#/guesthouses/"+c.dataset.id});
 $$("[data-ed]").forEach(b=>b.onclick=()=>location.hash="#/guesthouses/"+b.dataset.ed+"?edit=1");
 $("#agh")&&($("#agh").onclick=addGuestHouse)};

function ghDetailsForm(h,done){drawer({title:"Edit guest house details",sub:h.name,label:"Save details",
 body:F("Name","n",{val:h.name})+F("Address","a",{val:h.address})+F("Area / landmark","lo",{val:h.location,ph:"Kilimani, near The Arch Place"})+F("Google Maps link","mu",{val:h.maps_url,ph:"https://maps.app.goo.gl/…",hint:"Paste the share link from Google Maps. If empty, the pin below is used."})
  +`<div class="grid g2">${F("Latitude","la",{type:"number",step:"any",val:h.lat})}${F("Longitude","ln",{type:"number",step:"any",val:h.lng})}${F("Floors","fl",{type:"number",val:h.floors})}${F("Halls","ha",{type:"number",val:h.halls})}${F("Balconies","ba",{type:"number",val:h.balconies})}${F("Kitchens","ki",{type:"number",val:h.kitchens})}</div>`
  +F("Amenities","am",{rows:2,val:h.amenities,hint:"Comma separated: WiFi, Parking, Generator backup…"})+F("Contact person","cn",{val:h.contact_name})+F("Contact phone","cp",{val:h.contact_phone})+F("Notes","no",{rows:2,val:h.notes}),
 onOpen:()=>{if(h.amenities)$("#f_am").value=h.amenities;if(h.notes)$("#f_no").value=h.notes},
 onSave:async()=>{await api(`/guesthouses/${h.id}/profile`,{body:{name:val("n"),address:val("a"),location:val("lo"),maps_url:val("mu"),lat:val("la"),lng:val("ln"),floors:val("fl"),halls:val("ha"),balconies:val("ba"),kitchens:val("ki"),amenities:val("am"),contact_name:val("cn"),contact_phone:val("cp"),notes:val("no")}});toast("Details saved");await loadRef();done()}})}

function roomForm(h,r,done){const E=!!r;drawer({title:E?`Edit ${r.name}`:"Add room",sub:h.name,label:E?"Save room":"Add room",
 body:F("Room name","n",{req:1,val:r?.name,ph:"Room 1"})+F("Floor","f",{val:r?.floor,ph:"1"})+F("Beds in this room","b",{type:"number",val:r?.beds||2,hint:"A twin room has 2. Occupancy is shown per bed."})+F("Features","ft",{val:(r?.features||[]).join(", "),ph:"AC, Attached bathroom, Balcony",hint:"Comma separated."})+F("Notes","no",{rows:2})
  +(E?`<button type="button" class="btn ghost sm" id="rdel" style="color:var(--bad)">Delete this room</button>`:""),
 onOpen:()=>{if(r?.notes)$("#f_no").value=r.notes;$("#rdel")&&($("#rdel").onclick=async()=>{if(!confirm(`Delete ${r.name}? This cannot be undone.`))return;try{await api(`/rooms/${r.id}/delete`,{method:"POST"});toast("Room deleted");closeDrawer();done()}catch(e){$("#ferr").textContent=e.message}})},
 onSave:async()=>{if(!val("n"))throw Error("Room name is required.");await api(`/guesthouses/${h.id}/rooms`,{body:{id:r?.id,name:val("n"),floor:val("f"),beds:val("b"),features:val("ft"),notes:val("no")}});toast(E?"Room saved":"Room added");done()}})}

P2.guesthouse=async function(id){
 const q=new URLSearchParams((location.hash.split("?")[1]||""));
 const d=await api("/guesthouses/"+id),h=d.guesthouse,cur=d.allocations.filter(a=>a.status=="allocated"),past=d.allocations.filter(a=>a.status!="allocated");
 crumbs([["Administration"],["Guest houses","guesthouses"],[h.name]]);addRecent(h.name,"guesthouses/"+id,"building");
 refPanel({title:h.name,kind:"Guest house",entity:"premises",id,kv:[["Building",esc(premName(h.parent_id))],["Beds",`${h.occupied} of ${h.beds??"?"} occupied`],["Rooms",h.bedrooms||"–"],["Assets",h.assets]]});
 const free=h.beds!=null?h.beds-h.occupied:null,ending=cur.filter(a=>a.to_date&&dayN(a.to_date)<=3).length,done=()=>route();
 const toChip=a=>!a.to_date?`<span class="muted">Open stay</span>`:dayN(a.to_date)<0?chip(`Ended ${-dayN(a.to_date)}d ago`,"bad")+`<div class="sec">${fmtD(a.to_date)}</div>`:dayN(a.to_date)<=3?chip(`Ends in ${dayN(a.to_date)}d`,"warn")+`<div class="sec">${fmtD(a.to_date)}</div>`:fmtD(a.to_date);
 const rcard=r=>{const n=r.occupants.length;return `<div class="room ${n>=r.beds?"full":n?"part":""}"><div class="rt"><b>${esc(r.name)}</b><span class="muted small">${r.floor?"Floor "+esc(r.floor):""}</span><span class="sp"></span>${n>=r.beds?chip("Full","bad"):n?chip(`${r.beds-n} bed${r.beds-n>1?"s":""} free`,"warn"):chip("Vacant","ok")}</div>
   ${bedBar(n,r.beds,true)}<div class="muted small" style="margin:4px 0 6px">${n} of ${r.beds} bed${r.beds>1?"s":""} occupied</div><div class="fts" style="margin:0 0 6px">${featChips(r.features)}</div>
   ${r.occupants.map(o=>`<div class="occp"><span class="dot-g"></span><div><b>${esc(o.name)}</b> ${GRADE(o.grade)}<div class="muted small">${esc(o.designation||"")}${o.to_date?" · until "+fmtD(o.to_date):""}</div></div>${d.can_allocate?`<button class="btn sm ghost" data-v="${o.id}">Vacate</button>`:""}</div>`).join("")}
   <div class="racts">${d.can_allocate&&n<r.beds?`<button class="btn sm" data-al="${r.id}">${I("plus")}Allocate</button>`:""}${d.can_edit?`<button class="btn sm ghost" data-re="${r.id}">Edit room</button>`:""}</div></div>`};
 const cats={};d.assets.forEach(a=>cats[a.category]=(cats[a.category]||0)+1);
 const acols=[{h:"Asset",f:r=>`<div class="primary">${esc(r.name)}</div><div class="sec">${esc(r.asset_tag)}${r.location?" · "+esc(r.location):""}</div>`},{h:"Category",f:r=>esc(catL(r.category))},{h:"Condition",f:r=>sc(CS,r.condition)},{h:"Next service",f:r=>svcChip(r)},{h:"Warranty",f:r=>warChip(r)},{h:"Status",f:r=>sc(AS,r.status)}];
 const cols=[{h:"Employee",f:r=>`<div class="primary">${esc(r.name)}</div><div class="sec">${esc(r.emp_code||"")}</div>`},{h:"Grade",f:r=>GRADE(r.grade)},{h:"Designation",f:r=>`<div>${esc(r.designation||"–")}</div><div class="sec">${esc(r.department||"")}</div>`},
  {h:"Building",f:r=>esc(premName(r.building_id))},{h:"Room",f:r=>esc(r.room||"–")},{h:"Purpose",f:r=>esc(r.purpose||"–")},{h:"From",f:r=>fmtD(r.from_date)},{h:"Until",f:r=>toChip(r)},
  {h:"",cls:"right",f:r=>(["resigned","inactive"].includes(r.emp_status)?chip("Employee exited","bad")+" ":"")+(d.can_allocate?`<button class="btn sm ghost" data-v="${r.id}">Vacate</button>`:"")}];
 const hcols=[{h:"Employee",f:r=>`<span class="primary">${esc(r.name)}</span> <span class="muted">${esc(r.emp_code||"")}</span>`},{h:"Grade",f:r=>GRADE(r.grade)},{h:"Room",f:r=>esc(r.room||"–")},{h:"Stayed",f:r=>`${fmtD(r.from_date)} to ${fmtD(r.vacated_on||r.to_date)}`}];
 const mu=mapUrl(h),emb=h.lat!=null&&h.lng!=null?`https://maps.google.com/maps?q=${h.lat},${h.lng}&z=15&output=embed`:"";
 $("#main").innerHTML=`<div class="page"><div class="rh"><div class="big">${I("building")}</div><div><h1>${esc(h.name)}</h1><p>Guest house of ${esc(premName(h.parent_id))} · ${esc(cName(h.company_id))}</p></div><div>${can("premises.occupancy")?`<select id="gocc" title="HR and Admin can change this" style="height:32px"><option value="occupied">Occupied</option><option value="partial">Partly occupied</option><option value="vacant">Vacant</option></select>`:(h.occupancy?chip(...OC[h.occupancy]):"")}</div>
  <div class="acts">${can("tickets.raise")?`<button class="btn ghost" id="gt">${I("ticket")}Raise ticket</button>`:""}${d.can_edit?`<button class="btn ghost" id="ged">Edit details</button><button class="btn ghost" id="gr">${I("plus")}Add room</button>`:""}</div></div>
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">Bedrooms</div><div class="v">${h.bedrooms||"–"}</div><div class="s">${spaces({...h,bedrooms:0})||"Add details"}</div></div><div class="kpi"><div class="k">Beds occupied</div><div class="v">${h.occupied}<span style="font-size:15px;color:var(--ink2)"> / ${h.beds??"?"}</span></div><div class="s">${bedBar(h.occupied,h.beds)}</div></div>
   <div class="kpi ${free!=null&&free<=0?"bad":""}"><div class="k">Beds free</div><div class="v">${free??"–"}</div><div class="s">${ending?ending+" stay(s) ending within 3 days":"&nbsp;"}</div></div><div class="kpi ${h.assets_attention?"warn":""}"><div class="k">${I("box")}Assets</div><div class="v">${h.assets}</div><div class="s">${h.assets_attention?h.assets_attention+" need attention":"All in order"}</div></div></div>
  <div class="grid g2-1" style="margin-bottom:16px"><div class="panel"><div class="hd"><h2>Rooms &amp; occupancy</h2><div class="acts"><span class="muted small">Each segment is one bed. Green = occupied.</span></div></div><div class="bd">${d.rooms.length?`<div class="roomgrid">${d.rooms.map(rcard).join("")}</div>`:emptyState("No rooms added yet",d.can_edit?"Use Add room to define bedrooms and beds.":"","building")}
    ${d.unplaced.length?`<p class="muted small" style="margin:12px 0 0">${d.unplaced.length} resident(s) are not placed in a room: ${d.unplaced.map(x=>esc(x.name)).join(", ")}.</p>`:""}</div></div>
   <div style="display:grid;gap:16px;align-content:start"><div class="panel"><div class="hd"><h2>Property details</h2></div><div class="bd"><dl class="dl"><dt>Address</dt><dd>${esc(h.address||"–")}</dd><dt>Area</dt><dd>${esc(h.location||"–")}</dd><dt>Floors</dt><dd>${h.floors??"–"}</dd><dt>Halls</dt><dd>${h.halls??"–"}</dd><dt>Balconies</dt><dd>${h.balconies??"–"}</dd><dt>Kitchens</dt><dd>${h.kitchens??"–"}</dd><dt>Contact</dt><dd>${esc(h.contact_name||"–")}${h.contact_phone?`<div class="sec">${esc(h.contact_phone)}</div>`:""}</dd></dl>
     ${h.amenities?`<div class="fts" style="margin-top:10px">${featChips(h.amenities)}</div>`:""}${h.notes?`<p class="muted small" style="margin:10px 0 0">${esc(h.notes)}</p>`:""}${mu?`<p style="margin:12px 0 0"><a class="btn sm ghost" href="${esc(mu)}" target="_blank" rel="noopener">${I("route")}Open in Google Maps</a></p>`:""}</div></div>
    ${emb?`<div class="panel" style="overflow:hidden"><iframe title="Map" src="${emb}" loading="lazy" referrerpolicy="no-referrer" style="border:0;width:100%;height:210px;display:block"></iframe></div>`:""}</div></div>
  <div class="panel" style="margin-bottom:16px"><div class="hd"><h2>Assets in this guest house</h2><div class="acts">${can("assets.write")?`<button class="btn sm" id="gaa">${I("plus")}Add asset</button>`:""}<a class="btn sm ghost" href="#/assets">Asset register</a></div></div>
   <div class="bd" style="padding-bottom:0"><div class="fts">${chip(h.assets+" total","gold")}${h.assets_attention?chip(h.assets_attention+" need attention","warn"):chip("All in order","ok")}${Object.entries(cats).map(([k,n])=>`<span class="ft">${esc(catL(k))} · ${n}</span>`).join("")}</div></div>
   ${d.assets.length?`<div class="tscroll"><table class="dt"><thead><tr>${acols.map(c=>`<th>${c.h}</th>`).join("")}</tr></thead><tbody>${d.assets.map(r=>`<tr class="click" data-a="${r.id}">${acols.map(c=>`<td>${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:emptyState("No assets mapped yet","Add assets here or by bulk upload, choosing this guest house as the premises.","box")}</div>
  ${can("utilities.read")?`<div class="panel" id="gutil" style="margin-bottom:16px"></div>`:""}
  <div style="display:grid;gap:16px">${table("t_cur",cols,cur,{noBar:true,empty:"Nobody is allocated"}).replace('<div class="tbar"></div>',subHead("Current residents","<span class='muted small'>With grade and stay dates</span>"))}
  ${past.length?table("t_past",hcols,past,{noBar:true}).replace('<div class="tbar"></div>',subHead("Previous stays")):""}</div></div>`;
 wire("t_cur",cur,[],{});past.length&&wire("t_past",past,[],{});
 $$("[data-v]").forEach(b=>b.onclick=async()=>{try{await api(`/allocations/${b.dataset.v}/vacate`,{method:"POST"});toast("Bed vacated");route()}catch(e){toast(e.message,false)}});
 $$("tr[data-a]").forEach(tr=>tr.onclick=()=>location.hash="#/assets/"+tr.dataset.a);
 $("#gt")&&($("#gt").onclick=()=>raiseTicket({premises_id:id}));$("#ged")&&($("#ged").onclick=()=>ghDetailsForm(h,done));$("#gr")&&($("#gr").onclick=()=>roomForm(h,null,done));
 $("#gaa")&&($("#gaa").onclick=()=>assetForm(null,id));
 can("utilities.read")&&utilitiesPanel("#gutil",id,{exact:true,title:"Utilities"});
 if($("#gocc")){$("#gocc").value=h.occupancy||"occupied";$("#gocc").onchange=async e=>{try{await api(`/premises/${id}/occupancy`,{body:{status:e.target.value}});toast("Occupancy updated")}catch(x){toast(x.message,false)}}}
 $$("[data-re]").forEach(b=>b.onclick=()=>roomForm(h,d.rooms.find(x=>x.id==b.dataset.re),done));
 const alloc=async roomId=>{const emps=(await api("/employees")).filter(e=>e.company_id==h.company_id&&!e.guest_house_id&&["active","on_leave","notice"].includes(e.status)).sort((a,b)=>(b.premises_id==h.parent_id)-(a.premises_id==h.parent_id)||a.name.localeCompare(b.name));
  const open=d.rooms.filter(r=>r.free>0);
  drawer({title:"Allocate to "+h.name,sub:!d.rooms.length?"Add rooms first so beds can be shown per room.":`Employees of ${premName(h.parent_id)} are listed first.`,label:"Allocate",
   body:F("Room","r",{opts:[["","Select a room"],...open.map(r=>[r.id,`${r.name}${r.floor?" · floor "+r.floor:""} · ${r.free} of ${r.beds} bed${r.beds>1?"s":""} free`])],val:roomId||""})+F("Employee","e",{opts:[["","Select an employee"],...emps.map(e=>[e.id,`${e.name} · ${e.emp_code} · ${e.grade||"no grade"} · ${premName(e.premises_id)}`])]})+F("Purpose","p",{ph:"Training, relocation, visit…"})+F("From","f",{type:"date",val:new Date().toISOString().slice(0,10)})+F("Until","t",{type:"date",hint:"Leave empty for an open-ended stay."}),
   onSave:async()=>{if(!val("r"))throw Error("Select a room.");if(!val("e"))throw Error("Select an employee.");await api(`/guesthouses/${id}/allocate`,{body:{room_id:+val("r"),employee_id:+val("e"),purpose:val("p"),from_date:val("f"),to_date:val("t")||null}});toast("Allocated");route()}})};
 $$("[data-al]").forEach(b=>b.onclick=()=>alloc(+b.dataset.al));
 if(q.get("edit")&&d.can_edit){history.replaceState(null,"","#/guesthouses/"+id);ghDetailsForm(h,done)}};

/* ======================= TRAVEL ADVANCES ======================= */
P2.advances=async function(){
 const [a,emps]=await Promise.all([api("/travel-advances"),api("/employees")]);crumbs([["People"],["Travel advances"]]);refPanel();
 const cols=[{h:"Reference",f:r=>`<span class="primary">${r.ref}</span><div class="sec">${fmtDT(r.created_at)}</div>`,t:r=>r.ref},{h:"Employee",f:r=>`<div class="primary">${esc(r.employee_name||"Not in this portal")}</div><div class="sec">${esc(r.employee_code)}</div>`,t:r=>r.employee_code},
  {h:"Amount",cls:"num right",f:r=>`${esc(r.currency)} ${n0(r.amount)}`,t:r=>r.amount},{h:"Trip",f:r=>`<div>${esc(r.destination||"–")}</div><div class="sec">${esc(r.purpose||"")}${r.from_date?" · "+fmtD(r.from_date):""}</div>`,t:r=>r.destination},
  {h:"Raised by",f:r=>r.source=="claims"?chip("Claims system","gold"):`<div>${chip("Admin","")}</div><div class="sec">${esc(r.created_by||"")}</div>`,t:r=>r.source},
  {h:"HR status",f:r=>sc(AD,r.status)+(r.status=="pushed"?`<div class="sec">${esc(r.hrms_ref||"")}</div>`:r.error?`<div class="sec" style="color:var(--bad)">${esc(r.error)}</div>`:""),t:r=>r.status},
  {h:"",cls:"right",f:r=>r.status!="pushed"?`<button class="btn sm" data-r="${r.id}">Retry</button>`:""}];
 const o={tabs:[["all","All",()=>true],["wait","Needs attention",r=>r.status!="pushed"],["sent","Sent to HR",r=>r.status=="pushed"]],q:r=>`${r.ref} ${r.employee_code} ${r.employee_name} ${r.destination} ${r.claim_ref}`,csv:"travel-advances",ph:"Search advances",empty:"No travel advances yet",emptySub:"Advances raised by Admin or received from the Claims system appear here and go to HR."};
 const bad=a.filter(x=>x.status!="pushed").length;
 $("#main").innerHTML=`<div class="page">${head("Travel advances","Raised by Admin or received from Claims, then sent to HR in the HRMS",`<button class="btn" id="na">${I("plus")}Record advance</button>`)}
  <div class="grid g3" style="margin-bottom:16px"><div class="kpi"><div class="k">Sent to HR</div><div class="v">${a.length-bad}</div></div><div class="kpi ${bad?"bad":""}"><div class="k">Needs attention</div><div class="v">${bad}</div><div class="s">waiting or failed</div></div><div class="kpi"><div class="k">From Claims</div><div class="v">${a.filter(x=>x.source=="claims").length}</div></div></div>${table("t_ad",cols,a,o)}</div>`;
 wire("t_ad",a,cols,o);
 $$("[data-r]").forEach(b=>b.onclick=async()=>{b.disabled=true;try{const x=await api(`/travel-advances/${b.dataset.r}/retry`,{method:"POST"});toast(x.status=="pushed"?"Sent to HR":"Still failing: "+x.error,x.status=="pushed")}catch(e){toast(e.message,false)}route()});
 $("#na").onclick=()=>drawer({title:"Record a travel advance",sub:"It is sent to HR in the HRMS when you save. If HR cannot be reached it is kept here to retry.",label:"Save & send to HR",
  body:F("Employee","e",{opts:[["","Select an employee"],...emps.map(e=>[e.emp_code,`${e.name} · ${e.emp_code}`])]})+F("Amount","a",{type:"number",step:"0.01"})+F("Currency","c",{val:"INR",hint:"INR, KES…"})+F("Destination","d")+F("Purpose","p")+F("Travel from","f",{type:"date"})+F("Travel to","t",{type:"date"}),
  onOpen:()=>$("#f_e").onchange=e=>{const em=emps.find(x=>x.emp_code==e.target.value),c=em&&COMP.find(x=>x.id==em.company_id);if(c)$("#f_c").value=c.currency},
  onSave:async()=>{if(!val("e")||!val("a"))throw Error("Choose an employee and enter the amount.");const x=await api("/travel-advances",{body:{employee_code:val("e"),amount:val("a"),currency:val("c"),destination:val("d"),purpose:val("p"),from_date:val("f")||null,to_date:val("t")||null}});toast(x.status=="pushed"?"Sent to HR":"Saved, but HR could not be reached",x.status=="pushed");route()}})};

/* ======================= HRMS INTEGRATION (System admin) ======================= */
const stChip=s=>chip(...(HS[s]||[s,""]));
P2.integrations=async function(){
 const [c,log,sm]=await Promise.all([api("/hrms/config"),api("/hrms/log"),api("/summary")]);crumbs([["Administration"],["HRMS integration"]]);refPanel();const h=sm.hrms||{};
 const LC={pull:"HR → Admin",push:"Admin → HR"};
 const lcols=[{h:"When",cls:"nowrap",f:r=>fmtDT(r.at)},{h:"Flow",f:r=>chip(LC[r.direction]||r.direction,"gold")},{h:"Operation",f:r=>`<span style="text-transform:capitalize">${esc(r.operation.replace(/_/g," "))}</span>`},{h:"Result",f:r=>chip(r.status=="ok"?"OK":"Error",r.status=="ok"?"ok":"bad")},
  {h:"HTTP",cls:"num right",f:r=>r.http_status??"–"},{h:"Time",cls:"num right",f:r=>r.ms!=null?r.ms+" ms":"–"},{h:"Detail",f:r=>`<span class="small">${esc(r.message||"")}${r.ref?` <span class="muted">${esc(r.ref)}</span>`:""}</span>`},{h:"By",f:r=>esc(r.user_name||"")}];
 $("#main").innerHTML=`<div class="page">${head("HRMS integration","Connect the portal to your HR system. The URL and credentials are set here, and all calls are made by the server.",`<button class="btn ghost" id="ht">${I("check")}Test connection</button>`)}
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi ${h.state=="error"?"bad":h.state=="ok"?"":"warn"}"><div class="k">${I("shield")}Status</div><div class="v" style="font-size:20px;margin:6px 0">${stChip(h.state)}</div><div class="s">${c.last_checked?"Checked "+fmtDT(c.last_checked):"Never tested"}</div></div>
   <div class="kpi"><div class="k">Calls · 24 h</div><div class="v">${(h.ok_24h||0)+(h.failed_24h||0)}</div><div class="s">${h.ok_24h||0} ok · ${h.failed_24h||0} failed</div></div><div class="kpi ${h.advances_waiting?"warn":""}"><div class="k">Advances waiting</div><div class="v">${h.advances_waiting||0}</div><div class="s">not yet in the HRMS</div></div><div class="kpi"><div class="k">Last success</div><div class="v" style="font-size:18px">${h.last_ok?fmtDT(h.last_ok):"–"}</div></div></div>
  ${c.last_error&&h.state=="error"?`<div class="panel" style="border-color:var(--bad);margin-bottom:16px"><div class="bd" style="color:var(--bad)">${I("alert")} ${esc(c.last_error)}</div></div>`:""}
  <div class="grid g2-1" style="margin-bottom:16px"><div class="panel"><div class="hd"><h2>Connection settings</h2></div><div class="bd">
   ${F("Integration","en",{opts:[["1","Switched on"],["","Switched off"]],val:c.enabled?"1":""})}${F("Base URL","u",{val:c.base_url,ph:"https://hrms.example.com/api/v1",hint:"The server calls this address. It must be reachable from the server, not just your browser."})}
   ${F("Authentication","at",{opts:[["api_key","API key in a header"],["bearer","Bearer token"],["basic","Username and password"]],val:c.auth_type})}<div id="ah">${F("Header name","ah",{val:c.auth_header,ph:"X-API-Key"})}</div><div id="au">${F("Username","un",{val:c.username})}</div>
   ${F("Key / token / password","sc",{type:"password",ph:c.secret_set?"Saved. Leave empty to keep it.":"Paste the credential",hint:"Stored encrypted. It is never shown again."})}
   <div class="grid g2">${F("Employee search path","sp",{val:c.search_path})}${F("Search query parameter","spp",{val:c.search_param,hint:"Gets the name, username or code"})}${F("Travel advance path","tp",{val:c.travel_path})}${F("Health check path","hp",{val:c.health_path})}</div>
   ${F("Timeout (seconds)","to",{type:"number",val:c.timeout_s})}${F("Field mapping (JSON)","fm",{rows:9,hint:"Left: our field. Right: the field name in the HRMS response."})}
   <p class="ferr" id="cerr"></p><button class="btn" id="hs">Save settings</button></div></div>
   <div style="display:grid;gap:16px;align-content:start"><div class="panel"><div class="hd"><h2>What flows where</h2></div><div class="bd">
    <div class="row"><div class="grow"><b>Employee lookup</b><div class="muted small">HR → Admin. HR, Admin and Maintenance staff search the HRMS by name, username or code, and add the person to a building here.</div></div></div>
    <div class="row"><div class="grow"><b>Travel advance</b><div class="muted small">Claims and Admin → HR. Each advance is recorded here, sent to the HRMS, and retried if HR was unreachable.</div></div></div>
    <div class="row"><div class="grow"><b>Employee master sync</b><div class="muted small">Planned. Until then, employees and grades are added manually or by CSV.</div></div></div></div></div>
   <div class="panel"><div class="hd"><h2>For the Claims system</h2></div><div class="bd"><p class="muted small" style="margin:0 0 6px">Claims posts advances here with the integration API key:</p><code>POST /api/integration/travel-advances</code><p class="muted small" style="margin:8px 0 0">Body: <code>{"items":[{"employee_code","amount","currency","purpose","destination","from_date","to_date","claim_ref"}]}</code></p></div></div></div></div>
  ${table("t_lg",lcols,log,{noBar:true,empty:"No calls yet",emptySub:"Test the connection to see the first entry."}).replace('<div class="tbar"></div>',subHead("Activity log","<span class='muted small'>Latest 60 calls. Credentials and payloads are never logged.</span>"))}</div>`;
 wire("t_lg",log,[],{});$("#f_fm").value=c.field_map||"";
 const tg=()=>{$("#ah").style.display=val("at")=="api_key"?"":"none";$("#au").style.display=val("at")=="basic"?"":"none"};tg();$("#f_at").onchange=tg;
 $("#ht").onclick=async()=>{const b=$("#ht");b.disabled=true;try{const r=await api("/hrms/test",{method:"POST"});toast(r.message,r.ok)}catch(e){toast(e.message,false)}route()};
 $("#hs").onclick=async()=>{$("#cerr").textContent="";try{await api("/hrms/config",{method:"PUT",body:{enabled:!!val("en"),base_url:val("u"),auth_type:val("at"),auth_header:val("ah"),username:val("un"),secret:val("sc"),search_path:val("sp"),search_param:val("spp"),travel_path:val("tp"),health_path:val("hp"),timeout_s:+val("to")||10,field_map:val("fm")}});toast("Settings saved. Use Test connection to check them.");route()}catch(e){$("#cerr").textContent=e.message}}};

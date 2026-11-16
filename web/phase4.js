"use strict";
/* Phase 4 pages: Premises (cards, hierarchy, detail), document vault, Utilities. Registered by app.js. */
const P4={};
const DS={expired:["Expired","bad"],d7:["Due in 7 days","bad"],d30:["Due in 30 days","warn"],d90:["Due in 90 days","gold"],ok:["Valid","ok"]};
const BS={paid:["Paid","ok"],overdue:["Overdue","bad"],due_soon:["Due soon","warn"],due:["Due","gold"]};
const UL={electricity:"Electricity",water:"Water",internet:"Internet",gas:"Gas",telephone:"Telephone",waste:"Waste",other:"Other"};
const DTL={lease:"Lease / rental agreement",purchase_deed:"Purchase document (deed)",govt_registration:"Government registration",tax:"Tax",insurance:"Insurance",occupancy_certificate:"Occupancy certificate",fire_noc:"Fire safety certificate",floor_plan:"Floor plan / approvals",litigation:"Legal / litigation",other:"Other"};
const OC={occupied:["Occupied","ok"],partial:["Partly occupied","warn"],vacant:["Vacant",""]};
const TYL={office:"Office",guest_house:"Guest house",branch:"Branch",hospital:"Hospital office"};
const sqft=n=>n?Number(n).toLocaleString()+" sq ft":"–";
const curOf=pid=>COMP.find(c=>c.id==pById(pid)?.company_id)?.currency||"INR";
const money=(n,c)=>n==null?"–":`${c||""} ${Number(n).toLocaleString(undefined,{maximumFractionDigits:0})}`.trim();
const mapOf=(p,m)=>(m&&m.maps_url)||(p.lat!=null&&p.lng!=null?`https://www.google.com/maps?q=${p.lat},${p.lng}`:p.address?`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.address)}`:"");
const mapEmbed=p=>p.lat!=null&&p.lng!=null?`<div class="panel" style="overflow:hidden"><iframe title="Map" src="https://maps.google.com/maps?q=${p.lat},${p.lng}&z=15&output=embed" loading="lazy" referrerpolicy="no-referrer" style="border:0;width:100%;height:220px;display:block"></iframe></div>`:"";
const ZERO={employees:0,guest_houses:0,open_tickets:0,litigation:0,doc_alerts:0,assets_attention:0,vehicles:0,area_sqft:0};

/* ======================= PREMISES: cards + hierarchy ======================= */
P4.premises=async function(){
 await loadRef();const sm=await api("/premises/summary");const S=Object.fromEntries(sm.map(x=>[x.id,x]));crumbs([["Administration"],["Premises"]]);refPanel();
 let mode=localStorage.bms_pmode||"cards";
 const base=id=>({...ZERO,...Object.fromEntries(Object.entries(S[id]||{}).filter(([k])=>k in ZERO).map(([k,v])=>[k,v||0]))});
 const memo={},roll=id=>{if(memo[id])return memo[id];const o=base(id);PL.filter(k=>k.parent_id==id).forEach(k=>{const r=roll(k.id);for(const key in ZERO)o[key]+=r[key]});return memo[id]=o};
 const bl=PL.filter(p=>p.type!="guest_house");
 const card=p=>{const s=S[p.id]||{},tot=roll(p.id);return `<div class="panel ghc" data-id="${p.id}"><div class="top"><div class="big">${I("building")}</div><div style="min-width:0"><h3>${esc(p.name)}</h3><div class="muted small">${esc(cName(p.company_id))} · ${esc(TYL[p.type]||p.type)}</div></div></div>
  <div class="ghaddr">${esc(p.address||"No address recorded")}</div><div class="fts">${s.occupancy?chip(...OC[s.occupancy]):""}${s.area_sqft?`<span class="ft">${sqft(s.area_sqft)}</span>`:""}${s.doc_alerts?chip(s.doc_alerts+" document alert"+(s.doc_alerts>1?"s":""),"warn"):""}</div>
  <div class="pstats"><div><b>${s.employees||0}</b><span>Employees${s.declared_headcount?` / ${s.declared_headcount}`:""}</span></div><div><b>${s.guest_houses||0}</b><span>Guest houses</span></div><div><b>${tot.open_tickets}</b><span>Open issues</span></div><div><b>${s.litigation||0}</b><span>Litigation</span></div></div>
  <div class="ghfoot"><span class="sp"></span><a class="btn sm" href="#/premises/${p.id}">Open</a></div></div>`};
 const num=(n,cls="")=>n?`<b class="${cls}">${n.toLocaleString()}</b>`:`<span class="muted">0</span>`;
 const trow=(label,sub,o,lvl,id,leaf)=>`<div class="trow ${leaf?"leaf":""}"><div class="tname" style="padding-left:${lvl*22+(leaf?18:0)}px">${id?`<a href="#/${PL.find(x=>x.id==id)?.type=="guest_house"?"guesthouses":"premises"}/${id}"><b>${esc(label)}</b></a>`:`<b>${esc(label)}</b>`}<div class="muted small">${esc(sub||"")}</div></div>
   <div>${o.occ?chip(...OC[o.occ]):""}</div><div class="r">${o.area?Number(o.area).toLocaleString():"–"}</div><div class="r">${num(o.employees)}</div><div class="r">${num(o.guest_houses)}</div><div class="r">${num(o.open_tickets,o.open_tickets?"warn":"")}</div><div class="r">${num(o.litigation)}</div><div class="r">${num(o.doc_alerts,o.doc_alerts?"warn":"")}</div></div>`;
 const node=(p,lvl)=>{const k=PL.filter(x=>x.parent_id==p.id),o={...roll(p.id),occ:S[p.id]?.occupancy,area:roll(p.id).area_sqft},own=base(p.id);
  const row=trow(p.name,`${TYL[p.type]||p.type}${k.length?` · own: ${own.employees} emp, ${own.open_tickets} issues`:""}`,{...(k.length?o:{...own,occ:S[p.id]?.occupancy,area:own.area_sqft})},lvl,p.id,!k.length);
  return k.length?`<details open><summary>${row}</summary>${k.map(x=>node(x,lvl+1)).join("")}</details>`:row};
 const tree=()=>{const roots=PL.filter(p=>!p.parent_id||!pById(p.parent_id)),byC={};roots.forEach(r=>(byC[r.company_id]=byC[r.company_id]||[]).push(r));
  const comp=Object.entries(byC).map(([cid,rs])=>{const o=rs.reduce((a,r)=>{const x=roll(r.id);for(const k in ZERO)a[k]+=x[k];return a},{...ZERO});return `<details open><summary>${trow(cName(+cid),"Company",{...o,area:o.area_sqft},1,null,false)}</summary>${rs.map(r=>node(r,2)).join("")}</details>`}).join("");
  const g=Object.values(byC).flat().reduce((a,r)=>{const x=roll(r.id);for(const k in ZERO)a[k]+=x[k];return a},{...ZERO});
  return `<div class="panel tree"><div class="trow thead"><div>Administration hierarchy</div><div>Occupancy</div><div class="r">Sq ft</div><div class="r">Employees</div><div class="r">Guest houses</div><div class="r">Open issues</div><div class="r">Litigation</div><div class="r">Doc alerts</div></div>
   <details open><summary>${trow("Group","All companies",{...g,area:g.area_sqft},0,null,false)}</summary>${comp}</details></div><p class="muted small" style="margin:8px 2px">Parent rows add up everything beneath them. Open issues are unresolved tickets.</p>`};
 const paint=()=>{$("#pbody").innerHTML=mode=="cards"?`<div class="ghgrid">${bl.map(card).join("")||emptyState("No premises yet","","building")}</div>`:tree();
  $$("#pmode button").forEach(b=>b.classList.toggle("on",b.dataset.m==mode));$$(".ghc[data-id]").forEach(c=>c.onclick=e=>{if(!e.target.closest("a,button"))location.hash="#/premises/"+c.dataset.id})};
 $("#main").innerHTML=`<div class="page">${head("Premises","Buildings, their documents, utilities and the guest houses beneath them",(can("premises.write")?bulkBtns("premises")+`<button class="btn" id="addp">${I("plus")}Add premises</button>`:""))}
  <div class="tabs" id="pmode"><button data-m="cards">Premises</button><button data-m="tree">Hierarchy</button></div><div id="pbody"></div></div>`;
 $$("#pmode button").forEach(b=>b.onclick=()=>{mode=b.dataset.m;localStorage.bms_pmode=mode;paint()});paint();$("#addp")&&($("#addp").onclick=addPremisesDrawer)};

/* ======================= PREMISES DETAIL ======================= */
function profileForm(d,done){const p=d.premises,m=d.meta;drawer({title:"Edit premises details",sub:p.name,label:"Save details",
 body:F("Name","n",{val:p.name})+F("Address","a",{val:p.address})+F("Area / landmark","lo",{val:m.location,ph:"Kilimani, near The Arch Place"})+F("Google Maps link","mu",{val:m.maps_url,ph:"https://maps.app.goo.gl/…",hint:"Paste the share link. If empty, the pin below is used."})
  +`<div class="grid g2">${F("Latitude","la",{type:"number",step:"any",val:p.lat})}${F("Longitude","ln",{type:"number",step:"any",val:p.lng})}${F("Area taken (sq ft)","sq",{type:"number",val:m.area_sqft})}${F("Floors taken (number)","fl",{type:"number",val:m.floors})}</div>`
  +F("Floors taken (which)","ft",{val:m.floors_taken,ph:"7th to 9th floor"})+F("Ownership","ow",{opts:[["","Not set"],["leased","Leased"],["rented","Rented"],["owned","Owned"]],val:m.ownership||""})
  +`<div class="grid g2">${F("Employees working (declared)","hc",{type:"number",val:m.declared_headcount,hint:"The portal also counts mapped employees."})}${F("Legal litigation (cases)","lc",{type:"number",val:m.litigation_count})}</div>`
  +F("Litigation notes","ln2",{rows:2})+F("Contact person","cn",{val:m.contact_name})+F("Contact phone","cp",{val:m.contact_phone})+F("Amenities","am",{rows:2,hint:"Comma separated."})+F("Notes","no",{rows:2}),
 onOpen:()=>{$("#f_ln2").value=m.litigation_notes||"";$("#f_am").value=m.amenities||"";$("#f_no").value=m.notes||""},
 onSave:async()=>{await api(`/premises/${p.id}/profile`,{body:{name:val("n"),address:val("a"),location:val("lo"),maps_url:val("mu"),lat:val("la"),lng:val("ln"),area_sqft:val("sq"),floors:val("fl"),floors_taken:val("ft"),ownership:val("ow"),declared_headcount:val("hc"),litigation_count:val("lc"),litigation_notes:val("ln2"),contact_name:val("cn"),contact_phone:val("cp"),amenities:val("am"),notes:val("no")}});toast("Details saved");await loadRef();done()}})}

function docForm(pid,done,pre){drawer({title:"Upload a document",sub:"Uploading the same type and title again creates the next version. Reminders go out at 90, 30 and 7 days before expiry.",label:"Upload",
 body:F("Document type","t",{opts:Object.entries(DTL),val:pre?.doc_type||"lease"})+F("Title","ti",{val:pre?.title,ph:"Office lease, 7th to 9th floor"})+F("Number / reference","n",{val:pre?.number})+F("Issuing authority / landlord","a",{val:pre?.authority})+F("Issued on","i",{type:"date"})+F("Valid until","v",{type:"date",hint:"Lease end, licence or certificate expiry."})+F("Notes","no",{rows:2})+F("File (PDF, image, Word or Excel)","f",{type:"file",accept:".pdf,.doc,.docx,.xls,.xlsx,image/*"}),
 onSave:async()=>{const f=new FormData();f.append("doc_type",val("t"));f.append("title",val("ti"));f.append("number",val("n"));f.append("authority",val("a"));f.append("issued_on",val("i"));f.append("valid_to",val("v"));f.append("notes",val("no"));const fl=$("#f_f").files[0];if(fl)f.append("file",fl);
  await api(`/premises/${pid}/documents`,{body:f});toast("Document saved");done()}})}

P4.premise=async function(id){
 const d=await api("/premises/"+id+"/profile"),p=d.premises,m=d.meta,st=d.stats;await loadRef();
 crumbs([["Administration"],["Premises","premises"],[p.name]]);addRecent(p.name,"premises/"+id,"building");
 refPanel({title:p.name,kind:"Premises",entity:"premises",id,kv:[["Type",esc(TYL[p.type]||p.type)],["Company",esc(cName(p.company_id))],["Area",sqft(m.area_sqft)],["Employees",st.employees]]});
 let tab=location.hash.includes("tab=")?new URLSearchParams(location.hash.split("?")[1]).get("tab"):"overview";const done=()=>route();
 const tabs=[["overview","Overview"],...(d.can_docs?[["docs","Documents"]]:[]),...(can("utilities.read")?[["util","Utilities"]]:[]),["subs",`Guest houses & sub-premises (${d.children.length})`]];if(!tabs.find(t=>t[0]==tab))tab="overview";
 const gh=d.children.filter(k=>k.type=="guest_house"),mu=mapOf(p,m);
 const paint=async()=>{const c=$("#tabc");
  if(tab=="overview")c.innerHTML=`<div class="grid g2-1"><div class="panel"><div class="hd"><h2>Property details</h2></div><div class="bd"><dl class="dl"><dt>Address</dt><dd>${esc(p.address||"–")}</dd><dt>Area</dt><dd>${esc(m.location||"–")}</dd><dt>Area taken</dt><dd>${sqft(m.area_sqft)}</dd><dt>Floors taken</dt><dd>${esc(m.floors_taken||"–")}${m.floors?` (${m.floors})`:""}</dd><dt>Ownership</dt><dd style="text-transform:capitalize">${esc(m.ownership||"–")}</dd>
    <dt>Employees</dt><dd>${st.employees} mapped${m.declared_headcount?` · ${m.declared_headcount} declared`:""}</dd><dt>Guest houses</dt><dd>${st.guest_houses}</dd><dt>Legal litigation</dt><dd>${m.litigation_count??0} case${m.litigation_count==1?"":"s"}</dd>${m.litigation_notes?`<dt>Litigation notes</dt><dd>${esc(m.litigation_notes)}</dd>`:""}<dt>Contact</dt><dd>${esc(m.contact_name||"–")}${m.contact_phone?`<div class="sec">${esc(m.contact_phone)}</div>`:""}</dd></dl>
    ${m.amenities?`<div class="fts" style="margin-top:10px">${featChips(m.amenities)}</div>`:""}${mu?`<p style="margin:12px 0 0"><a class="btn sm ghost" href="${esc(mu)}" target="_blank" rel="noopener">${I("route")}Open in Google Maps</a></p>`:""}</div></div>
    <div style="display:grid;gap:16px;align-content:start">${mapEmbed(p)}<div class="panel"><div class="hd"><h2>Inventory & issues</h2></div><div class="bd"><div class="row"><div class="grow">Assets (inventory)</div><b>${st.assets}</b></div><div class="row"><div class="grow">Vehicles</div><b>${st.vehicles}</b></div><div class="row"><div class="grow">Open tickets</div><b>${st.open_tickets}</b></div>
     <p style="margin:12px 0 0;display:flex;gap:8px"><a class="btn sm ghost" href="#/assets">Asset register</a><a class="btn sm ghost" href="#/tickets">Tickets</a></p></div></div></div></div>`;
  else if(tab=="docs"){c.innerHTML=`<div class="panel"><div class="hd"><h2>Document vault</h2><div class="acts"><button class="btn sm" id="ud">${I("upload")}Upload document</button></div></div><div id="dbody"><div class="bd"><div class="skel"></div></div></div></div>`;
   const L=await api(`/premises/${id}/documents`),latest={};L.forEach(x=>{const k=x.doc_type+"|"+(x.title||"");if(!latest[k]||x.version>latest[k].version)latest[k]=x});
   const cols=[{h:"Document",f:r=>`<div class="primary">${esc(r.title||DTL[r.doc_type])}</div><div class="sec">${esc(DTL[r.doc_type]||r.doc_type)}${r.number?" · "+esc(r.number):""}</div>`},{h:"Authority",f:r=>esc(r.authority||"–")},{h:"Valid until",f:r=>r.valid_to?fmtD(r.valid_to):"–"},
    {h:"Status",f:r=>r.state?sc(DS,r.state):`<span class="muted">No expiry</span>`},{h:"Version",f:r=>`v${r.version}${latest[r.doc_type+"|"+(r.title||"")]?.id==r.id?"":` <span class="muted small">(older)</span>`}`},{h:"File",f:r=>fileLink(r.file,"Open")||""},{h:"",cls:"right",f:r=>latest[r.doc_type+"|"+(r.title||"")]?.id==r.id?`<button class="btn sm ghost" data-rn="${r.id}">Renew</button>`:""}];
   $("#dbody").innerHTML=L.length?`<div class="tscroll"><table class="dt"><thead><tr>${cols.map(c=>`<th class="${c.cls||""}">${c.h}</th>`).join("")}</tr></thead><tbody>${L.map(r=>`<tr>${cols.map(c=>`<td class="${c.cls||""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:emptyState("No documents yet","Upload the lease, purchase document, government registration, tax papers and anything else Admin needs.","file");
   $("#ud").onclick=()=>docForm(id,done);$$("[data-rn]").forEach(b=>b.onclick=()=>docForm(id,done,L.find(x=>x.id==b.dataset.rn)))}
  else if(tab=="util"){c.innerHTML=`<div class="panel" id="upanel"></div>`;utilitiesPanel("#upanel",id,{exact:true})}
  else c.innerHTML=`<div class="panel"><div class="hd"><h2>Guest houses & sub-premises</h2><div class="acts">${d.can_edit?`<button class="btn sm" id="asb">${I("plus")}Add</button>`:""}</div></div>${d.children.length?`<div class="bd"><div class="ghgrid">${d.children.map(k=>`<div class="panel ghc" style="box-shadow:none" onclick="location.hash='#/${k.type=="guest_house"?"guesthouses":"premises"}/${k.id}'"><div class="top"><div class="big">${I("building")}</div><div><h3>${esc(k.name)}</h3><div class="muted small">${esc(TYL[k.type]||k.type)}</div></div></div><div class="ghaddr">${esc(k.address||"")}</div></div>`).join("")}</div></div>`:emptyState("None yet","Add a guest house or sub-premises beneath this building.","building")}</div>`;
  $("#asb")&&($("#asb").onclick=addPremisesDrawer)};
 $("#main").innerHTML=`<div class="page"><div class="rh"><div class="big">${I("building")}</div><div><h1>${esc(p.name)}</h1><p>${esc(cName(p.company_id))} · ${esc(TYL[p.type]||p.type)}${m.ownership?" · "+esc(m.ownership):""}</p></div>
   <div style="display:flex;gap:8px;align-items:center">${d.can_occupancy?`<select id="occ" title="HR and Admin can change this" style="height:32px"><option value="occupied">Occupied</option><option value="partial">Partly occupied</option><option value="vacant">Vacant</option></select>`:(m.occupancy?chip(...OC[m.occupancy]):"")}</div>
   <div class="acts">${can("tickets.raise")?`<button class="btn ghost" id="pt">${I("ticket")}Raise ticket</button>`:""}${d.can_edit?`<button class="btn" id="pe">Edit details</button>`:""}</div></div>
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">Area taken</div><div class="v" style="font-size:22px">${sqft(m.area_sqft)}</div><div class="s">${esc(m.floors_taken||"Floors not set")}</div></div><div class="kpi"><div class="k">${I("users")}Employees</div><div class="v">${st.employees}</div><div class="s">${m.declared_headcount?m.declared_headcount+" declared":"mapped in the portal"}</div></div>
   <div class="kpi"><div class="k">${I("building")}Guest houses</div><div class="v">${st.guest_houses}</div><div class="s">${d.children.length} sub-premises in all</div></div><div class="kpi ${m.litigation_count?"warn":""}"><div class="k">Legal litigation</div><div class="v">${m.litigation_count??0}</div><div class="s">${st.open_tickets} open tickets here</div></div></div>
  <div class="tabs" id="ptabs">${tabs.map(([k,l])=>`<button data-t="${k}" class="${k==tab?"on":""}">${l}</button>`).join("")}</div><div id="tabc"></div></div>`;
 $$("#ptabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.t;$$("#ptabs button").forEach(x=>x.classList.toggle("on",x==b));paint()});
 $("#pe")&&($("#pe").onclick=()=>profileForm(d,done));$("#pt")&&($("#pt").onclick=()=>raiseTicket({premises_id:id}));
 if($("#occ")){$("#occ").value=m.occupancy||"occupied";$("#occ").onchange=async e=>{try{await api(`/premises/${id}/occupancy`,{body:{status:e.target.value}});toast("Occupancy updated")}catch(x){toast(x.message,false)}}}
 paint()};

/* ======================= UTILITIES ======================= */
function utilityForm(pid,done){drawer({title:"Add a utility account",sub:"One account per supplier and meter. Bills are added to it each month.",label:"Add utility",
 body:(pid?"":F("Premises","p",{opts:premOpts(),val:PREM}))+F("Utility","k",{opts:Object.entries(UL)})+F("Supplier / provider name","pv",{req:1,ph:"Kenya Power, Zuku Fiber…",hint:"For internet, the internet provider's name."})+F("Account / meter reference","ar")+F("Billing","fq",{opts:[["monthly","Monthly"],["quarterly","Quarterly"],["annual","Annual"]]})+F("Supplier contact","ct")+F("Notes","no",{rows:2}),
 onSave:async()=>{if(!val("pv"))throw Error("Enter the supplier name.");await api("/utilities/accounts",{body:{premises_id:+(pid||val("p")),kind:val("k"),provider:val("pv"),account_ref:val("ar"),frequency:val("fq"),contact:val("ct"),notes:val("no")}});toast("Utility added");done()}})}
function billForm(a,done,accts){const now=new Date(),per=now.toISOString().slice(0,7);drawer({title:"Add a bill",sub:a?`${UL[a.kind]} · ${a.provider}`:"Record the supplier's invoice.",label:"Save bill",
 body:(a?"":F("Utility account","ac",{opts:accts.map(x=>[x.id,`${premName(x.premises_id)} · ${UL[x.kind]} · ${x.provider}`])}))+F("Billing period","pe",{type:"month",val:per})+F("Invoice number","in")+F("Invoice date","id",{type:"date"})+F("Due date","dd",{type:"date"})+F("Amount","am",{type:"number",step:"0.01"})+F("Currency","cu",{val:a?curOf(a.premises_id):"INR"})+F("Notes","no",{rows:2})+F("Invoice (PDF or image)","f",{type:"file",accept:".pdf,image/*"}),
 onSave:async()=>{const acc=a||accts.find(x=>x.id==val("ac"));if(!val("am"))throw Error("Enter the invoice amount.");const f=new FormData();["pe:period","in:invoice_no","id:invoice_date","dd:due_date","am:amount","cu:currency","no:notes"].forEach(x=>{const[k,n]=x.split(":");f.append(n,val(k)||"")});const fl=$("#f_f").files[0];if(fl)f.append("file",fl);
  await api(`/utilities/accounts/${acc.id}/bills`,{body:f});toast("Bill recorded");done()}})}
function payForm(b,done){drawer({title:"Mark as paid",sub:`${UL[b.kind]||""} · ${b.provider||""} · ${money(b.amount,b.currency)}`,label:"Confirm payment",
 body:F("Paid on","d",{type:"date",val:new Date().toISOString().slice(0,10)})+F("Payment reference","r",{ph:"Bank / M-Pesa reference"})+F("Payment proof (PDF or image)","f",{type:"file",accept:".pdf,image/*",hint:"Attach the proof or enter a reference."}),
 onSave:async()=>{const f=new FormData();f.append("paid_on",val("d"));f.append("payment_ref",val("r"));const fl=$("#f_f").files[0];if(fl)f.append("file",fl);await api(`/utilities/bills/${b.id}/pay`,{body:f});toast("Marked as paid");done()}})}

const billCols=(done,showPrem)=>[...(showPrem?[{h:"Premises",f:r=>esc(premName(r.premises_id)),t:r=>premName(r.premises_id)}]:[]),{h:"Utility",f:r=>`<div class="primary">${esc(UL[r.kind]||r.kind)}</div><div class="sec">${esc(r.provider||"")}${r.account_ref?" · "+esc(r.account_ref):""}</div>`,t:r=>`${r.kind} ${r.provider}`},
 {h:"Period",f:r=>esc(r.period||"–"),t:r=>r.period},{h:"Invoice",f:r=>`<div>${esc(r.invoice_no||"–")}</div><div class="sec">${fileLink(r.invoice_file,"View")||""}</div>`,t:r=>r.invoice_no},{h:"Amount",cls:"num right",f:r=>money(r.amount,r.currency),t:r=>r.amount},
 {h:"Due",f:r=>r.due_date?fmtD(r.due_date):"–",t:r=>r.due_date},{h:"Status",f:r=>sc(BS,r.state)+(r.state=="paid"?`<div class="sec">${fmtD(r.paid_on)}${r.proof_file?" · "+fileLink(r.proof_file,"proof"):r.payment_ref?" · "+esc(r.payment_ref):""}</div>`:""),t:r=>BS[r.state]?.[0]},
 {h:"",cls:"right",f:r=>r.status!="paid"&&can("utilities.write")?`<button class="btn sm" data-pay="${r.id}">Mark paid</button>`:""}];

async function utilitiesPanel(sel,pid,o={}){const el=$(sel);el.innerHTML=`<div class="bd"><div class="skel" style="width:40%"></div></div>`;
 const [acc,bills]=await Promise.all([api(`/utilities/accounts?premises_id=${pid}${o.exact?"&exact=true":""}`),api(`/utilities/bills?premises_id=${pid}`)]);
 const ids=new Set(acc.map(a=>a.id)),B=bills.filter(b=>ids.has(b.account_id)),redo=()=>{utilitiesPanel(sel,pid,o);refreshNotes()};
 const ac=[{h:"Utility",f:r=>`<div class="primary">${esc(UL[r.kind]||r.kind)}</div><div class="sec">${esc(r.provider)}</div>`},{h:"Account ref",f:r=>esc(r.account_ref||"–")},{h:"Billing",f:r=>esc(r.frequency)},{h:"Next due",f:r=>r.next_due?fmtD(r.next_due):"–"},
  {h:"Status",f:r=>r.overdue?chip(r.overdue+" overdue","bad"):r.unpaid?chip(r.unpaid+" to pay","warn"):chip("Up to date","ok")},{h:"Last bill",cls:"num right",f:r=>r.last_bill?money(r.last_bill.amount,r.last_bill.currency):"–"},
  {h:"",cls:"right",f:r=>`<div style="display:flex;gap:6px;justify-content:flex-end">${can("utilities.write")?`<button class="btn sm ghost" data-ab="${r.id}">Add bill</button>`:""}${can("tickets.raise")?`<button class="btn sm ghost" data-tk="${r.id}">${I("ticket")}Raise ticket</button>`:""}</div>`}];
 el.innerHTML=`<div class="hd"><h2>${o.title||"Utilities"}</h2><div class="acts">${can("utilities.write")?`<button class="btn sm" id="au">${I("plus")}Add utility</button>`:""}<a class="btn sm ghost" href="#/utilities">All utilities</a></div></div>`
  +(acc.length?`<div class="tscroll"><table class="dt"><thead><tr>${ac.map(c=>`<th class="${c.cls||""}">${c.h}</th>`).join("")}</tr></thead><tbody>${acc.map(r=>`<tr>${ac.map(c=>`<td class="${c.cls||""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:emptyState("No utilities recorded","Add electricity, water and internet with the supplier and account reference.","plug"))
  +(B.length?`<div class="hd" style="border-top:1px solid var(--gold-l)"><h2 style="font-size:13px">Bills</h2></div><div class="tscroll"><table class="dt"><thead><tr>${billCols(redo).map(c=>`<th class="${c.cls||""}">${c.h}</th>`).join("")}</tr></thead><tbody>${B.map(r=>`<tr>${billCols(redo).map(c=>`<td class="${c.cls||""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`:"");
 $("#au",el)&&($("#au",el).onclick=()=>utilityForm(pid,redo));
 $$("[data-ab]",el).forEach(b=>b.onclick=()=>billForm(acc.find(x=>x.id==b.dataset.ab),redo));$$("[data-pay]",el).forEach(b=>b.onclick=()=>payForm(B.find(x=>x.id==b.dataset.pay),redo));
 $$("[data-tk]",el).forEach(b=>b.onclick=()=>raiseTicket({premises_id:pid,utility:acc.find(x=>x.id==b.dataset.tk)}))}

P4.utilities=async function(){
 const [acc,bills]=await Promise.all([api("/utilities/accounts"),api("/utilities/bills")]);await loadRef();crumbs([["Facilities"],["Utilities"]]);refPanel();
 const B=bills.filter(b=>inPrem(b.premises_id)),A=acc.filter(a=>inPrem(a.premises_id)),done=()=>{route();refreshNotes()};
 const cols=billCols(done,true),mon=new Date().toISOString().slice(0,7);
 const o={tabs:[["pay","To pay",r=>r.status!="paid"],["over","Overdue",r=>r.state=="overdue"],["soon","Due in 7 days",r=>r.state=="due_soon"],["paid","Paid",r=>r.status=="paid"],["all","All",()=>true]],q:r=>`${premName(r.premises_id)} ${r.kind} ${r.provider} ${r.invoice_no} ${r.account_ref}`,csv:"utility-bills",ph:"Search premises, supplier, invoice",empty:"No bills yet",emptySub:"Add a utility to a premises, then record each monthly bill."};
 const unpaid=B.filter(b=>b.status!="paid"),sum=unpaid.reduce((a,b)=>a+b.amount,0);
 $("#main").innerHTML=`<div class="page">${head("Utilities","Electricity, water, internet and other bills: supplier, account, invoice, due date and payment proof",can("utilities.write")?`<button class="btn ghost" id="ua">${I("plus")}Add utility</button><button class="btn" id="ub">${I("plus")}Add bill</button>`:"")}
  <div class="grid g4" style="margin-bottom:16px"><div class="kpi"><div class="k">${I("plug")}Utility accounts</div><div class="v">${A.length}</div></div><div class="kpi ${unpaid.length?"warn":""}"><div class="k">To pay</div><div class="v">${unpaid.length}</div><div class="s">${unpaid.length?money(sum,""):"All paid"}</div></div><div class="kpi ${B.some(b=>b.state=="overdue")?"bad":""}"><div class="k">Overdue</div><div class="v">${B.filter(b=>b.state=="overdue").length}</div></div><div class="kpi"><div class="k">Paid this month</div><div class="v">${B.filter(b=>b.status=="paid"&&(b.paid_on||"").startsWith(mon)).length}</div></div></div>
  ${table("t_ub",cols,B,o)}</div>`;
 wire("t_ub",B,cols,o);$$("[data-pay]").forEach(b=>b.onclick=()=>payForm(B.find(x=>x.id==b.dataset.pay),done));
 $("#ua")&&($("#ua").onclick=()=>utilityForm(null,done));$("#ub")&&($("#ub").onclick=()=>A.length?billForm(null,done,A):toast("Add a utility first.",false))};

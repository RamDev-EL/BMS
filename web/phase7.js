"use strict";
/* Phase 7: dashboard as grouped tiles, the "waiting for you / pending" bar shown on every page, and "my recent activity" in the right panel. */
const P7={};let MINE=null;

/* ---------- right panel: my past activity ---------- */
async function loadMine(){try{MINE=await api("/me/activity")}catch{MINE=[]}paintMine()}
function paintMine(){const el=$("#mine");if(!el)return;
 el.innerHTML=`<h4>My recent activity</h4>`+(MINE&&MINE.length?`<div class="tl act">${MINE.slice(0,8).map(a=>`<a class="ev" href="#/${a.link}"><b style="text-transform:capitalize">${esc(a.action)}</b><small>${esc(String(a.entity).replace(/_/g," "))}${a.entity_id?" #"+a.entity_id:""} · ${fmtDT(a.at)}</small></a>`).join("")}</div>`:`<p class="muted small">Nothing yet. What you do here appears in this list.</p>`)}

/* ---------- top bar: what is waiting for me, what is pending ---------- */
function renderActionBar(){const el=$("#abar");if(!el||!ME)return;
 const S=SUM||{},T=TSUM||{},N=NOTE||{},F=S.fleet||{},nt=k=>(NOTI||[]).filter(n=>n.kind==k).length;
 const wait=[[T.awaiting_me,"Travel approvals","travel","warn"],[can("service.approve")?F.services_pending_approval:0,"Quotations to approve","vservices","warn"],[can("vehicles.write")?F.returns_pending:0,"Vehicle returns to sign","handovers","bad"],
  [can("tickets.manage")?S.tickets?.unassigned:0,"Tickets to assign","tickets","warn"],[(NOTI||[]).filter(n=>n.kind=="travel"&&/claim/i.test(n.title)).length,"Claims to approve or pay","travel","warn"],[nt("incident"),"New incidents","incidents","bad"]].filter(x=>x[0]);
 const pend=[[S.tickets?.overdue,"Tickets overdue","tickets","bad"],[S.utilities?.overdue,"Utility bills overdue","utilities","bad"],[S.utilities?.due_soon,"Bills due in 7 days","utilities","warn"],[S.docs?.count,"Premises documents expiring","premises",S.docs?.expired?"bad":"warn"],
  [N.expiring?.length,"Vehicle renewals due","compliance","warn"],[S.assets?.service_overdue,"Assets overdue for service","assets","warn"],[N.fuel_flagged,"Fuel entries to review","fuel","warn"],[N.trips_unassigned,"Trips need a driver","trips","warn"],[F.open_incidents,"Open incidents","incidents","warn"],
  [T.refunds_pending,"Refunds pending","refunds","warn"],[T.visas_expiring,"Visas expiring","visas","warn"],[S.hrms?.advances_waiting,"Advances not in HRMS","advances","warn"],[S.hrms?.state=="error"?1:0,"HRMS not reachable","integrations","bad"]].filter(x=>x[0]);
 const chips=a=>a.map(([n,l,to,tone])=>`<a class="ac ${tone}" href="#/${to}"><b>${n}</b>${esc(l)}</a>`).join("");
 const wn=wait.reduce((a,x)=>a+x[0],0);
 el.innerHTML=wait.length||pend.length?`<div class="abar"><div class="ag"><span class="al">${I("bell")} Waiting for you${wn?` · ${wn}`:""}</span>${wait.length?chips(wait):`<span class="muted small">Nothing needs your action</span>`}</div><div class="ag"><span class="al">${I("clock")} Pending</span>${pend.length?chips(pend):`<span class="muted small">Nothing pending</span>`}</div></div>`
  :`<div class="abar clear"><span class="al">${I("check")} You are all caught up. Nothing is waiting for you.</span></div>`}

/* ---------- dashboard: grouped tiles ---------- */
const tile=(ic,label,val,sub,to,tone="")=>`<a class="tl2 ${tone}" href="#/${to}"><span class="ti">${I(ic)}</span><span class="tb"><b>${val}</b><span>${label}</span>${sub?`<small>${sub}</small>`:""}</span></a>`;
const group=(ic,title,to,tiles)=>tiles.length?`<section class="panel dgroup"><div class="dgh"><span class="ti">${I(ic)}</span><h2>${title}</h2>${to?`<a class="small" href="#/${to}">Open ${I("chev")}</a>`:""}</div><div class="tgrid">${tiles.join("")}</div></section>`:"";

P7.dashboard=async function(){
 const q=PREM?"?premises_id="+PREM:"";
 const [d,trips,sm,ts]=await Promise.all([api("/dashboard"+q),can("trips.read")?api("/trips?status=requested"):[],api("/summary"+q),can("travel.read")?api("/travel/summary").catch(()=>null):null]);
 if(!PREM){NOTE=d;SUM=sm;TSUM=ts;renderBell();renderMenu();renderActionBar()}
 crumbs([["Dashboard"]]);refPanel();
 const hr=new Date().getHours(),g=hr<12?"Good morning":hr<17?"Good afternoon":"Good evening",open=trips.filter(t=>inPrem(t.premises_id));
 const P=sm.people,A=sm.assets,K=sm.tickets,F=sm.fleet,H=sm.hrms,Dc=sm.docs,U=sm.utilities,T=ts;
 const tone=(n,bad)=>n?(bad?"bad":"warn"):"";
 const blds=PL.filter(p=>p.type!="guest_house"&&inPrem(p.id)).length;
 const premises=[PL.length?tile("building","Premises",blds,PL.filter(p=>p.type=="guest_house"&&inPrem(p.id)).length+" guest houses","premises"):"",
  P?tile("users","Employees",P.total,`${P.on_leave} on leave · ${P.notice} on notice`,"employees"):"",P?tile("building","Guest house beds",`${P.occupied}<span class="of"> / ${P.beds||"?"}</span>`,`${(P.beds||0)-P.occupied} free`,"guesthouses"):"",
  Dc?tile("file","Premises documents",Dc.count,`${Dc.expired} expired`,"premises",tone(Dc.count,Dc.expired)):"",U?tile("plug","Utility bills",U.overdue+U.due_soon,`${U.overdue} overdue · ${U.due_soon} due soon`,"utilities",tone(U.overdue+U.due_soon,U.overdue)):""].filter(Boolean);
 const fleet=[tile("car","Fleet",d.vehicles,`${d.available} available · ${d.on_trip} on trip`,"vehicles"),can("trips.read")?tile("route","Open trips",d.trips_open,`${d.trips_unassigned} need a driver`,"trips",tone(d.trips_unassigned)):"",
  F?tile("users","Vehicle returns",F.returns_pending,"leavers holding a vehicle","handovers",tone(F.returns_pending,1)):"",tile("shield","Renewals due",d.expiring.length,"insurance, fitness, permits","compliance",tone(d.expiring.length,d.expiring.some(x=>x.days<0))),
  F?tile("wrench","Service & repairs",F.services_pending_approval+F.services_due,`${F.services_pending_approval} to approve · ${F.services_due} due`,"vservices",tone(F.services_pending_approval)):"",F?tile("alert","Incidents",F.open_incidents,"open","incidents",tone(F.open_incidents)):"",
  can("fuel.read")?tile("fuel","Fuel to review",d.fuel_flagged,`${n0(d.fuel_cost_month)} spent this month`,"fuel",tone(d.fuel_flagged,1)):""].filter(Boolean);
 const maint=[A?tile("box","Admin assets",A.total,`${A.under_maintenance} under maintenance`,"assets"):"",A?tile("wrench","Service due",A.service_overdue+A.service_soon,`${A.service_overdue} overdue · ${A.warranty_expiring} warranties ending`,"assets",tone(A.service_overdue+A.service_soon,A.service_overdue)):"",
  K?tile("ticket","Open tickets",K.open,`${K.unassigned} not assigned`,"tickets",tone(K.unassigned)):"",K?tile("alert","Tickets overdue",K.overdue,`${K.critical} high or critical`,"tickets",tone(K.overdue,1)):""].filter(Boolean);
 const adm=[T?tile("route","Travel approvals",T.awaiting_me,`${T.awaiting} awaiting in all`,"travel",tone(T.awaiting_me)):"",T?tile("route","Ready to book",T.approved_to_book,`${T.upcoming} upcoming trips`,"travel"):"",T?tile("file","Refunds pending",T.refunds_pending,"changes & cancellations","refunds",tone(T.refunds_pending)):"",
  T?tile("shield","Visas expiring",T.visas_expiring,"within 60 days","visas",tone(T.visas_expiring)):"",H?tile("plug","HRMS integration",chip(...(HS[H.state]||[H.state,""])),H.last_ok?"Last success "+fmtDT(H.last_ok):"No call yet",can("integrations.manage")?"integrations":"advances",H.state=="error"?"bad":H.state=="ok"?"":"warn"):"",
  H&&H.advances_waiting?tile("route","Advances not in HRMS",H.advances_waiting,"retry from Travel advances","advances","warn"):""].filter(Boolean);
 const rows=[...d.expiring.slice(0,4).map(e=>({t:`${e.vehicle} · ${e.doc_type}`,s:e.days<0?`Expired ${-e.days} days ago`:`Due in ${e.days} days`,to:"vehicles/"+e.vehicle_id,bad:e.days<0})),...((Dc&&Dc.items)||[]).slice(0,4).map(x=>({t:`${x.premises} · ${DTL[x.doc_type]||x.doc_type}`,s:x.state=="expired"?"Expired":`Due ${fmtD(x.valid_to)}`,to:"premises/"+x.premises_id,bad:x.state=="expired"}))];
 $("#main").innerHTML=`<div class="page">${head(`${g}, ${esc(ME.name.replace(/\(.*\)/,"").trim())}`,`${new Date().toLocaleDateString([],{weekday:"long",day:"numeric",month:"long",year:"numeric"})} · ${esc(premScope())}`,can("vehicles.write")?`<button class="btn" id="addv">${I("plus")}Add vehicle</button>`:"")}
  <div class="dgrid">${group("building","Premises & facilities","premises",premises)}${group("car","Vehicles & fleet","vehicles",fleet)}${group("wrench","Maintenance","assets",maint)}${group("route","Travel & administration","travel",adm)}</div>
  ${rows.length||open.length?`<div class="grid g2" style="margin-top:16px"><div class="panel"><div class="hd"><h2>Coming up</h2><span class="muted small">Renewals and expiries</span></div>${rows.length?rows.map(r=>`<a class="row click" href="#/${r.to}" style="text-decoration:none;color:inherit"><div class="grow"><b>${esc(r.t)}</b></div>${chip(r.s,r.bad?"bad":"warn")}</a>`).join(""):emptyState("Nothing due")}</div>
   <div class="panel"><div class="hd"><h2>Trips needing a driver</h2><a class="small" href="#/trips">View all</a></div>${open.length?open.slice(0,5).map(t=>`<a class="row click" href="#/trips" style="text-decoration:none;color:inherit"><div class="grow"><b>${esc(t.destination)}</b><div class="muted small">${esc(t.requester)} · ${fmtDT(t.needed_at)}</div></div>${chip("Unassigned","warn")}</a>`).join(""):emptyState("All trips are covered")}</div></div>`:""}</div>`;
 $("#addv")&&($("#addv").onclick=addVehicleDrawer)};

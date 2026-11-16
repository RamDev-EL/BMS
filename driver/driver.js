const m=document.getElementById("m");let TOKEN=localStorage.drv_token,ME=null;
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
if("serviceWorker"in navigator)navigator.serviceWorker.register("sw.js");
async function api(p,body){const h={Authorization:"Bearer "+TOKEN};let o={headers:h};
 if(body){o.method="POST";if(body instanceof FormData)o.body=body;else{h["Content-Type"]="application/json";o.body=JSON.stringify(body)}}
 const r=await fetch("/api"+p,o).catch(()=>{throw Error("No connection. Check your signal and try again.")});
 if(r.status==401&&p!="/auth/login"){out();throw Error("Signed out")}
 const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(j.detail||"Something went wrong");return j}
const out=()=>{localStorage.removeItem("drv_token");TOKEN=null;login()};
function login(msg){document.getElementById("who").innerHTML="";
 m.innerHTML=`<div class="login"><div class="logo">B</div><h2>Driver sign in</h2><p class="sub">Use the account given by your administrator.</p><div class="card"><label>Email<input id="e" type="email" placeholder="name@company.com" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false"></label><label>Password<input id="p" type="password" placeholder="Password" autocomplete="current-password" autocapitalize="none" autocorrect="off"></label><button id="b">Sign in</button><p class="err">${esc(msg||"")}</p></div></div>`;
 document.getElementById("b").onclick=async()=>{try{const j=await api("/auth/login",{email:e.value,password:p.value});
  if(!j.user.perms.includes("driver.app"))return login("This app is for drivers only.");TOKEN=j.token;localStorage.drv_token=TOKEN;home()}catch(x){login(x.message)}}}
const gps=()=>new Promise(r=>navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>r({lat:p.coords.latitude,lng:p.coords.longitude}),()=>r({}),{timeout:6000}):r({}));
async function home(){
 try{ME=await api("/me");const d=await api("/driver/trips");const fn=ME.name.replace(/\(.*\)/,"").trim().split(" ")[0];document.getElementById("who").innerHTML=`<span class="av">${esc(fn[0]||"D")}</span>${esc(fn)}`;
  const fmt=x=>new Date(x+"Z").toLocaleString([],{dateStyle:"medium",timeStyle:"short"});
  m.innerHTML=`<h2>My trips</h2><p class="sub">${d.active.length} active</p>`+(d.active.length?d.active.map(t=>`<div class="card trip"><span class="chip ${t.status}">${t.status}</span>
  <div class="route"><div class="rail"><span class="dot f"></span><span class="line"></span><span class="dot"></span></div><div><b>${esc(t.pickup||"Pickup")}</b><span class="muted">${t.needed_at?fmt(t.needed_at):"Pickup"}</span><div style="height:12px"></div><b>${esc(t.destination)}</b><span class="muted">${esc(t.purpose||"")}</span></div></div>
  <div class="meta"><div><small>Vehicle</small><span>${esc(t.vehicle||"Not set")}</span></div><div><small>Requested by</small><span>${esc(t.requester)}</span></div></div>
  <button onclick="${t.status=="assigned"?`startForm(${t.id})`:`endForm(${t.id})`}">${t.status=="assigned"?"Start trip":"End trip"}</button></div>`).join(""):`<div class="card empty"><b>No trips assigned</b>New trips will appear here once assigned.</div>`)+
  `<div class="actions"><button class="dark" onclick="fuelForm()">Log fuel</button><button class="dark" onclick="incidentForm()">Report accident</button></div><button class="ghost" onclick="out()" style="margin-top:0">Sign out</button>`+
  (d.recent.length?`<h3>Recent trips</h3>`+d.recent.map(t=>`<div class="card recent"><b>${esc(t.destination)}</b><span class="muted">${t.distance} km</span></div>`).join(""):"")
 }catch(e){e.message=="Signed out"||login(e.message)}}
const back=`<button class="ghost" onclick="home()">Cancel</button>`;
function formShell(title,body,fn,label){m.innerHTML=`<h2>${title}</h2><p class="sub">Meter photo is required for the audit trail.</p><div class="card">${body}<p class="err" id="er"></p><button id="sub">${label}</button>${back}</div>`;
 document.getElementById("sub").onclick=async()=>{const b=document.getElementById("sub");b.disabled=true;b.textContent="Saving…";
  try{await fn();home()}catch(e){document.getElementById("er").textContent=e.message;b.disabled=false;b.textContent=label}}}
const photoField=(id,l)=>`<label>${l}<input id="${id}" type="file" accept="image/*" capture="environment"></label>`;
function startForm(id){formShell("Start trip",`<label>Start meter (km)<input id="mt" type="number" inputmode="decimal"></label>${photoField("ph","Photo of the meter")}`,async()=>{
 const f=new FormData();if(!mt.value||!ph.files[0])throw Error("Enter the meter reading and take a meter photo.");f.append("meter",mt.value);f.append("photo",ph.files[0]);
 const g=await gps();if(g.lat!=null){f.append("lat",g.lat);f.append("lng",g.lng)}await api(`/driver/trips/${id}/start`,f)},"Start trip")}
function endForm(id){formShell("End trip",`<label>Closing meter (km)<input id="mt" type="number" inputmode="decimal"></label>${photoField("ph","Photo of the meter")}<label>Notes<textarea id="nt" rows="2"></textarea></label>`,async()=>{
 const f=new FormData();if(!mt.value||!ph.files[0])throw Error("Enter the meter reading and take a meter photo.");f.append("meter",mt.value);f.append("notes",nt.value);f.append("photo",ph.files[0]);
 const g=await gps();if(g.lat!=null){f.append("lat",g.lat);f.append("lng",g.lng)}await api(`/driver/trips/${id}/end`,f)},"End trip")}
async function fuelForm(){const v=await api("/driver/vehicles"),d=await api("/driver/trips"),cur=d.active.find(t=>t.status=="started");
 formShell("Log fuel",`<p class="sub" style="margin-top:-6px">Note the meter when you leave for the fuel station and again after filling, each with a photo.</p><label>Vehicle<select id="vh">${v.map(x=>`<option value="${x.id}" ${cur&&cur.vehicle_id==x.id?"selected":""}>${esc(x.reg_no)} · ${esc(x.make_model)}</option>`).join("")}</select></label>
 <label>Start meter, when leaving (km)<input id="sm" type="number" inputmode="decimal"></label>${photoField("sph","Photo of the start meter")}
 <label>Litres<input id="lt" type="number" step="0.01" inputmode="decimal"></label><label>Total cost<input id="co" type="number" step="0.01" inputmode="decimal"></label>
 <label>Closing meter, after fuel (km)<input id="mt" type="number" inputmode="decimal"></label>${photoField("ph","Photo of the closing meter")}${photoField("rc","Photo of the receipt")}`,async()=>{
 if(!lt.value||!co.value||!mt.value)throw Error("Fill litres, cost and the closing meter.");if(sm.value&&+mt.value<+sm.value)throw Error("The closing meter is lower than the start meter.");
 if((!ph.files[0]||(sm.value&&!sph.files[0]))&&!confirm("A meter photo is missing. This entry will be flagged for review. Continue?"))throw Error("Add the meter photos.");
 const f=new FormData();f.append("vehicle_id",vh.value);f.append("litres",lt.value);f.append("cost",co.value);f.append("meter_reading",mt.value);if(sm.value)f.append("start_meter",sm.value);
 if(cur)f.append("trip_id",cur.id);if(sph.files[0])f.append("start_photo",sph.files[0]);if(ph.files[0])f.append("meter_photo",ph.files[0]);if(rc.files[0])f.append("receipt",rc.files[0]);await api("/fuel",f)},"Save fuel entry")}
async function incidentForm(){const v=await api("/driver/vehicles"),d=await api("/driver/trips"),cur=d.active.find(t=>t.status=="started");
 formShell("Report an accident or damage",`<p class="sub" style="margin-top:-6px">Admin is told straight away. Take photos of the damage and the scene.</p><label>Vehicle<select id="vh">${v.map(x=>`<option value="${x.id}" ${cur&&cur.vehicle_id==x.id?"selected":""}>${esc(x.reg_no)} · ${esc(x.make_model)}</option>`).join("")}</select></label>
 <label>What happened<select id="kd"><option value="accident">Accident</option><option value="damage">Damage</option><option value="breakdown">Breakdown</option><option value="theft">Theft</option></select></label>
 <label>Where<input id="lc" placeholder="Road or landmark"></label><label>Details<textarea id="ds" rows="3"></textarea></label><label>Anyone injured?<select id="inj"><option value="">No</option><option value="1">Yes</option></select></label>
 <label>Photos<input id="ph" type="file" accept="image/*" capture="environment" multiple></label>`,async()=>{
 if(!ds.value.trim())throw Error("Describe what happened.");const f=new FormData();f.append("vehicle_id",vh.value);f.append("kind",kd.value);f.append("location",lc.value);f.append("description",ds.value);f.append("injuries",inj.value);[...ph.files].forEach(x=>f.append("photos",x));
 await api("/driver/incidents",f)},"Send report")}
TOKEN?home():login();

"""Phase 5: vehicle management. Assignment to employees with issue/return checklists, leaver (resignation) alerts to Admin and HR,
insurance & compliance review, servicing and repairs with quotation approval, and accident/incident register."""
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import *
from .core import *
from .phase1 import scoped, in_scope, pdate, pnum
from .phase4 import save_upload, notify, resolve_notes, doc_state

router = APIRouter()
LEAVING = ("notice", "resigned", "inactive")

def vscope(s, u, perm="vehicles.read"):
    q = s.query(Vehicle); ids = scope_premises(s, u, perm)
    return q.filter(Vehicle.premises_id.in_(ids or {-1})) if ids is not None else q

def get_veh(s, u, vid, perm="vehicles.read"):
    v = vscope(s, u, perm).filter(Vehicle.id == vid).first()
    if not v: raise HTTPException(404, "Vehicle not found in your scope")
    return v

# ---------- leaver (resignation) hook, called when an employee's status changes ----------
def on_employee_status(s, e, user=None):
    if e.status in LEAVING:
        held = s.query(VehicleAssignment).filter(VehicleAssignment.employee_id == e.id, VehicleAssignment.status.in_(["active", "return_pending"])).all()
        for a in held: a.status = "return_pending"
        bed = s.query(GuestAllocation).filter_by(employee_id=e.id, status="allocated").first()
        regs = [s.get(Vehicle, a.vehicle_id).reg_no for a in held]
        parts = ([f"Vehicle {', '.join(regs)} to be returned"] if regs else []) + ([f"Guest house bed to be vacated ({s.get(Premises, bed.guest_house_id).name})"] if bed else [])
        notify(s, "leaver", f"{e.name} ({e.emp_code}) is leaving: {e.status.replace('_', ' ')}", "; ".join(parts) or "No vehicle or guest house bed held. Confirm other admin items are recovered.",
               link="handovers" if held else "employees", premises_id=e.premises_id, perm="employees.write", ref=f"leaver:{e.id}")
    else:
        resolve_notes(s, f"leaver:{e.id}")
        for a in s.query(VehicleAssignment).filter_by(employee_id=e.id, status="return_pending"): a.status = "active"

def asg_out(s, a, emps=None, vehs=None):
    e = (emps or {}).get(a.employee_id) if emps is not None else (s.get(Employee, a.employee_id) if a.employee_id else None)
    v = (vehs or {}).get(a.vehicle_id) if vehs is not None else s.get(Vehicle, a.vehicle_id)
    return row(a, employee=e.name if e else "Common pool", emp_code=e.emp_code if e else None, grade=e.grade if e else None, emp_status=e.status if e else None,
               vehicle=v.reg_no if v else None, vehicle_name=v.make_model if v else None, premises_id=v.premises_id if v else None)

@router.get("/api/vehicles/{vid}/assignments")
def v_assignments(vid: int, u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    get_veh(s, u, vid)
    return [asg_out(s, a) for a in s.query(VehicleAssignment).filter_by(vehicle_id=vid).order_by(VehicleAssignment.id.desc())]

@router.get("/api/handovers")
def handovers(u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    V = {v.id: v for v in vscope(s, u)}; E = {e.id: e for e in s.query(Employee)}
    out = []
    for a in s.query(VehicleAssignment).filter(VehicleAssignment.vehicle_id.in_(list(V) or [-1]), VehicleAssignment.status.in_(["active", "return_pending", "returned"])).order_by(VehicleAssignment.id.desc()).limit(300):
        if a.employee_id is None: continue
        if a.status == "returned" and (not a.returned_on or (dt.date.today() - a.returned_on).days > 60): continue
        out.append(asg_out(s, a, E, V))
    return out

@router.post("/api/vehicles/{vid}/assign")
def v_assign(vid: int, employee_id: str = Form(""), from_date: str = Form(""), purpose: str = Form(""), issue_condition: str = Form(""), issue_meter: str = Form(""), issue_fuel: str = Form(""),
             photo: UploadFile | None = File(None), u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    v = get_veh(s, u, vid, "vehicles.write")
    if not employee_id: raise HTTPException(400, "Choose an employee. A vehicle with no assignment is in the common pool.")
    e = s.get(Employee, int(employee_id))
    if not e or e.company_id != v.company_id: raise HTTPException(400, "Employee must be in the same company as the vehicle")
    if e.status in ("resigned", "inactive"): raise HTTPException(400, f"{e.name} is {e.status}")
    cur = s.query(VehicleAssignment).filter(VehicleAssignment.vehicle_id == vid, VehicleAssignment.status.in_(["active", "return_pending"])).first()
    if cur: raise HTTPException(409, "This vehicle is already assigned. Complete its return first.")
    try: fd = pdate(from_date) or dt.date.today(); im = pnum(issue_meter, "meter")
    except ValueError as x: raise HTTPException(400, str(x))
    a = VehicleAssignment(vehicle_id=vid, employee_id=e.id, from_date=fd, purpose=purpose or None, issue_condition=issue_condition or None, issue_meter=im if im is not None else v.odometer,
                          issue_fuel=issue_fuel or None, issue_photo=save_upload(photo), created_by=u.name, status="return_pending" if e.status in LEAVING else "active")
    v.pool = False; s.add(a); s.flush(); audit(s, u, "vehicle", vid, "assigned", None, {"employee": f"{e.emp_code} {e.name}", "from": fd}); s.commit(); return asg_out(s, a)

@router.post("/api/assignments/{aid}/return")
def v_return(aid: int, return_condition: str = Form(""), return_meter: str = Form(""), return_fuel: str = Form(""), damage: str = Form(""), photo: UploadFile | None = File(None),
             u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    a = s.get(VehicleAssignment, aid)
    if not a: raise HTTPException(404)
    v = get_veh(s, u, a.vehicle_id, "vehicles.write")
    if a.status == "returned": raise HTTPException(400, "Already returned")
    if not return_condition.strip(): raise HTTPException(400, "Describe the condition at return")
    try: rm = pnum(return_meter, "meter")
    except ValueError as x: raise HTTPException(400, str(x))
    if rm is None: raise HTTPException(400, "Enter the meter reading at return")
    if a.issue_meter is not None and rm < a.issue_meter: raise HTTPException(400, f"Return meter ({rm:g}) is below the issue meter ({a.issue_meter:g})")
    a.return_condition, a.return_meter, a.return_fuel, a.damage, a.return_photo = return_condition, rm, return_fuel or None, bool(damage), save_upload(photo)
    a.status, a.returned_on, a.signed_by = "returned", dt.date.today(), u.name
    v.odometer = max(v.odometer, rm); v.status = "maintenance" if a.damage else "available"
    if a.damage:   # a difference between issue and return condition creates a damage ticket (Finance can recover the cost)
        e = s.get(Employee, a.employee_id); t = Ticket(company_id=v.company_id, premises_id=v.premises_id, category="vehicle", title=f"Damage on return: {v.reg_no}",
                    description=f"Returned by {e.name if e else 'employee'}. Issue: {a.issue_condition or 'no note'}. Return: {a.return_condition}", priority="medium", raised_by=u.id, raised_by_name=u.name,
                    due_at=dt.datetime.utcnow() + dt.timedelta(hours=72)); s.add(t); s.flush()
        s.add(TicketEvent(ticket_id=t.id, user_id=u.id, user_name=u.name, kind="created", text="Raised automatically from the vehicle return checklist"))
    if a.employee_id and not s.query(VehicleAssignment).filter(VehicleAssignment.employee_id == a.employee_id, VehicleAssignment.status.in_(["active", "return_pending"]), VehicleAssignment.id != a.id).count():
        resolve_notes(s, f"leaver:{a.employee_id}")
    if not s.query(VehicleAssignment).filter(VehicleAssignment.vehicle_id == v.id, VehicleAssignment.status.in_(["active", "return_pending"]), VehicleAssignment.id != a.id).count(): v.pool = True
    audit(s, u, "vehicle", v.id, "returned", None, {"signed_by": u.name, "meter": rm, "damage": a.damage}); s.commit(); return asg_out(s, a)

@router.post("/api/vehicles/{vid}/update")
async def v_update(vid: int, request: Request, u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    v = get_veh(s, u, vid, "vehicles.write"); b = await request.json(); prev = {}
    try:
        for k in ("make_model",):
            if b.get(k) and b[k] != getattr(v, k): prev[k] = getattr(v, k); setattr(v, k, b[k])
        for k in ("purchase_value", "current_value", "odometer"):
            if k in b: prev[k] = getattr(v, k); setattr(v, k, pnum(b[k], k) if k != "odometer" else (pnum(b[k], k) or v.odometer))
        if "year" in b: prev["year"] = v.year; v.year = int(pnum(b["year"], "year") or 0) or None
        if "purchase_date" in b: prev["purchase_date"] = v.purchase_date; v.purchase_date = pdate(b["purchase_date"])
        if b.get("status") in ("available", "maintenance", "retired") and b["status"] != v.status: prev["status"] = v.status; v.status = b["status"]
    except ValueError as x: raise HTTPException(400, str(x))
    audit(s, u, "vehicle", vid, "update", prev, {k: getattr(v, k) for k in prev}); s.commit(); return row(v)

# ---------- insurance & compliance ----------
@router.get("/api/compliance")
def compliance(u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    V = {v.id: v for v in vscope(s, u)}; latest = {}
    for d in s.query(VehicleDocument).filter(VehicleDocument.vehicle_id.in_(list(V) or [-1])).all():
        k = (d.vehicle_id, d.doc_type)
        if k not in latest or d.version > latest[k].version: latest[k] = d
    asg = {a.vehicle_id: a for a in s.query(VehicleAssignment).filter(VehicleAssignment.status.in_(["active", "return_pending"]))}; E = {e.id: e for e in s.query(Employee)}
    return [row(d, state=doc_state(d), vehicle=V[d.vehicle_id].reg_no, vehicle_name=V[d.vehicle_id].make_model, premises_id=V[d.vehicle_id].premises_id,
                holder=(E[asg[d.vehicle_id].employee_id].name if d.vehicle_id in asg and asg[d.vehicle_id].employee_id in E else None)) for d in latest.values()]

# ---------- servicing & repairs ----------
def svc_out(s, x, V=None):
    v = (V or {}).get(x.vehicle_id) if V is not None else s.get(Vehicle, x.vehicle_id)
    return row(x, vehicle=v.reg_no if v else None, vehicle_name=v.make_model if v else None, premises_id=v.premises_id if v else None)

@router.get("/api/vehicle-services")
def services(vehicle_id: int | None = None, u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    V = {v.id: v for v in vscope(s, u)}; q = s.query(VehicleService).filter(VehicleService.vehicle_id.in_(list(V) or [-1]))
    if vehicle_id: q = q.filter(VehicleService.vehicle_id == vehicle_id)
    return [svc_out(s, x, V) for x in q.order_by(VehicleService.id.desc()).limit(300)]

@router.post("/api/vehicles/{vid}/services")
def svc_add(vid: int, kind: str = Form("scheduled"), service_date: str = Form(""), mileage: str = Form(""), issue: str = Form(""), vendor: str = Form(""), quotation_amount: str = Form(""),
            next_service_date: str = Form(""), next_service_km: str = Form(""), quotation: UploadFile | None = File(None), u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    v = get_veh(s, u, vid, "vehicles.write")
    if kind not in ("scheduled", "breakdown", "repair"): raise HTTPException(400, "Unknown type")
    if not issue.strip(): raise HTTPException(400, "Describe the service or the issue")
    try: sd, nsd = pdate(service_date), pdate(next_service_date); mi, qa, nk = pnum(mileage, "mileage"), pnum(quotation_amount, "quotation"), pnum(next_service_km, "next service km")
    except ValueError as x: raise HTTPException(400, str(x))
    x = VehicleService(vehicle_id=vid, kind=kind, service_date=sd, mileage=mi, issue=issue, vendor=vendor or None, quotation_amount=qa, quotation_file=save_upload(quotation), next_service_date=nsd,
                       next_service_km=nk, created_by=u.name, approval="pending" if qa else "none", status="awaiting_approval" if qa else "open")
    s.add(x); s.flush(); audit(s, u, "vehicle", vid, "service_requested", None, {"kind": kind, "issue": issue, "quotation": qa})
    if qa: notify(s, "service_approval", f"Quotation to approve: {v.reg_no}", f"{kind.title()}: {issue[:120]} · {qa:,.0f}", link="vehicle-services", premises_id=v.premises_id, perm="service.approve", ref=f"svc:{x.id}")
    s.commit(); return svc_out(s, x)

@router.post("/api/vehicle-services/{sid}/approve")
async def svc_approve(sid: int, request: Request, u: User = Depends(need("service.approve")), s: Session = Depends(db)):
    x = s.get(VehicleService, sid)
    if not x: raise HTTPException(404)
    v = get_veh(s, u, x.vehicle_id, "service.approve"); b = await request.json()
    if x.approval != "pending": raise HTTPException(400, "Nothing to approve")
    ok = bool(b.get("approve")); x.approval = "approved" if ok else "rejected"; x.approved_by, x.approved_on = u.name, dt.date.today(); x.status = "approved" if ok else "cancelled"
    if ok: v.status = "maintenance"
    resolve_notes(s, f"svc:{x.id}"); audit(s, u, "vehicle", v.id, "service_approved" if ok else "service_rejected", None, {"quotation": x.quotation_amount, "note": b.get("note")}); s.commit(); return svc_out(s, x)

@router.post("/api/vehicle-services/{sid}/complete")
def svc_complete(sid: int, invoice_no: str = Form(""), invoice_amount: str = Form(""), mileage: str = Form(""), next_service_date: str = Form(""), next_service_km: str = Form(""),
                 invoice: UploadFile | None = File(None), report: UploadFile | None = File(None), u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    x = s.get(VehicleService, sid)
    if not x: raise HTTPException(404)
    v = get_veh(s, u, x.vehicle_id, "vehicles.write")
    if x.approval == "pending": raise HTTPException(409, "The quotation must be approved before the work is completed")
    if x.approval == "rejected" or x.status in ("completed", "cancelled"): raise HTTPException(400, "This request is closed")
    try: ia, mi, nsd, nk = pnum(invoice_amount, "invoice amount"), pnum(mileage, "mileage"), pdate(next_service_date), pnum(next_service_km, "next service km")
    except ValueError as e: raise HTTPException(400, str(e))
    inv, rep = save_upload(invoice), save_upload(report)
    if ia is None or not (inv or invoice_no.strip()): raise HTTPException(400, "Enter the invoice amount and attach the invoice (or its number)")
    if not rep: raise HTTPException(400, "Attach the service report")
    x.invoice_no, x.invoice_amount, x.invoice_file, x.report_file, x.status, x.service_date = invoice_no or None, ia, inv, rep, "completed", x.service_date or dt.date.today()
    if mi is not None: x.mileage = mi; v.odometer = max(v.odometer, mi)
    if nsd: x.next_service_date = nsd
    if nk: x.next_service_km = nk
    if not s.query(VehicleService).filter(VehicleService.vehicle_id == v.id, VehicleService.status == "approved", VehicleService.id != x.id).count(): v.status = "available"
    audit(s, u, "vehicle", v.id, "service_completed", None, {"invoice": ia, "next": x.next_service_date}); s.commit(); return svc_out(s, x)

# ---------- accidents & incidents ----------
def inc_out(s, i, V=None):
    v = (V or {}).get(i.vehicle_id) if V is not None else s.get(Vehicle, i.vehicle_id)
    return row(i, vehicle=v.reg_no if v else None, vehicle_name=v.make_model if v else None, premises_id=v.premises_id if v else None)

def create_incident(s, v, who, via, kind, when, location, description, injuries, police, estimate, photos, docs, doc_kind):
    try: at = dt.datetime.fromisoformat(when) if when else dt.datetime.utcnow()
    except ValueError: raise HTTPException(400, "Bad incident date")
    if kind not in ("accident", "damage", "theft", "breakdown"): raise HTTPException(400, "Unknown incident type")
    if not description.strip(): raise HTTPException(400, "Describe what happened")
    i = Incident(vehicle_id=v.id, incident_at=at, kind=kind, location=location or None, description=description, injuries=bool(injuries), police_report_no=police or None,
                 repair_estimate=pnum(estimate, "estimate") if estimate else None, reported_by=who, reported_via=via)
    s.add(i); s.flush()
    for f in photos or []:
        n = save_upload(f)
        if n: s.add(IncidentFile(incident_id=i.id, kind="photo", file=n))
    for f in docs or []:
        n = save_upload(f)
        if n: s.add(IncidentFile(incident_id=i.id, kind=doc_kind if doc_kind in ("police", "insurance", "estimate", "other") else "other", file=n))
    notify(s, "incident", f"{kind.title()} reported: {v.reg_no}", f"{who} via {via.replace('_', ' ')}: {description[:140]}", link=f"incidents", premises_id=v.premises_id, perm="vehicles.write", ref=f"inc:{i.id}")
    return i

@router.get("/api/incidents")
def incidents(vehicle_id: int | None = None, u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    V = {v.id: v for v in vscope(s, u)}; q = s.query(Incident).filter(Incident.vehicle_id.in_(list(V) or [-1]))
    if vehicle_id: q = q.filter(Incident.vehicle_id == vehicle_id)
    cnt = dict(s.query(IncidentFile.incident_id, func.count()).group_by(IncidentFile.incident_id).all())
    return [{**inc_out(s, i, V), "files": cnt.get(i.id, 0)} for i in q.order_by(Incident.id.desc()).limit(300)]

@router.get("/api/incidents/{iid}")
def incident(iid: int, u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    i = s.get(Incident, iid)
    if not i: raise HTTPException(404)
    get_veh(s, u, i.vehicle_id)
    return {"incident": inc_out(s, i), "files": [row(f) for f in s.query(IncidentFile).filter_by(incident_id=iid)]}

@router.post("/api/incidents")
def incident_add(vehicle_id: int = Form(...), kind: str = Form("accident"), incident_at: str = Form(""), location: str = Form(""), description: str = Form(""), injuries: str = Form(""),
                 police_report_no: str = Form(""), repair_estimate: str = Form(""), doc_kind: str = Form("police"), photos: list[UploadFile] = File(default=[]), docs: list[UploadFile] = File(default=[]),
                 u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    v = get_veh(s, u, vehicle_id, "vehicles.write")
    i = create_incident(s, v, u.name, "web", kind, incident_at, location, description, injuries, police_report_no, repair_estimate, photos, docs, doc_kind)
    audit(s, u, "vehicle", v.id, "incident_reported", None, {"kind": kind, "description": description[:100]}); s.commit(); return inc_out(s, i)

@router.post("/api/driver/incidents")
def driver_incident(vehicle_id: int = Form(...), kind: str = Form("accident"), location: str = Form(""), description: str = Form(""), injuries: str = Form(""),
                    photos: list[UploadFile] = File(default=[]), u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    v = s.get(Vehicle, vehicle_id)
    if not v or v.company_id not in [g.scope_id for g in u.grants if g.role == "driver"]: raise HTTPException(404, "Vehicle not found")
    i = create_incident(s, v, u.name, "driver_app", kind, "", location, description, injuries, "", "", photos, [], "other")
    audit(s, u, "vehicle", v.id, "incident_reported", None, {"kind": kind, "via": "driver_app"}); s.commit(); return {"id": i.id}

@router.post("/api/incidents/{iid}/update")
async def incident_update(iid: int, request: Request, u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    i = s.get(Incident, iid)
    if not i: raise HTTPException(404)
    get_veh(s, u, i.vehicle_id, "vehicles.write"); b = await request.json(); prev = {}
    try:
        for k, ok in (("status", ("open", "under_review", "closed")), ("claim_status", ("none", "filed", "approved", "rejected", "paid"))):
            if b.get(k) in ok and b[k] != getattr(i, k): prev[k] = getattr(i, k); setattr(i, k, b[k])
        for k in ("claim_ref", "police_report_no"):
            if k in b and (b[k] or None) != getattr(i, k): prev[k] = getattr(i, k); setattr(i, k, (b[k] or "").strip() or None)
        if "repair_estimate" in b: prev["repair_estimate"] = i.repair_estimate; i.repair_estimate = pnum(b["repair_estimate"], "estimate")
    except ValueError as x: raise HTTPException(400, str(x))
    if i.status == "closed": resolve_notes(s, f"inc:{i.id}")
    audit(s, u, "vehicle", i.vehicle_id, "incident_updated", prev, {k: getattr(i, k) for k in prev}); s.commit(); return inc_out(s, i)

@router.post("/api/incidents/{iid}/files")
def incident_files(iid: int, kind: str = Form("photo"), note: str = Form(""), files: list[UploadFile] = File(...), u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    i = s.get(Incident, iid)
    if not i: raise HTTPException(404)
    get_veh(s, u, i.vehicle_id, "vehicles.write"); n = 0
    for f in files:
        name = save_upload(f)
        if name: s.add(IncidentFile(incident_id=iid, kind=kind if kind in ("photo", "police", "insurance", "estimate", "other") else "other", file=name, note=note or None)); n += 1
    audit(s, u, "vehicle", i.vehicle_id, "incident_files_added", None, {"count": n}); s.commit(); return {"added": n}

# ---------- summary for the dashboard ----------
def fleet_summary(s, u):
    if not can(u, "vehicles.read"): return None
    V = {v.id: v for v in vscope(s, u)}; ids = list(V) or [-1]; t = dt.date.today()
    return {"returns_pending": s.query(VehicleAssignment).filter(VehicleAssignment.vehicle_id.in_(ids), VehicleAssignment.status == "return_pending").count(),
            "services_pending_approval": s.query(VehicleService).filter(VehicleService.vehicle_id.in_(ids), VehicleService.approval == "pending").count(),
            "services_due": s.query(VehicleService).filter(VehicleService.vehicle_id.in_(ids), VehicleService.status == "completed", VehicleService.next_service_date.isnot(None), VehicleService.next_service_date <= t + dt.timedelta(days=14)).count(),
            "open_incidents": s.query(Incident).filter(Incident.vehicle_id.in_(ids), Incident.status != "closed").count()}

# ---------- demo data ----------
def seed_phase5(s):
    if s.query(VehicleAssignment).first() or s.query(VehicleService).first(): return
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n)
    V = {v.reg_no: v for v in s.query(Vehicle)}; E = {e.emp_code: e for e in s.query(Employee)}
    if not V or not E: return
    inn, dzi, hil = V.get("GJ01AB1234"), V.get("GJ01CD5678"), V.get("KDG 123X")
    for v, cv, ins, cost in ((inn, 2050000, "ICICI Lombard", 62000), (dzi, 620000, "New India Assurance", 21000), (hil, 3400000, "Jubilee Insurance", 190000)):
        if not v: continue
        v.current_value = cv
        for d in s.query(VehicleDocument).filter_by(vehicle_id=v.id):
            if d.doc_type == "insurance": d.authority, d.renewal_cost = ins, cost
            elif d.doc_type in ("registration", "fitness", "pollution"): d.authority = d.authority or ("RTO" if v.company_id == 1 else "NTSA")
    if inn: s.add(VehicleAssignment(vehicle_id=inn.id, employee_id=E["JT1003"].id, from_date=D(-40), purpose="Senior management vehicle", issue_condition="Good, minor scratch on rear bumper", issue_meter=inn.odometer - 900, issue_fuel="3/4", created_by="demo seed", status="active")); inn.pool = False
    if dzi and "JT1008" in E:   # JT1008 is on notice: shows the leaver alert and the return queue
        s.add(VehicleAssignment(vehicle_id=dzi.id, employee_id=E["JT1008"].id, from_date=D(-200), purpose="Daily commute", issue_condition="Good", issue_meter=dzi.odometer - 6100, issue_fuel="Full", created_by="demo seed", status="return_pending")); dzi.pool = False
        e = E["JT1008"]; notify(s, "leaver", f"{e.name} ({e.emp_code}) is leaving: notice", f"Vehicle {dzi.reg_no} to be returned", link="handovers", premises_id=e.premises_id, perm="employees.write", ref=f"leaver:{e.id}")
    if hil and "AK2001" in E: s.add(VehicleAssignment(vehicle_id=hil.id, employee_id=E["AK2001"].id, from_date=D(-120), purpose="Country manager", issue_condition="Good", issue_meter=hil.odometer - 2200, issue_fuel="Full", created_by="demo seed", status="active")); hil.pool = False
    if inn:
        s.add(VehicleService(vehicle_id=inn.id, kind="scheduled", service_date=D(-70), mileage=inn.odometer - 2100, issue="10,000 km service", vendor="Toyota Service Centre", invoice_no="TSC-8841", invoice_amount=14800, status="completed", approval="none",
                             next_service_date=D(12), next_service_km=inn.odometer + 7900, created_by="demo seed", report_file=None))
    if dzi:
        s.add(VehicleService(vehicle_id=dzi.id, kind="repair", service_date=D(-2), mileage=dzi.odometer, issue="Brake pads and rotor replacement", vendor="Maruti Authorised Workshop", quotation_amount=26500, approval="pending", status="awaiting_approval", created_by="demo seed"))
        s.flush(); sv = s.query(VehicleService).filter_by(vehicle_id=dzi.id, status="awaiting_approval").first()
        notify(s, "service_approval", f"Quotation to approve: {dzi.reg_no}", "Repair: Brake pads and rotor replacement · 26,500", link="vehicle-services", premises_id=dzi.premises_id, perm="service.approve", ref=f"svc:{sv.id}")
    if hil: s.add(VehicleService(vehicle_id=hil.id, kind="breakdown", service_date=D(-25), mileage=hil.odometer - 300, issue="Clutch failure", vendor="Toyota Kenya", quotation_amount=88000, approval="approved", approved_by="Corporate Admin Head", approved_on=D(-24), invoice_no="TK-2210", invoice_amount=86400, status="completed", created_by="demo seed"))
    if dzi:
        i = Incident(vehicle_id=dzi.id, incident_at=dt.datetime.utcnow() - dt.timedelta(days=18), kind="accident", location="SG Highway, Ahmedabad", description="Rear-ended at a signal. Bumper and tail lamp damaged, no injuries.", injuries=False,
                     police_report_no="FIR-2026-4471", claim_ref="CLM-ICICI-7720", claim_status="filed", repair_estimate=34000, status="under_review", reported_by="Ravi Kumar (Driver)", reported_via="driver_app"); s.add(i)
    s.commit()

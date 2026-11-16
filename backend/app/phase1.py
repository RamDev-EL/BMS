"""Phase 1: onboarding (group admin, one-time), admin asset register + maintenance, tickets, and the
integration API that a future asset-management / ticketing system can use to merge data."""
import os, hmac, datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, Header, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import *
from .core import *

router = APIRouter()

ASSET_CATS = ["furniture", "electrical", "hvac", "it", "plumbing", "fire_safety", "appliance", "security", "building", "other"]
TICKET_CATS = ASSET_CATS + ["housekeeping", "vehicle", "utilities"]
PRIORITY_HOURS = {"critical": 4, "high": 24, "medium": 72, "low": 168}
STATUSES = ["open", "assigned", "in_progress", "on_hold", "resolved", "closed"]
OPEN = ["open", "assigned", "in_progress", "on_hold"]
PTYPES = {"office": "office", "guest house": "guest_house", "guest_house": "guest_house", "guesthouse": "guest_house",
          "branch": "branch", "hospital": "hospital", "hospital office": "hospital"}

def descendants(s, pid):
    rows = s.query(Premises.id, Premises.parent_id).all(); out, st = set(), [pid]
    while st:
        x = st.pop(); out.add(x); st += [r.id for r in rows if r.parent_id == x]
    return out

def in_scope(s, u, perm, pid):
    if not can(u, perm): return False
    ids = scope_premises(s, u, perm)
    return ids is None or pid in ids

def scoped(s, u, model, perm, premises_id=None):
    q = s.query(model); ids = scope_premises(s, u, perm)
    if ids is not None: q = q.filter(model.premises_id.in_(ids or {-1}))
    if premises_id: q = q.filter(model.premises_id.in_(descendants(s, premises_id)))
    return q

def pdate(v):
    if v in (None, ""): return None
    if isinstance(v, (dt.date,)): return v
    v = str(v).strip()
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try: return dt.datetime.strptime(v, f).date()
        except ValueError: pass
    raise ValueError(f"Bad date '{v}' (use YYYY-MM-DD)")

def pnum(v, what="number"):
    if v in (None, ""): return None
    try: return float(str(v).replace(",", ""))
    except ValueError: raise ValueError(f"Bad {what} '{v}'")

def cat(v, allowed=ASSET_CATS):
    v = (v or "other").strip().lower().replace(" ", "_").replace("&", "").replace("/", "_")
    return v if v in allowed else "other"

def next_due(interval, last):
    if not interval: return None
    return (last or dt.date.today()) + dt.timedelta(days=int(interval))

def make_asset(s, p, b):
    interval = int(pnum(b.get("service_interval_days"), "interval") or 0) or None
    last = pdate(b.get("last_service_date"))
    a = Asset(company_id=p.company_id, premises_id=p.id, name=str(b["name"]).strip(), category=cat(b.get("category")),
              make_model=b.get("make_model") or None, serial_no=(b.get("serial_no") or None), location=b.get("location") or None,
              purchase_date=pdate(b.get("purchase_date")), purchase_value=pnum(b.get("purchase_value"), "value"),
              warranty_to=pdate(b.get("warranty_to")), vendor=b.get("vendor") or None,
              condition=(b.get("condition") or "good").lower() if (b.get("condition") or "good").lower() in ("good", "fair", "poor") else "good",
              status=b.get("status") if b.get("status") in ("in_service", "under_maintenance", "retired") else "in_service",
              service_interval_days=interval, last_service_date=last, next_service_due=next_due(interval, last),
              notes=b.get("notes") or None, external_source=b.get("external_source") or None, external_id=b.get("external_id") or None)
    s.add(a); s.flush(); a.asset_tag = f"AST-{a.id:05d}"
    return a

def asset_out(a):
    t = dt.date.today()
    st = None if not a.next_service_due else "overdue" if a.next_service_due < t else "due_soon" if (a.next_service_due - t).days <= 14 else "ok"
    w = None if not a.warranty_to else "expired" if a.warranty_to < t else "expiring" if (a.warranty_to - t).days <= 30 else "ok"
    return row(a, service_state=st, warranty_state=w)

# ======================= summary (dashboard KPIs & notifications) =======================
@router.get("/api/summary")
def summary(premises_id: int | None = None, u: User = Depends(current_user), s: Session = Depends(db)):
    out, t, now_ = {"assets": None, "tickets": None}, dt.date.today(), dt.datetime.utcnow()
    if can(u, "assets.read"):
        A = scoped(s, u, Asset, "assets.read", premises_id).filter(Asset.status != "retired").all()
        out["assets"] = {"total": len(A), "service_overdue": sum(1 for a in A if a.next_service_due and a.next_service_due < t),
                         "service_soon": sum(1 for a in A if a.next_service_due and 0 <= (a.next_service_due - t).days <= 14),
                         "warranty_expiring": sum(1 for a in A if a.warranty_to and 0 <= (a.warranty_to - t).days <= 30),
                         "under_maintenance": sum(1 for a in A if a.status == "under_maintenance"), "poor": sum(1 for a in A if a.condition == "poor")}
    if can(u, "tickets.read"):
        T = scoped(s, u, Ticket, "tickets.read", premises_id).filter(Ticket.status.in_(OPEN)).all()
        out["tickets"] = {"open": len(T), "unassigned": sum(1 for x in T if x.status == "open"),
                          "critical": sum(1 for x in T if x.priority in ("critical", "high")),
                          "overdue": sum(1 for x in T if x.due_at and x.due_at < now_)}
    from .phase2 import people_summary, hrms_summary
    out["people"] = people_summary(s, u, premises_id) if can(u, "employees.read") else None
    out["hrms"] = hrms_summary(s) if (can(u, "dashboard") or can(u, "employees.read")) else None
    from .phase4 import docs_summary, util_summary
    from .phase5 import fleet_summary
    out["docs"], out["utilities"], out["fleet"] = docs_summary(s, u), util_summary(s, u), fleet_summary(s, u)
    return out

# ======================= assets =======================
@router.get("/api/assets")
def assets(premises_id: int | None = None, u: User = Depends(need("assets.read")), s: Session = Depends(db)):
    return [asset_out(a) for a in scoped(s, u, Asset, "assets.read", premises_id).order_by(Asset.asset_tag)]

@router.post("/api/assets")
async def add_asset(request: Request, u: User = Depends(need("assets.write")), s: Session = Depends(db)):
    b = await request.json(); p = s.get(Premises, b.get("premises_id"))
    if not p or not in_scope(s, u, "assets.write", p.id): raise HTTPException(403, "Premises outside your scope")
    if not (b.get("name") or "").strip(): raise HTTPException(400, "Asset name is required")
    try: a = make_asset(s, p, b)
    except ValueError as e: raise HTTPException(400, str(e))
    audit(s, u, "asset", a.id, "create", None, row(a)); s.commit(); return asset_out(a)

def get_asset(s, u, aid, perm="assets.read"):
    a = scoped(s, u, Asset, perm).filter(Asset.id == aid).first()
    if not a: raise HTTPException(404, "Asset not found in your scope")
    return a

@router.get("/api/assets/{aid}")
def asset_detail(aid: int, u: User = Depends(need("assets.read")), s: Session = Depends(db)):
    a = get_asset(s, u, aid)
    sv = s.query(AssetService).filter_by(asset_id=aid).order_by(AssetService.on.desc(), AssetService.id.desc()).all()
    tk = [row(t) for t in s.query(Ticket).filter_by(asset_id=aid).order_by(Ticket.id.desc()).limit(50)] if can(u, "tickets.read") else []
    return {"asset": asset_out(a), "services": [row(x) for x in sv], "tickets": tk}

@router.post("/api/assets/{aid}/update")
async def update_asset(aid: int, request: Request, u: User = Depends(need("assets.write")), s: Session = Depends(db)):
    a = get_asset(s, u, aid, "assets.write"); b = await request.json(); prev = {}
    try:
        for k in ("name", "make_model", "serial_no", "location", "vendor", "notes"):
            if k in b and b[k] != getattr(a, k): prev[k] = getattr(a, k); setattr(a, k, b[k] or None if k != "name" else b[k])
        if "category" in b: prev["category"] = a.category; a.category = cat(b["category"])
        for k in ("condition",):
            if b.get(k) in ("good", "fair", "poor") and b[k] != a.condition: prev[k] = a.condition; a.condition = b[k]
        if b.get("status") in ("in_service", "under_maintenance", "retired") and b["status"] != a.status: prev["status"] = a.status; a.status = b["status"]
        for k in ("purchase_date", "warranty_to", "next_service_due"):
            if k in b: prev[k] = getattr(a, k); setattr(a, k, pdate(b[k]))
        if "purchase_value" in b: prev["purchase_value"] = a.purchase_value; a.purchase_value = pnum(b["purchase_value"])
        if "service_interval_days" in b:
            a.service_interval_days = int(pnum(b["service_interval_days"]) or 0) or None
            if "next_service_due" not in b: a.next_service_due = next_due(a.service_interval_days, a.last_service_date)
    except ValueError as e: raise HTTPException(400, str(e))
    audit(s, u, "asset", a.id, "update", prev, {k: getattr(a, k) for k in prev}); s.commit(); return asset_out(a)

@router.post("/api/assets/{aid}/service")
async def log_service(aid: int, request: Request, u: User = Depends(need("assets.service")), s: Session = Depends(db)):
    a = get_asset(s, u, aid, "assets.service"); b = await request.json()
    try: on = pdate(b.get("on")) or dt.date.today(); cost = pnum(b.get("cost"), "cost")
    except ValueError as e: raise HTTPException(400, str(e))
    kind = b.get("kind") if b.get("kind") in ("preventive", "repair", "inspection") else "preventive"
    sv = AssetService(asset_id=a.id, on=on, kind=kind, cost=cost, vendor=b.get("vendor") or None, notes=b.get("notes") or None,
                      ticket_id=b.get("ticket_id"), by_name=u.name)
    s.add(sv); prev = {"last_service_date": a.last_service_date, "next_service_due": a.next_service_due, "status": a.status}
    if not a.last_service_date or on >= a.last_service_date: a.last_service_date = on
    a.next_service_due = next_due(a.service_interval_days, a.last_service_date)
    if a.status == "under_maintenance": a.status = "in_service"
    if b.get("condition") in ("good", "fair", "poor"): a.condition = b["condition"]
    s.flush(); audit(s, u, "asset", a.id, "service_logged", prev, {"kind": kind, "on": on, "cost": cost, "next_service_due": a.next_service_due})
    s.commit(); return row(sv)

# ======================= tickets =======================
def ticket_out(s, t, assets=None):
    a = (assets or {}).get(t.asset_id) if assets is not None else (s.get(Asset, t.asset_id) if t.asset_id else None)
    return row(t, ticket_no=f"TK-{t.id:04d}", asset_tag=a.asset_tag if a else None, asset_name=a.name if a else None)

def event(s, t, u, kind, text):
    s.add(TicketEvent(ticket_id=t.id, user_id=u.id if u else None, user_name=u.name if u else "system", kind=kind, text=text))

@router.get("/api/tickets")
def tickets(premises_id: int | None = None, u: User = Depends(need("tickets.read")), s: Session = Depends(db)):
    am = {a.id: a for a in s.query(Asset).all()}
    return [ticket_out(s, t, am) for t in scoped(s, u, Ticket, "tickets.read", premises_id).order_by(Ticket.id.desc())]

@router.post("/api/tickets")
async def raise_ticket(request: Request, u: User = Depends(need("tickets.raise")), s: Session = Depends(db)):
    b = await request.json(); a = s.get(Asset, b["asset_id"]) if b.get("asset_id") else None
    ut = s.get(UtilityAccount, b["utility_id"]) if b.get("utility_id") else None
    p = s.get(Premises, a.premises_id if a else (ut.premises_id if ut else b.get("premises_id")))
    if not p or not in_scope(s, u, "tickets.raise", p.id): raise HTTPException(403, "Premises outside your scope")
    if not (b.get("title") or "").strip(): raise HTTPException(400, "A short title is required")
    pr = b.get("priority") if b.get("priority") in PRIORITY_HOURS else "medium"
    t = Ticket(company_id=p.company_id, premises_id=p.id, asset_id=a.id if a else None, category=cat(b.get("category") or (a.category if a else None), TICKET_CATS),
               title=b["title"].strip(), description=b.get("description") or None, priority=pr, raised_by=u.id, raised_by_name=u.name,
               due_at=dt.datetime.utcnow() + dt.timedelta(hours=PRIORITY_HOURS[pr]), utility_id=ut.id if ut else None)
    s.add(t); s.flush(); event(s, t, u, "created", f"Raised by {u.name} · priority {pr}")
    if a and b.get("mark_under_maintenance"): a.status = "under_maintenance"
    audit(s, u, "ticket", t.id, "create", None, {"title": t.title, "priority": pr, "premises_id": p.id, "asset_id": t.asset_id}); s.commit()
    return ticket_out(s, t)

def get_ticket(s, u, tid):
    t = scoped(s, u, Ticket, "tickets.read").filter(Ticket.id == tid).first()
    if not t: raise HTTPException(404, "Ticket not found in your scope")
    return t

@router.get("/api/tickets/{tid}")
def ticket_detail(tid: int, u: User = Depends(need("tickets.read")), s: Session = Depends(db)):
    t = get_ticket(s, u, tid)
    ev = s.query(TicketEvent).filter_by(ticket_id=tid).order_by(TicketEvent.id).all()
    ut = s.get(UtilityAccount, t.utility_id) if t.utility_id else None
    return {"ticket": ticket_out(s, t), "events": [row(e) for e in ev], "utility": row(ut) if ut else None,
            "can_manage": in_scope(s, u, "tickets.manage", t.premises_id), "can_raise": in_scope(s, u, "tickets.raise", t.premises_id)}

@router.post("/api/tickets/{tid}/update")
async def update_ticket(tid: int, request: Request, u: User = Depends(need("tickets.read")), s: Session = Depends(db)):
    t = get_ticket(s, u, tid); b = await request.json()
    mgr, rsr = in_scope(s, u, "tickets.manage", t.premises_id), in_scope(s, u, "tickets.raise", t.premises_id)
    prev = {"status": t.status, "assigned_to": t.assigned_to}
    new_status, assignee = b.get("status"), (b.get("assigned_to") or "").strip()
    if assignee and assignee != (t.assigned_to or ""):
        if not mgr: raise HTTPException(403, "Only the maintenance team can assign tickets")
        t.assigned_to = assignee; event(s, t, u, "assign", f"Assigned to {assignee}")
        if t.status == "open" and not new_status: new_status = "assigned"
    if new_status and new_status != t.status:
        if new_status not in STATUSES: raise HTTPException(400, "Unknown status")
        if mgr:
            if new_status == "resolved" and not (b.get("resolution") or "").strip(): raise HTTPException(400, "Describe the resolution before resolving")
            if new_status == "assigned" and not t.assigned_to: raise HTTPException(400, "Enter who it is assigned to")
        elif rsr and t.status in ("resolved", "closed") and new_status in ("closed", "open"):
            pass   # the admin in-charge confirms the fix (close) or reopens it
        else: raise HTTPException(403, "You can't make that change")
        t.status = new_status
        if new_status == "resolved": t.resolved_at = dt.datetime.utcnow(); t.resolution = b.get("resolution").strip()
        if new_status == "closed": t.closed_at = dt.datetime.utcnow()
        if new_status == "open": t.resolved_at = t.closed_at = None
        event(s, t, u, "status", f"Status → {new_status.replace('_', ' ')}" + (f": {b['resolution'].strip()}" if new_status == "resolved" else ""))
        if new_status == "resolved" and t.asset_id and (a := s.get(Asset, t.asset_id)) and a.status == "under_maintenance": a.status = "in_service"
    if (c := (b.get("comment") or "").strip()): event(s, t, u, "comment", c)
    audit(s, u, "ticket", t.id, "update", prev, {"status": t.status, "assigned_to": t.assigned_to}); s.commit()
    return ticket_out(s, t)

# ======================= onboarding (Group Admin, one-time) =======================
@router.get("/api/onboarding/status")
def onboarding_status(u: User = Depends(need("onboarding")), s: Session = Depends(db)):
    vc = dict(s.query(Vehicle.premises_id, func.count()).group_by(Vehicle.premises_id).all())
    ac = dict(s.query(Asset.premises_id, func.count()).group_by(Asset.premises_id).all())
    ec = dict(s.query(Employee.premises_id, func.count()).group_by(Employee.premises_id).all())
    inch = {}
    for g, name in s.query(RoleGrant, User.name).join(User, User.id == RoleGrant.user_id).filter(RoleGrant.role == "premises_admin", RoleGrant.scope_level == "premises", User.active):
        inch.setdefault(g.scope_id, []).append(name)
    return {"premises": [{"id": p.id, "name": p.name, "parent_id": p.parent_id, "type": p.type, "company_id": p.company_id,
                          "vehicles": vc.get(p.id, 0), "assets": ac.get(p.id, 0), "employees": ec.get(p.id, 0), "incharge": inch.get(p.id, [])}
                         for p in s.query(Premises).order_by(Premises.name)],
            "totals": {"employees": s.query(Employee).count(), "premises": s.query(Premises).count(), "vehicles": s.query(Vehicle).count(), "assets": s.query(Asset).count()}}

def _norm(r): return {str(k).strip().lower().replace(" ", "_").replace("*", ""): (str(v).strip() if v is not None else "") for k, v in r.items()}
def _req(r, k):
    if not r.get(k): raise ValueError(f"'{k}' is required")
    return r[k]

KIND_PERM = {"premises": "premises.write", "employees": "employees.write", "vehicles": "vehicles.write", "assets": "assets.write", "travel_policy": "travel.policy", "visas": "travel.write"}
KIND_LABEL = {"premises": "Premises", "employees": "Employees", "vehicles": "Vehicles", "assets": "Assets", "travel_policy": "Travel policy", "visas": "Visas"}

def import_ctx(s):
    return {"comps": {c.name.lower(): c for c in s.query(Company)}, "prem": {p.name.lower(): p for p in s.query(Premises)},
            "regs": {v.reg_no for v in s.query(Vehicle.reg_no)}, "serials": {(a.company_id, (a.serial_no or "").lower()) for a in s.query(Asset) if a.serial_no}}

def run_import(s, u, kind, rows, ctx):
    """rows: list of (row_number, dict). Adds to the session only; the caller commits or rolls back."""
    comps, prem, regs, serials = ctx["comps"], ctx["prem"], ctx["regs"], ctx["serials"]
    errors, skipped, notes, created = [], [], [], 0
    if rows and not can(u, KIND_PERM[kind]):
        return {"rows": len(rows), "created": 0, "skipped": [], "errors": [{"row": rows[0][0], "msg": f"You don't have permission to import {KIND_LABEL[kind].lower()}"}], "notes": []}
    for i, r in rows:
        try:
            if not any(r.values()): continue
            if kind == "premises":
                name = _req(r, "name")
                if name.lower() in prem: skipped.append({"row": i, "msg": f"'{name}' already exists"}); continue
                parent = None
                if r.get("parent"):
                    parent = prem.get(r["parent"].lower())
                    if not parent: raise ValueError(f"Parent '{r['parent']}' not found. List parent premises above their children.")
                    comp = s.get(Company, parent.company_id)
                    if not in_scope(s, u, "premises.write", parent.id): raise ValueError("Parent premises is outside your scope")
                else:
                    if not can(u, "onboarding"): raise ValueError("Only a Group Admin can add a top-level site. Give a parent premises.")
                    cn = _req(r, "company"); comp = comps.get(cn.lower())
                    if not comp:
                        comp = Company(name=cn, country=r.get("country") or "India", currency=(r.get("currency") or "INR").upper()[:3])
                        s.add(comp); s.flush(); comps[cn.lower()] = comp; notes.append(f"New company will be created: {cn}")
                tp = PTYPES.get(r.get("type", "").lower(), "guest_house" if parent and "guest" in name.lower() else "office")
                p = Premises(company_id=comp.id, parent_id=parent.id if parent else None, name=name, type=tp, address=r.get("address") or None)
                s.add(p); s.flush(); prem[name.lower()] = p; audit(s, u, "premises", p.id, "create", None, row(p)); created += 1
                continue
            if kind == "travel_policy":
                g = _req(r, "grade"); tp = s.query(TravelPolicy).filter(func.lower(TravelPolicy.grade) == g.lower()).first() or TravelPolicy(grade=g)
                tp.currency, tp.flight_class = (r.get("currency") or "INR").upper()[:3], r.get("flight_class") or None
                for k in ("hotel_a", "hotel_b", "hotel_c", "daily_allowance", "advance_limit"): setattr(tp, k, pnum(r.get(k), k))
                s.add(tp); s.flush(); created += 1; continue
            if kind == "visas":
                e = s.query(Employee).filter_by(emp_code=_req(r, "employee_code")).first()
                if not e: raise ValueError(f"Employee '{r['employee_code']}' not found. Add them on the Employees sheet first.")
                if not in_scope(s, u, "travel.write", e.premises_id): raise ValueError(f"{e.name} is outside your scope")
                if r.get("passport_no") and not can(u, "visa.restricted"): raise ValueError("Only HR and the Travel Desk can load passport details")
                s.add(TravelVisa(employee_id=e.id, kind=(r.get("kind") or "visa").lower().replace(" ", "_") if (r.get("kind") or "visa").lower().replace(" ", "_") in ("visa", "work_permit", "special_pass") else "visa", country=_req(r, "country"),
                                 passport_no=r.get("passport_no") or None, application_ref=r.get("application_ref") or None, status=(r.get("status") or "applied").lower() if (r.get("status") or "applied").lower() in ("draft", "applied", "approved", "rejected", "expired") else "applied",
                                 applied_on=pdate(r.get("applied_on")), valid_to=pdate(r.get("valid_to")), created_by=u.name)); s.flush(); created += 1; continue
            p = prem.get(_req(r, "premises").lower())
            if not p: raise ValueError(f"Premises '{r['premises']}' not found. Add it on the Premises sheet first.")
            if not in_scope(s, u, KIND_PERM[kind], p.id): raise ValueError(f"Premises '{p.name}' is outside your scope")
            if kind == "employees":
                from .phase2 import make_employee
                if s.query(Employee).filter_by(company_id=p.company_id, emp_code=_req(r, "emp_code")).first(): skipped.append({"row": i, "msg": f"Employee {r['emp_code']} already exists"}); continue
                e = make_employee(s, p, r, "import"); audit(s, u, "employee", e.id, "create", None, row(e)); created += 1
            elif kind == "vehicles":
                reg = _req(r, "reg_no").upper(); mm = _req(r, "make_model")
                if reg in regs: skipped.append({"row": i, "msg": f"{reg} already exists"}); continue
                yr = pnum(r.get("year"), "year"); v = Vehicle(company_id=p.company_id, premises_id=p.id, reg_no=reg, make_model=mm,
                             year=int(yr) if yr else None, odometer=pnum(r.get("odometer"), "odometer") or 0,
                             purchase_date=pdate(r.get("purchase_date")), purchase_value=pnum(r.get("purchase_value"), "value"))
                s.add(v); s.flush(); regs.add(reg); audit(s, u, "vehicle", v.id, "create", None, row(v)); created += 1
            else:
                _req(r, "name"); sn = (r.get("serial_no") or "").lower()
                if sn and (p.company_id, sn) in serials: skipped.append({"row": i, "msg": f"Serial {r['serial_no']} already registered"}); continue
                a = make_asset(s, p, r)
                if sn: serials.add((p.company_id, sn))
                audit(s, u, "asset", a.id, "create", None, row(a)); created += 1
        except ValueError as e: errors.append({"row": i, "msg": str(e)})
    return {"rows": len(rows), "created": created, "skipped": skipped, "errors": errors, "notes": notes}

@router.post("/api/onboarding/{kind}")
async def onboard(kind: str, request: Request, u: User = Depends(current_user), s: Session = Depends(db)):
    if kind not in KIND_PERM: raise HTTPException(404)
    b = await request.json(); rows = [(i, _norm(r)) for i, r in enumerate(b.get("rows", [])[:2000], start=2)]
    res = run_import(s, u, kind, rows, import_ctx(s)); ok = bool(b.get("commit")) and not res["errors"]
    s.commit() if ok else s.rollback()
    return {**res, "committed": ok}

# ---------- Excel template + workbook upload ----------
SHEETS = {
 "premises": (["company", "name", "type", "parent", "address", "country", "currency"], {"company", "name"},
              ["(example) Jiva Technologies", "Corporate Office, Bengaluru", "office", "", "MG Road, Bengaluru", "India", "INR"],
              "Top-level sites need a company. Guest houses and sub-premises need the parent building's name instead. List a parent above its children."),
 "employees": (["premises", "emp_code", "name", "grade", "designation", "department", "email", "phone", "status", "join_date"], {"premises", "emp_code", "name"},
               ["(example) Corporate Office, Bengaluru", "JT2001", "Priya Sharma", "M2", "Manager", "HR", "priya@example.org", "", "active", "2021-07-01"],
               "The premises is the building the employee is mapped to. Status: active, on_leave, notice, resigned, inactive."),
 "vehicles": (["premises", "reg_no", "make_model", "year", "odometer", "purchase_date", "purchase_value"], {"premises", "reg_no", "make_model"},
              ["(example) Corporate Office, Bengaluru", "KA01AB1234", "Toyota Innova Crysta", "2023", "18250", "2023-04-01", "2400000"],
              "Insurance, fitness and other documents are uploaded on the vehicle afterwards."),
 "travel_policy": (["grade", "currency", "flight_class", "hotel_a", "hotel_b", "hotel_c", "daily_allowance", "advance_limit"], {"grade"},
              ["(example) M2", "INR", "economy", "7500", "5800", "4200", "1800", "40000"],
              "One row per grade. hotel_a, hotel_b, hotel_c are the nightly limits for city grades A, B and C. Existing grades are updated."),
 "visas": (["employee_code", "kind", "country", "passport_no", "application_ref", "status", "applied_on", "valid_to"], {"employee_code", "country"},
           ["(example) JT1004", "visa", "United Arab Emirates", "Z7654321", "UAE-77102", "applied", "2026-11-01", "2027-02-01"],
           "kind: visa, work_permit or special_pass. Passport numbers can be loaded by HR and the Travel Desk only."),
 "assets": (["premises", "name", "category", "make_model", "serial_no", "location", "purchase_date", "purchase_value", "warranty_to", "vendor", "service_interval_days", "last_service_date", "condition"],
            {"premises", "name"}, ["(example) Guest House 1", "Solar water heater", "plumbing", "Racold 200L", "RC-2231", "Terrace", "2023-02-10", "54000", "2026-02-10", "Racold AMC", "180", "2026-08-01", "good"],
            "Set service_interval_days (for example 90) to schedule routine maintenance. Leave it empty if the asset needs none."),
}
LISTS = {"type": ["office", "guest house", "branch", "hospital"], "status": ["active", "on_leave", "notice", "resigned", "inactive"],
         "category": ASSET_CATS, "condition": ["good", "fair", "poor"]}

@router.get("/api/templates/workbook.xlsx")
def template(sheet: str = "all", u: User = Depends(current_user), s: Session = Depends(db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    from fastapi.responses import Response
    import io
    if not any(can(u, p) for p in KIND_PERM.values()): raise HTTPException(403, "No permission to use the import template")
    kinds = list(SHEETS) if sheet == "all" else [sheet]
    if any(k not in SHEETS for k in kinds): raise HTTPException(404)
    kinds = [k for k in kinds if can(u, KIND_PERM[k])] or kinds
    wb = Workbook(); ins = wb.active; ins.title = "Instructions"
    gold, dark = PatternFill("solid", fgColor="E9D9A0"), PatternFill("solid", fgColor="9A7B1C")
    ins.column_dimensions["A"].width = 112
    lines = [("Bulk upload template", True), ("", False), ("How to use", True), ("1. Fill in the sheet(s) below. Dark gold headings are required, light gold are optional.", False),
             ("2. Delete nothing in row 1. The grey row marked (example) is skipped, so you can leave it or overwrite it.", False),
             ("3. Premises must already exist, or be listed on the Premises sheet of the same file. Use the exact building name.", False),
             ("4. Dates as YYYY-MM-DD (or DD/MM/YYYY). Numbers without currency symbols.", False),
             ("5. Send the file back to the Admin. It is validated first and nothing is saved until every row is clean.", False), ("", False), ("What each sheet needs", True)]
    for k in kinds: lines.append((f"{k.capitalize()}: {SHEETS[k][3]}", False))
    lines += [("", False), ("Allowed values", True), ("Premises type: " + ", ".join(LISTS["type"]), False), ("Employee status: " + ", ".join(LISTS["status"]), False),
              ("Asset category: " + ", ".join(LISTS["category"]), False), ("Asset condition: " + ", ".join(LISTS["condition"]), False)]
    for i, (t, bold) in enumerate(lines, 1):
        c = ins.cell(i, 1, t); c.font = Font(bold=bold, size=14 if i == 1 else 11, color="9A7B1C" if bold else "111827"); c.alignment = Alignment(wrap_text=True, vertical="top")
    lst = wb.create_sheet("Lists"); lst["A1"] = "Premises in the system"; lst["A1"].font = Font(bold=True)
    pn = [p.name for p in scoped_prem_all(s, u)]
    for i, n in enumerate(pn, 2): lst.cell(i, 1, n)
    lst.sheet_state = "hidden"
    for k in kinds:
        heads, req, ex, _ = SHEETS[k]; ws = wb.create_sheet(k.capitalize()); ws.freeze_panes = "A2"
        for j, h in enumerate(heads, 1):
            c = ws.cell(1, j, h); c.font = Font(bold=True, color="FFFFFF" if h in req else "3B2F0B"); c.fill = dark if h in req else gold
            ws.column_dimensions[c.column_letter].width = max(16, len(h) + 6)
        for j, v in enumerate(ex, 1): c = ws.cell(2, j, v); c.font = Font(italic=True, color="9CA3AF")
        def dv(col, formula):
            if col in heads:
                d = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=False); ws.add_data_validation(d)
                L = ws.cell(1, heads.index(col) + 1).column_letter; d.add(f"{L}3:{L}2000")
        if k != "premises": dv("premises", f"=Lists!$A$2:$A${max(len(pn) + 1, 2) + 200}")
        else: dv("parent", f"=Lists!$A$2:$A${max(len(pn) + 1, 2) + 200}")
        if k == "premises": dv("type", '"' + ",".join(LISTS["type"]) + '"')
        if k == "employees": dv("status", '"' + ",".join(LISTS["status"]) + '"')
        if k == "assets": dv("category", '"' + ",".join(LISTS["category"]) + '"'); dv("condition", '"' + ",".join(LISTS["condition"]) + '"')
    buf = io.BytesIO(); wb.save(buf)
    name = "bms-template.xlsx" if sheet == "all" else f"bms-{sheet}-template.xlsx"
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{name}"'})

def scoped_prem_all(s, u):
    q = s.query(Premises).order_by(Premises.name); ids = None
    for perm in KIND_PERM.values():
        if can(u, perm):
            x = scope_premises(s, u, perm)
            if x is None: ids = None; break
            ids = (ids or set()) | x
    return q.filter(Premises.id.in_(ids or {-1})) if ids is not None else q

def cellstr(v):
    if v is None: return ""
    if isinstance(v, (dt.datetime, dt.date)): return (v.date() if isinstance(v, dt.datetime) else v).isoformat()
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v).strip()

@router.post("/api/bulk/upload")
def workbook_upload(file: UploadFile = File(...), commit: str = Form(""), kind: str = Form(""), u: User = Depends(current_user), s: Session = Depends(db)):
    import io, csv
    raw = file.file.read(6_000_000 + 1)
    if len(raw) > 6_000_000: raise HTTPException(400, "File is larger than 6 MB")
    data = {}
    name = (file.filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xlsm")):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            for ws in wb.worksheets:
                k = ws.title.strip().lower()
                if k not in SHEETS: continue
                it = ws.iter_rows(values_only=True); head = next(it, None)
                if not head: continue
                keys = [str(h or "").strip().lower().replace(" ", "_").replace("*", "") for h in head]; rows = []
                for n, vals in enumerate(it, start=2):
                    r = {keys[j]: cellstr(v) for j, v in enumerate(vals) if j < len(keys) and keys[j]}
                    first = next((x for x in r.values() if x), "")
                    if not first or first.lower().startswith("(example)"): continue
                    rows.append((n, r))
                data[k] = rows
        elif name.endswith(".csv"):
            if kind not in SHEETS: raise HTTPException(400, "Choose which list this CSV is for")
            rd = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
            keys = [h.strip().lower().replace(" ", "_") for h in rd[0]] if rd else []
            data[kind] = [(n, {keys[j]: (v or "").strip() for j, v in enumerate(r) if j < len(keys)}) for n, r in enumerate(rd[1:], start=2) if any(x.strip() for x in r)
                          and not r[0].lower().startswith("(example)")]
        else: raise HTTPException(400, "Upload the .xlsx template (or a .csv)")
    except HTTPException: raise
    except Exception: raise HTTPException(400, "That file could not be read. Use the downloaded template.")
    if not any(data.values()): raise HTTPException(400, "No data rows found. Fill in the template below the grey example row.")
    ctx, out, tot_err, tot_new = import_ctx(s), {}, 0, 0
    for k in ("premises", "employees", "vehicles", "assets", "travel_policy", "visas"):
        if k in data and data[k]:
            out[k] = run_import(s, u, k, data[k], ctx); tot_err += len(out[k]["errors"]); tot_new += out[k]["created"]
    ok = bool(commit) and not tot_err
    s.commit() if ok else s.rollback()
    return {"sheets": out, "created": tot_new, "errors": tot_err, "committed": ok}

# ======================= integration API (for a future asset-management / ticketing system) =======================
def api_key(x_api_key: str | None = Header(None)):
    k = os.environ.get("INTEGRATION_API_KEY")
    if not k or not x_api_key or not hmac.compare_digest(k, x_api_key): raise HTTPException(401, "Invalid or missing X-API-Key")

def since(v):
    try: return dt.datetime.fromisoformat(v.replace("Z", "")) if v else None
    except ValueError: raise HTTPException(400, "updated_since must be an ISO timestamp")

@router.get("/api/integration/assets", dependencies=[Depends(api_key)])
def int_assets(updated_since: str | None = None, s: Session = Depends(db)):
    q = s.query(Asset); d = since(updated_since)
    if d: q = q.filter(Asset.updated_at >= d)
    pn = {p.id: p.name for p in s.query(Premises)}
    return [{**asset_out(a), "premises": pn.get(a.premises_id)} for a in q.order_by(Asset.id)]

@router.post("/api/integration/assets", dependencies=[Depends(api_key)])
async def int_assets_upsert(request: Request, s: Session = Depends(db)):
    b = await request.json(); src = (b.get("source") or "").strip()
    if not src: raise HTTPException(400, "source is required")
    prem = {p.name.lower(): p for p in s.query(Premises)}; res = {"created": 0, "updated": 0, "errors": []}
    for i, it in enumerate(b.get("items", [])):
        try:
            xid = str(_req(it, "external_id")); a = s.query(Asset).filter_by(external_source=src, external_id=xid).first()
            if a:
                for k in ("name", "make_model", "serial_no", "location", "vendor", "notes"):
                    if k in it: setattr(a, k, it[k])
                if "category" in it: a.category = cat(it["category"])
                if it.get("status") in ("in_service", "under_maintenance", "retired"): a.status = it["status"]
                if it.get("condition") in ("good", "fair", "poor"): a.condition = it["condition"]
                for k in ("purchase_date", "warranty_to", "last_service_date", "next_service_due"):
                    if k in it: setattr(a, k, pdate(it[k]))
                audit(s, None, "asset", a.id, f"sync:{src}", None, {k: v for k, v in it.items()}); res["updated"] += 1
            else:
                p = prem.get(str(_req(it, "premises")).lower())
                if not p: raise ValueError(f"premises '{it['premises']}' not found")
                _req(it, "name"); a = make_asset(s, p, {**it, "external_source": src, "external_id": xid})
                audit(s, None, "asset", a.id, f"sync:{src}", None, row(a)); res["created"] += 1
        except (ValueError, KeyError) as e: res["errors"].append({"index": i, "error": str(e)})
    s.commit(); return res

@router.get("/api/integration/tickets", dependencies=[Depends(api_key)])
def int_tickets(updated_since: str | None = None, s: Session = Depends(db)):
    q = s.query(Ticket); d = since(updated_since)
    if d: q = q.filter(Ticket.updated_at >= d)
    pn = {p.id: p.name for p in s.query(Premises)}
    return [{**ticket_out(s, t), "premises": pn.get(t.premises_id)} for t in q.order_by(Ticket.id)]

@router.post("/api/integration/tickets", dependencies=[Depends(api_key)])
async def int_tickets_upsert(request: Request, s: Session = Depends(db)):
    """Match on BMS ticket id, else (source, external_id). Existing tickets accept status / assigned_to / resolution; unknown ones are created."""
    b = await request.json(); src = (b.get("source") or "").strip()
    if not src: raise HTTPException(400, "source is required")
    prem = {p.name.lower(): p for p in s.query(Premises)}; res = {"created": 0, "updated": 0, "errors": []}
    for i, it in enumerate(b.get("items", [])):
        try:
            t = s.get(Ticket, it["id"]) if it.get("id") else (s.query(Ticket).filter_by(source=src, external_id=str(it["external_id"])).first() if it.get("external_id") else None)
            if t:
                if it.get("status") in STATUSES and it["status"] != t.status:
                    t.status = it["status"]; event(s, t, None, "status", f"{src}: status → {t.status.replace('_', ' ')}")
                    if t.status == "resolved": t.resolved_at = dt.datetime.utcnow()
                if it.get("assigned_to"): t.assigned_to = it["assigned_to"]
                if it.get("resolution"): t.resolution = it["resolution"]
                if it.get("external_id") and not t.external_id: t.external_id = str(it["external_id"]); t.source = src
                audit(s, None, "ticket", t.id, f"sync:{src}", None, it); res["updated"] += 1
            else:
                p = prem.get(str(_req(it, "premises")).lower())
                if not p: raise ValueError(f"premises '{it['premises']}' not found")
                pr = it.get("priority") if it.get("priority") in PRIORITY_HOURS else "medium"
                t = Ticket(company_id=p.company_id, premises_id=p.id, category=cat(it.get("category"), TICKET_CATS), title=_req(it, "title"),
                           description=it.get("description"), priority=pr, raised_by_name=it.get("raised_by") or src, source=src,
                           external_id=str(it["external_id"]) if it.get("external_id") else None,
                           due_at=dt.datetime.utcnow() + dt.timedelta(hours=PRIORITY_HOURS[pr]))
                s.add(t); s.flush(); event(s, t, None, "created", f"Imported from {src}"); audit(s, None, "ticket", t.id, f"sync:{src}", None, {"title": t.title}); res["created"] += 1
        except (ValueError, KeyError) as e: res["errors"].append({"index": i, "error": str(e)})
    s.commit(); return res

# ======================= demo data top-up (idempotent) =======================
def seed_phase1(s):
    if s.query(User).filter_by(email="maintenance@bms.local").first(): return
    from .core import hash_pw
    hq = s.query(Premises).filter(Premises.parent_id.is_(None), Premises.name.like("Corporate%")).first()
    gh = s.query(Premises).filter_by(name="Guest House 1").first()
    nb = s.query(Premises).filter(Premises.name.like("Nairobi%")).first()
    if not (hq and gh and nb): return
    def mk(email, name, pw, role, level, sid):
        x = User(email=email, name=name, password_hash=hash_pw(pw)); s.add(x); s.flush()
        s.add(RoleGrant(user_id=x.id, role=role, scope_level=level, scope_id=sid)); return x
    mk("maintenance@bms.local", "Maintenance Head", "maint123", "maintenance_head", "group", None)
    ghi = mk("guesthouse@bms.local", "Meera Joseph (Guest House In-charge)", "gh123", "premises_admin", "premises", gh.id)
    hqu = s.query(User).filter_by(email="premises@bms.local").first()
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n)
    A = {}
    for key, p, name, c, mm, loc, pv, warr, itv, last in [
        ("dg", hq, "Diesel generator 125 kVA", "electrical", "Kirloskar KG1-125", "Basement", 1850000, 400, 90, -80),
        ("ac1", hq, "Central AC chiller", "hvac", "Daikin EWAD", "Terrace", 2600000, 20, 90, -100),
        ("lift", hq, "Passenger lift 1", "building", "Otis Gen2", "Block A", 1400000, 300, 30, -12),
        ("fire", hq, "Fire panel & extinguishers", "fire_safety", "Honeywell", "All floors", 350000, -60, 180, -150),
        ("ups", hq, "UPS 40 kVA", "electrical", "APC Symmetra", "Server room", 620000, 700, 180, -30),
        ("ro", gh, "RO water purifier", "appliance", "Kent Supreme", "Kitchen", 28000, 120, 90, -95),
        ("geyser", gh, "Solar water heater", "plumbing", "Racold 200L", "Terrace", 54000, 200, 180, -20),
        ("ac2", gh, "Split AC, Room 2", "hvac", "Voltas 1.5T", "Room 2", 42000, 90, 120, -60),
        ("cctv", gh, "CCTV system, 8 camera", "security", "Hikvision", "Entrance", 95000, 15, 365, -200),
        ("gen2", nb, "Standby generator", "electrical", "Perkins 60kVA", "Yard", 1200000, 250, 90, -40)]:
        A[key] = make_asset(s, p, {"name": name, "category": c, "make_model": mm, "location": loc, "purchase_value": pv, "purchase_date": D(-700),
                                   "warranty_to": D(warr), "service_interval_days": itv, "last_service_date": D(last), "vendor": "AMC vendor"})
        audit(s, None, "asset", A[key].id, "create", None, {"name": name})
    A["ac2"].condition = "fair"; A["ac1"].status = "under_maintenance"
    for key, p, raiser, ast, title, desc, pr, status, assignee in [
        ("t1", hq, hqu, A["ac1"], "Chiller tripping on high pressure", "Trips twice a day in the afternoon; 3rd floor is too warm.", "high", "in_progress", "Cool-Air Services (Ramesh)"),
        ("t2", hq, hqu, A["lift"], "Lift 1 door sensor intermittently failing", "Door reopens repeatedly at ground floor.", "medium", "assigned", "Otis AMC team"),
        ("t3", gh, ghi, A["ro"], "RO water tastes salty", "Please check TDS and replace membrane if required.", "medium", "open", None),
        ("t4", gh, ghi, None, "Room 3 bathroom tap leaking", "Slow drip, needs washer replacement.", "low", "resolved", "In-house plumber")]:
        tk = Ticket(company_id=p.company_id, premises_id=p.id, asset_id=ast.id if ast else None, category=ast.category if ast else "plumbing", title=title,
                    description=desc, priority=pr, status=status, raised_by=raiser.id, raised_by_name=raiser.name, assigned_to=assignee,
                    raised_at=dt.datetime.utcnow() - dt.timedelta(hours=30 if pr == "high" else 6), due_at=dt.datetime.utcnow() + dt.timedelta(hours=PRIORITY_HOURS[pr] - (30 if pr == "high" else 6)))
        if status == "resolved": tk.resolved_at = dt.datetime.utcnow(); tk.resolution = "Washer replaced and tested."
        s.add(tk); s.flush(); event(s, tk, raiser, "created", f"Raised by {raiser.name} · priority {pr}")
        if assignee: event(s, tk, None, "assign", f"Assigned to {assignee}")
        if status != "open": event(s, tk, None, "status", f"Status → {status.replace('_', ' ')}")
        audit(s, raiser, "ticket", tk.id, "create", None, {"title": title})
    s.commit()

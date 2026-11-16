"""Phase 6: Travel & logistics. Requests with HR and Admin approval (or Business Head for self-pay), policy limits by grade,
flight and hotel options and bookings, changes and refunds with reconciliation, visas and permits, travel advances and claims."""
import re, datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Body
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import *
from .core import *
from .phase1 import scoped, in_scope, pdate, pnum
from .phase4 import save_upload, notify, resolve_notes

router = APIRouter()
STEP_PERM = {"awaiting_hr": ("hr", "travel.hr"), "awaiting_admin": ("admin", "travel.admin"), "awaiting_bhead": ("bhead", "travel.bhead")}
OPEN_STATES = ("awaiting_hr", "awaiting_admin", "awaiting_bhead", "approved", "booked")

def latlng(url):
    if not url: return None, None
    for pat in (r"@(-?\d+\.\d+),(-?\d+\.\d+)", r"[?&](?:q|ll|query|destination)=(-?\d+\.\d+),(-?\d+\.\d+)", r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", r"^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$"):
        m = re.search(pat, url)
        if m: return float(m[1]), float(m[2])
    return None, None

def setting(s, key, default=None):
    r = s.get(TravelSetting, key); return r.value if r and r.value is not None else default

def policy_for(s, grade):
    return s.query(TravelPolicy).filter(func.lower(TravelPolicy.grade) == (grade or "").lower()).first() if grade else None

def estimate(p, r):
    """What the policy allows for hotel and daily allowance on this trip (flights are not capped by amount, only by class)."""
    if not p: return None
    days = ((r.return_on - r.depart_on).days + 1) if r.return_on else max(r.nights, 0) + 1
    hotel = getattr(p, "hotel_" + r.city_grade.lower(), None)
    return {"days": days, "hotel_per_night": hotel, "hotel_total": hotel * r.nights if hotel and r.hotel_needed else 0, "da_per_day": p.daily_allowance,
            "da_total": (p.daily_allowance or 0) * days, "currency": p.currency}

def req_scope(s, u, perm="travel.read"):
    q = s.query(TravelRequest); ids = scope_premises(s, u, perm)
    return q.filter(TravelRequest.premises_id.in_(ids or {-1})) if ids is not None else q

def get_req(s, u, rid, perm="travel.read"):
    r = req_scope(s, u, perm).filter(TravelRequest.id == rid).first()
    if not r: raise HTTPException(404, "Travel request not found in your scope")
    return r

def required_steps(s, r):
    if r.arrangement == "self_pay":
        th = float(setting(s, "self_pay_threshold", "0") or 0)
        return ["bhead"] if (th <= 0 or (r.budget or 0) >= th) else []
    return ["hr", "admin"]

def can_decide(s, u, r):
    st = STEP_PERM.get(r.status)
    return bool(st) and in_scope(s, u, st[1], r.premises_id)

def req_out(s, r, detail=False):
    e = s.get(Employee, r.traveller_id); p = policy_for(s, e.grade if e else None)
    out = row(r, ref=f"TR-{r.id:04d}", traveller=e.name if e else "?", emp_code=e.emp_code if e else None, grade=e.grade if e else None, department=e.department if e else None)
    if detail:
        ap = s.query(TravelApproval).filter_by(request_id=r.id).order_by(TravelApproval.id).all()
        out.update(approvals=[row(a) for a in ap], steps=required_steps(s, r), policy=row(p) if p else None, estimate=estimate(p, r),
                   advance=None)
    return out

# ---------- requests ----------
@router.get("/api/travel/requests")
def requests(u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    E = {e.id: e for e in s.query(Employee)}; cnt = dict(s.query(TravelBooking.request_id, func.count()).filter(TravelBooking.status.in_(["booked", "changed"])).group_by(TravelBooking.request_id).all())
    out = []
    for r in req_scope(s, u).order_by(TravelRequest.id.desc()).limit(500):
        e = E.get(r.traveller_id)
        out.append(row(r, ref=f"TR-{r.id:04d}", traveller=e.name if e else "?", emp_code=e.emp_code if e else None, grade=e.grade if e else None, bookings=cnt.get(r.id, 0), can_decide=can_decide(s, u, r)))
    return out

@router.post("/api/travel/requests")
def request_add(b: dict = Body(...), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    e = scoped(s, u, Employee, "travel.write").filter(Employee.id == b.get("traveller_id")).first() if b.get("traveller_id") else None
    if not e: raise HTTPException(404, "Choose a traveller within your scope")
    if e.status in ("resigned", "inactive"): raise HTTPException(400, f"{e.name} is {e.status}")
    if not (b.get("purpose") or "").strip() or not (b.get("to_place") or "").strip(): raise HTTPException(400, "Purpose and destination are required")
    try: dep, ret = pdate(b.get("depart_on")), pdate(b.get("return_on")); bud = pnum(b.get("budget"), "budget"); adv = pnum(b.get("advance_requested"), "advance")
    except ValueError as x: raise HTTPException(400, str(x))
    if not dep: raise HTTPException(400, "Departure date is required")
    if ret and ret < dep: raise HTTPException(400, "Return date is before departure")
    arr = b.get("arrangement") if b.get("arrangement") in ("company", "self_pay") else "company"
    fl, fg = latlng(b.get("from_map")); tl, tg = latlng(b.get("to_map"))
    nights = int(pnum(b.get("nights"), "nights")) if b.get("nights") not in (None, "") else ((ret - dep).days if ret else 0)
    cur = (b.get("currency") or (s.get(Company, e.company_id).currency)).upper()[:3]
    r = TravelRequest(traveller_id=e.id, company_id=e.company_id, premises_id=e.premises_id, requested_by=u.name, purpose=b["purpose"].strip(), from_place=b.get("from_place") or None,
                      from_map=b.get("from_map") or None, from_lat=fl, from_lng=fg, to_place=b["to_place"].strip(), to_map=b.get("to_map") or None, to_lat=tl, to_lng=tg,
                      mode=b.get("mode") if b.get("mode") in ("flight", "train", "road", "other") else "flight", depart_on=dep, return_on=ret, nights=max(nights, 0),
                      city_grade=(b.get("city_grade") or "A").upper()[:1], hotel_needed=bool(b.get("hotel_needed", True)), arrangement=arr, budget=bud, currency=cur,
                      cost_centre=(b.get("cost_centre") or e.department or None), advance_requested=adv, notes=b.get("notes") or None)
    steps = required_steps(s, r); r.status = {"hr": "awaiting_bhead" if arr == "self_pay" else "awaiting_hr", "bhead": "awaiting_bhead"}.get(steps[0], "approved") if steps else "approved"
    s.add(r); s.flush(); audit(s, u, "travel", r.id, "request_created", None, {"traveller": e.emp_code, "to": r.to_place, "arrangement": arr})
    if r.status in STEP_PERM: notify(s, "travel", f"Travel request TR-{r.id:04d} needs your approval", f"{e.name} to {r.to_place}, {dep}. {arr.replace('_', ' ')}", link=f"travel/{r.id}", premises_id=r.premises_id, perm=STEP_PERM[r.status][1], ref=f"trv:{r.id}:{r.status}")
    s.commit(); return req_out(s, r, True)

@router.get("/api/travel/requests/{rid}")
def request_detail(rid: int, u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    r = get_req(s, u, rid); out = req_out(s, r, True)
    B = [row(x) for x in s.query(TravelBooking).filter_by(request_id=rid).order_by(TravelBooking.kind, TravelBooking.id)]
    ch = [row(c) for c in s.query(TravelChange).join(TravelBooking, TravelBooking.id == TravelChange.booking_id).filter(TravelBooking.request_id == rid).order_by(TravelChange.id.desc())]
    adv = [row(a, ref=f"TA-{a.id:05d}") for a in s.query(TravelAdvance).filter_by(request_id=rid).order_by(TravelAdvance.id.desc())]
    cl = s.query(TravelClaim).filter_by(request_id=rid).first()
    lines = [row(x) for x in s.query(TravelClaimLine).filter_by(claim_id=cl.id)] if cl else []
    return {"request": out, "bookings": B, "changes": ch, "advances": adv, "claim": row(cl) if cl else None, "lines": lines, "can_decide": can_decide(s, u, r),
            "can_write": in_scope(s, u, "travel.write", r.premises_id), "can_approve_claim": in_scope(s, u, "travel.approve", r.premises_id), "can_pay": in_scope(s, u, "travel.pay", r.premises_id)}

@router.post("/api/travel/requests/{rid}/decide")
def request_decide(rid: int, b: dict = Body(...), u: User = Depends(current_user), s: Session = Depends(db)):
    r = get_req(s, u, rid)
    if not can_decide(s, u, r): raise HTTPException(403, "This step is not waiting for you")
    step = STEP_PERM[r.status][0]; ok = b.get("decision") == "approve"
    if not ok and not (b.get("note") or "").strip(): raise HTTPException(400, "Give a reason for rejecting")
    s.add(TravelApproval(request_id=r.id, step=step, decision="approved" if ok else "rejected", by_name=u.name, note=(b.get("note") or "").strip() or None))
    resolve_notes(s, f"trv:{r.id}:{r.status}")
    if not ok: r.status = "rejected"
    elif step == "hr": r.status = "awaiting_admin"
    else: r.status = "approved"
    if r.status in STEP_PERM: notify(s, "travel", f"Travel request TR-{r.id:04d} needs your approval", f"{s.get(Employee, r.traveller_id).name} to {r.to_place}", link=f"travel/{r.id}", premises_id=r.premises_id, perm=STEP_PERM[r.status][1], ref=f"trv:{r.id}:{r.status}")
    audit(s, u, "travel", r.id, "approval_" + ("approved" if ok else "rejected"), None, {"step": step, "note": b.get("note")}); s.commit(); return req_out(s, r, True)

@router.post("/api/travel/requests/{rid}/status")
def request_status(rid: int, b: dict = Body(...), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    r = get_req(s, u, rid, "travel.write"); to = b.get("status")
    if to == "cancelled" and r.status in OPEN_STATES: r.status = "cancelled"
    elif to == "completed" and r.status == "booked": r.status = "completed"
    else: raise HTTPException(400, "That change is not allowed from the current status")
    audit(s, u, "travel", r.id, "status_" + to, None, None); s.commit(); return req_out(s, r, True)

@router.get("/api/travel/summary")
def travel_summary(u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    R = req_scope(s, u).all(); ids = [r.id for r in R] or [-1]; t = dt.date.today()
    mine = sum(1 for r in R if can_decide(s, u, r))
    refunds = s.query(TravelChange).join(TravelBooking, TravelBooking.id == TravelChange.booking_id).filter(TravelBooking.request_id.in_(ids), TravelChange.status == "pending").count()
    visas = [v for v in s.query(TravelVisa) if v.valid_to and (v.valid_to - t).days <= 60]
    return {"awaiting_me": mine, "awaiting": sum(1 for r in R if r.status in STEP_PERM), "approved_to_book": sum(1 for r in R if r.status == "approved"), "upcoming": sum(1 for r in R if r.status == "booked" and r.depart_on >= t),
            "refunds_pending": refunds, "visas_expiring": len(visas)}

# ---------- bookings (flight / hotel options, fare comparison, tickets) ----------
def parse_dt(v):
    if not v: return None
    try: return dt.datetime.fromisoformat(v)
    except ValueError: raise HTTPException(400, f"Bad date and time '{v}'")

@router.post("/api/travel/requests/{rid}/bookings")
def booking_add(rid: int, kind: str = Form("flight"), status: str = Form("option"), vendor: str = Form(""), booked_via: str = Form(""), route_or_city: str = Form(""), start_at: str = Form(""), end_at: str = Form(""),
                ref: str = Form(""), fare: str = Form(""), currency: str = Form(""), baggage: str = Form(""), meal_plan: str = Form(""), cancel_terms: str = Form(""), notes: str = Form(""),
                ticket: UploadFile | None = File(None), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    r = get_req(s, u, rid, "travel.write")
    if r.status not in ("approved", "booked"): raise HTTPException(409, "The request must be approved before booking")
    if kind not in ("flight", "hotel", "other") or status not in ("option", "booked"): raise HTTPException(400, "Bad type")
    if not vendor.strip(): raise HTTPException(400, "Enter the airline or hotel name")
    try: fr = pnum(fare, "fare")
    except ValueError as x: raise HTTPException(400, str(x))
    if status == "booked" and not (ref.strip() or ticket): raise HTTPException(400, "A booking needs the PNR / confirmation number or the ticket")
    b = TravelBooking(request_id=rid, kind=kind, status=status, vendor=vendor.strip(), booked_via=booked_via or None, route_or_city=route_or_city or None, start_at=parse_dt(start_at), end_at=parse_dt(end_at),
                      ref=ref or None, fare=fr, currency=(currency or r.currency).upper()[:3], baggage=baggage or None, meal_plan=meal_plan or None, cancel_terms=cancel_terms or None,
                      ticket_file=save_upload(ticket), notes=notes or None, created_by=u.name)
    s.add(b); s.flush()
    if status == "booked": r.status = "booked"
    audit(s, u, "travel", rid, "booking_" + status, None, {"kind": kind, "vendor": vendor, "fare": fr}); s.commit(); return row(b)

@router.post("/api/travel/bookings/{bid}/confirm")
def booking_confirm(bid: int, ref: str = Form(""), ticket: UploadFile | None = File(None), baggage: str = Form(""), cancel_terms: str = Form(""), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    b = s.get(TravelBooking, bid)
    if not b: raise HTTPException(404)
    r = get_req(s, u, b.request_id, "travel.write")
    if b.status != "option": raise HTTPException(400, "Only an option can be booked")
    tk = save_upload(ticket)
    if not (ref.strip() or tk): raise HTTPException(400, "Enter the PNR / confirmation number or attach the ticket")
    b.status, b.ref, b.ticket_file = "booked", ref or b.ref, tk or b.ticket_file
    if baggage: b.baggage = baggage
    if cancel_terms: b.cancel_terms = cancel_terms
    for o in s.query(TravelBooking).filter(TravelBooking.request_id == b.request_id, TravelBooking.kind == b.kind, TravelBooking.status == "option", TravelBooking.id != bid): o.status = "rejected"   # the other fare options are closed
    r.status = "booked"; audit(s, u, "travel", r.id, "booked", None, {"vendor": b.vendor, "ref": b.ref}); s.commit(); return row(b)

# ---------- changes, cancellations, refunds, reconciliation ----------
@router.post("/api/travel/bookings/{bid}/changes")
def change_add(bid: int, kind: str = Form(...), revised_ref: str = Form(""), penalty: str = Form(""), refund_expected: str = Form(""), refund_received: str = Form(""), refund_ref: str = Form(""),
               vendor_balance: str = Form(""), notes: str = Form(""), file: UploadFile | None = File(None), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    b = s.get(TravelBooking, bid)
    if not b: raise HTTPException(404)
    get_req(s, u, b.request_id, "travel.write")
    if kind not in ("change", "cancel", "refund"): raise HTTPException(400, "Choose change, cancellation or refund")
    if b.status not in ("booked", "changed", "cancelled"): raise HTTPException(400, "Only a booked ticket can be changed or cancelled")
    try: pe, re_, rr, vb = pnum(penalty, "penalty"), pnum(refund_expected, "refund"), pnum(refund_received, "refund received"), pnum(vendor_balance, "vendor balance")
    except ValueError as x: raise HTTPException(400, str(x))
    c = TravelChange(booking_id=bid, kind=kind, revised_ref=revised_ref or None, revised_file=save_upload(file), penalty=pe, refund_expected=re_, refund_received=rr, refund_ref=refund_ref or None,
                     vendor_balance=vb, notes=notes or None, created_by=u.name, status="settled" if (re_ is None or (rr is not None and rr >= re_)) and not vb else "pending")
    if kind == "cancel": b.status = "cancelled"
    elif kind == "change": b.status = "changed"; b.ref = revised_ref or b.ref
    s.add(c); s.flush(); audit(s, u, "travel", b.request_id, "booking_" + kind, None, {"penalty": pe, "refund_expected": re_}); s.commit(); return row(c)

@router.post("/api/travel/changes/{cid}/settle")
def change_settle(cid: int, b: dict = Body(...), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    c = s.get(TravelChange, cid); bk = s.get(TravelBooking, c.booking_id) if c else None
    if not c: raise HTTPException(404)
    get_req(s, u, bk.request_id, "travel.write")
    try: rr = pnum(b.get("refund_received"), "refund received")
    except ValueError as x: raise HTTPException(400, str(x))
    if rr is not None: c.refund_received = rr
    if b.get("refund_ref"): c.refund_ref = b["refund_ref"]
    if b.get("vendor_balance") is not None and b.get("vendor_balance") != "": c.vendor_balance = pnum(b["vendor_balance"], "vendor balance")
    c.status = "settled"; audit(s, u, "travel", bk.request_id, "reconciled", None, {"received": c.refund_received, "balance": c.vendor_balance}); s.commit(); return row(c)

@router.get("/api/travel/reconciliation")
def reconciliation(u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    R = {r.id: r for r in req_scope(s, u)}; E = {e.id: e for e in s.query(Employee)}; out = []
    for c, b in s.query(TravelChange, TravelBooking).join(TravelBooking, TravelBooking.id == TravelChange.booking_id).filter(TravelBooking.request_id.in_(list(R) or [-1])).order_by(TravelChange.id.desc()).limit(300):
        r = R[b.request_id]; e = E.get(r.traveller_id)
        out.append(row(c, ref=f"TR-{r.id:04d}", request_id=r.id, traveller=e.name if e else "?", vendor=b.vendor, kind_of=b.kind, original_ref=b.ref, original_fare=b.fare, currency=b.currency,
                       outstanding=(c.refund_expected or 0) - (c.refund_received or 0)))
    return out

# ---------- visas & permits ----------
def visa_out(v, E, restricted):
    e = E.get(v.employee_id); t = dt.date.today()
    st = None if not v.valid_to else ("expired" if v.valid_to < t else "d30" if (v.valid_to - t).days <= 30 else "d90" if (v.valid_to - t).days <= 90 else "ok")
    pp = v.passport_no if restricted else ("•" * 4 + v.passport_no[-3:] if v.passport_no else None)
    return row(v, passport_no=pp, passport_visible=restricted, employee=e.name if e else "?", emp_code=e.emp_code if e else None, grade=e.grade if e else None, state=st)

@router.get("/api/travel/visas")
def visas(u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    E = {e.id: e for e in scoped(s, u, Employee, "travel.read")}; res = can(u, "visa.restricted")
    return [visa_out(v, E, res) for v in s.query(TravelVisa).filter(TravelVisa.employee_id.in_(list(E) or [-1])).order_by(TravelVisa.valid_to.asc().nullslast(), TravelVisa.id.desc())]

@router.post("/api/travel/visas")
def visa_add(employee_id: int = Form(...), kind: str = Form("visa"), country: str = Form(""), passport_no: str = Form(""), application_ref: str = Form(""), status: str = Form("applied"), applied_on: str = Form(""),
             valid_to: str = Form(""), notes: str = Form(""), request_id: str = Form(""), file: UploadFile | None = File(None), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    e = scoped(s, u, Employee, "travel.write").filter(Employee.id == employee_id).first()
    if not e: raise HTTPException(404, "Employee not found in your scope")
    if not country.strip(): raise HTTPException(400, "Country is required")
    if passport_no.strip() and not can(u, "visa.restricted"): raise HTTPException(403, "Only HR and the Travel Desk can record passport details")
    try: ao, vt = pdate(applied_on), pdate(valid_to)
    except ValueError as x: raise HTTPException(400, str(x))
    v = TravelVisa(employee_id=e.id, kind=kind if kind in ("visa", "work_permit", "special_pass") else "visa", country=country.strip(), passport_no=passport_no.strip() or None, application_ref=application_ref or None,
                   status=status if status in ("draft", "applied", "approved", "rejected", "expired") else "applied", applied_on=ao, valid_to=vt, file=save_upload(file), notes=notes or None, request_id=int(request_id) if request_id else None, created_by=u.name)
    s.add(v); s.flush(); audit(s, u, "travel", None, "visa_added", None, {"employee": e.emp_code, "country": country, "kind": kind}); s.commit(); return visa_out(v, {e.id: e}, can(u, "visa.restricted"))

@router.post("/api/travel/visas/{vid}/update")
def visa_update(vid: int, b: dict = Body(...), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    v = s.get(TravelVisa, vid); E = {e.id: e for e in scoped(s, u, Employee, "travel.write")}
    if not v or v.employee_id not in E: raise HTTPException(404, "Not found in your scope")
    try:
        if b.get("status") in ("draft", "applied", "approved", "rejected", "expired"): v.status = b["status"]
        if "valid_to" in b: v.valid_to = pdate(b["valid_to"])
        if "application_ref" in b: v.application_ref = b["application_ref"] or None
        if "notes" in b: v.notes = b["notes"] or None
    except ValueError as x: raise HTTPException(400, str(x))
    audit(s, u, "travel", None, "visa_updated", None, {"visa": vid, "status": v.status}); s.commit(); return visa_out(v, E, can(u, "visa.restricted"))

# ---------- advance (to HRMS) and claim ----------
@router.post("/api/travel/requests/{rid}/advance")
def request_advance(rid: int, b: dict = Body(...), u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    from .phase2 import new_advance, push_advance, adv_out
    r = get_req(s, u, rid, "travel.write"); e = s.get(Employee, r.traveller_id)
    if r.status not in ("approved", "booked"): raise HTTPException(409, "The request must be approved first")
    amt = pnum(b.get("amount"), "amount"); p = policy_for(s, e.grade)
    if p and p.advance_limit and amt and amt > p.advance_limit: raise HTTPException(400, f"The advance limit for grade {e.grade} is {p.currency} {p.advance_limit:,.0f}")
    if s.query(TravelAdvance).filter(TravelAdvance.request_id == rid, TravelAdvance.status != "failed").count(): raise HTTPException(409, "An advance already exists for this trip")
    try: t = new_advance(s, {"employee_code": e.emp_code, "amount": amt, "currency": r.currency, "purpose": r.purpose, "destination": r.to_place, "from_date": r.depart_on, "to_date": r.return_on}, "admin", u.name)
    except ValueError as x: raise HTTPException(400, str(x))
    t.request_id = rid; audit(s, u, "travel", rid, "advance_requested", None, {"amount": amt}); push_advance(s, t, u); return adv_out(t)

CLAIM_CATS = ("ticket", "hotel", "local", "da", "other")

def get_claim(s, u, rid, create=False):
    r = get_req(s, u, rid, "travel.write")
    c = s.query(TravelClaim).filter_by(request_id=rid).first()
    if not c and create:
        if r.status not in ("booked", "completed", "approved"): raise HTTPException(409, "Claims start after the trip is approved")
        c = TravelClaim(request_id=rid); s.add(c); s.flush()
    if not c: raise HTTPException(404, "No claim yet")
    return r, c

@router.post("/api/travel/requests/{rid}/claim/lines")
def claim_line(rid: int, category: str = Form(...), description: str = Form(""), qty: str = Form(""), amount: str = Form(...), over_reason: str = Form(""), receipt: UploadFile | None = File(None),
               u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    r, c = get_claim(s, u, rid, True); e = s.get(Employee, r.traveller_id); p = policy_for(s, e.grade)
    if c.status not in ("draft", "rejected"): raise HTTPException(409, "The claim is already submitted")
    if category not in CLAIM_CATS: raise HTTPException(400, "Unknown category")
    try: amt, q = pnum(amount, "amount"), pnum(qty, "quantity")
    except ValueError as x: raise HTTPException(400, str(x))
    if not amt or amt <= 0: raise HTTPException(400, "Enter the amount")
    limit = None
    if p and category == "hotel": limit = (getattr(p, "hotel_" + r.city_grade.lower(), None) or 0) * (q or r.nights or 1) or None
    if p and category == "da": limit = (p.daily_allowance or 0) * (q or 1) or None
    if limit and amt > limit and not over_reason.strip(): raise HTTPException(400, f"This line is over the policy limit ({limit:,.0f}). Give a reason.")
    rc = save_upload(receipt)
    if category != "da" and not rc: raise HTTPException(400, "Attach the receipt")
    ln = TravelClaimLine(claim_id=c.id, category=category, description=description or None, qty=q, amount=amt, policy_limit=limit, over_reason=over_reason or None, receipt=rc)
    s.add(ln); c.status = "draft"; audit(s, u, "travel", rid, "claim_line", None, {"category": category, "amount": amt}); s.commit(); return row(ln)

@router.post("/api/travel/requests/{rid}/claim/submit")
def claim_submit(rid: int, u: User = Depends(need("travel.write")), s: Session = Depends(db)):
    r, c = get_claim(s, u, rid)
    if c.status not in ("draft", "rejected"): raise HTTPException(409, "Already submitted")
    if not s.query(TravelClaimLine).filter_by(claim_id=c.id).count(): raise HTTPException(400, "Add at least one line")
    c.status, c.submitted_on = "submitted", dt.date.today(); notify(s, "travel", f"Travel claim for TR-{r.id:04d} needs approval", None, link=f"travel/{r.id}", premises_id=r.premises_id, perm="travel.approve", ref=f"clm:{r.id}")
    audit(s, u, "travel", rid, "claim_submitted", None, None); s.commit(); return row(c)

@router.post("/api/travel/requests/{rid}/claim/decide")
def claim_decide(rid: int, b: dict = Body(...), u: User = Depends(need("travel.approve")), s: Session = Depends(db)):
    r, c = get_claim(s, u, rid)
    if not in_scope(s, u, "travel.approve", r.premises_id) or c.status != "submitted": raise HTTPException(403, "Nothing for you to approve")
    ok = b.get("decision") == "approve"
    if not ok and not (b.get("note") or "").strip(): raise HTTPException(400, "Give a reason")
    c.status, c.approved_by, c.notes = ("approved" if ok else "rejected"), u.name, (b.get("note") or None); resolve_notes(s, f"clm:{r.id}")
    if ok: notify(s, "travel", f"Travel claim TR-{r.id:04d} approved, ready for payment", None, link=f"travel/{r.id}", premises_id=r.premises_id, perm="travel.pay", ref=f"pay:{r.id}")
    audit(s, u, "travel", rid, "claim_" + c.status, None, {"note": b.get("note")}); s.commit(); return row(c)

@router.post("/api/travel/requests/{rid}/claim/pay")
def claim_pay(rid: int, b: dict = Body(...), u: User = Depends(need("travel.pay")), s: Session = Depends(db)):
    r = get_req(s, u, rid, "travel.pay"); c = s.query(TravelClaim).filter_by(request_id=rid).first()
    if not c or c.status != "approved": raise HTTPException(409, "The claim must be approved first")
    if not (b.get("pay_ref") or "").strip(): raise HTTPException(400, "Enter the payment reference")
    c.status, c.paid_on, c.pay_ref = "paid", dt.date.today(), b["pay_ref"].strip(); resolve_notes(s, f"pay:{rid}"); audit(s, u, "travel", rid, "claim_paid", None, {"ref": c.pay_ref}); s.commit(); return row(c)

# ---------- policy (HR) ----------
@router.get("/api/travel/policy")
def policy_list(u: User = Depends(need("travel.read")), s: Session = Depends(db)):
    return {"rows": [row(p) for p in s.query(TravelPolicy).order_by(TravelPolicy.grade)], "self_pay_threshold": float(setting(s, "self_pay_threshold", "0") or 0), "can_edit": can(u, "travel.policy")}

@router.post("/api/travel/policy")
def policy_save(b: dict = Body(...), u: User = Depends(need("travel.policy")), s: Session = Depends(db)):
    g = (b.get("grade") or "").strip()
    if not g: raise HTTPException(400, "Grade is required")
    try: vals = {k: pnum(b.get(k), k) for k in ("hotel_a", "hotel_b", "hotel_c", "daily_allowance", "advance_limit")}
    except ValueError as x: raise HTTPException(400, str(x))
    p = policy_for(s, g) or TravelPolicy(grade=g); prev = row(p) if p.id else None
    p.currency, p.flight_class, p.notes = (b.get("currency") or "INR").upper()[:3], b.get("flight_class") or None, b.get("notes") or None
    for k, v in vals.items(): setattr(p, k, v)
    s.add(p); s.flush(); audit(s, u, "travel", None, "policy_saved", prev, {"grade": g}); s.commit(); return row(p)

@router.post("/api/travel/policy/settings")
def policy_settings(b: dict = Body(...), u: User = Depends(need("travel.policy")), s: Session = Depends(db)):
    try: v = pnum(b.get("self_pay_threshold"), "threshold") or 0
    except ValueError as x: raise HTTPException(400, str(x))
    r = s.get(TravelSetting, "self_pay_threshold") or TravelSetting(key="self_pay_threshold"); r.value = str(v); s.add(r); audit(s, u, "travel", None, "policy_settings", None, {"self_pay_threshold": v}); s.commit(); return {"self_pay_threshold": v}

# ---------- demo data ----------
def seed_phase6(s):
    if s.query(TravelPolicy).first(): return
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n); E = {e.emp_code: e for e in s.query(Employee)}
    if not E: return
    for g, cur, fc, a, b_, c, da, adv in [("M1", "INR", "economy", 6500, 5000, 3800, 1500, 30000), ("M2", "INR", "economy", 7500, 5800, 4200, 1800, 40000), ("M3", "INR", "premium economy", 9000, 7000, 5000, 2200, 60000), ("M4", "INR", "business", 12000, 9500, 6500, 3000, 100000),
                                          ("E2", "INR", "economy", 4500, 3500, 2800, 1000, 15000), ("E3", "INR", "economy", 5000, 3800, 3000, 1100, 20000), ("E4", "INR", "economy", 5500, 4200, 3200, 1200, 25000), ("E5", "INR", "economy", 6000, 4600, 3500, 1300, 25000),
                                          ("G1", "KES", "economy", 7000, 5500, 4000, 2500, 25000), ("G2", "KES", "economy", 9000, 7000, 5000, 3200, 40000), ("G3", "KES", "economy", 12000, 9000, 6500, 4200, 60000), ("G4", "KES", "business", 18000, 14000, 9500, 6000, 120000)]:
        s.add(TravelPolicy(grade=g, currency=cur, flight_class=fc, hotel_a=a, hotel_b=b_, hotel_c=c, daily_allowance=da, advance_limit=adv))
    s.add(TravelSetting(key="self_pay_threshold", value="0")); s.flush()
    def req(code, to, purpose, dep, ret, arr, budget, cur, grade_city, status, by="HR Manager"):
        e = E[code]; r = TravelRequest(traveller_id=e.id, company_id=e.company_id, premises_id=e.premises_id, requested_by=by, purpose=purpose, from_place=("Nairobi" if cur == "KES" else "Ahmedabad"), to_place=to, from_map=None,
                                       to_map=None, mode="flight", depart_on=D(dep), return_on=D(ret), nights=ret - dep, city_grade=grade_city, arrangement=arr, budget=budget, currency=cur, cost_centre=e.department, status=status)
        s.add(r); s.flush(); return r
    r1 = req("AK2007", "Mombasa, Kenya", "Programme review with county partners", 9, 12, "company", 85000, "KES", "B", "awaiting_hr")
    r2 = req("JT1004", "Mumbai, India", "Regulatory filing meeting", 14, 16, "company", 42000, "INR", "A", "awaiting_admin")
    s.add(TravelApproval(request_id=r2.id, step="hr", decision="approved", by_name="HR Manager", note="Within policy"))
    r3 = req("AK2002", "Kampala, Uganda", "Finance system audit", 6, 10, "company", 210000, "KES", "B", "booked")
    for st, by, note in (("hr", "HR Manager", "Policy checked"), ("admin", "Group Admin", "Confirmed")): s.add(TravelApproval(request_id=r3.id, step=st, decision="approved", by_name=by, note=note))
    o1 = TravelBooking(request_id=r3.id, kind="flight", status="booked", vendor="Kenya Airways", booked_via="MakeMyTrip", route_or_city="NBO to EBB", start_at=dt.datetime.combine(D(6), dt.time(7, 30)), end_at=dt.datetime.combine(D(6), dt.time(9, 10)), ref="KQ4Q7B",
                       fare=46500, currency="KES", baggage="23 kg check-in + 7 kg cabin", cancel_terms="Refundable up to 24h before departure, 15% fee", created_by="Travel Desk")
    s.add_all([o1, TravelBooking(request_id=r3.id, kind="flight", status="rejected", vendor="RwandAir", booked_via="Travel desk", route_or_city="NBO to EBB", fare=52200, currency="KES", baggage="20 kg", created_by="Travel Desk"),
               TravelBooking(request_id=r3.id, kind="hotel", status="booked", vendor="Kampala Serena Hotel", booked_via="Travel desk", route_or_city="Kampala", start_at=dt.datetime.combine(D(6), dt.time(14)), end_at=dt.datetime.combine(D(10), dt.time(11)),
                             ref="SER-88120", fare=96000, currency="KES", meal_plan="Breakfast included", cancel_terms="Free cancellation until 48h before check-in", created_by="Travel Desk")]); s.flush()
    s.add(TravelChange(booking_id=o1.id, kind="change", revised_ref="KQ4Q7B-R1", penalty=4500, notes="Moved the return by one day", created_by="Travel Desk", status="settled"))
    r4 = req("JT1009", "Dubai, UAE", "Governance conference", 25, 29, "self_pay", 160000, "INR", "A", "awaiting_bhead", by="Admin")
    r5 = req("AK2006", "Kisumu, Kenya", "Audit follow-up", -12, -9, "company", 52000, "KES", "C", "completed")
    for st, by in (("hr", "HR Manager"), ("admin", "Group Admin")): s.add(TravelApproval(request_id=r5.id, step=st, decision="approved", by_name=by))
    b5 = TravelBooking(request_id=r5.id, kind="flight", status="cancelled", vendor="Jambojet", booked_via="MakeMyTrip", route_or_city="NBO to KIS", ref="JM88K2", fare=18400, currency="KES", created_by="Travel Desk"); s.add(b5); s.flush()
    s.add(TravelChange(booking_id=b5.id, kind="cancel", penalty=2760, refund_expected=15640, refund_received=None, refund_ref=None, notes="Trip moved to road travel. Refund requested from the airline.", created_by="Travel Desk", status="pending"))
    s.add(TravelVisa(employee_id=E["AK2002"].id, kind="visa", country="Uganda", passport_no="A1234567", application_ref="UG-EV-5521", status="approved", applied_on=D(-30), valid_to=D(55), created_by="Travel Desk"))
    s.add(TravelVisa(employee_id=E["JT1009"].id, kind="visa", country="United Arab Emirates", passport_no="Z7654321", application_ref="UAE-77102", status="applied", applied_on=D(-3), valid_to=None, created_by="HR Manager"))
    s.add(TravelVisa(employee_id=E["JT1003"].id, kind="work_permit", country="Kenya", passport_no="P9988776", application_ref="WP-KE-3301", status="approved", applied_on=D(-300), valid_to=D(20), created_by="HR Manager"))
    notify(s, "travel", f"Travel request TR-{r1.id:04d} needs your approval", "David Mwangi to Mombasa, Kenya", link=f"travel/{r1.id}", premises_id=r1.premises_id, perm="travel.hr", ref=f"trv:{r1.id}:awaiting_hr")
    notify(s, "travel", f"Travel request TR-{r2.id:04d} needs your approval", "Neha Shah to Mumbai, India", link=f"travel/{r2.id}", premises_id=r2.premises_id, perm="travel.admin", ref=f"trv:{r2.id}:awaiting_admin")
    notify(s, "travel", f"Travel request TR-{r4.id:04d} needs your approval", "Pooja Trivedi to Dubai, UAE", link=f"travel/{r4.id}", premises_id=r4.premises_id, perm="travel.bhead", ref=f"trv:{r4.id}:awaiting_bhead")
    from .core import hash_pw
    if not s.query(User).filter_by(email="traveldesk@bms.local").first():
        u2 = User(email="traveldesk@bms.local", name="Travel Desk", password_hash=hash_pw("travel123")); s.add(u2); s.flush(); s.add(RoleGrant(user_id=u2.id, role="travel_desk", scope_level="group", scope_id=None))
    fin = s.query(User).filter_by(email="finance@bms.local").first()
    if not fin:
        fin = User(email="finance@bms.local", name="Finance Officer", password_hash=hash_pw("finance123")); s.add(fin); s.flush(); s.add(RoleGrant(user_id=fin.id, role="finance", scope_level="group", scope_id=None))
    s.commit()

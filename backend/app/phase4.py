"""Phase 4: premises profile (area, floors taken, legal), document vault, hierarchy summary, occupancy,
utilities (accounts + monthly bills + payment proof), and in-app notifications."""
import os, uuid, datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import *
from .core import *
from .phase1 import scoped, in_scope, descendants, pdate, pnum

router = APIRouter()
UPLOAD = os.environ.get("UPLOAD_DIR", "/data/uploads")
DOC_TYPES = ["lease", "purchase_deed", "govt_registration", "tax", "insurance", "occupancy_certificate", "fire_noc", "floor_plan", "litigation", "other"]
UTIL_KINDS = ["electricity", "water", "internet", "gas", "telephone", "waste", "other"]
META_INT = ("floors", "halls", "balconies", "kitchens", "declared_headcount", "litigation_count")
META_TXT = ("maps_url", "location", "amenities", "contact_name", "contact_phone", "notes", "floors_taken", "ownership", "litigation_notes")

def save_upload(f):
    if not f or not getattr(f, "filename", None): return None
    ext = os.path.splitext(f.filename)[1].lower()[:8] or ".pdf"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".doc", ".docx", ".xls", ".xlsx"}: raise HTTPException(400, "Unsupported file type")
    data = f.file.read(15_000_001)
    if len(data) > 15_000_000: raise HTTPException(400, "File too large (15 MB max)")
    os.makedirs(UPLOAD, exist_ok=True); name = uuid.uuid4().hex + ext
    open(os.path.join(UPLOAD, name), "wb").write(data); return name

def get_prem(s, u, pid, perm="premises.view"):
    p = s.get(Premises, pid); ids = scope_premises(s, u, perm) if can(u, perm) else set()
    if not p or (ids is not None and pid not in ids): raise HTTPException(404, "Premises not found in your scope")
    return p

def meta_dict(m):
    keys = META_INT + META_TXT + ("area_sqft", "occupancy", "beds", "rooms")
    return {k: (getattr(m, k, None) if m else None) for k in keys}

# ---------- notifications ----------
def notify(s, kind, title, body=None, link=None, premises_id=None, perm="employees.write", ref=None):
    if ref and s.query(Notification).filter_by(ref=ref, resolved=False).first(): return
    s.add(Notification(kind=kind, title=title, body=body, link=link, premises_id=premises_id, perm=perm, ref=ref))

def resolve_notes(s, ref):
    for n in s.query(Notification).filter_by(ref=ref, resolved=False): n.resolved = True

@router.get("/api/notifications")
def notifications(u: User = Depends(current_user), s: Session = Depends(db)):
    read = {r.notification_id for r in s.query(NotificationRead).filter_by(user_id=u.id)}; out = []; sc = {}
    for n in s.query(Notification).filter_by(resolved=False).order_by(Notification.id.desc()).limit(100):
        if n.id in read or not can(u, n.perm): continue
        if n.perm not in sc: sc[n.perm] = scope_premises(s, u, n.perm)
        if n.premises_id and sc[n.perm] is not None and n.premises_id not in sc[n.perm]: continue
        out.append(row(n))
    return out

@router.post("/api/notifications/{nid}/read")
def note_read(nid: int, u: User = Depends(current_user), s: Session = Depends(db)):
    if not s.get(NotificationRead, (u.id, nid)): s.add(NotificationRead(user_id=u.id, notification_id=nid)); s.commit()
    return {"ok": True}

# ---------- premises profile ----------
@router.get("/api/premises/summary")
def premises_summary(u: User = Depends(need("premises.view")), s: Session = Depends(db)):
    ids = scope_premises(s, u, "premises.view"); q = s.query(Premises)
    P = q.filter(Premises.id.in_(ids or {-1})).all() if ids is not None else q.all()
    metas = {m.premises_id: m for m in s.query(PremisesMeta)}
    emp = dict(s.query(Employee.premises_id, func.count()).filter(Employee.status.in_(["active", "on_leave", "notice"])).group_by(Employee.premises_id).all())
    tk = dict(s.query(Ticket.premises_id, func.count()).filter(Ticket.status.in_(["open", "assigned", "in_progress", "on_hold"])).group_by(Ticket.premises_id).all())
    veh = dict(s.query(Vehicle.premises_id, func.count()).group_by(Vehicle.premises_id).all()); today = dt.date.today(); att = {}
    for a in s.query(Asset).filter(Asset.status != "retired"):
        if a.status == "under_maintenance" or a.condition == "poor" or (a.next_service_due and a.next_service_due < today): att[a.premises_id] = att.get(a.premises_id, 0) + 1
    docs = {}
    for d in s.query(PremisesDocument).filter(PremisesDocument.valid_to.isnot(None), PremisesDocument.valid_to <= today + dt.timedelta(days=90)): docs[d.premises_id] = docs.get(d.premises_id, 0) + 1
    kids = {}
    for p in P:
        if p.parent_id and p.type == "guest_house": kids[p.parent_id] = kids.get(p.parent_id, 0) + 1
    return [{"id": p.id, "employees": emp.get(p.id, 0), "declared_headcount": (metas.get(p.id).declared_headcount if metas.get(p.id) else None), "guest_houses": kids.get(p.id, 0),
             "open_tickets": tk.get(p.id, 0), "assets_attention": att.get(p.id, 0), "vehicles": veh.get(p.id, 0), "litigation": (metas.get(p.id).litigation_count or 0) if metas.get(p.id) else 0,
             "area_sqft": metas.get(p.id).area_sqft if metas.get(p.id) else None, "occupancy": metas.get(p.id).occupancy if metas.get(p.id) else None, "doc_alerts": docs.get(p.id, 0)} for p in P]

@router.get("/api/premises/{pid}/profile")
def prem_profile(pid: int, u: User = Depends(need("premises.view")), s: Session = Depends(db)):
    p = get_prem(s, u, pid); m = s.get(PremisesMeta, pid); sub = descendants(s, pid)
    kids = s.query(Premises).filter_by(parent_id=pid).order_by(Premises.name).all()
    open_t = s.query(Ticket).filter(Ticket.premises_id.in_(sub), Ticket.status.in_(["open", "assigned", "in_progress", "on_hold"])).count()
    stats = {"employees": s.query(Employee).filter(Employee.premises_id == pid, Employee.status.in_(["active", "on_leave", "notice"])).count(),
             "guest_houses": sum(1 for k in kids if k.type == "guest_house"), "sub_premises": len(kids), "vehicles": s.query(Vehicle).filter(Vehicle.premises_id.in_(sub)).count(),
             "assets": s.query(Asset).filter(Asset.premises_id.in_(sub), Asset.status != "retired").count(), "open_tickets": open_t}
    return {"premises": row(p), "meta": meta_dict(m), "stats": stats, "children": [row(k) for k in kids],
            "can_edit": in_scope(s, u, "premises.write", pid), "can_occupancy": in_scope(s, u, "premises.occupancy", pid), "can_docs": in_scope(s, u, "premises.docs", pid)}

@router.post("/api/premises/{pid}/profile")
async def prem_profile_save(pid: int, request: Request, u: User = Depends(need("premises.write")), s: Session = Depends(db)):
    p = get_prem(s, u, pid, "premises.write"); b = await request.json(); m = s.get(PremisesMeta, pid) or PremisesMeta(premises_id=pid); prev = {}
    try:
        if (b.get("name") or "").strip() and b["name"].strip() != p.name: prev["name"] = p.name; p.name = b["name"].strip()
        if "address" in b and (b["address"] or None) != p.address: prev["address"] = p.address; p.address = b["address"] or None
        for k in ("lat", "lng"):
            if k in b: prev[k] = getattr(p, k); setattr(p, k, pnum(b[k], k))
        if "area_sqft" in b: prev["area_sqft"] = m.area_sqft; m.area_sqft = pnum(b["area_sqft"], "area")
        for k in META_INT:
            if k in b: prev[k] = getattr(m, k); setattr(m, k, int(pnum(b[k], k) or 0) if b[k] not in (None, "") else None)
        for k in META_TXT:
            if k in b: prev[k] = getattr(m, k); setattr(m, k, (b[k] or "").strip() or None)
    except ValueError as e: raise HTTPException(400, str(e))
    if m.maps_url and not m.maps_url.lower().startswith(("http://", "https://")): raise HTTPException(400, "The map link must start with https://")
    if m.ownership and m.ownership not in ("owned", "leased", "rented"): raise HTTPException(400, "Ownership must be owned, leased or rented")
    s.add(m); s.flush(); audit(s, u, "premises", pid, "profile_updated", prev, {k: (getattr(p, k, None) if hasattr(p, k) else getattr(m, k, None)) for k in prev}); s.commit()
    return {"ok": True}

@router.post("/api/premises/{pid}/occupancy")
async def set_occupancy(pid: int, request: Request, u: User = Depends(need("premises.occupancy")), s: Session = Depends(db)):
    p = get_prem(s, u, pid, "premises.occupancy"); b = await request.json()
    if b.get("status") not in ("occupied", "partial", "vacant"): raise HTTPException(400, "Choose occupied, partial or vacant")
    m = s.get(PremisesMeta, pid) or PremisesMeta(premises_id=pid); prev = m.occupancy; m.occupancy = b["status"]
    s.add(m); audit(s, u, "premises", pid, "occupancy_changed", {"occupancy": prev}, {"occupancy": m.occupancy}); s.commit(); return {"occupancy": m.occupancy}

# ---------- premises document vault ----------
def doc_state(d, today=None):
    t = today or dt.date.today()
    if not d.valid_to: return None
    n = (d.valid_to - t).days
    return "expired" if n < 0 else "d7" if n <= 7 else "d30" if n <= 30 else "d90" if n <= 90 else "ok"

@router.get("/api/premises/{pid}/documents")
def prem_docs(pid: int, u: User = Depends(need("premises.docs")), s: Session = Depends(db)):
    get_prem(s, u, pid, "premises.docs")
    return [row(d, state=doc_state(d)) for d in s.query(PremisesDocument).filter_by(premises_id=pid).order_by(PremisesDocument.doc_type, PremisesDocument.version.desc())]

@router.post("/api/premises/{pid}/documents")
def add_prem_doc(pid: int, doc_type: str = Form(...), title: str = Form(""), number: str = Form(""), authority: str = Form(""), issued_on: str = Form(""), valid_to: str = Form(""),
                 notes: str = Form(""), file: UploadFile | None = File(None), u: User = Depends(need("premises.docs")), s: Session = Depends(db)):
    get_prem(s, u, pid, "premises.docs")
    if doc_type not in DOC_TYPES: raise HTTPException(400, "Unknown document type")
    try: iso, vt = pdate(issued_on), pdate(valid_to)
    except ValueError as e: raise HTTPException(400, str(e))
    prev = s.query(PremisesDocument).filter(PremisesDocument.premises_id == pid, PremisesDocument.doc_type == doc_type, func.coalesce(PremisesDocument.title, "") == (title or "")).order_by(PremisesDocument.version.desc()).first()
    d = PremisesDocument(premises_id=pid, doc_type=doc_type, title=title or None, number=number or None, authority=authority or None, issued_on=iso, valid_to=vt, notes=notes or None,
                         file=save_upload(file), version=(prev.version + 1) if prev else 1, uploaded_by=u.name)
    s.add(d); s.flush(); audit(s, u, "premises", pid, "document_added", {"version": prev.version} if prev else None, {"type": doc_type, "title": title, "valid_to": vt, "version": d.version}); s.commit()
    return row(d, state=doc_state(d))

def docs_summary(s, u):
    """Documents expiring within 90 days (latest version only), for the dashboard and bell. Reminder levels: 90, 30, 7 days."""
    if not can(u, "premises.docs"): return None
    ids = scope_premises(s, u, "premises.docs"); q = s.query(PremisesDocument)
    if ids is not None: q = q.filter(PremisesDocument.premises_id.in_(ids or {-1}))
    latest = {}
    for d in q.filter(PremisesDocument.valid_to.isnot(None)).all():
        k = (d.premises_id, d.doc_type, d.title or "")
        if k not in latest or d.version > latest[k].version: latest[k] = d
    names = {p.id: p.name for p in s.query(Premises)}
    items = sorted([{"premises_id": d.premises_id, "premises": names.get(d.premises_id), "doc_type": d.doc_type, "title": d.title, "valid_to": d.valid_to.isoformat(), "state": doc_state(d)}
                    for d in latest.values() if doc_state(d) not in (None, "ok")], key=lambda x: x["valid_to"])
    return {"count": len(items), "expired": sum(1 for x in items if x["state"] == "expired"), "items": items[:8]}

# ---------- utilities ----------
def bill_state(b, today=None):
    t = today or dt.date.today()
    if b.status == "paid": return "paid"
    if not b.due_date: return "due"
    n = (b.due_date - t).days
    return "overdue" if n < 0 else "due_soon" if n <= 7 else "due"

def acct_out(s, a, bills=None):
    B = bills if bills is not None else s.query(UtilityBill).filter_by(account_id=a.id).order_by(UtilityBill.id.desc()).all()
    last = B[0] if B else None; unpaid = [b for b in B if b.status != "paid"]
    nxt = min((b.due_date for b in unpaid if b.due_date), default=None)
    return row(a, bills=len(B), unpaid=len(unpaid), overdue=sum(1 for b in unpaid if bill_state(b) == "overdue"), next_due=nxt.isoformat() if nxt else None,
               last_bill=row(last, state=bill_state(last)) if last else None)

def util_accounts_q(s, u, perm="utilities.read", premises_id=None):
    q = s.query(UtilityAccount); ids = scope_premises(s, u, perm)
    if ids is not None: q = q.filter(UtilityAccount.premises_id.in_(ids or {-1}))
    if premises_id: q = q.filter(UtilityAccount.premises_id.in_(descendants(s, premises_id)))
    return q

@router.get("/api/utilities/accounts")
def util_accounts(premises_id: int | None = None, exact: bool = False, u: User = Depends(need("utilities.read")), s: Session = Depends(db)):
    q = util_accounts_q(s, u)
    if premises_id: q = q.filter(UtilityAccount.premises_id == premises_id) if exact else q.filter(UtilityAccount.premises_id.in_(descendants(s, premises_id)))
    return [acct_out(s, a) for a in q.order_by(UtilityAccount.premises_id, UtilityAccount.kind)]

@router.post("/api/utilities/accounts")
async def util_add(request: Request, u: User = Depends(need("utilities.write")), s: Session = Depends(db)):
    b = await request.json(); p = s.get(Premises, b.get("premises_id"))
    if not p or not in_scope(s, u, "utilities.write", p.id): raise HTTPException(403, "Premises outside your scope")
    if b.get("kind") not in UTIL_KINDS: raise HTTPException(400, "Choose a utility type")
    if not (b.get("provider") or "").strip(): raise HTTPException(400, "Supplier / provider name is required")
    a = UtilityAccount(premises_id=p.id, kind=b["kind"], provider=b["provider"].strip(), account_ref=(b.get("account_ref") or "").strip() or None, frequency=b.get("frequency") or "monthly",
                       contact=b.get("contact") or None, notes=b.get("notes") or None)
    s.add(a); s.flush(); audit(s, u, "premises", p.id, "utility_added", None, {"kind": a.kind, "provider": a.provider}); s.commit(); return acct_out(s, a)

@router.post("/api/utilities/accounts/{aid}/update")
async def util_update(aid: int, request: Request, u: User = Depends(need("utilities.write")), s: Session = Depends(db)):
    a = s.get(UtilityAccount, aid)
    if not a or not in_scope(s, u, "utilities.write", a.premises_id): raise HTTPException(404, "Account not found in your scope")
    b = await request.json(); prev = {}
    for k in ("provider", "account_ref", "frequency", "contact", "notes"):
        if k in b and (b[k] or None) != getattr(a, k): prev[k] = getattr(a, k); setattr(a, k, (b[k] or "").strip() or None if k != "provider" else (b[k] or a.provider))
    if "active" in b: prev["active"] = a.active; a.active = bool(b["active"])
    audit(s, u, "premises", a.premises_id, "utility_updated", prev, {k: getattr(a, k) for k in prev}); s.commit(); return acct_out(s, a)

@router.get("/api/utilities/bills")
def util_bills(premises_id: int | None = None, u: User = Depends(need("utilities.read")), s: Session = Depends(db)):
    A = {a.id: a for a in util_accounts_q(s, u, premises_id=premises_id)}; comp = {c.id: c.currency for c in s.query(Company)}
    out = []
    for b in s.query(UtilityBill).filter(UtilityBill.account_id.in_(list(A) or [-1])).order_by(UtilityBill.due_date.desc().nullslast(), UtilityBill.id.desc()).limit(500):
        a = A[b.account_id]; out.append(row(b, state=bill_state(b), kind=a.kind, provider=a.provider, account_ref=a.account_ref, premises_id=a.premises_id))
    return out

@router.post("/api/utilities/accounts/{aid}/bills")
def util_bill_add(aid: int, period: str = Form(""), invoice_no: str = Form(""), invoice_date: str = Form(""), due_date: str = Form(""), amount: str = Form(...), currency: str = Form(""),
                  notes: str = Form(""), file: UploadFile | None = File(None), u: User = Depends(need("utilities.write")), s: Session = Depends(db)):
    a = s.get(UtilityAccount, aid)
    if not a or not in_scope(s, u, "utilities.write", a.premises_id): raise HTTPException(404, "Account not found in your scope")
    try: amt = pnum(amount, "amount"); idt, dd = pdate(invoice_date), pdate(due_date)
    except ValueError as e: raise HTTPException(400, str(e))
    if amt is None or amt < 0: raise HTTPException(400, "Enter the invoice amount")
    p = s.get(Premises, a.premises_id); cur = (currency or (s.get(Company, p.company_id).currency if p else "INR")).upper()[:3]
    b = UtilityBill(account_id=aid, period=period or None, invoice_no=invoice_no or None, invoice_date=idt, due_date=dd, amount=amt, currency=cur, notes=notes or None,
                    invoice_file=save_upload(file), created_by=u.name)
    s.add(b); s.flush(); audit(s, u, "premises", a.premises_id, "utility_bill_added", None, {"kind": a.kind, "amount": amt, "due": dd, "invoice": invoice_no}); s.commit()
    return row(b, state=bill_state(b))

@router.post("/api/utilities/bills/{bid}/pay")
def util_bill_pay(bid: int, paid_on: str = Form(""), payment_ref: str = Form(""), file: UploadFile | None = File(None), u: User = Depends(need("utilities.write")), s: Session = Depends(db)):
    b = s.get(UtilityBill, bid); a = s.get(UtilityAccount, b.account_id) if b else None
    if not b or not in_scope(s, u, "utilities.write", a.premises_id): raise HTTPException(404, "Bill not found in your scope")
    if b.status == "paid": raise HTTPException(400, "Already marked paid")
    proof = save_upload(file)
    if not proof and not payment_ref.strip(): raise HTTPException(400, "Attach the payment proof or enter a payment reference")
    try: b.paid_on = pdate(paid_on) or dt.date.today()
    except ValueError as e: raise HTTPException(400, str(e))
    b.status, b.payment_ref, b.proof_file = "paid", payment_ref or None, proof
    audit(s, u, "premises", a.premises_id, "utility_bill_paid", None, {"kind": a.kind, "amount": b.amount, "ref": b.payment_ref}); s.commit(); return row(b, state="paid")

def util_summary(s, u):
    if not can(u, "utilities.read"): return None
    A = {a.id for a in util_accounts_q(s, u)}; B = [b for b in s.query(UtilityBill).filter(UtilityBill.account_id.in_(list(A) or [-1]), UtilityBill.status != "paid")]
    return {"overdue": sum(1 for b in B if bill_state(b) == "overdue"), "due_soon": sum(1 for b in B if bill_state(b) == "due_soon"), "accounts": len(A)}

# ---------- demo data: remove Bengaluru, give The Arch Place full details, utilities and documents ----------
def seed_phase4(s):
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n)
    hq = s.query(Premises).filter_by(name="Corporate Office, Bengaluru").first()
    cgc = s.query(Premises).filter(Premises.name.like("Corporate Governance Center%")).first()
    if hq and cgc:   # re-home everything that sat in Bengaluru to CGC Ahmedabad (same company), then remove Bengaluru
        for M in (Vehicle, Trip, Asset, Ticket, Employee):
            for o in s.query(M).filter(M.premises_id == hq.id): o.premises_id = cgc.id
        for k in s.query(Premises).filter_by(parent_id=hq.id):
            k.parent_id = cgc.id
            if k.name == "Guest House 1": k.name, k.address, k.lat, k.lng = "CGC Guest House 2, Ahmedabad", "Ahmedabad, Gujarat, India", 23.0225, 72.5714
        for g in s.query(RoleGrant).filter_by(scope_level="premises", scope_id=hq.id): g.scope_id = cgc.id
        for v in s.query(Vehicle).filter(Vehicle.reg_no.like("KA01%")): v.reg_no = "GJ01" + v.reg_no[4:]
        for tr in s.query(Trip):
            tr.pickup = (tr.pickup or "").replace("Corporate Office", "CGC Office") or None
            tr.destination = tr.destination.replace("Kempegowda Airport", "Ahmedabad Airport").replace("Whitefield Site", "Sanand Site")
        hu = s.query(User).filter_by(email="premises@bms.local").first()
        if hu: hu.name = "Admin In-charge (CGC)"
        gm = s.get(PremisesMeta, hq.id)
        if gm: s.delete(gm)
        s.flush(); s.delete(hq); s.flush()
    arch = s.query(Premises).filter(Premises.name.like("Corporate Business Center%")).first()
    if not arch: s.commit(); return
    m = s.get(PremisesMeta, arch.id) or PremisesMeta(premises_id=arch.id)
    if m.area_sqft is None:
        m.area_sqft, m.floors, m.floors_taken, m.ownership, m.declared_headcount = 18500, 3, "7th to 9th floor", "leased", 120
        m.litigation_count, m.occupancy, m.location = 2, "occupied", "Kilimani, Nairobi"
        m.litigation_notes = "2 open matters: a lease dispute with a former sub-tenant and a labour claim. Sample data, replace with the legal team's figures."
        m.maps_url = "https://www.google.com/maps?q=-1.2890,36.7900"; m.contact_name, m.contact_phone = "Building manager", "+254 700 200 001"; m.amenities = "Lift, Basement parking, Generator backup, 24h security, Reception"
        s.add(m)
        for typ, title, num, auth, iss, vt in [("lease", "Office lease, 7th to 9th floor", "LSE/2023/0187", "Landlord (sample)", -700, 40), ("govt_registration", "Single business permit", "SBP-2026-4412", "Nairobi County", -300, 65),
                                              ("tax", "Land rates / property tax receipt", "LR-2026-0099", "Nairobi County", -120, -5), ("occupancy_certificate", "Occupancy certificate", "OC-7781", "Nairobi County", -900, 300),
                                              ("fire_noc", "Fire safety certificate", "FSC-2025-310", "Fire Department", -200, 20), ("purchase_deed", "Not applicable, leased premises (placeholder)", None, None, None, None)]:
            if typ == "purchase_deed": continue
            s.add(PremisesDocument(premises_id=arch.id, doc_type=typ, title=title, number=num, authority=auth, issued_on=D(iss), valid_to=D(vt), notes="Sample record. Upload the scan to complete it.", uploaded_by="demo seed"))
    for name, occ in (("Kileleshwa Guest House%", "partial"), ("Westlands Guest House%", "vacant"), ("The Arch Place Guest House%", "occupied")):
        g = s.query(Premises).filter(Premises.name.like(name)).first()
        if g:
            gm = s.get(PremisesMeta, g.id) or PremisesMeta(premises_id=g.id)
            if not gm.occupancy: gm.occupancy = occ; s.add(gm)
    if not s.query(UtilityAccount).first():
        def acct(p, kind, prov, ref, bills):
            a = UtilityAccount(premises_id=p.id, kind=kind, provider=prov, account_ref=ref, frequency="monthly"); s.add(a); s.flush()
            for per, inv, amt, due, paid in bills:
                b = UtilityBill(account_id=a.id, period=per, invoice_no=inv, invoice_date=D(due - 20), due_date=D(due), amount=amt, currency="KES", created_by="demo seed")
                if paid: b.status, b.paid_on, b.payment_ref = "paid", D(due - 2), "MPESA-DEMO"
                s.add(b)
            return a
        kil = s.query(Premises).filter(Premises.name.like("The Arch Place Guest House%")).first(); kel = s.query(Premises).filter(Premises.name.like("Kileleshwa Guest House%")).first()
        acct(arch, "electricity", "Kenya Power (sample)", "ACC-0010001", [("2026-09", "KP-9001", 184500, -45, True), ("2026-10", "KP-9102", 191200, -15, False), ("2026-11", "KP-9203", 176800, 12, False)])
        acct(arch, "water", "Nairobi City Water (sample)", "ACC-0020002", [("2026-10", "NW-5501", 22400, -8, False), ("2026-11", "NW-5602", 21800, 20, False)])
        acct(arch, "internet", "Safaricom Business Fibre (sample)", "ACC-0030003", [("2026-10", "SF-7001", 65000, -12, True), ("2026-11", "SF-7102", 65000, 5, False)])
        if kil:
            acct(kil, "electricity", "Kenya Power (sample)", "ACC-1100011", [("2026-10", "KP-4410", 14200, -10, True), ("2026-11", "KP-4511", 15100, 9, False)])
            acct(kil, "internet", "Zuku Fiber (sample)", "ACC-1100012", [("2026-10", "ZK-3301", 5500, -6, False)])
            acct(kil, "water", "Nairobi City Water (sample)", "ACC-1100013", [("2026-10", "NW-2201", 3200, -20, True)])
        if kel: acct(kel, "electricity", "Kenya Power (sample)", "ACC-1200021", [("2026-10", "KP-6601", 12900, 3, False)]); acct(kel, "internet", "Safaricom Home Fibre (sample)", "ACC-1200022", [("2026-10", "SF-8801", 4999, 11, False)])
        if kil:
            net = s.query(UtilityAccount).filter_by(premises_id=kil.id, kind="internet").first(); u2 = s.query(User).filter_by(email="guesthouse@bms.local").first() or s.query(User).first()
            tk = Ticket(company_id=kil.company_id, premises_id=kil.id, category="utilities", title="Internet down since morning", description="WiFi router shows no signal. Provider contacted, please follow up.",
                        priority="high", status="open", raised_by=u2.id, raised_by_name=u2.name, utility_id=net.id, due_at=dt.datetime.utcnow() + dt.timedelta(hours=24)); s.add(tk); s.flush()
            s.add(TicketEvent(ticket_id=tk.id, user_id=u2.id, user_name=u2.name, kind="created", text=f"Raised by {u2.name} · priority high"))
    s.commit()

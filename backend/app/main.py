import os, uuid, datetime as dt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from .models import *
from .core import *
from .seed import seed
from .phase1 import router as phase1_router, seed_phase1
from .phase4 import router as phase4_router, seed_phase4
from .phase5 import router as phase5_router, seed_phase5
from .phase6 import router as phase6_router, seed_phase6
from .phase7 import router as phase7_router, seed_phase7
from .phase2 import router as phase2_router, seed_phase2, seed_phase3

UPLOAD = os.environ.get("UPLOAD_DIR", "/data/uploads")
os.makedirs(UPLOAD, exist_ok=True)
app = FastAPI(title="Building Management System API", version="0.1")

@app.on_event("startup")
def startup():
    import time
    for _ in range(20):
        try: Base.metadata.create_all(engine); break
        except Exception: time.sleep(1)
    from sqlalchemy import text   # create_all never alters existing tables, so add later columns here (idempotent)
    ALTERS = [("premises_meta", c, t) for c, t in (("floors", "INTEGER"), ("halls", "INTEGER"), ("balconies", "INTEGER"), ("kitchens", "INTEGER"), ("maps_url", "VARCHAR(500)"),
              ("location", "VARCHAR(200)"), ("amenities", "TEXT"), ("contact_name", "VARCHAR(200)"), ("contact_phone", "VARCHAR(40)"), ("area_sqft", "DOUBLE PRECISION"),
              ("floors_taken", "VARCHAR(100)"), ("ownership", "VARCHAR(20)"), ("declared_headcount", "INTEGER"), ("litigation_count", "INTEGER"), ("litigation_notes", "TEXT"), ("occupancy", "VARCHAR(20)"))] + [
              ("guest_allocations", "room_id", "INTEGER"), ("tickets", "utility_id", "INTEGER"), ("vehicles", "current_value", "DOUBLE PRECISION"), ("travel_advances", "request_id", "INTEGER"),
              ("vehicle_documents", "renewal_cost", "DOUBLE PRECISION"), ("fuel_logs", "start_meter", "DOUBLE PRECISION"), ("fuel_logs", "start_photo", "VARCHAR(300)")]
    with engine.begin() as c:
        for tbl, col, typ in ALTERS: c.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typ}"))
    if os.environ.get("SEED_DEMO") == "1":
        with SessionLocal() as s: seed(s); seed_phase1(s); seed_phase2(s); seed_phase3(s); seed_phase4(s); seed_phase5(s); seed_phase6(s); seed_phase7(s)

    em, pw = os.environ.get("BOOTSTRAP_ADMIN_EMAIL"), os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if em and pw:   # first-run Group Admin for a real (non-demo) deployment; no-op once any user exists
        with SessionLocal() as s:
            if not s.query(User).count():
                u = User(email=em.lower(), name=os.environ.get("BOOTSTRAP_ADMIN_NAME", "Group Admin"), password_hash=hash_pw(pw)); s.add(u); s.flush()
                s.add(RoleGrant(user_id=u.id, role="group_admin", scope_level="group", scope_id=None)); s.commit()

async def save(f: UploadFile | None):
    if not f or not f.filename: return None
    ext = os.path.splitext(f.filename)[1].lower()[:8] or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}: raise HTTPException(400, "Unsupported file type")
    data = await f.read()
    if len(data) > 15_000_000: raise HTTPException(400, "File too large (15 MB max)")
    name = uuid.uuid4().hex + ext
    open(os.path.join(UPLOAD, name), "wb").write(data)
    return name

@app.get("/api/files/{name}")
def get_file(name: str, u: User = Depends(current_user)):
    p = os.path.join(UPLOAD, os.path.basename(name))
    if not os.path.exists(p): raise HTTPException(404)
    return FileResponse(p)

# ---------- auth ----------
@app.post("/api/auth/login")
async def login(request: Request, s: Session = Depends(db)):
    b = await request.json()
    u = s.query(User).filter(func.lower(User.email) == b.get("email", "").lower().strip()).first()
    if not u or not u.active or not check_pw(b.get("password", ""), u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(u.id), "user": me_payload(u)}

DEMO_ACCOUNTS = [("Group Admin", "admin@bms.local", "admin123"), ("Corporate Admin Head", "head@bms.local", "head123"),
                 ("Admin In-charge (HQ)", "premises@bms.local", "premises123"),
                 ("Guest House In-charge", "guesthouse@bms.local", "gh123"), ("Maintenance Head", "maintenance@bms.local", "maint123"), ("Travel Desk", "traveldesk@bms.local", "travel123"), ("HR Manager", "hr@bms.local", "hr123"), ("CGC Admin In-charge", "cgc@bms.local", "cgc123"),
                 ("Driver", "driver1@bms.local", "driver123")]

@app.get("/api/auth/demo")
def demo_accounts():
    """Only when SEED_DEMO=1: lets the login page offer one-click demo sign-in. Never enable in production."""
    if os.environ.get("SEED_DEMO") != "1": return []
    return [{"label": l, "email": e, "password": p} for l, e, p in DEMO_ACCOUNTS]

def me_payload(u):
    return {"id": u.id, "name": u.name, "email": u.email,
            "grants": [{"role": g.role, "scope_level": g.scope_level, "scope_id": g.scope_id} for g in u.grants],
            "perms": sorted({p for g in u.grants for p in ROLE_PERMS.get(g.role, set())})}

@app.get("/api/me")
def me(u: User = Depends(current_user)): return me_payload(u)

# ---------- reference data ----------
@app.get("/api/companies")
def companies(u: User = Depends(current_user), s: Session = Depends(db)):
    return [row(c) for c in s.query(Company).order_by(Company.name)]

@app.get("/api/premises")
def premises(u: User = Depends(current_user), s: Session = Depends(db)):
    q = s.query(Premises).order_by(Premises.name)
    perm = next((p for p in ("premises.write", "vehicles.read", "assets.read", "tickets.read", "employees.read") if can(u, p)), "premises.write")
    ids = scope_premises(s, u, perm)
    if ids is not None: q = q.filter(Premises.id.in_(ids or {-1}))
    return [row(p) for p in q]

@app.post("/api/premises")
async def add_premises(request: Request, u: User = Depends(need("premises.write")), s: Session = Depends(db)):
    b = await request.json()
    parent = s.get(Premises, b["parent_id"]) if b.get("parent_id") else None
    ids = scope_premises(s, u, "premises.write")
    if ids is not None and (not parent or parent.id not in ids): raise HTTPException(403, "Outside your scope")
    p = Premises(company_id=parent.company_id if parent else b["company_id"], parent_id=b.get("parent_id"),
                 name=b["name"], type=b.get("type", "office"), address=b.get("address"))
    s.add(p); s.flush(); audit(s, u, "premises", p.id, "create", None, row(p)); s.commit()
    return row(p)

@app.get("/api/users")
def users(u: User = Depends(need("users.admin")), s: Session = Depends(db)):
    return [{**row(x), "grants": [{"role": g.role, "scope_level": g.scope_level, "scope_id": g.scope_id} for g in x.grants]}
            for x in s.query(User).order_by(User.name)]

@app.post("/api/users")
async def add_user(request: Request, u: User = Depends(need("users.admin")), s: Session = Depends(db)):
    b = await request.json()
    if b["role"] not in ROLE_PERMS: raise HTTPException(400, "Unknown role")
    if b["role"] == "group_admin" and not any(g.role == "group_admin" for g in u.grants):
        raise HTTPException(403, "Only a Group Admin can create a Group Admin")
    if s.query(User).filter(func.lower(User.email) == b["email"].lower()).first(): raise HTTPException(409, "Email already exists")
    n = User(email=b["email"].strip(), name=b["name"], phone=b.get("phone"), password_hash=hash_pw(b["password"]))
    s.add(n); s.flush()
    s.add(RoleGrant(user_id=n.id, role=b["role"], scope_level=b.get("scope_level", "company"), scope_id=b.get("scope_id")))
    audit(s, u, "user", n.id, "create", None, {"email": n.email, "role": b["role"], "scope": [b.get("scope_level"), b.get("scope_id")]})
    s.commit(); return row(n)

# ---------- vehicles ----------
def vehicle_q(s, u):
    q = s.query(Vehicle)
    ids = scope_premises(s, u, "vehicles.read")
    if ids is not None: q = q.filter(Vehicle.premises_id.in_(ids or {-1}))
    return q

@app.get("/api/vehicles")
def vehicles(u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    today = dt.date.today()
    out = []
    for v in vehicle_q(s, u).order_by(Vehicle.reg_no):
        docs = s.query(VehicleDocument).filter_by(vehicle_id=v.id).all()
        nxt = min((d.valid_to for d in docs if d.valid_to), default=None)
        out.append(row(v, next_expiry=nxt.isoformat() if nxt else None,
                       expiry_state=None if not nxt else "overdue" if nxt < today else "due_soon" if (nxt - today).days <= 30 else "ok"))
    return out

@app.post("/api/vehicles")
async def add_vehicle(request: Request, u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    b = await request.json()
    p = s.get(Premises, b["premises_id"])
    ids = scope_premises(s, u, "vehicles.write")
    if not p or (ids is not None and p.id not in ids): raise HTTPException(403, "Premises outside your scope")
    if s.query(Vehicle).filter_by(reg_no=b["reg_no"].strip().upper()).first(): raise HTTPException(409, "Registration already exists")
    v = Vehicle(company_id=p.company_id, premises_id=p.id, reg_no=b["reg_no"].strip().upper(), make_model=b["make_model"],
                year=b.get("year"), odometer=b.get("odometer") or 0, pool=b.get("pool", True))
    s.add(v); s.flush(); audit(s, u, "vehicle", v.id, "create", None, row(v)); s.commit(); return row(v)

def get_vehicle(s, u, vid):
    v = vehicle_q(s, u).filter(Vehicle.id == vid).first()
    if not v: raise HTTPException(404, "Vehicle not found in your scope")
    return v

@app.get("/api/vehicles/{vid}")
def vehicle_detail(vid: int, u: User = Depends(need("vehicles.read")), s: Session = Depends(db)):
    v = get_vehicle(s, u, vid)
    return {"vehicle": row(v),
            "documents": [row(d) for d in s.query(VehicleDocument).filter_by(vehicle_id=vid).order_by(VehicleDocument.valid_to)],
            "trips": [row(t) for t in s.query(Trip).filter_by(vehicle_id=vid).order_by(Trip.id.desc()).limit(20)],
            "fuel": [row(f) for f in s.query(FuelLog).filter_by(vehicle_id=vid).order_by(FuelLog.id.desc()).limit(20)]}

@app.post("/api/vehicles/{vid}/documents")
async def add_doc(vid: int, doc_type: str = Form(...), number: str = Form(""), authority: str = Form(""),
                  valid_to: str = Form(""), renewal_cost: str = Form(""), file: UploadFile | None = File(None),
                  u: User = Depends(need("vehicles.write")), s: Session = Depends(db)):
    get_vehicle(s, u, vid)
    prev = s.query(VehicleDocument).filter_by(vehicle_id=vid, doc_type=doc_type).order_by(VehicleDocument.version.desc()).first()
    d = VehicleDocument(vehicle_id=vid, doc_type=doc_type, number=number or None, authority=authority or None,
                        valid_to=dt.date.fromisoformat(valid_to) if valid_to else None, file=await save(file),
                        renewal_cost=float(renewal_cost) if renewal_cost else None,
                        version=(prev.version + 1) if prev else 1)
    s.add(d); s.flush(); audit(s, u, "vehicle", vid, "document_added", row(prev) if prev else None, row(d)); s.commit()
    return row(d)

# ---------- trips ----------
def trip_view(s, t):
    v = s.get(Vehicle, t.vehicle_id) if t.vehicle_id else None
    dr = s.get(User, t.driver_id) if t.driver_id else None
    rq = s.get(User, t.requester_id)
    return row(t, vehicle=v.reg_no if v else None, vehicle_name=v.make_model if v else None,
               driver=dr.name if dr else None, requester=rq.name if rq else None,
               distance=(t.end_meter - t.start_meter) if t.end_meter is not None and t.start_meter is not None else None)

@app.get("/api/trips")
def trips(status: str | None = None, u: User = Depends(current_user), s: Session = Depends(db)):
    q = s.query(Trip).order_by(Trip.id.desc())
    if can(u, "trips.read"):
        ids = scope_premises(s, u, "trips.read")
        if ids is not None: q = q.filter(Trip.premises_id.in_(ids or {-1}))
    else:
        q = q.filter(Trip.requester_id == u.id)  # employees: own records only
    if status: q = q.filter(Trip.status == status)
    return [trip_view(s, t) for t in q.limit(300)]

@app.post("/api/trips")
async def request_trip(request: Request, u: User = Depends(need("trips.request")), s: Session = Depends(db)):
    b = await request.json()
    comp = next((g.scope_id for g in u.grants if g.scope_level == "company"), None)
    pid = b.get("premises_id")
    p = s.get(Premises, pid) if pid else s.query(Premises).filter_by(company_id=comp, parent_id=None).first()
    if not p: raise HTTPException(400, "No premises for this request")
    t = Trip(company_id=p.company_id, premises_id=p.id, requester_id=u.id, pickup=b.get("pickup"),
             destination=b["destination"], purpose=b.get("purpose"),
             needed_at=dt.datetime.fromisoformat(b["needed_at"]) if b.get("needed_at") else None)
    s.add(t); s.flush(); audit(s, u, "trip", t.id, "create", None, row(t)); s.commit(); return trip_view(s, t)

@app.get("/api/drivers")
def drivers(u: User = Depends(need("trips.assign")), s: Session = Depends(db)):
    q = s.query(User).join(RoleGrant).filter(RoleGrant.role == "driver", User.active)
    return [{"id": d.id, "name": d.name, "phone": d.phone} for d in q.distinct()]

@app.post("/api/trips/{tid}/assign")
async def assign(tid: int, request: Request, u: User = Depends(need("trips.assign")), s: Session = Depends(db)):
    b = await request.json()
    t = s.get(Trip, tid)
    ids = scope_premises(s, u, "trips.assign")
    if not t or (ids is not None and t.premises_id not in ids): raise HTTPException(404)
    if t.status not in ("requested", "assigned"): raise HTTPException(409, f"Trip is already {t.status}")
    v = get_vehicle(s, u, b["vehicle_id"]) if b.get("vehicle_id") else None
    if v and v.status in ("maintenance", "retired"): raise HTTPException(409, f"Vehicle is {v.status}")
    prev = {"vehicle_id": t.vehicle_id, "driver_id": t.driver_id, "status": t.status}
    t.vehicle_id = v.id if v else None; t.driver_id = b.get("driver_id"); t.status = "assigned"
    audit(s, u, "trip", t.id, "assign", prev, {"vehicle_id": t.vehicle_id, "driver_id": t.driver_id, "status": t.status}); s.commit()
    return trip_view(s, t)

@app.post("/api/trips/{tid}/cancel")
def cancel(tid: int, u: User = Depends(current_user), s: Session = Depends(db)):
    t = s.get(Trip, tid)
    if not t or not (can(u, "trips.assign") or t.requester_id == u.id): raise HTTPException(404)
    if t.status in ("started", "completed"): raise HTTPException(409, "Trip already started")
    audit(s, u, "trip", t.id, "cancel", {"status": t.status}, {"status": "cancelled"}); t.status = "cancelled"; s.commit()
    return trip_view(s, t)

# ---------- driver app ----------
@app.get("/api/driver/trips")
def driver_trips(u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    q = s.query(Trip).filter(Trip.driver_id == u.id, Trip.status.in_(["assigned", "started"])).order_by(Trip.needed_at)
    recent = s.query(Trip).filter(Trip.driver_id == u.id, Trip.status == "completed").order_by(Trip.id.desc()).limit(5)
    return {"active": [trip_view(s, t) for t in q], "recent": [trip_view(s, t) for t in recent]}

@app.get("/api/driver/vehicles")
def driver_vehicles(u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    comps = [g.scope_id for g in u.grants if g.role == "driver"]
    return [row(v) for v in s.query(Vehicle).filter(Vehicle.company_id.in_(comps), Vehicle.status != "retired")]

def my_trip(s, u, tid, status):
    t = s.get(Trip, tid)
    if not t or t.driver_id != u.id: raise HTTPException(404, "Trip not found")
    if t.status != status: raise HTTPException(409, f"Trip is {t.status}, expected {status}")
    return t

@app.post("/api/driver/trips/{tid}/start")
async def start_trip(tid: int, meter: float = Form(...), lat: float | None = Form(None), lng: float | None = Form(None),
                     photo: UploadFile = File(...), u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    t = my_trip(s, u, tid, "assigned")
    v = s.get(Vehicle, t.vehicle_id)
    if not v: raise HTTPException(409, "No vehicle assigned to this trip")
    if meter < v.odometer: raise HTTPException(400, f"Meter cannot be below last recorded reading ({v.odometer:g})")
    t.start_meter, t.start_photo, t.start_at, t.start_lat, t.start_lng, t.status = meter, await save(photo), now(), lat, lng, "started"
    v.status = "on_trip"; v.odometer = meter
    audit(s, u, "trip", t.id, "start", {"status": "assigned"}, {"status": "started", "start_meter": meter}); s.commit()
    return trip_view(s, t)

@app.post("/api/driver/trips/{tid}/end")
async def end_trip(tid: int, meter: float = Form(...), notes: str = Form(""), lat: float | None = Form(None),
                   lng: float | None = Form(None), photo: UploadFile = File(...),
                   u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    t = my_trip(s, u, tid, "started")
    if meter < t.start_meter: raise HTTPException(400, f"Closing meter must be at least the start meter ({t.start_meter:g})")
    t.end_meter, t.end_photo, t.end_at, t.end_lat, t.end_lng, t.notes, t.status = meter, await save(photo), now(), lat, lng, notes or None, "completed"
    v = s.get(Vehicle, t.vehicle_id); v.status = "available"; v.odometer = max(v.odometer, meter)
    audit(s, u, "trip", t.id, "end", {"status": "started"}, {"status": "completed", "end_meter": meter}); s.commit()
    return trip_view(s, t)

# ---------- fuel ----------
@app.post("/api/fuel")
async def add_fuel(vehicle_id: int = Form(...), litres: float = Form(...), cost: float = Form(...), meter_reading: float = Form(...),
                   trip_id: int | None = Form(None), start_meter: float | None = Form(None), start_photo: UploadFile | None = File(None),
                   meter_photo: UploadFile | None = File(None), receipt: UploadFile | None = File(None),
                   u: User = Depends(need("driver.app")), s: Session = Depends(db)):
    v = s.get(Vehicle, vehicle_id)
    if not v or v.company_id not in [g.scope_id for g in u.grants if g.role == "driver"]: raise HTTPException(404, "Vehicle not found")
    if litres <= 0 or cost < 0: raise HTTPException(400, "Litres must be above zero")
    prev = s.query(FuelLog).filter_by(vehicle_id=vehicle_id).order_by(FuelLog.meter_reading.desc()).first()
    flags, kmpl = [], None
    mp = await save(meter_photo)
    sp = await save(start_photo)
    if not mp: flags.append("no_meter_photo")
    if start_meter is not None:
        if meter_reading < start_meter: flags.append("closing_below_start")
        if not sp: flags.append("no_start_photo")
    if prev:
        if meter_reading < prev.meter_reading: flags.append("meter_rollback")
        else:
            kmpl = round((meter_reading - prev.meter_reading) / litres, 2)
            if kmpl < 4 or kmpl > 30: flags.append("unusual_mileage")
    f = FuelLog(vehicle_id=vehicle_id, driver_id=u.id, trip_id=trip_id, litres=litres, cost=cost, meter_reading=meter_reading,
                meter_photo=mp, receipt=await save(receipt), mileage_kmpl=kmpl, start_meter=start_meter, start_photo=sp, flag=",".join(flags) or None)
    s.add(f); v.odometer = max(v.odometer, meter_reading); s.flush()
    audit(s, u, "vehicle", vehicle_id, "fuel_entry", None, {"litres": litres, "cost": cost, "meter": meter_reading, "kmpl": kmpl, "flag": f.flag})
    s.commit(); return row(f)

@app.get("/api/fuel")
def fuel(flagged: bool = False, premises_id: int | None = None, u: User = Depends(need("fuel.read")), s: Session = Depends(db)):
    q = s.query(FuelLog).join(Vehicle)
    if premises_id: q = q.filter(Vehicle.premises_id.in_(sub_ids(s, premises_id)))
    ids = scope_premises(s, u, "fuel.read")
    if ids is not None: q = q.filter(Vehicle.premises_id.in_(ids or {-1}))
    if flagged: q = q.filter(FuelLog.flag.isnot(None), FuelLog.reviewed.is_(False))
    out = []
    for f in q.order_by(FuelLog.id.desc()).limit(300):
        v, d = s.get(Vehicle, f.vehicle_id), s.get(User, f.driver_id)
        out.append(row(f, vehicle=v.reg_no, driver=d.name))
    return out

@app.post("/api/fuel/{fid}/review")
def review_fuel(fid: int, u: User = Depends(need("fuel.review")), s: Session = Depends(db)):
    f = s.get(FuelLog, fid)
    if not f: raise HTTPException(404)
    get_vehicle(s, u, f.vehicle_id)
    f.reviewed = True; audit(s, u, "vehicle", f.vehicle_id, "fuel_reviewed", {"flag": f.flag}, {"reviewed": True}); s.commit()
    return row(f)

# ---------- dashboard & audit ----------
def sub_ids(s, pid):
    """Premises id plus all descendants (sub-premises)."""
    rows = s.query(Premises.id, Premises.parent_id).all(); out, stack = set(), [pid]
    while stack:
        x = stack.pop(); out.add(x); stack += [r.id for r in rows if r.parent_id == x]
    return out

@app.get("/api/dashboard")
def dashboard(premises_id: int | None = None, u: User = Depends(need("dashboard")), s: Session = Depends(db)):
    today = dt.date.today(); vs = vehicle_q(s, u).all()
    narrow = sub_ids(s, premises_id) if premises_id else None
    if narrow is not None: vs = [v for v in vs if v.premises_id in narrow]
    vids = [v.id for v in vs]
    docs = s.query(VehicleDocument).filter(VehicleDocument.vehicle_id.in_(vids or [-1]), VehicleDocument.valid_to.isnot(None)).all()
    latest = {}
    for d in docs:
        k = (d.vehicle_id, d.doc_type)
        if k not in latest or d.version > latest[k].version: latest[k] = d   # only the current version counts
    reg = {v.id: v.reg_no for v in vs}
    expiring = sorted([{"vehicle": reg[d.vehicle_id], "vehicle_id": d.vehicle_id, "doc_type": d.doc_type, "valid_to": d.valid_to.isoformat(),
                        "days": (d.valid_to - today).days} for d in latest.values() if (d.valid_to - today).days <= 30], key=lambda x: x["days"])
    first = dt.datetime(today.year, today.month, 1)
    fl = s.query(FuelLog).filter(FuelLog.vehicle_id.in_(vids or [-1]), FuelLog.at >= first).all()
    tr = s.query(Trip).filter(Trip.end_at >= first, Trip.vehicle_id.in_(vids or [-1]), Trip.status == "completed").all()
    km = sum(t.end_meter - t.start_meter for t in tr)
    cost = sum(f.cost for f in fl)
    tq = s.query(Trip)
    ids = scope_premises(s, u, "trips.read")
    if ids is not None: tq = tq.filter(Trip.premises_id.in_(ids or {-1}))
    if narrow is not None: tq = tq.filter(Trip.premises_id.in_(narrow))
    return {"vehicles": len(vs), "available": sum(v.status == "available" for v in vs), "on_trip": sum(v.status == "on_trip" for v in vs),
            "maintenance": sum(v.status == "maintenance" for v in vs),
            "trips_open": tq.filter(Trip.status.in_(["requested", "assigned", "started"])).count(),
            "trips_unassigned": tq.filter(Trip.status == "requested").count(),
            "fuel_flagged": sum(1 for f in fl if f.flag and not f.reviewed),
            "fuel_cost_month": round(cost, 2), "km_month": round(km, 1),
            "cost_per_km": round(cost / km, 2) if km else None, "expiring": expiring}

@app.get("/api/audit")
def audit_log(entity: str | None = None, entity_id: int | None = None, u: User = Depends(need("audit.read")), s: Session = Depends(db)):
    q = s.query(Audit).order_by(Audit.id.desc())
    if entity:
        q = q.filter(Audit.entity == entity)
        if entity_id: q = q.filter(Audit.entity_id == entity_id)
    return [row(a) for a in q.limit(100)]

app.include_router(phase1_router)
app.include_router(phase2_router)
app.include_router(phase4_router)
app.include_router(phase5_router)
app.include_router(phase6_router)
app.include_router(phase7_router)

# ---------- static front-ends ----------
@app.get("/")
def root(): return RedirectResponse("/app/")
for mount, d in (("/app", "/srv/web"), ("/driver", "/srv/driver")):
    if os.path.isdir(d): app.mount(mount, StaticFiles(directory=d, html=True), name=mount.strip("/"))

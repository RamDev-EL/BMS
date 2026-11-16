"""Phase 2: employees per building, guest-house allocation, HRMS integration (configurable URL + credentials),
employee lookup (HR -> Admin) and travel-advance push (Admin / Claims -> HR)."""
import os, json, time, base64, hashlib, urllib.request, urllib.error, urllib.parse, datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, Header, Body
from sqlalchemy import func
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken
from .models import *
from .core import *
from .phase1 import scoped, in_scope, descendants, pdate, pnum, api_key

router = APIRouter()
ESTATUS = ["active", "on_leave", "notice", "resigned", "inactive"]

# ---------- employees ----------
def norm_status(v):
    v = (v or "").strip().lower().replace("-", " ").replace("_", " ")
    if not v: return "active"
    if "leave" in v: return "on_leave"
    if "notice" in v: return "notice"
    if any(x in v for x in ("resign", "exit", "terminat", "separat", "abscond", "left")): return "resigned"
    if "inactive" in v or "suspend" in v: return "inactive"
    return "active"

def make_employee(s, p, b, source="manual"):
    code, name = str(b.get("emp_code") or "").strip(), str(b.get("name") or "").strip()
    if not code or not name: raise ValueError("Employee code and name are required")
    if s.query(Employee).filter_by(company_id=p.company_id, emp_code=code).first(): raise ValueError(f"Employee code '{code}' already exists")
    e = Employee(company_id=p.company_id, premises_id=p.id, emp_code=code, name=name, email=b.get("email") or None, phone=b.get("phone") or None,
                 grade=(b.get("grade") or None), designation=b.get("designation") or None, department=b.get("department") or None,
                 status=norm_status(b.get("status")), join_date=pdate(b.get("join_date")), source=source)
    s.add(e); s.flush(); return e

def alloc_map(s):
    """employee_id -> active allocation row."""
    return {a.employee_id: a for a in s.query(GuestAllocation).filter_by(status="allocated")}

def emp_out(e, am, names):
    a = am.get(e.id)
    return row(e, guest_house_id=a.guest_house_id if a else None, guest_house=names.get(a.guest_house_id) if a else None, allocation_id=a.id if a else None)

@router.get("/api/employees")
def employees(premises_id: int | None = None, u: User = Depends(need("employees.read")), s: Session = Depends(db)):
    names = {p.id: p.name for p in s.query(Premises)}; am = alloc_map(s)
    return [emp_out(e, am, names) for e in scoped(s, u, Employee, "employees.read", premises_id).order_by(Employee.name)]

@router.post("/api/employees")
async def add_employee(request: Request, u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    b = await request.json(); p = s.get(Premises, b.get("premises_id"))
    if not p or not in_scope(s, u, "employees.write", p.id): raise HTTPException(403, "Premises outside your scope")
    try: e = make_employee(s, p, b)
    except ValueError as x: raise HTTPException(400, str(x))
    audit(s, u, "employee", e.id, "create", None, row(e)); s.commit(); return row(e)

@router.post("/api/employees/{eid}/update")
async def update_employee(eid: int, request: Request, u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    e = scoped(s, u, Employee, "employees.write").filter(Employee.id == eid).first()
    if not e: raise HTTPException(404, "Employee not found in your scope")
    b = await request.json(); prev = {}
    try:
        for k in ("name", "email", "phone", "grade", "designation", "department"):
            if k in b and (b[k] or None) != getattr(e, k): prev[k] = getattr(e, k); setattr(e, k, b[k] or None)
        if b.get("status") in ESTATUS and b["status"] != e.status:
            prev["status"] = e.status; e.status = b["status"]; from .phase5 import on_employee_status; s.flush(); on_employee_status(s, e, u)
        if "join_date" in b: prev["join_date"] = e.join_date; e.join_date = pdate(b["join_date"])
        if b.get("premises_id") and int(b["premises_id"]) != e.premises_id:
            p = s.get(Premises, int(b["premises_id"]))
            if not p or p.company_id != e.company_id or not in_scope(s, u, "employees.write", p.id): raise HTTPException(400, "Building must be in the same company and your scope")
            prev["premises_id"] = e.premises_id; e.premises_id = p.id
    except ValueError as x: raise HTTPException(400, str(x))
    audit(s, u, "employee", e.id, "update", prev, {k: getattr(e, k) for k in prev}); s.commit(); return row(e)

# ---------- guest houses ----------
PROFILE_INT = ("floors", "halls", "balconies", "kitchens")
PROFILE_TXT = ("maps_url", "location", "amenities", "contact_name", "contact_phone", "notes", "occupancy")

def scoped_prem(s, u):
    q = s.query(Premises); ids = scope_premises(s, u, "employees.read")
    return q.filter(Premises.id.in_(ids or {-1})) if ids is not None else q

def get_gh(s, u, gid):
    p = scoped_prem(s, u).filter(Premises.id == gid, Premises.type == "guest_house").first()
    if not p: raise HTTPException(404, "Guest house not found in your scope")
    return p

def attention(a, today):
    return a.status == "under_maintenance" or a.condition == "poor" or bool(a.next_service_due and a.next_service_due < today)

def gh_bundle(s, ps):
    """Guest-house rows with profile, bed counts (from rooms), occupancy and asset summary."""
    ids = [p.id for p in ps] or [-1]; today = dt.date.today()
    metas = {m.premises_id: m for m in s.query(PremisesMeta).filter(PremisesMeta.premises_id.in_(ids))}
    rooms, occ, assets = {}, {}, {}
    for r in s.query(GuestRoom).filter(GuestRoom.guest_house_id.in_(ids)): rooms.setdefault(r.guest_house_id, []).append(r)
    for g, n in s.query(GuestAllocation.guest_house_id, func.count()).filter(GuestAllocation.guest_house_id.in_(ids), GuestAllocation.status == "allocated").group_by(GuestAllocation.guest_house_id): occ[g] = n
    for a in s.query(Asset).filter(Asset.premises_id.in_(ids), Asset.status != "retired"): assets.setdefault(a.premises_id, []).append(a)
    out = []
    for p in ps:
        m, rs, A = metas.get(p.id), rooms.get(p.id, []), assets.get(p.id, [])
        prof = {k: getattr(m, k, None) if m else None for k in PROFILE_INT + PROFILE_TXT}
        out.append(row(p, **prof, bedrooms=len(rs), beds=sum(r.beds for r in rs) if rs else (m.beds if m else None), occupied=occ.get(p.id, 0),
                       assets=len(A), assets_attention=sum(1 for a in A if attention(a, today))))
    return out

def occupancy(s): return dict(s.query(GuestAllocation.guest_house_id, func.count()).filter_by(status="allocated").group_by(GuestAllocation.guest_house_id).all())

@router.get("/api/guesthouses")
def guesthouses(u: User = Depends(need("employees.read")), s: Session = Depends(db)):
    return gh_bundle(s, scoped_prem(s, u).filter(Premises.type == "guest_house").order_by(Premises.name).all())

@router.get("/api/guesthouses/{gid}")
def guesthouse(gid: int, u: User = Depends(need("employees.read")), s: Session = Depends(db)):
    from .phase1 import asset_out
    p = get_gh(s, u, gid); emps = {e.id: e for e in s.query(Employee)}
    al = s.query(GuestAllocation).filter_by(guest_house_id=gid).order_by(GuestAllocation.status, GuestAllocation.from_date.desc()).all()
    out, by_room = [], {}
    for a in al:
        e = emps.get(a.employee_id)
        x = row(a, emp_code=e.emp_code if e else None, name=e.name if e else "?", grade=e.grade if e else None, designation=e.designation if e else None,
                department=e.department if e else None, emp_status=e.status if e else None, building_id=e.premises_id if e else None)
        out.append(x)
        if a.status == "allocated" and a.room_id: by_room.setdefault(a.room_id, []).append(x)
    rooms = []
    for r in s.query(GuestRoom).filter_by(guest_house_id=gid).order_by(GuestRoom.floor, GuestRoom.name):
        occ = by_room.get(r.id, []); rooms.append(row(r, features=[f.strip() for f in (r.features or "").split(",") if f.strip()], occupants=occ, free=r.beds - len(occ)))
    unplaced = [x for x in out if x["status"] == "allocated" and not x["room_id"]]
    A = s.query(Asset).filter_by(premises_id=gid).order_by(Asset.asset_tag).all() if can(u, "assets.read") else []
    return {"guesthouse": gh_bundle(s, [p])[0], "rooms": rooms, "unplaced": unplaced, "allocations": out, "assets": [asset_out(a) for a in A],
            "can_allocate": in_scope(s, u, "allocations.write", gid), "can_edit": in_scope(s, u, "premises.write", gid)}

@router.post("/api/guesthouses/{gid}/profile")
async def gh_profile(gid: int, request: Request, u: User = Depends(need("premises.write")), s: Session = Depends(db)):
    p = get_gh(s, u, gid)
    if not in_scope(s, u, "premises.write", gid): raise HTTPException(403, "Outside your scope")
    b = await request.json(); m = s.get(PremisesMeta, gid) or PremisesMeta(premises_id=gid); prev = {}
    try:
        if (b.get("name") or "").strip() and b["name"].strip() != p.name: prev["name"] = p.name; p.name = b["name"].strip()
        if "address" in b and (b["address"] or None) != p.address: prev["address"] = p.address; p.address = b["address"] or None
        for k in ("lat", "lng"):
            if k in b: prev[k] = getattr(p, k); setattr(p, k, pnum(b[k], k))
        for k in PROFILE_INT:
            if k in b: prev[k] = getattr(m, k); setattr(m, k, int(pnum(b[k], k) or 0) or None)
        for k in PROFILE_TXT:
            if k in b: prev[k] = getattr(m, k); setattr(m, k, (b[k] or "").strip() or None)
    except ValueError as e: raise HTTPException(400, str(e))
    if m.maps_url and not m.maps_url.lower().startswith(("http://", "https://")): raise HTTPException(400, "The map link must start with https://")
    s.add(m); s.flush(); audit(s, u, "premises", gid, "guesthouse_details", prev, {k: (getattr(p, k, None) if hasattr(p, k) else getattr(m, k, None)) for k in prev}); s.commit()
    return gh_bundle(s, [p])[0]

@router.post("/api/guesthouses/{gid}/rooms")
async def gh_room(gid: int, request: Request, u: User = Depends(need("premises.write")), s: Session = Depends(db)):
    get_gh(s, u, gid)
    if not in_scope(s, u, "premises.write", gid): raise HTTPException(403, "Outside your scope")
    b = await request.json(); name = (b.get("name") or "").strip()
    if not name: raise HTTPException(400, "Room name is required")
    try: beds = int(pnum(b.get("beds"), "beds") or 1)
    except ValueError as e: raise HTTPException(400, str(e))
    if beds < 1 or beds > 20: raise HTTPException(400, "Beds must be between 1 and 20")
    r = s.get(GuestRoom, b["id"]) if b.get("id") else None
    if r and r.guest_house_id != gid: raise HTTPException(404)
    if s.query(GuestRoom).filter(GuestRoom.guest_house_id == gid, func.lower(GuestRoom.name) == name.lower(), GuestRoom.id != (r.id if r else -1)).first(): raise HTTPException(409, f"A room called '{name}' already exists")
    if r:
        n = s.query(GuestAllocation).filter_by(room_id=r.id, status="allocated").count()
        if beds < n: raise HTTPException(400, f"{n} people are in this room. Vacate them before reducing beds below {n}.")
    else: r = GuestRoom(guest_house_id=gid)
    prev = {"name": r.name, "beds": r.beds} if r.id else None
    r.name, r.beds, r.floor, r.features, r.notes = name, beds, (b.get("floor") or "").strip() or None, (b.get("features") or "").strip() or None, (b.get("notes") or "").strip() or None
    s.add(r); s.flush(); audit(s, u, "premises", gid, "guest_room_saved", prev, {"room": name, "beds": beds, "floor": r.floor}); s.commit(); return row(r)

@router.post("/api/rooms/{rid}/delete")
def room_delete(rid: int, u: User = Depends(need("premises.write")), s: Session = Depends(db)):
    r = s.get(GuestRoom, rid)
    if not r or not in_scope(s, u, "premises.write", r.guest_house_id): raise HTTPException(404, "Room not found in your scope")
    if s.query(GuestAllocation).filter_by(room_id=rid, status="allocated").count(): raise HTTPException(409, "Someone is still in this room. Vacate them first.")
    audit(s, u, "premises", r.guest_house_id, "guest_room_deleted", {"room": r.name}, None); s.delete(r); s.commit(); return {"ok": True}

@router.post("/api/guesthouses/{gid}/meta")
async def gh_meta(gid: int, request: Request, u: User = Depends(need("allocations.write")), s: Session = Depends(db)):
    p = get_gh(s, u, gid); b = await request.json(); m = s.get(PremisesMeta, gid) or PremisesMeta(premises_id=gid)
    prev = {"beds": m.beds, "rooms": m.rooms}
    m.beds = int(pnum(b.get("beds"), "beds") or 0) or None; m.rooms = int(pnum(b.get("rooms"), "rooms") or 0) or None; m.notes = b.get("notes") or m.notes
    s.add(m); audit(s, u, "premises", gid, "guesthouse_capacity", prev, {"beds": m.beds, "rooms": m.rooms}); s.commit(); return gh_bundle(s, [p])[0]

@router.post("/api/guesthouses/{gid}/allocate")
async def allocate(gid: int, request: Request, u: User = Depends(need("allocations.write")), s: Session = Depends(db)):
    p = get_gh(s, u, gid)
    if not in_scope(s, u, "allocations.write", gid): raise HTTPException(403, "Outside your scope")
    b = await request.json(); e = scoped(s, u, Employee, "employees.read").filter(Employee.id == b.get("employee_id")).first()
    if not e: raise HTTPException(404, "Employee not found in your scope")
    if e.status in ("resigned", "inactive"): raise HTTPException(400, f"{e.name} is {e.status}; cannot allocate")
    if e.company_id != p.company_id: raise HTTPException(400, "Employee belongs to a different company than this guest house")
    cur = s.query(GuestAllocation).filter_by(employee_id=e.id, status="allocated").first()
    if cur: raise HTTPException(409, f"{e.name} already has a bed in {s.get(Premises, cur.guest_house_id).name}. Vacate it first.")
    rooms = s.query(GuestRoom).filter_by(guest_house_id=gid).all(); room = None
    if rooms:
        room = next((r for r in rooms if r.id == b.get("room_id")), None)
        if not room: raise HTTPException(400, "Choose a room")
        if s.query(GuestAllocation).filter_by(room_id=room.id, status="allocated").count() >= room.beds: raise HTTPException(409, f"{room.name} is full ({room.beds} of {room.beds} beds)")
    else:
        m = s.get(PremisesMeta, gid)
        if m and m.beds and occupancy(s).get(gid, 0) >= m.beds: raise HTTPException(409, f"No free beds ({m.beds} of {m.beds} occupied)")
    try: fd = pdate(b.get("from_date")) or dt.date.today(); td = pdate(b.get("to_date"))
    except ValueError as x: raise HTTPException(400, str(x))
    if td and td < fd: raise HTTPException(400, "End date is before the start date")
    a = GuestAllocation(guest_house_id=gid, employee_id=e.id, room_id=room.id if room else None, room=room.name if room else (b.get("room") or None), purpose=b.get("purpose") or None, from_date=fd, to_date=td, allocated_by=u.name)
    s.add(a); s.flush(); audit(s, u, "premises", gid, "guest_allocated", None, {"employee": e.emp_code + " " + e.name, "from": fd, "to": td, "room": a.room}); s.commit(); return row(a)

@router.post("/api/allocations/{aid}/vacate")
def vacate(aid: int, u: User = Depends(need("allocations.write")), s: Session = Depends(db)):
    a = s.get(GuestAllocation, aid)
    if not a or not in_scope(s, u, "allocations.write", a.guest_house_id): raise HTTPException(404, "Allocation not found in your scope")
    if a.status != "allocated": raise HTTPException(400, "Already vacated")
    a.status, a.vacated_on = "vacated", dt.date.today(); e = s.get(Employee, a.employee_id)
    audit(s, u, "premises", a.guest_house_id, "guest_vacated", None, {"employee": f"{e.emp_code} {e.name}" if e else a.employee_id}); s.commit(); return row(a)

# ---------- HRMS configuration & client ----------
DEFAULT_MAP = {"emp_code": "employee_code", "name": "name", "email": "email", "phone": "phone", "grade": "grade", "designation": "designation",
               "department": "department", "location": "location", "status": "status", "join_date": "join_date"}

def fernet(): return Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))
def enc(v): return fernet().encrypt(v.encode()).decode()
def dec(v):
    try: return fernet().decrypt(v.encode()).decode()
    except (InvalidToken, ValueError): return ""

def get_cfg(s): return s.query(HrmsConfig).first()
def fmap(cfg):
    try: return {**DEFAULT_MAP, **json.loads(cfg.field_map or "{}")}
    except ValueError: return DEFAULT_MAP

def cfg_out(c):
    if not c: return {"configured": False, "enabled": False, "auth_type": "api_key", "auth_header": "X-API-Key", "search_path": "/employees", "search_param": "search",
                      "travel_path": "/travel-advances", "health_path": "/health", "timeout_s": 10, "field_map": json.dumps(DEFAULT_MAP, indent=1), "secret_set": False}
    return {**row(c, configured=bool(c.base_url), secret_set=bool(c.secret_enc)), "secret_enc": None, "field_map": c.field_map or json.dumps(DEFAULT_MAP, indent=1)}

class HrmsError(Exception): pass

def hrms_call(s, cfg, op, direction, method, path, params=None, body=None, ref=None, user=None, allow_disabled=False):
    if not cfg or not cfg.base_url: raise HrmsError("HRMS is not configured yet")
    if not cfg.enabled and not allow_disabled: raise HrmsError("HRMS integration is switched off")
    if not cfg.base_url.lower().startswith(("http://", "https://")): raise HrmsError("The base URL must start with http:// or https://")
    url = cfg.base_url.rstrip("/") + "/" + path.lstrip("/") + (("?" + urllib.parse.urlencode(params)) if params else "")
    h = {"Accept": "application/json"}; sec = dec(cfg.secret_enc) if cfg.secret_enc else ""
    if cfg.auth_type == "bearer": h["Authorization"] = "Bearer " + sec
    elif cfg.auth_type == "basic": h["Authorization"] = "Basic " + base64.b64encode(f"{cfg.username or ''}:{sec}".encode()).decode()
    else: h[cfg.auth_header or "X-API-Key"] = sec
    data = None
    if body is not None: data = json.dumps(body, default=str).encode(); h["Content-Type"] = "application/json"
    t0, st, msg, out = time.time(), None, None, None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=cfg.timeout_s or 10) as r:
            st = r.status; raw = r.read(2_000_000)
            try: out = json.loads(raw) if raw else {}
            except ValueError: raise HrmsError("The HRMS did not return JSON")
    except urllib.error.HTTPError as e:
        st = e.code; msg = {401: "HRMS rejected the credentials (401)", 403: "HRMS denied access (403)", 404: "HRMS endpoint not found (404). Check the path in the settings."}.get(e.code, f"HRMS returned HTTP {e.code}")
    except urllib.error.URLError as e: msg = f"Cannot reach the HRMS: {getattr(e, 'reason', e)}"
    except TimeoutError: msg = "The HRMS did not respond in time"
    except HrmsError as e: msg = str(e)
    except Exception as e: msg = f"Unexpected error: {e}"
    s.add(IntegrationLog(direction=direction, operation=op, status="error" if msg else "ok", http_status=st, ms=int((time.time() - t0) * 1000), message=msg, ref=ref, user_name=user.name if user else "system"))
    link_down = bool(msg) and (st is None or st in (401, 403, 404) or st >= 500)   # a 4xx data rejection (e.g. unknown employee) does not mean the link is down
    if link_down or not msg: cfg.last_status, cfg.last_checked, cfg.last_error = ("error", dt.datetime.utcnow(), msg) if msg else ("ok", dt.datetime.utcnow(), None)
    s.commit()
    if msg: raise HrmsError(msg)
    return out

@router.get("/api/hrms/config")
def hrms_config(u: User = Depends(need("integrations.manage")), s: Session = Depends(db)): return cfg_out(get_cfg(s))

@router.put("/api/hrms/config")
async def hrms_save(request: Request, u: User = Depends(need("integrations.manage")), s: Session = Depends(db)):
    b = await request.json(); c = get_cfg(s) or HrmsConfig(); prev = {"base_url": c.base_url, "enabled": c.enabled}
    url = (b.get("base_url") or "").strip()
    if url and not url.lower().startswith(("http://", "https://")): raise HTTPException(400, "The base URL must start with http:// or https://")
    if b.get("auth_type") not in ("api_key", "bearer", "basic"): raise HTTPException(400, "Choose an authentication type")
    try: json.loads(b.get("field_map") or "{}")
    except ValueError: raise HTTPException(400, "The field mapping must be valid JSON")
    c.base_url, c.auth_type, c.enabled = url or None, b["auth_type"], bool(b.get("enabled"))
    c.auth_header, c.username = (b.get("auth_header") or "X-API-Key").strip(), (b.get("username") or "").strip() or None
    for k, d in (("search_path", "/employees"), ("search_param", "search"), ("travel_path", "/travel-advances"), ("health_path", "/health")): setattr(c, k, (b.get(k) or d).strip())
    c.timeout_s = max(2, min(60, int(b.get("timeout_s") or 10))); c.field_map = b.get("field_map") or None; c.updated_by = u.name
    if b.get("secret"): c.secret_enc = enc(b["secret"])
    s.add(c); s.flush(); audit(s, u, "integration", c.id, "hrms_config", prev, {"base_url": c.base_url, "enabled": c.enabled, "secret_changed": bool(b.get("secret"))}); s.commit()
    return cfg_out(c)

@router.post("/api/hrms/test")
def hrms_test(u: User = Depends(need("integrations.manage")), s: Session = Depends(db)):
    c = get_cfg(s)
    try: hrms_call(s, c, "test", "pull", "GET", c.health_path if c else "/", user=u, allow_disabled=True); return {"ok": True, "message": "Connected. The HRMS accepted the credentials."}
    except HrmsError as e: return {"ok": False, "message": str(e)}

@router.get("/api/hrms/log")
def hrms_log(u: User = Depends(need("integrations.manage")), s: Session = Depends(db)):
    return [row(x) for x in s.query(IntegrationLog).order_by(IntegrationLog.id.desc()).limit(60)]

def items_of(d):
    if isinstance(d, list): return d
    if isinstance(d, dict):
        for k in ("data", "results", "employees", "items", "content", "records"):
            if isinstance(d.get(k), list): return d[k]
    return []

@router.get("/api/hrms/search")
def hrms_search(q: str, u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    """HR -> Admin: look an employee up in the HRMS by name, username or employee code."""
    q = q.strip()
    if len(q) < 2: raise HTTPException(400, "Type at least 2 characters")
    c = get_cfg(s)
    try: data = hrms_call(s, c, "employee_search", "pull", "GET", c.search_path if c else "", params={c.search_param or "search": q}, ref=q[:100], user=u)
    except HrmsError as e: raise HTTPException(502, str(e))
    fm, res = fmap(c), []
    have = {(e.company_id, e.emp_code): e.id for e in s.query(Employee)}
    for it in items_of(data)[:25]:
        if not isinstance(it, dict): continue
        m = {k: (str(it.get(v)).strip() if it.get(v) is not None else "") for k, v in fm.items()}
        m["status"] = norm_status(m.get("status")); m["exists"] = any(k[1] == m["emp_code"] for k in have)
        if m["emp_code"]: res.append(m)
    return {"results": res}

@router.post("/api/hrms/import")
async def hrms_import(request: Request, u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    b = await request.json(); p = s.get(Premises, b.get("premises_id")); m = b.get("employee") or {}
    if not p or not in_scope(s, u, "employees.write", p.id): raise HTTPException(403, "Choose a building within your scope")
    e = s.query(Employee).filter_by(company_id=p.company_id, emp_code=str(m.get("emp_code", "")).strip()).first()
    try:
        if e:
            prev = {k: getattr(e, k) for k in ("name", "grade", "designation", "department", "status")}
            e.name = m.get("name") or e.name; e.email = m.get("email") or e.email; e.phone = m.get("phone") or e.phone; e.grade = m.get("grade") or e.grade
            e.designation = m.get("designation") or e.designation; e.department = m.get("department") or e.department; e.status = norm_status(m.get("status"))
            e.source, e.external_id, e.synced_at = "hrms", e.emp_code, dt.datetime.utcnow(); s.flush()
            if prev["status"] != e.status:
                from .phase5 import on_employee_status; on_employee_status(s, e, u)
            audit(s, u, "employee", e.id, "hrms_refresh", prev, {k: getattr(e, k) for k in prev}); act = "updated"
        else:
            e = make_employee(s, p, m, "hrms"); e.external_id, e.synced_at = e.emp_code, dt.datetime.utcnow(); audit(s, u, "employee", e.id, "hrms_import", None, row(e)); act = "created"
    except ValueError as x: raise HTTPException(400, str(x))
    s.commit(); return {"action": act, "employee": row(e)}

# ---------- travel advances (Admin / Claims -> HR) ----------
def push_advance(s, t, user=None):
    c = get_cfg(s); t.attempts += 1
    body = {"employee_code": t.employee_code, "amount": t.amount, "currency": t.currency, "purpose": t.purpose, "destination": t.destination,
            "from_date": t.from_date, "to_date": t.to_date, "reference": f"TA-{t.id:05d}", "source": t.source, "claim_ref": t.claim_ref}
    try:
        r = hrms_call(s, c, "travel_advance", "push", "POST", c.travel_path if c else "", body=body, ref=body["reference"], user=user)
        t.status, t.pushed_at, t.error = "pushed", dt.datetime.utcnow(), None
        t.hrms_ref = str((r or {}).get("reference") or (r or {}).get("id") or (r or {}).get("hrms_ref") or "") or None
    except HrmsError as e: t.status, t.error = "failed", str(e)[:400]
    s.commit()

def adv_out(t): return row(t, ref=f"TA-{t.id:05d}")

def new_advance(s, b, source, user_name):
    code = str(b.get("employee_code") or "").strip(); amt = pnum(b.get("amount"), "amount")
    if not code: raise ValueError("Employee code is required")
    if not amt or amt <= 0: raise ValueError("Amount must be greater than zero")
    e = s.query(Employee).filter_by(emp_code=code).first()
    t = TravelAdvance(employee_code=code, employee_name=(e.name if e else b.get("employee_name")), amount=amt, currency=(b.get("currency") or "INR").upper()[:3],
                      purpose=b.get("purpose") or None, destination=b.get("destination") or None, from_date=pdate(b.get("from_date")), to_date=pdate(b.get("to_date")),
                      source=source, claim_ref=b.get("claim_ref") or None, created_by=user_name)
    s.add(t); s.flush(); return t

@router.get("/api/travel-advances")
def advances(u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    return [adv_out(t) for t in s.query(TravelAdvance).order_by(TravelAdvance.id.desc()).limit(200)]

@router.post("/api/travel-advances")
def add_advance(b: dict = Body(...), u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    try: t = new_advance(s, b, "admin", u.name)
    except ValueError as e: raise HTTPException(400, str(e))
    audit(s, u, "travel_advance", t.id, "create", None, {"employee_code": t.employee_code, "amount": t.amount}); push_advance(s, t, u); return adv_out(t)

@router.post("/api/travel-advances/{tid}/retry")
def retry_advance(tid: int, u: User = Depends(need("employees.write")), s: Session = Depends(db)):
    t = s.get(TravelAdvance, tid)
    if not t: raise HTTPException(404)
    if t.status == "pushed": raise HTTPException(400, "Already sent to HR")
    push_advance(s, t, u); return adv_out(t)

@router.post("/api/integration/travel-advances", dependencies=[Depends(api_key)])
def claims_advances(b: dict = Body(...), s: Session = Depends(db)):
    """Called by the Claims system. Each advance is recorded here and forwarded to the HRMS."""
    res = {"received": 0, "pushed": 0, "failed": 0, "errors": []}
    for i, it in enumerate(b.get("items", [])):
        try: t = new_advance(s, it, "claims", "claims system")
        except ValueError as e: res["errors"].append({"index": i, "error": str(e)}); continue
        push_advance(s, t); res["received"] += 1; res["pushed" if t.status == "pushed" else "failed"] += 1
    return res

# ---------- dashboard summaries ----------
def people_summary(s, u, premises_id=None):
    E = scoped(s, u, Employee, "employees.read", premises_id).all(); out = {st: sum(1 for e in E if e.status == st) for st in ESTATUS}; out["total"] = len(E)
    ghs = scoped_prem(s, u).filter(Premises.type == "guest_house").all()
    if premises_id: ids = descendants(s, premises_id); ghs = [g for g in ghs if g.id in ids]
    B = gh_bundle(s, ghs); out.update(guest_houses=len(ghs), beds=sum(b["beds"] or 0 for b in B), occupied=sum(b["occupied"] for b in B)); return out

def hrms_summary(s):
    c = get_cfg(s); since = dt.datetime.utcnow() - dt.timedelta(hours=24)
    state = "not_configured" if not c or not c.base_url else "off" if not c.enabled else "error" if c.last_status == "error" else "ok" if c.last_status == "ok" else "untested"
    q = s.query(IntegrationLog).filter(IntegrationLog.at >= since)
    last_ok = s.query(func.max(IntegrationLog.at)).filter_by(status="ok").scalar()
    return {"state": state, "ok_24h": q.filter_by(status="ok").count(), "failed_24h": q.filter_by(status="error").count(),
            "last_ok": last_ok.isoformat() if last_ok else None, "last_error": c.last_error if c else None,
            "advances_waiting": s.query(TravelAdvance).filter(TravelAdvance.status != "pushed").count()}

# ---------- mock HRMS (demo only, so the integration can be tried without a real HRMS) ----------
MOCK = [("JT1001", "Ramesh Iyer", "M4", "Senior Manager", "Finance", "Bengaluru"), ("JT1002", "Asha Nair", "M2", "Manager", "HR", "Bengaluru"),
        ("JT1003", "Kiran Patel", "M3", "Associate Director", "Operations", "Ahmedabad"), ("JT1004", "Neha Shah", "E5", "Executive", "Compliance", "Ahmedabad"),
        ("JT1005", "Anil Menon", "M1", "Team Lead", "Technology", "Bengaluru"), ("JT1006", "Divya Rao", "E3", "Analyst", "Technology", "Bengaluru"),
        ("AK2001", "Joseph Otieno", "G4", "Country Manager", "Operations", "Nairobi"), ("AK2002", "Grace Wanjiru", "G3", "Finance Lead", "Finance", "Nairobi"),
        ("AK2003", "Peter Kamau", "G2", "Programme Officer", "Programmes", "Nairobi"), ("AK2004", "Amina Hassan", "G2", "HR Officer", "HR", "Nairobi"),
        ("JT1007", "Sanjay Kulkarni", "E4", "Engineer", "Technology", "Bengaluru"), ("JT1008", "Mihir Desai", "E2", "Associate", "Compliance", "Ahmedabad"), ("JT1009", "Pooja Trivedi", "M1", "Team Lead", "Governance", "Ahmedabad"),
        ("AK2005", "Lucy Achieng", "G2", "Admin Assistant", "Admin", "Nairobi"), ("AK2006", "Mary Njeri", "G2", "Accountant", "Finance", "Nairobi"), ("AK2007", "David Mwangi", "G3", "Programme Manager", "Programmes", "Nairobi"),
        ("AK2008", "Faith Wambui", "G1", "Admin Assistant", "Admin", "Nairobi"), ("AK2009", "Samuel Ochieng", "G3", "Field Coordinator", "Programmes", "Nairobi"), ("AK2010", "Esther Mutheu", "G2", "HR Officer", "HR", "Nairobi"),
        ("AK2011", "Brian Kiptoo", "G4", "Regional Manager", "Operations", "Nairobi"), ("AK2012", "Janet Chebet", "G2", "M&E Officer", "Programmes", "Nairobi"), ("AK2013", "Kevin Otieno", "G3", "IT Officer", "Technology", "Nairobi")]

def mock_auth(x_api_key):
    if os.environ.get("SEED_DEMO") != "1": raise HTTPException(404)
    if x_api_key != "demo-hrms-key": raise HTTPException(401, "bad key")

@router.get("/mock-hrms/health")
def mock_health(x_api_key: str | None = Header(None)): mock_auth(x_api_key); return {"status": "up"}

@router.get("/mock-hrms/employees")
def mock_emps(search: str = "", x_api_key: str | None = Header(None)):
    mock_auth(x_api_key); q = search.lower()
    return {"data": [{"employeeId": c, "fullName": n, "workEmail": n.lower().replace(" ", ".") + "@example.org", "mobile": "+00 00000 0" + c[-3:], "gradeCode": g, "jobTitle": t, "dept": d, "location": l,
                      "employmentStatus": "ACTIVE", "doj": "2019-06-01"} for c, n, g, t, d, l in MOCK if q in (c + n + t + d).lower()]}

@router.post("/mock-hrms/travel-advances")
async def mock_adv(request: Request, x_api_key: str | None = Header(None)):
    mock_auth(x_api_key); b = await request.json()
    if not any(m[0] == b.get("employee_code") for m in MOCK): raise HTTPException(422, "unknown employee")
    return {"reference": "HRTA-" + str(abs(hash(b.get("reference"))) % 90000 + 10000), "status": "received"}

# ---------- demo seed (idempotent top-up) ----------
def seed_phase2(s):
    if s.query(User).filter_by(email="hr@bms.local").first(): return
    jt, ke = s.query(Company).filter_by(name="Jiva Technologies").first(), s.query(Company).filter_by(name="Africare Kenya").first()
    if not (jt and ke): return
    hq = s.query(Premises).filter(Premises.name.like("Corporate Office%")).first(); gh1 = s.query(Premises).filter_by(name="Guest House 1").first()
    nb = s.query(Premises).filter(Premises.name.like("Nairobi%")).first()
    def prem(c, parent, name, typ, addr):
        p = s.query(Premises).filter_by(name=name).first()
        if not p: p = Premises(company_id=c.id, parent_id=parent.id if parent else None, name=name, type=typ, address=addr); s.add(p); s.flush()
        return p
    cgc = prem(jt, None, "Corporate Governance Center (CGC), Ahmedabad", "office", "Ahmedabad, Gujarat, India")
    cgc_gh = prem(jt, cgc, "CGC Guest House, Ahmedabad", "guest_house", "Ahmedabad, Gujarat, India")
    arch = prem(ke, None, "Corporate Business Center, The Arch Place, Nairobi", "office", "The Arch Place, Nairobi, Kenya")
    arch_gh = prem(ke, arch, "The Arch Place Guest House, Nairobi", "guest_house", "Nairobi, Kenya")
    for p, beds, rooms in ((gh1, 6, 3), (cgc_gh, 4, 2), (arch_gh, 4, 2)):
        if p and not s.get(PremisesMeta, p.id): s.add(PremisesMeta(premises_id=p.id, beds=beds, rooms=rooms))
    from .core import hash_pw
    u = User(email="hr@bms.local", name="HR Manager", password_hash=hash_pw("hr123")); s.add(u); s.flush()
    s.add(RoleGrant(user_id=u.id, role="hr", scope_level="group", scope_id=None))
    # admin in-charges for the new buildings
    for em, nm, pw, pr in (("cgc@bms.local", "CGC Admin In-charge", "cgc123", cgc), ("archplace@bms.local", "Arch Place Admin In-charge", "arch123", arch)):
        x = User(email=em, name=nm, password_hash=hash_pw(pw)); s.add(x); s.flush(); s.add(RoleGrant(user_id=x.id, role="premises_admin", scope_level="premises", scope_id=pr.id))
    E = {}
    for code, name, bld, co, grade, des, dept, status, src in [
        ("JT1001", "Ramesh Iyer", hq, jt, "M4", "Senior Manager", "Finance", "active", "hrms"), ("JT1002", "Asha Nair", hq, jt, "M2", "Manager", "HR", "active", "hrms"),
        ("JT1005", "Anil Menon", hq, jt, "M1", "Team Lead", "Technology", "active", "hrms"), ("JT1007", "Sanjay Kulkarni", hq, jt, "E4", "Engineer", "Technology", "on_leave", "manual"),
        ("JT1003", "Kiran Patel", cgc, jt, "M3", "Associate Director", "Operations", "active", "hrms"), ("JT1004", "Neha Shah", cgc, jt, "E5", "Executive", "Compliance", "active", "hrms"),
        ("JT1008", "Mihir Desai", cgc, jt, "E2", "Associate", "Compliance", "notice", "manual"), ("JT1009", "Pooja Trivedi", cgc, jt, "M1", "Team Lead", "Governance", "active", "manual"),
        ("AK2001", "Joseph Otieno", nb, ke, "G4", "Country Manager", "Operations", "active", "hrms"), ("AK2002", "Grace Wanjiru", arch, ke, "G3", "Finance Lead", "Finance", "active", "hrms"),
        ("AK2003", "Peter Kamau", arch, ke, "G2", "Programme Officer", "Programmes", "active", "hrms"), ("AK2005", "Lucy Achieng", arch, ke, "G2", "Admin Assistant", "Admin", "active", "manual")]:
        e = Employee(company_id=co.id, premises_id=bld.id, emp_code=code, name=name, email=name.lower().replace(" ", ".") + "@example.org", grade=grade, designation=des, department=dept,
                     status=status, join_date=dt.date(2020, 1, 15), source=src, external_id=code if src == "hrms" else None, synced_at=dt.datetime.utcnow() if src == "hrms" else None)
        s.add(e); s.flush(); E[code] = e
    t = dt.date.today()
    for code, gh, room, purpose, f, to in [("JT1005", gh1, "Room 1", "Relocation", -20, 40), ("JT1007", gh1, "Room 2", "Long stay", -60, None), ("JT1003", cgc_gh, "Room 1", "Quarterly review visit", -2, 5),
                                           ("AK2003", arch_gh, "Room 1", "Training", -3, 10)]:
        s.add(GuestAllocation(guest_house_id=gh.id, employee_id=E[code].id, room=room, purpose=purpose, from_date=t + dt.timedelta(days=f), to_date=t + dt.timedelta(days=to) if to is not None else None, allocated_by="Admin In-charge"))
    if not get_cfg(s):
        s.add(HrmsConfig(enabled=True, base_url="http://localhost:8000/mock-hrms", auth_type="api_key", auth_header="X-API-Key", secret_enc=enc("demo-hrms-key"),
                         field_map=json.dumps({"emp_code": "employeeId", "name": "fullName", "email": "workEmail", "phone": "mobile", "grade": "gradeCode", "designation": "jobTitle",
                                               "department": "dept", "location": "location", "status": "employmentStatus", "join_date": "doj"}, indent=1), updated_by="demo seed"))
    s.commit()

# ---------- demo seed: guest house rooms + six Nairobi guest houses near The Arch Place (sample data, editable) ----------
def seed_phase3(s):
    if s.query(Premises).filter_by(name="Lavington Guest House, Nairobi").first(): return
    from .phase1 import make_asset
    ke = s.query(Company).filter_by(name="Africare Kenya").first()
    arch = s.query(Premises).filter(Premises.name.like("Corporate Business Center%")).first()
    if not (ke and arch): return
    if arch.lat is None: arch.lat, arch.lng = -1.2890, 36.7900
    arch.address = arch.address or "The Arch Place, Nairobi, Kenya"
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n)
    def prof(p, **kw):
        m = s.get(PremisesMeta, p.id) or PremisesMeta(premises_id=p.id)
        for k, v in kw.items(): setattr(m, k, v)
        s.add(m); s.flush()
    R = {}
    def rooms(p, specs):
        for name, floor, beds, feat in specs:
            r = GuestRoom(guest_house_id=p.id, name=name, floor=floor, beds=beds, features=feat); s.add(r); s.flush(); R[(p.id, name)] = r
    # existing guest houses get rooms (their free-text room names are linked below)
    gh1 = s.query(Premises).filter_by(name="Guest House 1").first(); cgc = s.query(Premises).filter(Premises.name.like("CGC Guest House%")).first()
    kil = s.query(Premises).filter(Premises.name.like("The Arch Place Guest House%")).first()
    if gh1:
        prof(gh1, floors=2, halls=1, balconies=1, kitchens=1, location="Indiranagar", amenities="WiFi, Parking, Housekeeping, Power backup", contact_name="Caretaker", contact_phone="+91 90000 00010",
             maps_url="https://www.google.com/maps?q=12.9784,77.6408"); gh1.lat, gh1.lng = 12.9784, 77.6408
        rooms(gh1, [("Room 1", "1", 2, "AC, Attached bathroom"), ("Room 2", "1", 2, "AC, Attached bathroom, Balcony"), ("Room 3", "2", 2, "Attached bathroom")])
    if cgc:
        prof(cgc, floors=1, halls=1, balconies=1, kitchens=1, location="Ahmedabad", amenities="WiFi, Parking, Housekeeping")
        rooms(cgc, [("Room 1", "1", 2, "AC, Attached bathroom"), ("Room 2", "1", 2, "AC, Attached bathroom")])
    if kil:
        kil.address, kil.lat, kil.lng = "Kilimani, Nairobi, Kenya", -1.2905, 36.7870
        prof(kil, floors=2, halls=1, balconies=2, kitchens=1, location="Kilimani, near The Arch Place", amenities="WiFi, Secure parking, Generator backup, Housekeeping, 24h security, DSTV",
             contact_name="Wanjiku Mwangi (caretaker)", contact_phone="+254 700 100 001", maps_url="https://www.google.com/maps?q=-1.2905,36.7870", notes="Sample data. Confirm the address and map pin.")
        rooms(kil, [("Room 1", "1", 2, "AC, Attached bathroom, Balcony"), ("Room 2", "1", 2, "Attached bathroom"), ("Room 3", "2", 1, "AC, Attached bathroom, Work desk")])
    for a in s.query(GuestAllocation).filter(GuestAllocation.room_id.is_(None)):
        r = R.get((a.guest_house_id, a.room))
        if r: a.room_id = r.id
    NEW = [("Kileleshwa Guest House, Nairobi", "Kileleshwa, Nairobi, Kenya", -1.2800, 36.7840, "Kileleshwa", 2, 1, 1, 1, "WiFi, Parking, Generator backup, Housekeeping, DSTV", "Joyce Akinyi (caretaker)", "+254 700 100 002",
            [("Room 1", "1", 2, "AC, Attached bathroom"), ("Room 2", "1", 2, "Attached bathroom"), ("Room 3", "2", 2, "AC, Attached bathroom, Balcony"), ("Room 4", "2", 1, "Attached bathroom")]),
           ("Lavington Guest House, Nairobi", "Lavington, Nairobi, Kenya", -1.2790, 36.7730, "Lavington", 3, 2, 3, 1, "WiFi, Garden, Secure parking, Generator backup, Housekeeping, Gym access, 24h security", "Moses Karanja (caretaker)", "+254 700 100 003",
            [("Room 1", "1", 2, "AC, Attached bathroom, Balcony"), ("Room 2", "2", 2, "AC, Attached bathroom, Balcony"), ("Room 3", "2", 2, "AC, Attached bathroom"), ("Room 4", "3", 2, "AC, Attached bathroom, Balcony")]),
           ("Hurlingham Guest House, Nairobi", "Hurlingham, Nairobi, Kenya", -1.2930, 36.7980, "Hurlingham", 1, 1, 0, 1, "WiFi, Parking, Housekeeping, Water tank", "Rose Wanjiku (caretaker)", "+254 700 100 004",
            [("Room 1", "G", 2, "Attached bathroom"), ("Room 2", "G", 2, "Attached bathroom")]),
           ("Westlands Guest House, Nairobi", "Westlands, Nairobi, Kenya", -1.2670, 36.8110, "Westlands", 1, 1, 2, 1, "WiFi, Lift, Pool access, Secure parking, 24h security", "Daniel Mutua (caretaker)", "+254 700 100 005",
            [("Room 1", "5", 2, "AC, Attached bathroom, Balcony"), ("Room 2", "5", 2, "AC, Attached bathroom"), ("Room 3", "5", 1, "Attached bathroom, Work desk")]),
           ("Parklands Guest House, Nairobi", "Parklands, Nairobi, Kenya", -1.2630, 36.8200, "Parklands", 2, 1, 1, 1, "WiFi, Parking, Housekeeping, Generator backup", "Esther Naliaka (caretaker)", "+254 700 100 006",
            [("Room 1", "1", 1, "Attached bathroom"), ("Room 2", "1", 1, "Attached bathroom"), ("Room 3", "2", 2, "AC, Attached bathroom")])]
    G = {"Kilimani": kil}
    for name, addr, la, ln, loc, fl, ha, ba, ki, am, cn, cp, rs in NEW:
        p = Premises(company_id=ke.id, parent_id=arch.id, name=name, type="guest_house", address=addr, lat=la, lng=ln); s.add(p); s.flush(); G[loc] = p
        prof(p, floors=fl, halls=ha, balconies=ba, kitchens=ki, location=loc + ", near The Arch Place", amenities=am, contact_name=cn, contact_phone=cp, maps_url=f"https://www.google.com/maps?q={la},{ln}", notes="Sample data. Confirm the address and map pin.")
        rooms(p, rs)
    # sample Kenyan employees at The Arch Place, and bed allocations that show full / half / empty rooms
    E = {e.emp_code: e for e in s.query(Employee).filter(Employee.emp_code.like("AK%"))}
    for code, name, grade, des, dept in [("AK2006", "Mary Njeri", "G2", "Accountant", "Finance"), ("AK2007", "David Mwangi", "G3", "Programme Manager", "Programmes"), ("AK2008", "Faith Wambui", "G1", "Admin Assistant", "Admin"),
                                         ("AK2009", "Samuel Ochieng", "G3", "Field Coordinator", "Programmes"), ("AK2010", "Esther Mutheu", "G2", "HR Officer", "HR"), ("AK2011", "Brian Kiptoo", "G4", "Regional Manager", "Operations"),
                                         ("AK2012", "Janet Chebet", "G2", "M&E Officer", "Programmes"), ("AK2013", "Kevin Otieno", "G3", "IT Officer", "Technology")]:
        e = Employee(company_id=ke.id, premises_id=arch.id, emp_code=code, name=name, email=name.lower().replace(" ", ".") + "@example.org", grade=grade, designation=des, department=dept, status="active", join_date=D(-900), source="manual")
        s.add(e); s.flush(); E[code] = e
    for code, gh, room, purpose, f, to in [("AK2006", kil, "Room 1", "Training", -4, 6), ("AK2007", kil, "Room 2", "Site visit", -1, 3),
                                           ("AK2008", G["Kileleshwa"], "Room 1", "Relocation", -12, 30), ("AK2009", G["Kileleshwa"], "Room 1", "Relocation", -12, 30), ("AK2010", G["Kileleshwa"], "Room 2", "Training", -2, 2),
                                           ("AK2011", G["Lavington"], "Room 1", "Quarterly review", -1, 4), ("AK2012", G["Hurlingham"], "Room 1", "Project assignment", -20, 40), ("AK2013", G["Hurlingham"], "Room 1", "Project assignment", -20, 40),
                                           ("AK2005", G["Parklands"], "Room 1", "Temporary stay", -6, -1)]:
        r = R[(gh.id, room)]; s.add(GuestAllocation(guest_house_id=gh.id, employee_id=E[code].id, room_id=r.id, room=room, purpose=purpose, from_date=D(f), to_date=D(to), allocated_by="Admin In-charge"))
    # assets mapped to the guest houses
    def assets(p, items):
        for name, cat, mm, loc, itv, last, warr, cond in items:
            a = make_asset(s, p, {"name": name, "category": cat, "make_model": mm, "location": loc, "service_interval_days": itv, "last_service_date": D(last) if last is not None else None,
                                  "warranty_to": D(warr) if warr is not None else None, "purchase_date": D(-600), "condition": cond, "vendor": "Local AMC vendor"}); audit(s, None, "asset", a.id, "create", None, {"name": name})
    assets(kil, [("Water heater (geyser)", "plumbing", "Ariston 80L", "Room 1", 180, -60, 200, "good"), ("Split AC", "hvac", "LG 1.5T", "Room 1", 120, -150, -30, "fair"), ("RO water purifier", "appliance", "Kent", "Kitchen", 90, -40, 100, "good"),
                 ("CCTV system", "security", "Hikvision 4-cam", "Gate", 365, -100, 250, "good"), ("Inverter / UPS", "electrical", "Luminous 1.5kVA", "Hall", 180, -200, 20, "good")])
    assets(G["Kileleshwa"], [("Solar water heater", "plumbing", "Sunlux 200L", "Terrace", 180, -30, 300, "good"), ("Split AC, Room 1", "hvac", "Samsung 1.5T", "Room 1", 120, -40, 150, "good"), ("Split AC, Room 3", "hvac", "Samsung 1.5T", "Room 3", 120, -140, 150, "good"),
                             ("Refrigerator", "appliance", "Hisense 300L", "Kitchen", None, None, 60, "good"), ("Washing machine", "appliance", "LG 8kg", "Utility", 180, -50, 80, "poor")])
    assets(G["Lavington"], [("Standby generator 20kVA", "electrical", "Perkins", "Yard", 90, -120, 300, "good"), ("Electric fence", "security", "Gallagher", "Perimeter", 180, -60, 400, "good"), ("CCTV system", "security", "Hikvision 8-cam", "Gate", 365, -30, 300, "good"),
                            ("Water heaters x4", "plumbing", "Ariston", "Bathrooms", 180, -70, 100, "good"), ("Dining set", "furniture", "Custom 8 seat", "Hall", None, None, None, "good")])
    assets(G["Hurlingham"], [("Water heater", "plumbing", "Racold 100L", "Room 1", 180, -80, 90, "good"), ("Water pump", "plumbing", "Pedrollo", "Pump room", 180, -190, -10, "fair")])
    assets(G["Westlands"], [("Smart TV 50 inch", "it", "Samsung", "Hall", None, None, 120, "good"), ("Refrigerator", "appliance", "Samsung 250L", "Kitchen", None, None, 200, "good"), ("Microwave oven", "appliance", "Panasonic", "Kitchen", None, None, 40, "good")])
    assets(G["Parklands"], [("Water heater", "plumbing", "Ariston 50L", "Room 3", 180, -90, 60, "good"), ("Refrigerator", "appliance", "Hisense 200L", "Kitchen", None, None, 90, "good")])
    s.commit()

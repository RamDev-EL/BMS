import os, hashlib, hmac, json, datetime as dt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .models import SessionLocal, User, Premises, Audit

SECRET = os.environ.get("JWT_SECRET", "dev")

def db():
    s = SessionLocal()
    try: yield s
    finally: s.close()

# ---- passwords (PBKDF2) ----
def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + h.hex()

def check_pw(pw: str, stored: str) -> bool:
    salt, h = stored.split("$")
    c = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(c.hex(), h)

def make_token(uid: int) -> str:
    return jwt.encode({"uid": uid, "exp": dt.datetime.utcnow() + dt.timedelta(hours=12)}, SECRET, "HS256")

# ---- default role seed (Section 2: configurable later, this is the seed matrix) ----
ROLE_PERMS = {
    "group_admin": {"*"},
    "corporate_admin_head": {"premises.write", "vehicles.read", "vehicles.write", "trips.read", "trips.assign",
                             "fuel.read", "fuel.review", "users.admin", "audit.read", "dashboard",
                       "assets.read", "assets.write", "assets.service", "tickets.read", "tickets.raise",
                       "employees.read", "employees.write", "allocations.write",
                       "premises.view", "premises.docs", "utilities.read", "utilities.write", "premises.occupancy", "service.approve", "travel.read", "travel.write", "travel.admin", "travel.bhead", "travel.approve", "travel.policy"},
    "premises_admin": {"premises.write", "vehicles.read", "vehicles.write", "trips.read", "trips.assign",
                       "fuel.read", "fuel.review", "audit.read", "dashboard",
                       "assets.read", "assets.write", "assets.service", "tickets.read", "tickets.raise",
                       "employees.read", "employees.write", "allocations.write",
                       "premises.view", "premises.docs", "utilities.read", "utilities.write", "premises.occupancy", "travel.read", "travel.write", "travel.admin"},
    "finance": {"vehicles.read", "fuel.read", "trips.read", "dashboard", "assets.read", "premises.view", "utilities.read", "utilities.write", "travel.read", "travel.pay"},
    # Phase 1: the maintenance head sees every ticket in scope and works them; tickets are RAISED by admin in-charges.
    "maintenance_head": {"premises.view", "utilities.read", "assets.read", "assets.service", "tickets.read", "tickets.manage", "tickets.raise"},
    "hr": {"travel.read", "travel.write", "travel.hr", "travel.approve", "travel.policy", "visa.restricted", "premises.view", "utilities.read", "utilities.write", "premises.occupancy", "vehicles.read", "trips.read", "dashboard", "assets.read", "tickets.read", "tickets.raise",
           "employees.read", "employees.write", "allocations.write"},
    "travel_desk": {"travel.read", "travel.write", "visa.restricted", "employees.read", "premises.view"},
    "driver": {"driver.app"},
    "employee": {"trips.request"},
}

def grants_with(user: User, perm: str):
    today = dt.date.today()
    for g in user.grants:
        if g.valid_to and g.valid_to < today: continue
        p = ROLE_PERMS.get(g.role, set())
        if "*" in p or perm in p: yield g

def can(user: User, perm: str) -> bool:
    return any(True for _ in grants_with(user, perm))

def scope_premises(s: Session, user: User, perm: str):
    """None = unrestricted. Otherwise a set of premises ids (scope premises + descendants)."""
    ids: set[int] = set()
    all_p = s.query(Premises.id, Premises.company_id, Premises.parent_id).all()
    for g in grants_with(user, perm):
        if g.scope_level == "group": return None
        if g.scope_level == "company":
            ids |= {p.id for p in all_p if p.company_id == g.scope_id}
        else:
            stack = [g.scope_id]
            while stack:
                x = stack.pop(); ids.add(x)
                stack += [p.id for p in all_p if p.parent_id == x]
    return ids

def current_user(request: Request, s: Session = Depends(db)) -> User:
    tok = request.headers.get("authorization", "")[7:] or request.query_params.get("t", "")
    try: uid = jwt.decode(tok, SECRET, ["HS256"])["uid"]
    except Exception: raise HTTPException(401, "Not signed in")
    u = s.get(User, uid)
    if not u or not u.active: raise HTTPException(401, "Not signed in")
    return u

def need(perm: str):
    def dep(u: User = Depends(current_user)) -> User:
        if not can(u, perm): raise HTTPException(403, f"Missing permission: {perm}")
        return u
    return dep

def audit(s: Session, user, entity: str, entity_id, action: str, prev=None, new=None):
    j = lambda v: None if v is None else json.dumps(v, default=str)
    s.add(Audit(user_id=user.id if user else None, user_name=user.name if user else "system",
                entity=entity, entity_id=entity_id, action=action, prev=j(prev), new=j(new)))

def snap(o, *fields): return {f: getattr(o, f) for f in fields}


def row(o, **extra):
    d = {c.name: (v.isoformat() if isinstance(v := getattr(o, c.name), (dt.date, dt.datetime)) else v)
         for c in o.__table__.columns if c.name != "password_hash"}
    return {**d, **extra}

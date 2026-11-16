"""Phase 7: 'my recent activity' for the right panel, and one more Arch Place corporate business premises with a 12-bed guest house (demo)."""
import datetime as dt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .models import *
from .core import *

router = APIRouter()

def link_for(s, entity, eid):
    if entity == "vehicle": return f"vehicles/{eid}" if eid else "vehicles"
    if entity == "ticket": return f"tickets/{eid}" if eid else "tickets"
    if entity == "asset": return f"assets/{eid}" if eid else "assets"
    if entity == "travel": return f"travel/{eid}" if eid else "travel"
    if entity == "premises":
        p = s.get(Premises, eid) if eid else None
        return ("guesthouses/" if p and p.type == "guest_house" else "premises/") + str(eid) if eid else "premises"
    return {"employee": "employees", "integration": "integrations", "user": "users", "travel_advance": "advances"}.get(entity, "dashboard")

@router.get("/api/me/activity")
def my_activity(u: User = Depends(current_user), s: Session = Depends(db)):
    out = []
    for a in s.query(Audit).filter(Audit.user_id == u.id).order_by(Audit.id.desc()).limit(14):
        out.append({"at": a.at.isoformat(), "action": a.action.replace("_", " "), "entity": a.entity, "entity_id": a.entity_id, "link": link_for(s, a.entity, a.entity_id)})
    return out

def seed_phase7(s):
    name = "Corporate Business Premises, The Arch Place, Nairobi, Kenya"
    if s.query(Premises).filter_by(name=name).first(): return
    ke = s.query(Company).filter_by(name="Africare Kenya").first()
    if not ke: return
    from .phase1 import make_asset
    from .models import UtilityAccount, UtilityBill, PremisesDocument
    t = dt.date.today(); D = lambda n: t + dt.timedelta(days=n)
    p = Premises(company_id=ke.id, name=name, type="office", address="The Arch Place, Nairobi, Kenya", lat=-1.2896, lng=36.7893); s.add(p); s.flush()
    s.add(PremisesMeta(premises_id=p.id, area_sqft=24000, floors=3, floors_taken="4th to 6th floor", ownership="leased", declared_headcount=85, litigation_count=0, occupancy="partial",
                       location="Kilimani, Nairobi", maps_url="https://www.google.com/maps?q=-1.2896,36.7893", contact_name="Building manager", contact_phone="+254 700 200 002", amenities="Lift, Basement parking, Generator backup, 24h security, Reception",
                       notes="Sample data. Confirm the address and map pin."))
    g = Premises(company_id=ke.id, parent_id=p.id, name="The Arch Place Residence, Nairobi", type="guest_house", address="Kilimani, Nairobi, Kenya", lat=-1.2910, lng=36.7860); s.add(g); s.flush()
    s.add(PremisesMeta(premises_id=g.id, floors=3, halls=2, balconies=4, kitchens=1, location="Kilimani, near The Arch Place", occupancy="occupied", maps_url="https://www.google.com/maps?q=-1.2910,36.7860",
                       amenities="WiFi, Lift, Secure parking, Generator backup, Housekeeping, 24h security, Gym access", contact_name="Residence manager", contact_phone="+254 700 100 012", notes="12 beds in 6 twin rooms. Sample data."))
    R = []
    for i, (fl, feat) in enumerate([("1", "AC, Attached bathroom, Balcony"), ("1", "AC, Attached bathroom"), ("2", "AC, Attached bathroom, Balcony"), ("2", "AC, Attached bathroom"), ("3", "AC, Attached bathroom, Balcony"), ("3", "AC, Attached bathroom, Work desk")], 1):
        r = GuestRoom(guest_house_id=g.id, name=f"Room {i}", floor=fl, beds=2, features=feat); s.add(r); s.flush(); R.append(r)
    emps = []
    for code, nm, gr, des, dept in [("AK3001", "Alice Wangari", "G3", "Finance Manager", "Finance"), ("AK3002", "Dennis Mutiso", "G2", "Programme Officer", "Programmes"), ("AK3003", "Ruth Chepkoech", "G2", "HR Officer", "HR"),
                                    ("AK3004", "George Omondi", "G4", "Director, Operations", "Operations"), ("AK3005", "Naomi Wekesa", "G1", "Admin Assistant", "Admin")]:
        e = Employee(company_id=ke.id, premises_id=p.id, emp_code=code, name=nm, email=nm.lower().replace(" ", ".") + "@example.org", grade=gr, designation=des, department=dept, status="active", join_date=D(-600), source="manual")
        s.add(e); s.flush(); emps.append(e)
    for e, r, purpose, f, to in [(emps[0], R[0], "Quarterly review", -5, 4), (emps[1], R[0], "Training", -5, 4), (emps[2], R[1], "Training", -3, 6), (emps[3], R[2], "Board visit", -1, 3), (emps[4], R[4], "Relocation", -20, 40)]:
        s.add(GuestAllocation(guest_house_id=g.id, employee_id=e.id, room_id=r.id, room=r.name, purpose=purpose, from_date=D(f), to_date=D(to), allocated_by="Admin In-charge"))
    for typ, title, num, auth, vt in [("lease", "Office lease, 4th to 6th floor", "LSE/2024/0231", "Landlord (sample)", 210), ("govt_registration", "Single business permit", "SBP-2026-5120", "Nairobi County", 140), ("fire_noc", "Fire safety certificate", "FSC-2026-077", "Fire Department", 26)]:
        s.add(PremisesDocument(premises_id=p.id, doc_type=typ, title=title, number=num, authority=auth, issued_on=D(-300), valid_to=D(vt), notes="Sample record. Upload the scan to complete it.", uploaded_by="demo seed"))
    for kind, prov, ref, bills in [("electricity", "Kenya Power (sample)", "ACC-3300011", [("2026-10", "KP-7001", 98000, -9, True), ("2026-11", "KP-7102", 102500, 10, False)]), ("internet", "Safaricom Business Fibre (sample)", "ACC-3300012", [("2026-11", "SF-9001", 48000, 6, False)])]:
        a = UtilityAccount(premises_id=p.id, kind=kind, provider=prov, account_ref=ref); s.add(a); s.flush()
        for per, inv, amt, due, paid in bills:
            b = UtilityBill(account_id=a.id, period=per, invoice_no=inv, invoice_date=D(due - 20), due_date=D(due), amount=amt, currency="KES", created_by="demo seed")
            if paid: b.status, b.paid_on, b.payment_ref = "paid", D(due - 2), "MPESA-DEMO"
            s.add(b)
    for nm, cat, mm, loc, itv, last in [("Standby generator 40kVA", "electrical", "Perkins", "Basement", 90, -60), ("Passenger lifts x2", "building", "Otis", "Core", 30, -20), ("Fire panel and extinguishers", "fire_safety", "Honeywell", "All floors", 180, -90), ("Reception CCTV", "security", "Hikvision 16-cam", "Ground", 365, -40)]:
        make_asset(s, p, {"name": nm, "category": cat, "make_model": mm, "location": loc, "service_interval_days": itv, "last_service_date": D(last), "purchase_date": D(-500), "vendor": "Local AMC vendor"})
    for nm, cat, mm, loc, itv, last in [("Water heaters x6", "plumbing", "Ariston", "Bathrooms", 180, -60), ("Split ACs x6", "hvac", "LG", "Rooms", 120, -100), ("Kitchen appliances", "appliance", "Samsung", "Kitchen", None, None)]:
        make_asset(s, g, {"name": nm, "category": cat, "make_model": mm, "location": loc, "service_interval_days": itv, "last_service_date": D(last) if last else None, "purchase_date": D(-400), "vendor": "Local AMC vendor"})
    s.commit()

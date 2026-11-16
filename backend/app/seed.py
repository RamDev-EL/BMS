import datetime as dt
from .models import *
from .core import hash_pw

def seed(s):
    if s.query(Company).count(): return
    jt = Company(name="Jiva Technologies", country="India", currency="INR")
    ke = Company(name="Africare Kenya", country="Kenya", currency="KES")
    s.add_all([jt, ke]); s.flush()
    hq = Premises(company_id=jt.id, name="Corporate Office, Bengaluru", type="office", address="Bengaluru, India", lat=12.9716, lng=77.5946)
    nb = Premises(company_id=ke.id, name="Nairobi Office", type="office", address="Nairobi, Kenya", lat=-1.2921, lng=36.8219)
    s.add_all([hq, nb]); s.flush()
    s.add(Premises(company_id=jt.id, parent_id=hq.id, name="Guest House 1", type="guest_house", address="Bengaluru, India"))

    def user(email, name, pw, role, level="group", sid=None, phone=None):
        u = User(email=email, name=name, phone=phone, password_hash=hash_pw(pw)); s.add(u); s.flush()
        s.add(RoleGrant(user_id=u.id, role=role, scope_level=level, scope_id=sid)); return u
    user("admin@bms.local", "Group Admin", "admin123", "group_admin")
    user("head@bms.local", "Corporate Admin Head", "head123", "corporate_admin_head", "company", jt.id)
    user("premises@bms.local", "Premises Admin (HQ)", "premises123", "premises_admin", "premises", hq.id)
    d1 = user("driver1@bms.local", "Ravi Kumar (Driver)", "driver123", "driver", "company", jt.id, "+91 90000 00001")
    user("driver2@bms.local", "Joseph Otieno (Driver)", "driver123", "driver", "company", ke.id, "+254 700 000002")
    emp = user("employee1@bms.local", "Asha Nair (Employee)", "employee123", "employee", "company", jt.id)

    v1 = Vehicle(company_id=jt.id, premises_id=hq.id, reg_no="KA01AB1234", make_model="Toyota Innova Crysta", year=2023, purchase_value=2400000, odometer=18250)
    v2 = Vehicle(company_id=jt.id, premises_id=hq.id, reg_no="KA01CD5678", make_model="Maruti Dzire", year=2022, purchase_value=900000, odometer=41200)
    v3 = Vehicle(company_id=ke.id, premises_id=nb.id, reg_no="KDG 123X", make_model="Toyota Hilux", year=2021, odometer=60500)
    s.add_all([v1, v2, v3]); s.flush()
    t = dt.date.today()
    for v, kind, num, days in [(v1,"insurance","POL-77821",20),(v1,"registration","RC-4411",900),(v1,"pollution","PUC-9912",5),
                               (v2,"insurance","POL-55120",-10),(v2,"fitness","FIT-221",200),(v3,"insurance","KE-INS-33",120)]:
        s.add(VehicleDocument(vehicle_id=v.id, doc_type=kind, number=num, valid_to=t + dt.timedelta(days=days)))
    s.add(Trip(company_id=jt.id, premises_id=hq.id, vehicle_id=v1.id, requester_id=emp.id, driver_id=d1.id,
               pickup="Corporate Office", destination="Kempegowda Airport", purpose="Visitor pickup", status="assigned",
               needed_at=dt.datetime.utcnow() + dt.timedelta(hours=2)))
    s.add(Trip(company_id=jt.id, premises_id=hq.id, requester_id=emp.id, pickup="Corporate Office",
               destination="Whitefield Site", purpose="Site visit", status="requested"))
    s.commit()

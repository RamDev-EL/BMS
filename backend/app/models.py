import os, datetime as dt
from sqlalchemy import create_engine, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

_url = os.environ["DATABASE_URL"]
if _url.startswith("postgres://"): _url = "postgresql+psycopg2://" + _url[len("postgres://"):]   # Render/Heroku style
elif _url.startswith("postgresql://"): _url = "postgresql+psycopg2://" + _url[len("postgresql://"):]
engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def now(): return dt.datetime.utcnow()

class Base(DeclarativeBase): pass

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    country: Mapped[str] = mapped_column(String(60))
    currency: Mapped[str] = mapped_column(String(3))
    logo: Mapped[str | None] = mapped_column(String(300))

class Premises(Base):
    __tablename__ = "premises"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("premises.id"))
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(40), default="office")  # office, guest_house, branch, hospital
    address: Mapped[str | None] = mapped_column(String(400))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="active")

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    grants: Mapped[list["RoleGrant"]] = relationship(lazy="selectin")

class RoleGrant(Base):
    """Role + scope. scope_level: group | company | premises. scope_id null for group."""
    __tablename__ = "role_grants"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(40))
    scope_level: Mapped[str] = mapped_column(String(20), default="group")
    scope_id: Mapped[int | None] = mapped_column(Integer)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int | None] = mapped_column(ForeignKey("premises.id"))
    reg_no: Mapped[str] = mapped_column(String(40), unique=True)
    make_model: Mapped[str] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(Integer)
    purchase_date: Mapped[dt.date | None] = mapped_column(Date)
    purchase_value: Mapped[float | None] = mapped_column(Float)
    pool: Mapped[bool] = mapped_column(Boolean, default=True)  # common vehicle
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="available")  # available, on_trip, maintenance, retired
    odometer: Mapped[float] = mapped_column(Float, default=0)
    current_value: Mapped[float | None] = mapped_column(Float)

class VehicleDocument(Base):
    __tablename__ = "vehicle_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    doc_type: Mapped[str] = mapped_column(String(60))  # registration, insurance, fitness, permit, pollution, licence
    number: Mapped[str | None] = mapped_column(String(100))
    authority: Mapped[str | None] = mapped_column(String(150))
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    file: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=1)
    renewal_cost: Mapped[float | None] = mapped_column(Float)

class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int | None] = mapped_column(ForeignKey("premises.id"))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pickup: Mapped[str | None] = mapped_column(String(300))
    destination: Mapped[str] = mapped_column(String(300))
    purpose: Mapped[str | None] = mapped_column(String(300))
    needed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested, assigned, started, completed, cancelled
    start_meter: Mapped[float | None] = mapped_column(Float)
    end_meter: Mapped[float | None] = mapped_column(Float)
    start_photo: Mapped[str | None] = mapped_column(String(300))
    end_photo: Mapped[str | None] = mapped_column(String(300))
    start_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    end_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lng: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class FuelLog(Base):
    __tablename__ = "fuel_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    litres: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    meter_reading: Mapped[float] = mapped_column(Float)
    meter_photo: Mapped[str | None] = mapped_column(String(300))
    receipt: Mapped[str | None] = mapped_column(String(300))
    mileage_kmpl: Mapped[float | None] = mapped_column(Float)
    start_meter: Mapped[float | None] = mapped_column(Float)       # meter when leaving for the fuel station
    start_photo: Mapped[str | None] = mapped_column(String(300))
    flag: Mapped[str | None] = mapped_column(String(200))   # review reasons, comma separated
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    user_id: Mapped[int | None] = mapped_column(Integer)
    user_name: Mapped[str | None] = mapped_column(String(200))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    prev: Mapped[str | None] = mapped_column(Text)
    new: Mapped[str | None] = mapped_column(Text)

# ---------------- Phase 1: assets, maintenance, tickets ----------------
class Asset(Base):
    """Admin asset register. external_source/external_id let a future asset-management system merge via the API."""
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    asset_tag: Mapped[str | None] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="other")
    make_model: Mapped[str | None] = mapped_column(String(160))
    serial_no: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(200))          # floor / room
    purchase_date: Mapped[dt.date | None] = mapped_column(Date)
    purchase_value: Mapped[float | None] = mapped_column(Float)
    warranty_to: Mapped[dt.date | None] = mapped_column(Date)
    vendor: Mapped[str | None] = mapped_column(String(200))             # supplier / AMC vendor
    condition: Mapped[str] = mapped_column(String(20), default="good")  # good, fair, poor
    status: Mapped[str] = mapped_column(String(30), default="in_service")  # in_service, under_maintenance, retired
    service_interval_days: Mapped[int | None] = mapped_column(Integer)
    last_service_date: Mapped[dt.date | None] = mapped_column(Date)
    next_service_due: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    external_source: Mapped[str | None] = mapped_column(String(40))
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

class AssetService(Base):
    __tablename__ = "asset_services"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    on: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20), default="preventive")  # preventive, repair, inspection
    cost: Mapped[float | None] = mapped_column(Float)
    vendor: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    ticket_id: Mapped[int | None] = mapped_column(Integer)
    by_name: Mapped[str | None] = mapped_column(String(200))

class Ticket(Base):
    """Raised by the premises admin in-charge, worked by the maintenance team. source/external_id allow merge with a ticketing system later."""
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"))
    category: Mapped[str] = mapped_column(String(40), default="other")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, critical
    status: Mapped[str] = mapped_column(String(20), default="open")      # open, assigned, in_progress, on_hold, resolved, closed
    utility_id: Mapped[int | None] = mapped_column(Integer)
    raised_by: Mapped[int | None] = mapped_column(Integer)
    raised_by_name: Mapped[str | None] = mapped_column(String(200))
    raised_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    resolution: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="bms")
    external_id: Mapped[str | None] = mapped_column(String(100), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

class TicketEvent(Base):
    __tablename__ = "ticket_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    user_id: Mapped[int | None] = mapped_column(Integer)
    user_name: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))   # created, comment, status, assign
    text: Mapped[str | None] = mapped_column(Text)


# ---------------- Phase 2: people, guest houses, HRMS integration ----------------
class Employee(Base):
    """Employee master. Entered manually now; source/external_id/synced_at let the HRMS take over later."""
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("company_id", "emp_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)   # building the employee is mapped to
    emp_code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    grade: Mapped[str | None] = mapped_column(String(20))
    designation: Mapped[str | None] = mapped_column(String(150))
    department: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="active")   # active, on_leave, notice, resigned, inactive
    join_date: Mapped[dt.date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default="manual")   # manual, import, hrms
    external_id: Mapped[str | None] = mapped_column(String(100))
    synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

class PremisesMeta(Base):
    __tablename__ = "premises_meta"
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), primary_key=True)
    beds: Mapped[int | None] = mapped_column(Integer)      # used only when no rooms are defined
    rooms: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    floors: Mapped[int | None] = mapped_column(Integer)
    halls: Mapped[int | None] = mapped_column(Integer)
    balconies: Mapped[int | None] = mapped_column(Integer)
    kitchens: Mapped[int | None] = mapped_column(Integer)
    maps_url: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(200))   # area / landmark
    amenities: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    area_sqft: Mapped[float | None] = mapped_column(Float)
    floors_taken: Mapped[str | None] = mapped_column(String(100))
    ownership: Mapped[str | None] = mapped_column(String(20))      # owned, leased, rented
    declared_headcount: Mapped[int | None] = mapped_column(Integer)
    litigation_count: Mapped[int | None] = mapped_column(Integer)
    litigation_notes: Mapped[str | None] = mapped_column(Text)
    occupancy: Mapped[str | None] = mapped_column(String(20))      # occupied, partial, vacant (HR / Admin can change)

class GuestAllocation(Base):
    __tablename__ = "guest_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    guest_house_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    room: Mapped[str | None] = mapped_column(String(40))
    purpose: Mapped[str | None] = mapped_column(String(200))
    from_date: Mapped[dt.date] = mapped_column(Date)
    to_date: Mapped[dt.date | None] = mapped_column(Date)
    room_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="allocated")   # allocated, vacated
    vacated_on: Mapped[dt.date | None] = mapped_column(Date)
    allocated_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class HrmsConfig(Base):
    __tablename__ = "hrms_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    base_url: Mapped[str | None] = mapped_column(String(300))
    auth_type: Mapped[str] = mapped_column(String(20), default="api_key")   # api_key, bearer, basic
    auth_header: Mapped[str | None] = mapped_column(String(60), default="X-API-Key")
    username: Mapped[str | None] = mapped_column(String(200))
    secret_enc: Mapped[str | None] = mapped_column(Text)                    # encrypted at rest, never returned by the API
    search_path: Mapped[str] = mapped_column(String(200), default="/employees")
    search_param: Mapped[str] = mapped_column(String(40), default="search")
    travel_path: Mapped[str] = mapped_column(String(200), default="/travel-advances")
    health_path: Mapped[str] = mapped_column(String(200), default="/health")
    field_map: Mapped[str | None] = mapped_column(Text)                     # JSON: our field -> HRMS field
    timeout_s: Mapped[int] = mapped_column(Integer, default=10)
    last_status: Mapped[str | None] = mapped_column(String(20))             # ok, error
    last_checked: Mapped[dt.datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(400))
    updated_by: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

class IntegrationLog(Base):
    __tablename__ = "integration_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
    system: Mapped[str] = mapped_column(String(20), default="hrms")
    direction: Mapped[str] = mapped_column(String(10))    # pull (HR to Admin), push (Admin to HR)
    operation: Mapped[str] = mapped_column(String(40))    # test, employee_search, travel_advance
    status: Mapped[str] = mapped_column(String(10))       # ok, error
    http_status: Mapped[int | None] = mapped_column(Integer)
    ms: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(400))
    ref: Mapped[str | None] = mapped_column(String(100))
    user_name: Mapped[str | None] = mapped_column(String(200))

class TravelAdvance(Base):
    """Raised by Admin (travel desk) or received from the Claims system, then pushed to the HRMS."""
    __tablename__ = "travel_advances"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(40))
    employee_name: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    purpose: Mapped[str | None] = mapped_column(String(300))
    destination: Mapped[str | None] = mapped_column(String(200))
    from_date: Mapped[dt.date | None] = mapped_column(Date)
    to_date: Mapped[dt.date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), default="admin")   # admin, claims
    claim_ref: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, pushed, failed
    hrms_ref: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(String(400))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    pushed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class GuestRoom(Base):
    """A bedroom in a guest house. Occupancy = active allocations in the room, against beds."""
    __tablename__ = "guest_rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    guest_house_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    floor: Mapped[str | None] = mapped_column(String(20))
    beds: Mapped[int] = mapped_column(Integer, default=1)
    features: Mapped[str | None] = mapped_column(String(300))   # comma separated: AC, attached bathroom, balcony ...
    notes: Mapped[str | None] = mapped_column(Text)


# ---------------- Phase 4/5: premises vault, utilities, notifications, vehicle management ----------------
class PremisesDocument(Base):
    __tablename__ = "premises_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))   # lease, purchase_deed, govt_registration, tax, insurance, occupancy_certificate, fire_noc, litigation, other
    title: Mapped[str | None] = mapped_column(String(200))
    number: Mapped[str | None] = mapped_column(String(100))
    authority: Mapped[str | None] = mapped_column(String(200))   # landlord / issuing authority
    issued_on: Mapped[dt.date | None] = mapped_column(Date)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    file: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(String(200))
    uploaded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class UtilityAccount(Base):
    __tablename__ = "utility_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))        # electricity, water, internet, gas, telephone, waste, other
    provider: Mapped[str] = mapped_column(String(200))   # supplier / internet provider
    account_ref: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    contact: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class UtilityBill(Base):
    __tablename__ = "utility_bills"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("utility_accounts.id"), index=True)
    period: Mapped[str | None] = mapped_column(String(20))     # e.g. 2026-10
    invoice_no: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[dt.date | None] = mapped_column(Date)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    invoice_file: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="due")   # due, paid
    paid_on: Mapped[dt.date | None] = mapped_column(Date)
    payment_ref: Mapped[str | None] = mapped_column(String(100))
    proof_file: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class Notification(Base):
    """In-app alert for everyone holding `perm` within the scope of premises_id (e.g. a leaver holding a vehicle goes to Admin and HR)."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(200))
    premises_id: Mapped[int | None] = mapped_column(Integer)
    perm: Mapped[str] = mapped_column(String(40), default="employees.write")
    ref: Mapped[str | None] = mapped_column(String(80), index=True)    # dedupe key, e.g. leaver:12
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

class NotificationRead(Base):
    __tablename__ = "notification_reads"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(primary_key=True)

class VehicleAssignment(Base):
    """Who holds a vehicle, with issue and return checklists. Return is complete only when Admin signs it."""
    __tablename__ = "vehicle_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    employee_id: Mapped[int | None] = mapped_column(Integer, index=True)    # null = common pool
    from_date: Mapped[dt.date] = mapped_column(Date)
    to_date: Mapped[dt.date | None] = mapped_column(Date)
    purpose: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")        # active, return_pending, returned
    issue_condition: Mapped[str | None] = mapped_column(Text)
    issue_meter: Mapped[float | None] = mapped_column(Float)
    issue_fuel: Mapped[str | None] = mapped_column(String(20))
    issue_photo: Mapped[str | None] = mapped_column(String(300))
    return_condition: Mapped[str | None] = mapped_column(Text)
    return_meter: Mapped[float | None] = mapped_column(Float)
    return_fuel: Mapped[str | None] = mapped_column(String(20))
    return_photo: Mapped[str | None] = mapped_column(String(300))
    damage: Mapped[bool] = mapped_column(Boolean, default=False)
    returned_on: Mapped[dt.date | None] = mapped_column(Date)
    signed_by: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str | None] = mapped_column(String(200))

class VehicleService(Base):
    """Scheduled servicing, breakdowns and repairs, with quotation approval, invoice and service report."""
    __tablename__ = "vehicle_services"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="scheduled")      # scheduled, breakdown, repair
    service_date: Mapped[dt.date | None] = mapped_column(Date)
    mileage: Mapped[float | None] = mapped_column(Float)
    issue: Mapped[str | None] = mapped_column(Text)
    vendor: Mapped[str | None] = mapped_column(String(200))
    quotation_amount: Mapped[float | None] = mapped_column(Float)
    quotation_file: Mapped[str | None] = mapped_column(String(300))
    approval: Mapped[str] = mapped_column(String(12), default="none")        # none, pending, approved, rejected
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_on: Mapped[dt.date | None] = mapped_column(Date)
    invoice_no: Mapped[str | None] = mapped_column(String(100))
    invoice_amount: Mapped[float | None] = mapped_column(Float)
    invoice_file: Mapped[str | None] = mapped_column(String(300))
    report_file: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open")          # open, awaiting_approval, approved, completed, cancelled
    next_service_date: Mapped[dt.date | None] = mapped_column(Date)
    next_service_km: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    incident_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    kind: Mapped[str] = mapped_column(String(20), default="accident")        # accident, damage, theft, breakdown
    location: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    injuries: Mapped[bool] = mapped_column(Boolean, default=False)
    police_report_no: Mapped[str | None] = mapped_column(String(100))
    claim_ref: Mapped[str | None] = mapped_column(String(100))
    claim_status: Mapped[str] = mapped_column(String(12), default="none")    # none, filed, approved, rejected, paid
    repair_estimate: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(15), default="open")          # open, under_review, closed
    reported_by: Mapped[str | None] = mapped_column(String(200))
    reported_via: Mapped[str] = mapped_column(String(15), default="web")     # web, driver_app
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class IncidentFile(Base):
    __tablename__ = "incident_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(15), default="photo")           # photo, police, insurance, estimate, other
    file: Mapped[str] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(String(300))


# ---------------- Phase 6: Travel & logistics ----------------
class TravelSetting(Base):
    __tablename__ = "travel_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(300))

class TravelPolicy(Base):
    """Entitlements by grade, maintained by HR (travel policy document). Shown to the traveller on the request screen."""
    __tablename__ = "travel_policy"
    id: Mapped[int] = mapped_column(primary_key=True)
    grade: Mapped[str] = mapped_column(String(20), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    flight_class: Mapped[str | None] = mapped_column(String(30))      # economy, premium economy, business
    hotel_a: Mapped[float | None] = mapped_column(Float)              # nightly limit by city grade
    hotel_b: Mapped[float | None] = mapped_column(Float)
    hotel_c: Mapped[float | None] = mapped_column(Float)
    daily_allowance: Mapped[float | None] = mapped_column(Float)
    advance_limit: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(300))

class TravelRequest(Base):
    __tablename__ = "travel_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    traveller_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    premises_id: Mapped[int] = mapped_column(ForeignKey("premises.id"), index=True)    # the traveller's building
    requested_by: Mapped[str | None] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(300))
    from_place: Mapped[str | None] = mapped_column(String(300))
    from_map: Mapped[str | None] = mapped_column(String(500))
    from_lat: Mapped[float | None] = mapped_column(Float)
    from_lng: Mapped[float | None] = mapped_column(Float)
    to_place: Mapped[str] = mapped_column(String(300))
    to_map: Mapped[str | None] = mapped_column(String(500))
    to_lat: Mapped[float | None] = mapped_column(Float)
    to_lng: Mapped[float | None] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(15), default="flight")                  # flight, train, road, other
    depart_on: Mapped[dt.date] = mapped_column(Date)
    return_on: Mapped[dt.date | None] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer, default=0)
    city_grade: Mapped[str] = mapped_column(String(1), default="A")
    hotel_needed: Mapped[bool] = mapped_column(Boolean, default=True)
    arrangement: Mapped[str] = mapped_column(String(10), default="company")          # company, self_pay
    budget: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    cost_centre: Mapped[str | None] = mapped_column(String(100))
    advance_requested: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="awaiting_hr")           # awaiting_hr, awaiting_admin, awaiting_bhead, approved, booked, completed, rejected, cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, onupdate=now)

class TravelApproval(Base):
    __tablename__ = "travel_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("travel_requests.id"), index=True)
    step: Mapped[str] = mapped_column(String(10))       # hr, admin, bhead
    decision: Mapped[str] = mapped_column(String(10))   # approved, rejected
    by_name: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(500))
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class TravelBooking(Base):
    """Flight or hotel option (fare comparison) and the chosen booking, with ticket, PNR, baggage and cancellation terms."""
    __tablename__ = "travel_bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("travel_requests.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="flight")    # flight, hotel, other
    status: Mapped[str] = mapped_column(String(10), default="option")  # option, booked, changed, cancelled, rejected
    vendor: Mapped[str | None] = mapped_column(String(200))           # airline / hotel
    booked_via: Mapped[str | None] = mapped_column(String(40))        # MakeMyTrip, other app, direct, travel desk
    route_or_city: Mapped[str | None] = mapped_column(String(300))
    start_at: Mapped[dt.datetime | None] = mapped_column(DateTime)    # departure / check-in
    end_at: Mapped[dt.datetime | None] = mapped_column(DateTime)      # arrival / check-out
    ref: Mapped[str | None] = mapped_column(String(100))              # PNR / hotel confirmation
    fare: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    baggage: Mapped[str | None] = mapped_column(String(200))
    meal_plan: Mapped[str | None] = mapped_column(String(100))
    cancel_terms: Mapped[str | None] = mapped_column(String(500))
    ticket_file: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

class TravelChange(Base):
    """Change, cancellation or refund against a booking, with penalty, refund reference and reconciliation."""
    __tablename__ = "travel_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("travel_bookings.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))       # change, cancel, refund
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    revised_ref: Mapped[str | None] = mapped_column(String(100))
    revised_file: Mapped[str | None] = mapped_column(String(300))
    penalty: Mapped[float | None] = mapped_column(Float)
    refund_expected: Mapped[float | None] = mapped_column(Float)
    refund_received: Mapped[float | None] = mapped_column(Float)
    refund_ref: Mapped[str | None] = mapped_column(String(100))
    vendor_balance: Mapped[float | None] = mapped_column(Float)   # owed to (+) or by (-) the vendor
    status: Mapped[str] = mapped_column(String(10), default="pending")   # pending, settled
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))

class TravelVisa(Base):
    __tablename__ = "travel_visas"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    kind: Mapped[str] = mapped_column(String(15), default="visa")      # visa, work_permit, special_pass
    country: Mapped[str] = mapped_column(String(80))
    passport_no: Mapped[str | None] = mapped_column(String(40))      # restricted to HR and Travel Desk
    application_ref: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(12), default="applied")   # draft, applied, approved, rejected, expired
    applied_on: Mapped[dt.date | None] = mapped_column(Date)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    file: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(200))

class TravelClaim(Base):
    __tablename__ = "travel_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("travel_requests.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="draft")   # draft, submitted, approved, paid, rejected
    submitted_on: Mapped[dt.date | None] = mapped_column(Date)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    paid_on: Mapped[dt.date | None] = mapped_column(Date)
    pay_ref: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(500))

class TravelClaimLine(Base):
    __tablename__ = "travel_claim_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("travel_claims.id"), index=True)
    category: Mapped[str] = mapped_column(String(15))   # ticket, hotel, local, da, other
    description: Mapped[str | None] = mapped_column(String(300))
    qty: Mapped[float | None] = mapped_column(Float)    # nights or days, for the policy limit
    amount: Mapped[float] = mapped_column(Float)
    policy_limit: Mapped[float | None] = mapped_column(Float)
    over_reason: Mapped[str | None] = mapped_column(String(300))
    receipt: Mapped[str | None] = mapped_column(String(300))

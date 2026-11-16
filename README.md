# Building Management System – first slice

Built from *Building_Management_System_Requirements_v6.docx*. This slice = foundation + Module 4 (vehicles, trips, fuel) + driver app.

## Run
    docker compose up -d --build
- Web admin: http://localhost:8000/app/
- Driver app (PWA, open on a phone, "Add to Home Screen"): http://localhost:8000/driver/
- API docs: http://localhost:8000/docs

## Demo logins (SEED_DEMO=1; remove before production)
| Email | Password | Role |
|---|---|---|
| admin@bms.local | admin123 | Group Admin |
| head@bms.local | head123 | Corporate Admin Head (Jiva Technologies) |
| premises@bms.local | premises123 | Premises Admin (HQ only) |
| driver1@bms.local | driver123 | Driver |
| employee1@bms.local | employee123 | Employee (can request trips via API) |

## Built
Roles + scope (group/company/premises) enforced on every API call · premises & sub-premises · vehicles, documents with versions and 30-day expiry
· trip request → assign → driver start/end (meter + photo, GPS) · fuel with mileage calc and flags (no photo, unusual km/l, meter rollback)
· dashboard · audit trail (user, time, previous, new) · white/gold three-panel web UI · driver PWA.

## Not built yet (per the requirements doc)
Tickets, assets, fire & safety, meeting rooms, travel, budget, integrations (HRMS, Tally, Outlook, WhatsApp, DMS...), leaver handover,
employee and maintenance apps, SSO, admin settings page, DB migrations (tables use create_all for now), offline queue in the driver app.

## Phase 1 additions: onboarding, assets, tickets

New demo logins: `guesthouse@bms.local / gh123` (Admin In-charge, Guest House 1 only), `maintenance@bms.local / maint123` (Maintenance Head, sees every ticket).

- **Onboarding** (Group Admin only): import premises/guest houses, vehicles and assets from CSV (template download, dry-run validation, all-or-nothing import, safe to re-run).
- **Asset register**: tag, premises, category, condition, warranty, service schedule and history; per-premises scope.
- **Tickets**: raised by the Admin In-charge (employees cannot raise); the Maintenance Head assigns, progresses and resolves; the in-charge confirms and closes.
- **Integration API** (`X-API-Key` = `INTEGRATION_API_KEY` in docker-compose.yml, change it): `GET/POST /api/integration/assets` and `/api/integration/tickets`, matched on `source` + `external_id`, `updated_since` for incremental sync. Reference at `/docs`.
- New tables only; existing data is untouched. Rebuild with `docker compose up -d --build api`.

## Phase 2: people, guest houses, HRMS integration

Demo logins: `hr@bms.local / hr123` (HR, all companies), `cgc@bms.local / cgc123` (Admin In-charge, CGC Ahmedabad), `archplace@bms.local / arch123` (Admin In-charge, The Arch Place Nairobi).
Demo buildings: Corporate Governance Center (CGC), Ahmedabad and Corporate Business Center, The Arch Place, Nairobi, each with a guest house.

- **Tickets** can be raised by HR, Admin (in-charges, heads, group admin) and the Maintenance Head only. Employee logins come later.
- **Employees** are mapped to a building with grade and status; headcount by building and status is on the Employees page. Add manually, by CSV (Onboarding step 2), or from the HRMS.
- **Guest houses** belong to a building, have beds, and employees are allocated with room, purpose and dates (one bed per employee, capacity enforced).
- **HRMS integration** (Group Admin, Administration menu): base URL, auth (API key header / bearer / basic), paths and a field mapping, all configurable. The secret is stored encrypted and never returned. Calls are made by the server and logged (no credentials or payloads). The dashboard shows connection status.
  - HR to Admin: employee search by name, username or code (`GET {search_path}?{search_param}=...`).
  - Admin and Claims to HR: travel advances (`POST {travel_path}`), retried if HR is unreachable. Claims posts to `POST /api/integration/travel-advances` with the integration API key.
- Demo mode ships a mock HRMS at `/mock-hrms` (key `demo-hrms-key`) so this works without a real HRMS. It only exists when `SEED_DEMO=1`.

## Bulk upload (Excel template)

`Template` and `Bulk upload` buttons appear on Asset register, Vehicles, Employees, Premises and Onboarding. The template is an .xlsx with an Instructions sheet, dropdowns (type, status, category, condition, existing premises names) and a grey example row that is skipped. Upload is validated first, all-or-nothing, and safe to repeat (existing records are skipped). Scope is enforced per row: an in-charge can only import into their own premises, and only a Group Admin can add top-level sites. API: `GET /api/templates/workbook.xlsx?sheet=all|premises|employees|vehicles|assets`, `POST /api/bulk/upload` (file, commit, kind for CSV).

## Guest houses (rooms, occupancy, assets)

Menu: Administration > Guest houses (below Premises). Each guest house has a profile (address, area, Google Maps link and pin, floors, halls, balconies, kitchens, amenities, contact), rooms with beds and features, and assets mapped to it. Occupancy is per bed: a 2-bed room with one resident is half green, two residents is fully green. Allocation is by room and refuses a full room. Editing details and rooms needs `premises.write` (in scope); allocating needs `allocations.write`.
Demo data: six sample guest houses in Nairobi around Kilimani near The Arch Place (Kilimani, Kileleshwa, Lavington, Hurlingham, Westlands, Parklands). Addresses and map pins are approximate samples: edit them.
Note: new columns on existing tables are added automatically at startup (`ALTER ... IF NOT EXISTS`).

## Premises vault, utilities, vehicle management

- **Premises** (Administration > Premises): cards and a Hierarchy view (group > company > building > guest house, with roll-ups for employees, guest houses, open issues, litigation and document alerts). Each premises has area (sq ft), floors taken, ownership, declared headcount, legal litigation count and notes, address and Google Map, an occupancy status HR and Admin can change, and a document vault (lease, purchase deed, government registration, tax, insurance, occupancy and fire certificates, floor plans, litigation). Documents are versioned; reminders at 90, 30 and 7 days show on the dashboard and bell.
- **Utilities** (Facilities > Utilities, and a section on each premises and guest house): accounts (electricity, water, internet and so on, with supplier and account reference) and monthly bills (invoice, due date, status). Marking paid needs proof or a payment reference. Tickets can be raised against a utility.
- **Vehicles**: assignment to employees with issue and return checklists (side by side), Handovers queue, leaver alerts to Admin and HR (`notifications` table, shown in the bell), insurance and compliance review, servicing and repairs with quotation approval (Corporate Admin Head / Group Admin), accidents and incidents with photos and claims. Driver app: fuel with start and closing meter photos, and Report accident.
- Demo data: Bengaluru was removed. Its vehicles, assets, tickets and employees were re-homed to CGC Ahmedabad; The Arch Place (Nairobi) carries the full profile, documents, utilities and six guest houses.

## Travel & logistics

Menu: Travel (Travel requests, Visa & permits, Refunds & reconciliation) and Administration > Travel policy. Raised by HR, Admin or the Travel Desk on behalf of the traveller (employee logins come later).
- **Request and approval:** company arrangement goes HR (policy check) then Admin; self-pay goes to the Business Head first (threshold configurable, 0 = every self-pay trip). Exact route with Google Maps pins, dates, budget, cost centre, advance. The screen shows the traveller's policy limits by grade.
- **Booking:** flight and hotel fare options compared side by side, then booked with PNR / confirmation, ticket, baggage and cancellation terms. MakeMyTrip and other apps open as search suggestions in a new tab (no traveller data is sent).
- **Changes, refunds and reconciliation:** original and revised ticket, penalty, refund expected and received, vendor balance.
- **Visa & permits:** passport numbers visible to HR and Travel Desk only (masked for others), expiry reminders.
- **Advance and claim:** advance limited by grade and pushed to the HRMS; claim lines with receipts and policy limits (over-limit lines need a reason), manager approval, then Finance pays.
- **Bulk upload:** the Excel template now includes `Travel_policy` and `Visas` sheets. Demo logins: `traveldesk@bms.local / travel123`, `finance@bms.local / finance123`.

## Layout: waiting for you, tiles, my activity

- **Action bar** under the top bar on every page: "Waiting for you" (approvals, returns to sign, tickets to assign, new incidents) and "Pending" (overdue tickets and bills, expiring documents and renewals, refunds, visas and more). Each chip opens the page to act on. It only shows what the signed-in role can see.
- **Dashboard**: tiles grouped into Premises & facilities, Vehicles & fleet, Maintenance, and Travel & administration. Tile colour shows urgency; every tile opens its page.
- **Right panel**: the selected record and its history, **My recent activity** (what the signed-in user did, each linked), and recently opened pages. `GET /api/me/activity`.
- Demo data: a second corporate business premises at The Arch Place, Nairobi, with "The Arch Place Residence", a 12-bed guest house (6 twin rooms).

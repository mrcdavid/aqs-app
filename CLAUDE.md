# CLAUDE.md — AQS APP (Automatic Quotation System)

Read this file fully at the start of every session. Source of intent: `plan.md.txt` (in the repo
root). If this file and a habit conflict, follow this file. If this file and `plan.md.txt`
conflict, this file wins (it records decisions made after the plan) — but point out the conflict.
Detailed business rules (pricing, options, items, statuses, PDF, dashboard): **`docs/quotations.md`**.

> Product name is **AQS APP** (repo folder `AQS-APP`, local folder `AES APP`). Use "AQS" in code,
> package names, DB names, and UI text.

---

## 1. What this project is

A web app that produces **automatic quotation PDFs** for glass, aluminum, and metal
fabrication jobs (sliding windows, sliding doors, window grills, etc.).

A customer — or staff, for a walk-in client — adds one or more items (product, glass choice,
add-ons such as an open back frame, width × height in inches (or cm), quantity), clicks **Process**,
and immediately gets a draft PDF estimate. An admin reviews it (optionally adjusting the final
amount) and approves it; the approved quote becomes the official PDF and feeds the dashboard.
Pricing follows the shop (v2, 2026-10-17): sliding windows are sold **per sq ft** at owner-set rates;
grills are priced from the **whole bars** they use plus labour; materials are entered in the units
they are bought in (21-ft bars, kilos, pieces, feet, sq ft). Prices include VAT.

### Roles (exactly three — do not add more without asking)

| Role          | Login method                       | Can do |
|---------------|------------------------------------|--------|
| `user`        | Google OAuth, `@up.edu.ph` only    | Create profile, create quotation requests, view/print own draft & approved PDFs, cancel own pending requests, edit own profile |
| `admin`       | Email + password (staff account)   | Everything a user can + quote walk-in clients; manage products, templates (choices, add-ons), materials, labour rates, settings; approve/reject/cancel requests; view users, audit log, dashboard |
| `super_admin` | Email + password (staff account)   | Everything an admin can + create/disable/delete admins and users, monitor sessions, **delete any quotation** (soft delete), modify any setting |

## 2. Goals

1. A customer can go from login → profile → quotation PDF in under 2 minutes.
2. Prices are always computed **on the server** from the current price list; the client never sends a price.
3. Approved quotes are immutable and reproducible (price snapshot stored with each item).
4. Admin dashboard: approved quotations per day, by location and product, value, approval rate.
5. Secure by default (see §6) while staying simple — a small team must be able to maintain it.

## 3. Confirmed decisions (log)

Superseded entries say so; current detail lives in `docs/quotations.md`.

| Date       | Decision |
|------------|----------|
| 2026-09-26 | Product name is AQS APP. |
| 2026-09-26 | Customers log in with Google OAuth restricted to `@up.edu.ph`. Staff (admin/super_admin) log in with email + password. |
| 2026-09-26 | "Process" generates an instant **draft** PDF watermarked `ESTIMATE – PENDING APPROVAL`. After admin approval, a **final** PDF with a quote number is issued. |
| 2026-09-26 | Run locally on Windows for now (PostgreSQL via local install / pgAdmin 4). Hosting decided later. |
| 2026-09-26 | PDF library: **ReportLab** (pure Python, installs cleanly on Windows). |
| 2026-09-26 | Sessions: server-side sessions in an httpOnly cookie — **no JWT in the browser, nothing in localStorage**. |
| 2026-09-26 | Customers: UP people only (`ALLOWED_EMAIL_DOMAIN=up.edu.ph`). Google consent screen is External; the domain is enforced server-side. May open to any verified Google account later (make the domain optional + tests). |
| 2026-09-26 | DB enforces: Google accounts are always `user`; staff (`admin`/`super_admin`) always password. |
| 2026-09-26 | audit_log is append-only via a DB trigger; users with audit history can only be soft-deleted. |
| 2026-09-26 | Profile: full name, age 18–120, PH mobile (09… / +639…), street, city, province. |
| 2026-09-26 | ~~Pricing = templates in m²/m, markup, then VAT% added~~ — superseded 2026-10-17 (pricing v2). Still true: line cost = measurement × factor × (1 + waste%) × item price; half-up to centavos at each step. |
| 2026-09-26 | Defaults: markup 0%, VAT 12%, PHP (single `pricing_settings` row). Products are archived, never deleted. Materials/labour rates can be archived, or deleted one at a time only when no template uses them (409 otherwise). An item's unit can't change while a template uses it. |
| 2026-09-26 | ~~One product per quote; customers see unit price/VAT/total~~ — superseded 2026-10-12 / 2026-10-16. Prices frozen at Process; business details frozen at approval (still true). |
| 2026-09-26 | Approval assigns `AQS-<year>-<6 digits>` (Philippine time, counter per year), valid 30 days (editable), stores the final PDF once in `backend/storage/quotes/`. Rejection needs a note; the customer sees notes. |
| 2026-09-26 | Limits: 10 quote requests/min per IP, max 20 pending per customer. |
| 2026-09-26 | Audit log viewer at `/admin/audit-log` (admin + super_admin): read-only, filters by action prefix / actor email / PHT date range, 50 per page. |
| 2026-09-26 | ~~Dashboard counts all requests~~ — superseded 2026-10-16. Date range by request date (PHT, max 366 days); approval rate = approved ÷ (approved + rejected). |
| 2026-09-26 | User management: all staff can view; only super_admin can change. No self-changes. Disable/delete/role change/password reset revoke sessions. Deletes are soft. Customers can't be promoted to staff. Active sessions page is super_admin only. |
| 2026-09-26 | Admin pages are lazy-loaded (`features/admin/pages.ts`) so customers never download them. |
| 2026-09-27 | UI: Blue→Indigo gradient; Light/Dark/System theme (Zustand + localStorage `aqs-theme`, class-based dark mode); Inter via `@fontsource-variable/inter`; add/edit/confirm in native `<dialog>` modals (`components/ui/Modal.tsx`, `confirmAction()` in `stores/feedback.ts`); toasts; shared UI kit in `components/ui/`. Colours only via semantic tokens in `index.css` (bg-surface, text-ink, border-line, bg-brand…). |
| 2026-10-12 | Staff (admin/super_admin) quote **walk-in clients** without an account (name, PH mobile, optional email, address): `user_id` NULL, `created_by` = staff, starts pending, never shown in a customer account. |
| 2026-10-12 | Amounts **round up** to the next `rounding_step` (Settings, default ₱100, 0 = off). On approval an admin may set a different final amount (audited `adjusted_from`). |
| 2026-10-12 | Customers (API + PDF) never see VAT, unit prices, costs or markup — only amounts (VAT included). PDF shows 50% downpayment / 50% upon completion and installation, and signature lines: owner (Settings → owner name, "Cleo David") and client ("Conforme"). |
| 2026-10-12 | **Add-ons**: optional template parts (e.g. open back), unticked by default, chosen by customers and staff; listed as "With: …". |
| 2026-10-14 | Input validation shared by backend (`schemas/common.py`) and frontend (`lib/schemas.ts`): PH mobile only (separators stripped), letters-only names/places, optional-but-valid email. |
| 2026-10-15 | **Choice groups** ("choose one", e.g. Glass type; first choice pre-selected). Add-ons may reduce the window size: size typed = wall opening, other lines measured smaller (open back). |
| 2026-10-15 | Required fields show a red `*` (`Field required`, `RequiredMark`, `RequiredNote`). |
| 2026-10-15 | PDF redesigned in app colours (gradient header/total, rounded cards); draft watermark drawn **on top** of the content. |
| 2026-10-15 | Staff can **cancel** pending quotations (optional reason). Approve, reject and cancel ask a **Yes/No confirmation** first. |
| 2026-10-16 | **Several items per quotation** (1–20): each with its own product, size, qty, choices, add-ons and amount (rounded up per item); total = sum; a changed final amount shows as an adjustment. Existing quotes migrated to one item. |
| 2026-10-16 | The PDF never lists materials/labour ("Includes"). Admin price preview re-prices as soon as a choice/add-on changes. |
| 2026-10-16 | Dashboard counts **approved quotations only** (except approval rate and "waiting for review"). |
| 2026-10-16 | **Super admin can delete any quotation** — soft delete (`deleted_at`, `deleted_by`), hidden everywhere incl. dashboard, kept in DB + audit log. |
| 2026-10-17 | **Pricing v2 — buying units.** Materials per piece, kg, ft, sq ft or **bar** (stock length, e.g. 21 ft / 6 m; always whole bars, rounded up). Labour per piece, ft or sq ft. Old m²/m prices converted at the same cost (migration 0009). |
| 2026-10-17 | Products have a **pricing method**: `per_sqft` (sliding windows: area × (product rate + chosen options' rates), no markup; the template is a **cost guide** showing cost and margin to staff) or `computed` (e.g. grills: Σ lines × (1 + markup)). |
| 2026-10-17 | Glass type = a choice with its own rate per sq ft (first = default, e.g. 1/4 Bronze). Sheet size (4×7 ft default, 4×8, 4×6) = a zero-rate choice group: recorded, not priced. Open back = add-on with an extra rate per sq ft. |
| 2026-10-17 | Grills: bars used (area basis, factor = bars per sq ft; 48×48 in ≈ 3.5 → 4 bars of 6 m) + fixed labour per grill + markup. |
| 2026-10-17 | **Prices are final, VAT included** — VAT is never added (staff see the VAT inside each amount). Sizes typed in **inches by default** (cm accepted); area in sq ft from the exact inches. |
| 2026-10-17 | Staff can **raise (or lower) every rate per sq ft by N%** (Settings; −50…+100; Yes/No; audited). Computed products follow their material prices. |

Assumptions not yet confirmed (ask before relying on them heavily):
- Currency is PHP (₱) and VAT defaults to 12%, editable by admin.
- Staff accounts do not need an `@up.edu.ph` email.

## 4. Tech stack (pinned — do not swap or add major libraries without asking)

**Frontend** (`/frontend`): React 19 + TypeScript 6 (`strict`), Vite 8; Tailwind CSS v4 via `@tailwindcss/vite`,
tokens in `src/index.css` `@theme` (no `tailwind.config.js`); React Router v7 data router (`createBrowserRouter`,
from `react-router`; loaders/actions for server data); React Hook Form + Zod (`useFieldArray` for quotation items);
Zustand only for small UI state (sidebar, theme, toasts/confirm) — **never** auth or user data; `lucide-react`;
`@fontsource-variable/inter`; lint: oxlint.

**Backend** (`/backend`): Python 3.12+ (dev machine 3.14), FastAPI, Uvicorn — managed with `uv`; SQLAlchemy 2.0
async (typed `Mapped[]`) + asyncpg; Alembic; Pydantic v2 + `pydantic-settings`; Authlib (Google OIDC);
`pwdlib[argon2]` (Argon2id); ReportLab; `slowapi`; pytest + httpx; Ruff.

**Database**: PostgreSQL 16+ on this machine (managed with pgAdmin 4).

## 5. Architecture

```
Browser (React SPA)
   │  same-origin requests, cookie: __Host-aqs_session (httpOnly) + X-CSRF-Token header
   ▼
Vite dev server :5173 ──proxy /api──►  FastAPI :8000  ──asyncpg──►  PostgreSQL :5432 (db: aqs)
                                           │
                                           ├─ Google OIDC (customers)
                                           └─ backend/storage/quotes/*.pdf (final PDFs, not web-served)
```

- **Same origin in dev and prod.** Vite proxies `/api` to FastAPI in dev; in prod one reverse proxy
  serves the built SPA and `/api`. No CORS.
- All API routes live under `/api/v1/...`.
- Layers: `api` (routes, thin) → `services` (business logic) → `models` (DB). Routes never contain
  pricing or SQL beyond simple lookups.

### Auth flows
- **Customer**: `GET /api/v1/auth/google/login` → Google (`hd=up.edu.ph`, state, nonce, PKCE) →
  `/api/v1/auth/google/callback`. Server **must verify** the ID token, `email_verified == true`, email ends with
  `@up.edu.ph` and `hd == "up.edu.ph"`. First login creates a `user` row → profile setup before quoting.
- **Staff**: `POST /api/v1/auth/staff/login` (rate-limited 5/min, generic errors, lockout 15 min after 10 failures).
  No public staff registration — first `super_admin` via `scripts/create_super_admin.py`; later admins by super_admin
  (Users → Add staff account).
- **Session**: random 256-bit token, only its SHA-256 hash stored (`sessions`). Cookie `__Host-aqs_session` + `Secure`
  in production, `aqs_session` in dev/tests; always `HttpOnly`, `SameSite=Lax`, `Path=/`. Idle timeout 30 min staff,
  8 h users; absolute 7 days. Rotate on login and role change. Logout deletes the row.

### Quotation flow (detail: `docs/quotations.md`)
1. Customer (own profile) or staff (walk-in client details) adds 1–20 items: product, choices, add-ons, size + unit, qty.
2. Server converts to **integer mm** (stored, checked against per-product min/max) and **exact inches** (priced),
   validates options, prices each item with `services/pricing.py` + `services/options.py` (`Decimal`; per sq ft or
   computed), rounds each item up, freezes each item's snapshot, stores the quotation `pending` with total = Σ items.
3. Draft PDF generated on request from the snapshots (not stored), watermarked.
4. Admin approves (optional final amount → adjustment), rejects (note), or cancels; customers may cancel their own.
   Approval assigns `AQS-YYYY-000123`, generates the final PDF once, stores it, sets `approved`.
5. Super admin may soft-delete any quotation. Every state change writes an `audit_log` row.

Statuses: `pending` → `approved` | `rejected` | `cancelled` (+ `deleted_at` for soft-deleted).

### Core tables
`users`, `profiles`, `sessions`, `materials` (unit; bars: stock length), `labor_rates`, `products` (pricing method,
rate per sq ft), `product_option_groups`, `product_options` (add-ons and choices, size reductions, rate per sq ft),
`product_components` (template line: material XOR labour rate + basis/factor/waste + optional `option_id`),
`pricing_settings` (id=1: markup, VAT, currency, validity, rounding step, business
details, owner name), `quotations` (client snapshot, total, status, review fields, `user_id` nullable, `created_by`,
`deleted_at/by`), `quotation_items` (product, size, qty, amount, snapshot), `quote_counters`,
`audit_log` (append-only). UUID primary keys; `timestamptz` in UTC, displayed in Asia/Manila.

## 6. Security rules (non-negotiable)

- **Tokens**: never in localStorage, sessionStorage, Zustand, or JS-readable cookies.
- **CSRF**: `SameSite=Lax` **plus** double-submit token (`aqs_csrf` cookie → `X-CSRF-Token` on every
  POST/PUT/PATCH/DELETE); middleware also checks `Origin` against `APP_ORIGIN`. No state changes on GET.
- **CORS**: not enabled. If ever needed, exact origins with `allow_credentials=True` — never `*`.
- **Authorization** on the server in FastAPI dependencies (`StaffUser`, `SuperAdminUser`, `CustomerUser`) on every
  route. Ownership and `deleted_at IS NULL` are checked in the query (`not_deleted()`), not after. Hiding a button is
  not security.
- **Input validation**: Pydantic schemas with bounds on every field; `extra="forbid"`; shared field rules in
  `schemas/common.py`.
- **SQL**: SQLAlchemy only; never build SQL with f-strings or string concatenation.
- **Passwords** (staff only): Argon2id, min 12 chars, common-password check, rate limit, lockout.
- **Security headers**: CSP (`default-src 'none'`), nosniff, `strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  HSTS on HTTPS. (CSP blocks the Swagger page at `/api/docs` — known, not needed.)
- **Secrets** in git-ignored `.env`; commit only `.env.example`. `staff-accounts.txt` (owner's private notes) is
  git-ignored too — never read it out, print it, or commit it. Never print secrets in logs, errors, or chat.
- **Errors**: generic messages to clients; details in server logs. No stack traces in responses.
- **PDF files** only through authorized endpoints (`GET /api/v1/quotations/{id}/pdf`, admin equivalent).
- **Audit**: logins, role changes, price/settings/template changes, approvals, rejections, cancellations, deletions.
- **Deletion**: soft deletes (users: `is_active=false` + `deleted_at`; quotations: `deleted_at`) unless the owner
  explicitly asks for hard delete; audit rows are never deleted.
- **Dependencies**: pinned (`uv.lock` / `package-lock.json`); don't add packages without asking.

## 7. Where files go

```
AQS-APP/  CLAUDE.md, README.md (setup/run guide), plan.md.txt, docs/ (quotations.md = business rules)
├── backend/
│   ├── app/  main.py | core/ (config, security, csrf, headers, deps, rate_limit) | db/ (base, session)
│   │   ├── models/    user, session, catalog (materials…product_options), quotation (+ items), audit
│   │   ├── schemas/   auth, profile, catalog, quotation, dashboard, users, audit, common (shared field rules)
│   │   ├── api/v1/    auth, health, profile, quotations (customer), admin_catalog, admin_quotations,
│   │   │              admin_dashboard, admin_users, admin_audit
│   │   └── services/  pricing, options, catalog, quotations, quotation_views, pdf, dashboard, sessions, oauth, audit
│   ├── alembic/versions/  0001–0009, hand-reviewed (see docs/quotations.md §7)
│   ├── scripts/   create_db.py, create_super_admin.py, reset_staff_password.py
│   ├── storage/quotes/  final PDFs (git-ignored)
│   └── tests/     test_<area>.py, incl. test_migrations.py (data round-trip)
└── frontend/src/
    ├── main.tsx, router.tsx, index.css (Tailwind + @theme tokens)
    ├── api/        client.ts (fetch wrapper, CSRF), auth, profile, quotations, admin
    ├── features/   auth/, profile/, quotations/ (incl. shared QuoteItemFields + quoteItem.ts), admin/
    │               (staff + super-admin pages; super-admin/ is empty)
    ├── components/ layout + ui/ (Button, Card, Field, Modal, Badge, Feedback…)
    ├── lib/        schemas.ts (shared zod rules), format.ts, errors.ts, guards.ts
    └── stores/     Zustand UI-only stores: ui.ts (theme, sidebar), feedback.ts (toasts, confirm dialog)
```

Rules: new backend endpoint → router in `api/v1/`, schema in `schemas/`, logic in `services/`, test in `tests/`.
New page → `frontend/src/features/<feature>/`. Don't create new top-level folders without asking.

## 8. Database setup (local, pgAdmin 4)

- `backend/.env` holds `DATABASE_URL=postgresql+asyncpg://aqs_app:<pw>@localhost:5432/aqs` and, for setup only,
  `POSTGRES_ADMIN_URL` (the postgres superuser used in pgAdmin).
- `uv run python -m scripts.create_db` creates the `aqs_app` role (least privilege) and the `aqs` + `aqs_test`
  databases. Then `alembic upgrade head`, then `create_super_admin`. The catalogue (materials, labour, products,
  choices, add-ons) is entered through the admin UI — there is no seed script.
- Schema changes **only** through Alembic migrations. Never edit tables by hand in pgAdmin.
- Ask the owner for DB credentials; never guess, hard-code, or commit them.

## 9. How I (Claude) should work

- **Ask when unclear** — especially pricing formulas, product rules, or anything touching money or security.
- Keep it simple: standard library / pinned stack over new abstractions. No microservices, queues, or caches.
- Small, reviewable changes. After a change, say what was changed and how to run/test it.
- Money: `Decimal` in Python, `NUMERIC(12,2)` in Postgres, formatted strings in the UI. Never floats.
- Units: accept inches (default) or cm at the edge; store integer mm (limits); price from the exact inches (cm ÷ 2.54,
  never via rounded mm): lengths in ft, area in sq ft = w × h ÷ 144 (2 dp). PDF shows the typed size + sq ft.
- Write tests for pricing, unit conversion, auth/role checks, CSRF and data migrations before calling a feature done.
- Type everything: TS `strict`, Python type hints; Ruff clean; no `any` / `# type: ignore` without a comment why.
- Alembic autogenerate duplicates CHECK constraints for `str_enum` columns — hand-write/edit migrations (VARCHAR +
  one named `ck_...`), then run `alembic check`. Migrations that move data get a round-trip test.
- Tests wipe `aqs_test` — never point a dev server at it while running tests.
- PDFs: the browser pane can't show them; render to PNG (`uv run --with pypdfium2 --with pillow`). To assert PDF
  text in tests set `reportlab.rl_config.pageCompression = 0` — **before approval**, because the final PDF is stored
  at approval time. Keep a typical 2-item quote on one page (signatures included).
- Staff sessions expire after 30 idle minutes; Claude can't sign in (never types the owner's password) — ask the
  owner to sign in on the browser pane for UI checks, or verify via tests.
- Shell is Windows (PowerShell/Git Bash). PowerShell 5.1 has no `&&` — give one command per line.
- Git: `main`, pushed to GitHub (`origin`). The owner often commits/pushes themselves; check `git status` first.
  Never commit or push unless asked.
- Don't expose secrets, the user's email, or DB passwords in code, logs, or messages.

### Keeping this file current
When a decision changes or we learn something important (new rule, changed stack choice, a gotcha),
**propose an edit to CLAUDE.md, show the exact diff, and wait for approval before saving.**
Add confirmed decisions to the log in §3 with the date. Keep this file under ~300 lines —
move long detail into `docs/` (e.g. `docs/quotations.md`) and link it here.

## 10. Common commands

Dev servers: `.claude/launch.json` defines `backend` (:8000) and `frontend` (:5173). Full setup guide: `README.md`.

```bash
# backend (from backend/)
uv sync
uv run python -m scripts.create_db
uv run alembic upgrade head
uv run alembic check
uv run python -m scripts.create_super_admin   # first owner account (hidden password prompt)
uv run python -m scripts.reset_staff_password # forgotten staff/owner password (unlocks + signs out)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest      # aqs_test DB; ~5 min; DB tests skip if it's missing
uv run ruff check .
uv run ruff format .

# frontend (from frontend/)
npm install
npm run dev        # http://localhost:5173
npm run build      # also type-checks
npm run lint
```

Gotcha: restart the backend after editing `.env` — `--reload` only watches `.py` files.

## 11. Open questions

- Real catalogue to enter in the admin UI (pricing v2): rates per sq ft for each sliding window, glass type (1/4
  Bronze, reflective mirror, smoked…) and the open back extra; sheet sizes; 21-ft profile bars, kilo items (jamb
  rubber, vinyl #1); grill designs (bars per sq ft) and labour per grill.
- Sliding doors: per sq ft like windows? Open back size reductions are still entered in mm — switch to inches?
- Hide the "Includes: …" materials list on the customer's quotation page too (the PDF already hides it)?
- Dashboard dates: keep "requested in range" or switch to "approved in range" for sales figures?
- Restore for deleted quotations (a Deleted tab)? Allow PH landlines for walk-in clients?
- A font with the ₱ glyph for the PDF (needs a font file in the repo)?
- Is a minimum charge per window / per quotation needed (small windows priced per sq ft)? Business logo on the PDF?
- Enter real business name, address, contact and terms in Admin → Settings (placeholders now).
- Hosting target and domain (HTTPS, cookie `Secure`, backups). Google OAuth app is in "Testing": add test users;
  "Publish app" before real users.

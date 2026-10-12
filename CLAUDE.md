v# CLAUDE.md — AQS APP (Automatic Quotation System)

Read this file fully at the start of every session. Source of intent: `plan.md.txt`
(currently on the Desktop, outside this folder — move it into `AQS-APP/` to keep it in git).
If this file and a habit conflict, follow this file. If this file and `plan.md.txt`
conflict, this file wins (it records decisions made after the plan) — but point out the conflict.

> Product name is **AQS APP** (repo folder `AQS-APP`). Use "AQS" in code, package names,
> DB names, and UI text.

---

## 1. What this project is

A web app that produces **automatic quotation PDFs** for glass, aluminum, and metal
fabrication jobs (sliding windows, sliding doors, window grills, etc.).

A customer picks a product, enters width/length and height (cm or inch), clicks **Process**,
and immediately gets a PDF estimate. An admin reviews and approves it; the approved quote
becomes the official PDF and feeds the dashboard.

### Roles (exactly three — do not add more without asking)

| Role          | Login method                       | Can do |
|---------------|------------------------------------|--------|
| `user`        | Google OAuth, `@up.edu.ph` only    | Create profile, create quotation requests, view/print own draft & approved PDFs, edit own profile |
| `admin`       | Email + password (staff account)   | Everything a user can + manage products, materials & prices, product templates, labor rates, markup/VAT settings, all quotation requests (approve/reject), users, view audit log, dashboard |
| `super_admin` | Email + password (staff account)   | Everything an admin can + create/disable/delete admins and users, monitor active users/admins and sessions, view all logs, modify any setting |

## 2. Goals

1. A customer can go from login → profile → quotation PDF in under 2 minutes.
2. Prices are always computed **on the server** from the current price list; the client never sends a price.
3. Approved quotes are immutable and reproducible (price snapshot stored with the quote).
4. Admin dashboard: quotations per day, by location, total cost per project, approval rates.
5. Secure by default (see §6) while staying simple — a small team must be able to maintain it.

## 3. Confirmed decisions (log)

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
| 2026-09-26 | Pricing = admin-built templates. Line cost = measurement × factor × (1 + waste%) × item price. Customer unit price = cost per piece × (1 + markup%); amount = unit price × qty; then VAT%. Round half-up to centavos at each step. |
| 2026-09-26 | Defaults: markup 0%, VAT 12%, PHP (single `pricing_settings` row). Products are archived, never deleted. Materials/labour rates can be archived, or deleted one at a time only when no template uses them (409 otherwise). An item's unit can't change while a template uses it. |
| 2026-09-26 | Quotations: one product per quote (qty 1–100). Prices frozen in `quotations.snapshot` at Process; business details frozen at approval. Customers see unit price/VAT/total only, never costs or markup. |
| 2026-09-26 | Approval assigns `AQS-<year>-<6 digits>` (Philippine time, counter per year), valid 30 days (editable), stores the final PDF once in `backend/storage/quotes/`. Rejection needs a note; the customer sees notes. |
| 2026-09-26 | Limits: 10 quote requests/min per IP, max 20 pending per customer. |
| 2026-09-26 | Audit log viewer at `/admin/audit-log` (admin + super_admin): read-only, filters by action prefix / actor email / PHT date range, 50 per page. |
| 2026-09-26 | Dashboard at `/admin`: figures count requests created in a PHT date range (max 366 days); approval rate = approved ÷ (approved + rejected). |
| 2026-09-26 | User management: all staff can view; only super_admin can change. No self-changes. Disable/delete/role change/password reset revoke sessions. Deletes are soft. Customers can't be promoted to staff. Active sessions page is super_admin only. |
| 2026-09-26 | Admin pages are lazy-loaded (`features/admin/pages.ts`) so customers never download them. |
| 2026-09-27 | UI: Blue→Indigo gradient; Light/Dark/System theme (Zustand + localStorage `aqs-theme`, class-based dark mode); Inter via `@fontsource-variable/inter`; add/edit/confirm in native `<dialog>` modals (`components/ui/Modal.tsx`, `confirmAction()` in `stores/feedback.ts`); toasts; shared UI kit in `components/ui/`. Colours only via semantic tokens in `index.css` (bg-surface, text-ink, border-line, bg-brand…). |

Assumptions not yet confirmed (ask before relying on them heavily):
- Currency is PHP (₱) and VAT defaults to 12%, editable by admin.
- Staff accounts do not need an `@up.edu.ph` email.
- Customer profile fields: full name, age, contact number, address (city/province for dashboard location).

## 4. Tech stack (pinned — do not swap or add major libraries without asking)

**Frontend** (`/frontend`)
- React 19 with TypeScript 6 (`strict: true`), Vite 8
- Tailwind CSS v4 via `@tailwindcss/vite`; theme tokens in `src/index.css` with `@theme` (no `tailwind.config.js`)
- React Router v7 data router (`createBrowserRouter`, import from `react-router`); use loaders/actions for server data
- React Hook Form + Zod for forms
- Zustand only for small UI state (sidebar, theme) — **never** auth or user data
- `lucide-react` for icons
- `@fontsource-variable/inter` (self-hosted font)
- Lint: oxlint (Vite default)

**Backend** (`/backend`)
- Python 3.12+ (dev machine has 3.14), FastAPI, Uvicorn — managed with `uv`
- SQLAlchemy 2.0 async with typed `Mapped[]` models + asyncpg
- Alembic for migrations
- Pydantic v2 + `pydantic-settings`
- Authlib for Google OAuth/OIDC
- `pwdlib[argon2]` for staff password hashing (Argon2id; OWASP-recommended successor to bcrypt; `passlib` is unmaintained)
- ReportLab for PDFs
- `slowapi` for rate limiting
- pytest + httpx for tests; Ruff for lint/format

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
  serves the built SPA and `/api`. This lets us avoid CORS entirely.
- All API routes live under `/api/v1/...`.
- Layers in backend: `api` (routes, thin) → `services` (business logic) → `models` (DB). Routes never
  contain pricing or SQL beyond simple lookups.

### Auth flows
- **Customer**: `GET /api/v1/auth/google/login` → Google (with `hd=up.edu.ph`, state, nonce, PKCE) →
  `/api/v1/auth/google/callback`. Server **must verify** the ID token, `email_verified == true`,
  and that the email ends with `@up.edu.ph` and `hd == "up.edu.ph"` (the `hd` URL param alone is not a security control).
  First login creates a `user` row; user is redirected to profile setup before quoting.
- **Staff**: `POST /api/v1/auth/staff/login` with email + password. Rate-limited, generic error
  messages, account lockout after repeated failures. No public staff registration — the first
  `super_admin` is created by `backend/scripts/create_super_admin.py`; later admins by super_admin.
- **Session**: random 256-bit token; only its SHA-256 hash is stored in the `sessions` table
  (user_id, created_at, last_seen_at, expires_at, ip, user_agent). Cookie:
  `__Host-aqs_session` + `Secure` in production; `aqs_session` without `Secure` in local dev/tests
  (the `__Host-` prefix requires HTTPS). Always `HttpOnly`, `SameSite=Lax`, `Path=/`. Idle timeout 30 min for staff,
  8 h for users; absolute timeout 7 days. Rotate the token on login and role change.
  "Active users/admins" for super_admin = sessions with recent `last_seen_at`. Logout deletes the row.

### Quotation flow
1. User picks a product template, enters dimensions + unit (`cm` | `in`) and quantity.
2. Server converts to **integer millimetres**, validates min/max per product, computes cost with
   `services/pricing.py` using `Decimal` (never `float`), and stores a `quotation` with status
   `pending` plus a JSON **price snapshot** (materials, labor, markup, VAT, totals).
3. Draft PDF is generated on request from the snapshot (not stored), watermarked.
4. Admin approves/rejects (with note). On approval: assign quote number `AQS-YYYY-000123`,
   generate the final PDF once, store it in `backend/storage/quotes/`, set status `approved`.
5. Every state change writes an `audit_log` row.

Statuses: `pending` → `approved` | `rejected`; `cancelled` by the user while pending.

### Core tables
`users` (id, email, role, auth_provider, password_hash nullable, is_active, failed_logins, locked_until),
`profiles`, `sessions`, `materials`, `labor_rates`, `products`, `product_components` (template line: material XOR labour
rate + basis/factor/waste), `pricing_settings` (id=1, also business details + validity),
`quotations` (snapshot JSONB + dashboard columns), `quote_counters`,
`audit_log` (actor_id, action, entity, entity_id, before/after JSON, ip, created_at — append-only).
Use UUID primary keys; timestamps stored as `timestamptz` in UTC, displayed in Asia/Manila.

## 6. Security rules (non-negotiable)

- **Tokens**: never store session or auth tokens in localStorage, sessionStorage, Zustand, or JS-readable cookies.
- **CSRF**: `SameSite=Lax` cookie **plus** double-submit token: server sets a non-httpOnly `aqs_csrf`
  cookie; frontend sends it as `X-CSRF-Token` on every POST/PUT/PATCH/DELETE; middleware rejects
  mismatches and also checks the `Origin` header against `APP_ORIGIN`. No state changes on GET.
- **CORS**: not enabled (same-origin via proxy). If ever needed, allow only the exact origin(s) from
  settings with `allow_credentials=True` — never `*`.
- **Authorization** is enforced on the server in FastAPI dependencies (`require_role(...)`) on every
  route. Users can only access their own quotations/profile (check ownership in the query, not after).
  The frontend hiding a button is not security.
- **Input validation**: Pydantic schemas with bounds on every field (dimensions, quantity, string
  lengths). Reject unknown fields (`extra="forbid"`).
- **SQL**: SQLAlchemy only; never build SQL with f-strings or string concatenation.
- **Passwords** (staff only): Argon2id, min 12 chars, check against a common-password list, rate limit
  login (e.g. 5/min per IP+email), lock 15 min after 10 failures.
- **Security headers** middleware: `Content-Security-Policy` (self only), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, HSTS when on HTTPS.
- **Secrets** live in `.env` files that are git-ignored. Commit only `.env.example` with placeholder
  values. Never print secrets in logs, errors, or chat.
- **Errors**: return generic messages to clients; log details server-side. No stack traces in responses.
- **PDF files** are served only through an authorized endpoint (`GET /api/v1/quotations/{id}/pdf`),
  never from a public static folder.
- **Audit**: log logins (success/failure), role changes, price/settings changes, approvals, deletions.
- **Deletion**: super_admin deletes are soft deletes (`is_active=false`, `deleted_at`) unless the owner
  explicitly asks for hard delete; audit rows are never deleted.
- **Dependencies**: pin versions (`uv.lock` / `package-lock.json`); don't add packages without asking.

## 7. Where files go

```
AQS-APP/                     (repo root)
├── CLAUDE.md                this file
├── plan.md.txt              original plan from the owner
├── docs/                    extra docs (API notes, ERD, decisions longer than one line)
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app factory, middleware registration
│   │   ├── core/            config.py (Settings), security.py (hashing, sessions),
│   │   │                    csrf.py, headers.py, deps.py (current_user, require_role), rate_limit.py
│   │   ├── db/              base.py (DeclarativeBase), session.py (async engine/sessionmaker)
│   │   ├── models/          one file per aggregate: user.py, product.py, quotation.py, audit.py ...
│   │   ├── schemas/         Pydantic request/response models, mirrors models/
│   │   ├── api/v1/          routers: auth.py, profile.py, products.py, quotations.py,
│   │   │                    admin.py, super_admin.py, dashboard.py
│   │   └── services/        pricing.py, pdf.py, oauth.py, audit.py, units.py
│   ├── alembic/             migrations (versions/ reviewed by hand, never blindly autogenerated)
│   ├── scripts/             create_db.py, create_super_admin.py, seed_products.py
│   ├── storage/quotes/      generated final PDFs (git-ignored)
│   ├── tests/               mirrors app/ (test_pricing.py, test_auth.py, ...)
│   ├── pyproject.toml
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── main.tsx, router.tsx
    │   ├── index.css        Tailwind import + @theme tokens
    │   ├── api/             client.ts (fetch wrapper: credentials 'include', CSRF header), per-feature calls
    │   ├── features/        auth/, profile/, quotations/, admin/, super-admin/ (pages + feature components)
    │   ├── components/      shared UI (components/ui/ for buttons, inputs, tables, layout)
    │   ├── lib/             zod schemas shared by forms, formatters (currency, units)
    │   └── stores/          Zustand UI-only stores
    ├── public/
    ├── vite.config.ts       includes /api proxy to :8000
    └── .env.example
```

Rules: new backend endpoint → router in `api/v1/`, schema in `schemas/`, logic in `services/`,
test in `tests/`. New page → `frontend/src/features/<feature>/`. Don't create new top-level folders without asking.

## 8. Database setup (local, pgAdmin 4)

- `backend/.env` holds `DATABASE_URL=postgresql+asyncpg://aqs_app:<pw>@localhost:5432/aqs` and, for
  setup only, `POSTGRES_ADMIN_URL` (the postgres superuser you use in pgAdmin).
- `uv run python -m scripts.create_db` creates the `aqs_app` role (least privilege — no superuser) and the `aqs`
  database if missing. Then `alembic upgrade head` creates all tables. Then `create_super_admin.py`
  and `seed_products.py`. The database will then appear in pgAdmin automatically.
- Schema changes **only** through Alembic migrations. Never edit tables by hand in pgAdmin.
- Ask the owner for DB credentials; never guess, hard-code, or commit them.

## 9. How I (Claude) should work

- **Ask when unclear** — especially pricing formulas, product rules, or anything touching money or security.
- Keep it simple: prefer the standard library / pinned stack over new abstractions. No premature microservices,
  queues, or caches.
- Small, reviewable changes. After a change, say what was changed and how to run/test it.
- Money: `Decimal` in Python, `NUMERIC(12,2)` in Postgres, formatted strings in the UI. Never floats.
- Units: accept cm/in at the edge, store integer mm. Show the user's chosen unit on the PDF.
- Write tests for pricing, unit conversion, auth/role checks, and CSRF before calling a feature done.
- Type everything: TS `strict`, Python type hints; Ruff clean; no `any` / `# type: ignore` without a comment why.
- Alembic autogenerate duplicates CHECK constraints for `str_enum` columns — always hand-edit
  migrations to VARCHAR + one named `ck_...` constraint, then run `alembic check`.
- Tests wipe `aqs_test` — never point a dev server at it while running tests.
- The desktop app's browser pane can't show PDFs; check PDFs by rendering them to PNG (pypdfium2).
- Shell is Windows (PowerShell/Git Bash). Give commands that work there.
- Git repo on `main` (no commits yet). Never commit or push unless asked.
- Don't expose secrets, the user's email, or DB passwords in code, logs, or messages.

### Keeping this file current
When a decision changes or we learn something important (new rule, changed stack choice, a gotcha),
**propose an edit to CLAUDE.md, show the exact diff, and wait for approval before saving.**
Add confirmed decisions to the log in §3 with the date. Keep this file under ~300 lines —
move long detail into `docs/` and link it here.

## 10. Common commands (fill in as the project is scaffolded)

Dev servers: `.claude/launch.json` defines `backend` (:8000) and `frontend` (:5173).

```bash
# backend (from backend/)
uv sync
uv run python -m scripts.create_db
uv run alembic upgrade head
uv run python -m scripts.create_super_admin   # first owner account (hidden password prompt)
uv run python -m scripts.reset_staff_password # forgotten staff/owner password (hidden prompt; unlocks + signs out)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest      # uses the `aqs_test` DB (made by create_db); DB tests skip if it's missing
uv run ruff check . && uv run ruff format .

# frontend (from frontend/)
npm install
npm run dev        # http://localhost:5173
npm run build
npm run lint
```

Gotcha: restart the backend after editing `.env` — `--reload` only watches `.py` files.

## 11. Open questions

- Real materials, labour rates and product templates to enter (via the admin UI).
- Confirm: markup applied before VAT; is a minimum charge per quotation needed?
- Business name, logo, address, and terms text for the PDF header/footer.
- Hosting target and domain (affects HTTPS, cookie `Secure` in prod, backups).
- Google OAuth app is in "Testing": add test users now; click "Publish app" before real users.
- Enter real business name, address, contact and terms in Admin → Settings (placeholders now).
- Later: several products per quotation?

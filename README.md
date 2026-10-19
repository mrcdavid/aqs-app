# AQS APP — Automatic Quotation System

A web app that makes quotation PDFs for glass, aluminium and metal fabrication jobs
(sliding windows, sliding doors, window grills, …).

A customer signs in with their `@up.edu.ph` Google account — or staff quote a walk-in client —
adds one or more items (product, glass choice, add-ons such as an open back frame, size in inches
or cm, quantity) and clicks **Process** to get a draft PDF right away. An admin then approves
(optionally adjusting the final amount), rejects or cancels it; approved quotes get an official
number (`AQS-2026-000123`) and a final PDF with the 50/50 payment terms and signature lines.

Prices are always calculated on the server, rounded up in your favour, and are final with VAT
included (clients never see a VAT line, rates or materials). Sliding windows are sold **per sq ft** at
rates you set (per glass type, plus extras such as an open back); grills are priced from the **whole
bars** they use plus labour per grill; materials are entered as you buy them (21-ft bars, kilos,
pieces, feet, sq ft). The dashboard shows your
approved business. Detailed business rules: [docs/quotations.md](docs/quotations.md).

| Part      | Tech                                                           | Folder      |
|-----------|----------------------------------------------------------------|-------------|
| Frontend  | React 19, TypeScript, Vite, Tailwind CSS v4, React Router      | `frontend/` |
| Backend   | Python, FastAPI, SQLAlchemy (async), Alembic, ReportLab        | `backend/`  |
| Database  | PostgreSQL 16+                                                 | local install |

```
Browser ──► Vite dev server :5173 ──(/api)──► FastAPI :8000 ──► PostgreSQL :5432 (db: aqs)
```

Always open the app at **http://localhost:5173**. Vite forwards `/api` calls to FastAPI, so the
browser sees a single site (this is what makes the login cookies and CSRF checks work).

---

## 1. Requirements

Install these once:

| Tool | Version | Notes |
|------|---------|-------|
| [Python](https://www.python.org/downloads/) | 3.12 or newer | |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Python package/project manager — installs the backend's packages |
| [Node.js](https://nodejs.org/) | 22 LTS (20.19+ also works) | includes `npm` |
| [PostgreSQL](https://www.postgresql.org/download/windows/) | 16 or newer | the Windows installer also installs **pgAdmin 4** |
| Google Cloud OAuth client | — | only needed for **customer** sign-in (see step 4) |

Check them in a terminal:

```powershell
python --version
uv --version
node --version
```

All commands below are for **PowerShell** on Windows (they also work in Git Bash unless noted).

---

## 2. First-time setup — backend

Open a terminal in the `backend` folder.

### 2.1 Install Python packages

```powershell
cd backend
uv sync
```

This creates `backend/.venv` and installs the exact versions pinned in `uv.lock`.

### 2.2 Create your `.env` file

```powershell
Copy-Item .env.example .env
```

(Git Bash: `cp .env.example .env`)

Open `backend/.env` and fill it in:

| Variable | What to put |
|----------|-------------|
| `ENVIRONMENT` | `development` for local use |
| `APP_ORIGIN` | `http://localhost:5173` (must match the address in your browser exactly) |
| `DATABASE_URL` | Keep `aqs_app` and `aqs`; replace `CHANGE_ME_APP_PASSWORD` with a **new** password (16+ characters). The setup script creates this database user for you. |
| `POSTGRES_ADMIN_URL` | Replace `CHANGE_ME_POSTGRES_PASSWORD` with the password of the `postgres` user you chose when installing PostgreSQL (the one you use in pgAdmin). Only the setup script uses it. |
| `SECRET_KEY` | A long random string — generate one with the command below |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From Google Cloud (step 4). Can stay empty if you only need staff login for now. |
| `ALLOWED_EMAIL_DOMAIN` | `up.edu.ph` |

Generate a `SECRET_KEY`:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> If your passwords contain special characters such as `@ : / # %`, they must be URL-encoded
> inside the URLs (for example `@` → `%40`). Easiest is to use only letters, digits, `-` and `_`.

`.env` is git-ignored. **Never commit it** and never share it — it holds your passwords.

### 2.3 Create the database

Make sure the PostgreSQL service is running (it starts with Windows by default), then:

```powershell
uv run python -m scripts.create_db
```

This creates:
- the `aqs_app` login role (a normal user, **not** a superuser),
- the `aqs` database (used by the app),
- the `aqs_test` database (used and wiped by the automated tests).

### 2.4 Create the tables

```powershell
uv run alembic upgrade head
```

Alembic runs the migration files in `backend/alembic/versions/` to build every table. Re-run this
command whenever you pull new code that adds a migration.

### 2.5 Create the first owner account (super admin)

There is no public sign-up for staff. Create the first account from the terminal:

```powershell
uv run python -m scripts.create_super_admin
```

You'll be asked for an email and a password (hidden while you type, 12+ characters, not a common
password). After that, the super admin can create other admins from the app.

---

## 3. First-time setup — frontend

Open a second terminal in the `frontend` folder:

```powershell
cd frontend
npm install
```

Optional: `Copy-Item .env.example .env` (it only sets the app name). Frontend `.env` values are
bundled into the public JavaScript, so **never put secrets there**.

---

## 4. Google sign-in for customers (optional for staff-only testing)

Customers can only sign in with Google. Without these settings the "Sign in with Google" button
returns *"Google sign-in not configured"*; staff login still works.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create or choose a project.
2. **APIs & Services → OAuth consent screen**: user type **External**, fill in the app name and
   your email. While the app is in **Testing**, add each tester's `@up.edu.ph` email under
   **Test users** (others will be blocked by Google).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URI (exactly):
     `http://localhost:5173/api/v1/auth/google/callback`
4. Copy the **Client ID** and **Client secret** into `backend/.env`.
5. Restart the backend.

Only `@up.edu.ph` accounts with a verified email are accepted — this is checked on the server.

---

## 5. Running the app (every day)

You need **two terminals** and PostgreSQL running.

**Terminal 1 — backend** (from `backend/`):

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from `frontend/`):

```powershell
npm run dev
```

Then open **http://localhost:5173**.

| Page | Who |
|------|-----|
| http://localhost:5173/login | Customers (Google sign-in) |
| http://localhost:5173/staff/login | Admins and super admins (email + password) |
| http://localhost:5173/admin | Admin area (dashboard, quotations, catalogue, users, audit log) |
| http://localhost:5173/app | Customer area (profile, quotations) |

To stop a server, press `Ctrl + C` in its terminal.

> **Using the Claude desktop app?** `.claude/launch.json` defines `backend` and `frontend`, so
> both servers can be started from the app's preview panel instead.

### First things to do after signing in as super admin

The database starts empty (except default settings: markup 0 %, VAT 12 % included in prices, PHP,
round up to the next ₱100, owner name "Cleo David"). Before anyone can get quotes, set up the admin
area:

1. **Settings** — business name, address, contact, terms (printed on PDFs), owner name (signature
   line), markup (for products priced from materials), VAT (shown to staff as "included"), quote
   validity, and **Round totals up to the next** (100 turns 21,423 into 21,500; 0 = off).
2. **Materials** — at the price you buy them: per **bar** (give the bar length, e.g. aluminium
   profile *21 ft*, 10 mm square bar *6 m*; quotes always count whole bars), per **kilo** (jamb rubber,
   vinyl #1), per **piece** (handles, rollers), per **foot** or per **sq ft** (glass).
3. **Labour rates** — per piece (e.g. per grill), per foot or per sq ft.
4. **Products** — for each product set the allowed sizes and **how it is priced**:
   - **Per sq ft** (sliding windows): set a base rate per sq ft. Add a choice group *Glass type*
     (e.g. *1/4 Bronze* first, *Reflective mirror*, *Smoked*), each with its **rate per sq ft**, and a
     group *Glass sheet* (*4 x 7 ft* first, *4 x 8 ft*, *4 x 6 ft*, rate 0 — just recorded). Add an
     add-on *Open back* with its extra rate per sq ft. The material lines you add are a **cost guide**:
     the price preview shows your cost and margin.
   - **From materials** (grills): make the 10 mm square bar a **per bar** material (e.g. ₱300, bar
     length 6 m). Add it as a line measured by **Area** and use **Work it out from a sample grill**
     in the line dialog: "3.5 bars for a 48 × 48 in grill" sets the factor (0.2187 bars per sq ft);
     other sizes scale by area, rounded up to whole bars. Add the labour per grill as a line (per
     piece, Fixed, factor 1). Price per grill = whole bars × price per bar + labour, + markup.
   - Each line = a material or labour rate × how it's measured (area, perimeter, width, height or a
     fixed count) × factor × waste %. **Add-ons** for a frame around the window (open back) can make
     the rest measured smaller (in mm): the size typed is then the wall opening.
   - Use the **Price preview** (inches by default) to try sizes, choices and add-ons.
5. **Users → Add staff account** — create admin accounts (only the super admin can).

When material prices go up, update them under **Materials** (grills follow automatically) and use
**Settings → Raise all rates** to raise every rate per sq ft by a percentage (with a Yes/No check).

Then sign in as a customer, complete the profile, and create a quotation.

---

## 6. Using the app

| Task | Where | Notes |
|------|-------|-------|
| Request a quotation | Customer: **New quotation** | Add items with **Add another item** (up to 20): product, choice, add-ons, size, quantity. **Process** gives a draft PDF. |
| Quote a walk-in client | Admin: **Quotations → New quotation** | Type the client's name, PH mobile, optional email and address, then the items. |
| Review | Admin: open a pending quotation | **Approve** (you can change the final amount — it shows as an adjustment), **Reject** (reason required) or **Cancel**. Each asks *Yes / No* first. |
| Print | Customer: **View / print PDF** · Staff: **Draft PDF** / **Official PDF** | Drafts are watermarked *ESTIMATE · PENDING APPROVAL*; approved ones carry the quote number. |
| Delete | Super admin: open any quotation → **Delete** | Hidden from every list, the customer and the dashboard; kept in the database and the audit log. |
| Dashboard | Admin: **Dashboard** | Approved quotations only (value, average, per day, by province and product, largest projects); plus approval rate and the review queue. |
| Audit log | Admin: **Audit log** | Who did what and when (logins, price changes, approvals, deletions…). |

Required fields are marked with a red `*`. Mobile numbers must be Philippine mobile numbers
(`0917 123 4567` or `+63 917 123 4567`).

---

## 7. Tests and code checks

**Backend** (from `backend/`):

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

- Tests use the `aqs_test` database and **wipe it on every run**. Never point the dev server at
  `aqs_test`.
- If `aqs_test` doesn't exist, database tests are skipped — run `uv run python -m scripts.create_db`.

**Frontend** (from `frontend/`):

```powershell
npm run lint
npm run build
```

`npm run build` also type-checks the whole frontend and writes the production files to
`frontend/dist/`.

---

## 8. Common tasks

### Forgot a staff/owner password

Passwords are stored as one-way hashes, so they can't be recovered — only replaced:

```powershell
uv run python -m scripts.reset_staff_password
```

This sets a new password, unlocks the account and signs it out everywhere. It only works for
staff accounts (customers use Google).

### Add an admin account

Sign in as the super admin → **Users → Add staff account** → choose **Admin**, set a password
(12+ characters, not a common password, not containing the email name). If you keep a private
list of staff logins, `staff-accounts.txt` in the project folder is git-ignored (it is never
pushed to GitHub — but it is synced by OneDrive, so a password manager is safer).

### Changing the database structure

Never edit tables by hand in pgAdmin. Change the models in `backend/app/models/`, then
(from `backend/`):

```powershell
uv run alembic revision --autogenerate -m "short description"
```

Review and hand-edit the new file in `alembic/versions/` (autogenerate isn't always right), then:

```powershell
uv run alembic upgrade head
uv run alembic check
```

### Where things are stored

| What | Where |
|------|-------|
| All app data | PostgreSQL database `aqs` (browse it in pgAdmin 4) |
| Final (approved) quotation PDFs | `backend/storage/quotes/` — git-ignored, served only through the logged-in API |
| Draft PDFs | Not stored; generated on request from the saved price snapshots |
| Deleted quotations | Still in the `quotations` table (`deleted_at` set) and in the audit log |
| Business rules (pricing, options, items, dashboard) | [docs/quotations.md](docs/quotations.md) |

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| Changed `.env` but nothing happened | Restart the backend — `--reload` only watches `.py` files. |
| `Port 5173 is already in use` | Another Vite server is running. Close it (the port is fixed on purpose so the Google redirect URI keeps working). |
| `403` / "CSRF" errors when saving | Open the app at exactly `http://localhost:5173` (not `127.0.0.1`, not `:8000`) — it must match `APP_ORIGIN`. |
| Google says `redirect_uri_mismatch` | The redirect URI in Google Cloud must be exactly `http://localhost:5173/api/v1/auth/google/callback`. |
| Google says access is blocked / app not verified | The consent screen is in **Testing** — add the account under **Test users**. |
| "Google sign-in not configured" | `GOOGLE_CLIENT_ID` is empty in `backend/.env`; fill it in and restart. |
| `create_db` says "Set a real password (16+ chars)" | Replace `CHANGE_ME_APP_PASSWORD` in `DATABASE_URL` with a real 16+ character password. |
| `connection refused` / can't reach the database | Start PostgreSQL: Windows **Services** → `postgresql-x64-16` (or your version) → Start. |
| `password authentication failed for user "postgres"` | Wrong password in `POSTGRES_ADMIN_URL` — use the one you log into pgAdmin with. |
| `relation "..." does not exist` | Tables are missing or outdated — run `uv run alembic upgrade head`. |
| Staff account locked | 10 failed logins lock it for 15 minutes. Wait, or run `scripts.reset_staff_password`. |
| Signed out of the admin area | Staff sessions end after 30 minutes without activity (customers: 8 hours). Sign in again. |
| A product is missing from the quotation form | Sold per sq ft but no rate is set anywhere (product or its options); priced from materials but has no lines at all; uses an archived material; or every choice of one of its groups uses an archived material. Check it under **Products**. |
| An add-on or choice doesn't change the price | Per sq ft: give it a rate per sq ft. From materials: add its material/labour lines (the price preview marks it "adds nothing yet"). |
| "Item 2: width must be …" | That item's size is outside the product's allowed range (set on the product). |
| "Choose one option for Glass type" | Pick one choice in each group (the form pre-selects the first). |
| "The size is too small for the chosen options" | The opening minus the open back's reduction leaves no window — check the size or the add-on's mm. |
| The dashboard shows fewer quotations than the list | It counts approved quotations only (pending, rejected, cancelled and deleted ones are left out). |
| A quotation disappeared | A super admin deleted it; see **Audit log** (filter "quotation"). |

---

## 10. Production

Hosting hasn't been decided yet. When it is, the app must run behind **HTTPS** with one reverse
proxy (e.g. Nginx or Caddy) that serves the built frontend (`frontend/dist/`) and forwards `/api`
to FastAPI, so it stays a single site. Setting `ENVIRONMENT=production` turns on secure cookies
(`__Host-aqs_session`) and HSTS, and turns off the API docs. Update `APP_ORIGIN` and the Google
redirect URI to the real domain.

---

More detail for developers: architecture, security rules and the decisions log in
[CLAUDE.md](CLAUDE.md); pricing, options, items, statuses, PDF and dashboard rules in
[docs/quotations.md](docs/quotations.md).

# AQS APP — Automatic Quotation System

A web app that makes quotation PDFs for glass, aluminium and metal fabrication jobs
(sliding windows, sliding doors, window grills, …).

A customer signs in with their `@up.edu.ph` Google account, picks a product, enters the size
(cm or inches) and clicks **Process** to get a draft PDF right away. An admin then approves or
rejects it; approved quotes get an official number (`AQS-2026-000123`) and a final PDF.

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

The database starts empty (except default pricing settings: markup 0 %, VAT 12 %, PHP).
Before customers can get quotes, set up the catalogue in the admin area:

1. **Settings** — business name, address, contact details, terms, markup, VAT, quote validity.
2. **Materials** — e.g. aluminium frame, glass panel, with prices and units.
3. **Labour rates** — e.g. installation per metre.
4. **Products** — build each product template from materials and labour rates, with min/max sizes.

Then sign in as a customer, complete the profile, and create a quotation.

---

## 6. Tests and code checks

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

## 7. Common tasks

### Forgot a staff/owner password

Passwords are stored as one-way hashes, so they can't be recovered — only replaced:

```powershell
uv run python -m scripts.reset_staff_password
```

This sets a new password, unlocks the account and signs it out everywhere. It only works for
staff accounts (customers use Google).

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
| Draft PDFs | Not stored; generated on request from the saved price snapshot |

---

## 8. Troubleshooting

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

---

## 9. Production

Hosting hasn't been decided yet. When it is, the app must run behind **HTTPS** with one reverse
proxy (e.g. Nginx or Caddy) that serves the built frontend (`frontend/dist/`) and forwards `/api`
to FastAPI, so it stays a single site. Setting `ENVIRONMENT=production` turns on secure cookies
(`__Host-aqs_session`) and HSTS, and turns off the API docs. Update `APP_ORIGIN` and the Google
redirect URI to the real domain.

---

More detail for developers (architecture, security rules, decisions log): see [CLAUDE.md](CLAUDE.md).

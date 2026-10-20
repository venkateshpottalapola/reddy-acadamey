# REDDY ACADEMY — parent enquiries and private admin

The existing public-site design is retained. The project now includes a FastAPI backend, a PostgreSQL/Supabase data layer, private administrator login/dashboard, and a parent-enquiry form that posts to the backend.

## Current feature and data status

- The website did **not** previously have a Python backend or database integration in this workspace. This project now includes the backend and an Alembic schema.
- Enquiries and multiple associated student records are saved transactionally, assigned a unique `RA-YYYYMMDD-XXXXXXXX` reference, and begin in `New` status.
- The form calculates an estimated monthly fee automatically based on grade, tuition type, classes per week, and session duration. Fees are capped at ?15,000 per student. If a combination is not yet configured, the estimate shows as unavailable and the parent is prompted to submit for manual review. The backend validates all pricing on the API side; no fee is fabricated.
- Admin statistics, filters, pagination, details, status changes, private notes, deletion, and CSV export read/write database records, not sample data.
- The Supabase connection has **not** been verified until you configure `backend/.env`, run the migration, and receive `{"status":"ok","database":"connected"}` from `/api/health`.
- The form and dashboard are served by FastAPI on one origin. Do not use Python's static `http.server` for the integrated site; it cannot serve the API or admin routes.

## Windows / VS Code setup

### 1. Open the project

Open the `reddy-academy` folder in VS Code. Use **Terminal → New Terminal**, then run commands below from that folder.

### 2. Create and activate a virtual environment

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks local activation, for this terminal only run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### 4. Configure Supabase without sharing secrets

1. In Supabase, open **Project Settings → Database** and copy the PostgreSQL connection URI. Use the database password for this backend connection, not the anon/public or service-role API key.
2. Copy the example environment file:

   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

3. Open `backend/.env` in VS Code and replace the `DATABASE_URL` placeholder with your Supabase PostgreSQL URI. Preserve the `postgresql+psycopg://` driver prefix. URL-encode special characters in the password if required by the URI.
4. Replace `SECRET_KEY` with a new random value. To generate one locally:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

5. Keep `ENVIRONMENT=development`, `SESSION_COOKIE_SECURE=false`, and `FRONTEND_ORIGIN=http://localhost:5500` for local use. Never paste the database URI or generated key into chat or commit `backend/.env`.
6. Use the Supabase direct database connection for local migrations where available. If your project requires a pooler URI, follow its connection mode/port instructions.

### 5. Create the database schema

```powershell
Push-Location backend
alembic upgrade head
Pop-Location
```

This adds the `admins`, `admin_sessions`, `enquiries`, `students`, and `enquiry_notes` tables and indexes. It does not delete existing data. This workspace had no previous backend/schema to reuse; check for conflicting table names in Supabase before applying the migration if another application already created them.

### 6. Create the first admin securely

```powershell
Push-Location backend
python -m app.cli create-admin --email admin@example.com
Pop-Location
```

Enter and confirm a password of at least 12 characters at the prompts. The password is hashed with Argon2id; it is not an argument and is not printed. There is no public registration page. Create other authorized administrators through a secure database/admin process; do not insert plaintext passwords.

### 7. Start the integrated website and API

From the project folder:

The Stage 1 static preview may already be using port 5500. Stop that static server with `Ctrl+C` in its terminal first. Then start the integrated server:

```powershell
Push-Location backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5500
```

Open these URLs:

- Public website: <http://localhost:5500/>
- Admin login: <http://localhost:5500/admin/login>
- Admin dashboard: <http://localhost:5500/admin/dashboard>
- Database health: <http://localhost:5500/api/health>

Stop the server with `Ctrl+C`. The FastAPI server serves both the unchanged website assets and the API on the same origin.

### 8. Submit and inspect an enquiry

Complete all required form steps, include class/board details for each student, consent to the privacy notice, review, and submit. The form shows the reference only after FastAPI confirms the database commit. A database or validation failure is shown as an error, not success.

Sign in at `/admin/login`; the dashboard fetches actual records and refreshes periodically. Open **View details** to see each student's saved information. Status changes and private notes require an authenticated admin session and CSRF token. New enquiries are visible after refresh (and normally appear within the dashboard's 60-second refresh interval).

## Security and deployment notes

- Admin passwords use Argon2id. Session tokens are random, stored hashed in PostgreSQL, and delivered in `HttpOnly`, `SameSite=Strict` cookies. Mutating admin endpoints require a CSRF token.
- Login attempts are throttled per client address in this single-process development server. Production deployment with multiple workers should use shared rate-limit storage at the proxy or application layer.
- Set `ENVIRONMENT=production`, `SESSION_COOKIE_SECURE=true`, a strong `SECRET_KEY`, and the actual same-origin URL behind HTTPS in production. Do not expose the PostgreSQL URI to frontend code.
- Deploy backend and frontend on the same HTTPS origin where practical. Back up Supabase and review retention/privacy practices before accepting live enquiries.
- CSV export prefixes spreadsheet-formula-leading cell values to reduce formula injection risk.

## Automated tests

The API tests use an isolated in-memory SQLite database; they do not access or alter Supabase data:

```powershell
Push-Location backend
python -m pytest -q
Pop-Location
```

They cover multi-student enquiry persistence and retrieval, idempotent submission, validation, admin authorization, CSRF-protected status changes, notes, CSV escaping, and logout. A separate live Supabase end-to-end check must be performed after configuring your own project credentials.

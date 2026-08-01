# ApplyPilot

ApplyPilot is an AI-assisted job application review workspace. It searches for jobs, stores the enriched opportunities in Supabase, scores each job against your CV, and prepares application artifacts for human review.

ApplyPilot never submits applications automatically. The dashboard is the final review step before you copy, edit, and submit anything yourself.

## What is included

- FastAPI backend with health checks, job review endpoints, status transitions, and AI generation hooks.
- Static frontend dashboard for filtering jobs, reviewing generated artifacts, and updating pipeline status.
- Twice-daily discovery scheduler with run locking and retries.
- Supabase SQL schema and helper functions.
- Docker Compose setup for VPS and local runs.
- **VPS production deploy** target: Hostinger Docker Compose (`docs/vps-deployment.md`).
- Cursor Cloud environment config (`.cursor/environment.json`) and automation runbook.
- User guide in `docs/user-guide.md`.

## Quick start

1. Create a Supabase project.
2. Run `db/schema.sql`, then `db/schema_functions.sql` in the Supabase SQL editor.
3. Copy `config/.env.example` to `config/.env` and fill in the required keys. Use either `SUPABASE_SERVICE_KEY` for Supabase REST access or `DATABASE_URL` for direct Postgres access through the Supabase pooler.
4. Start the app:

```bash
docker compose up --build -d
```

5. Open `http://localhost:8765` and complete onboarding.
6. Save preferences in the dashboard so twice-daily discovery can run.

## Twice-daily scheduling

Default schedule: **08:00 and 20:00 Europe/London**.

```env
SCHEDULER_ENABLED=true
DISCOVERY_SCHEDULE_MODE=twice_daily
DISCOVERY_TIMES=08:00,20:00
DISCOVERY_TIMEZONE=Europe/London
```

Manual trigger:

```bash
curl -X POST http://127.0.0.1:8000/api/pipeline/run
```

Full automation setup (VPS, Cursor Automations, GitHub Actions backup): see `docs/twice-daily-automation.md`.

## Local backend development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend
```

## Testing

```bash
pytest backend/tests
python -m compileall backend/app
```

The backend tests use FastAPI dependency overrides and do not require Supabase or AI credentials.

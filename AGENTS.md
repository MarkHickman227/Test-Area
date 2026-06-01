# AGENTS.md

## Cursor Cloud specific instructions

This is a **LinkedIn Post Scheduler** built with FastAPI, SQLAlchemy, Celery, and Redis.

### Running the app

```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger docs: `http://localhost:8000/docs`
- The app loads config from `.env` via `pydantic-settings` (see `app/core/config.py`).

### Linting & Testing

```bash
flake8 app/ --max-line-length 100
pytest
```

### Key notes

- The database connection (Supabase PostgreSQL) is **not reachable** from Cloud Agent VMs due to network restrictions. The app handles this gracefully and starts without a DB.
- Celery requires Redis. Redis is not pre-installed in the Cloud Agent VM — Celery task scheduling will not work without it.
- LinkedIn OAuth requires a valid redirect URI matching the LinkedIn Developer Portal app config. The current `.env` redirect URI points to an n8n OAuth callback.

# AGENTS.md

## Cursor Cloud specific instructions

This is a **standalone LinkedIn scheduling agent** built with FastAPI,
SQLAlchemy, Celery, and Redis.

### Running the app

```bash
. .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger docs: `http://localhost:8000/docs`
- The app loads config from `.env` via `pydantic-settings` (see `app/core/config.py`).
- Docker deployment: `docker compose up --build -d`
- Celery worker: `celery -A app.core.celery_app.celery_app worker --loglevel=INFO`

### Linting & Testing

```bash
pytest
python -m compileall app
```

### Key notes

- Default standalone storage is SQLite at `./data/linkedin_agent.db`.
- Celery scheduling requires Redis. Docker Compose provides Redis for deployment.
- LinkedIn OAuth requires a redirect URI matching the LinkedIn Developer Portal config.
- The browser receives an HTTP-only session cookie, not LinkedIn access tokens.

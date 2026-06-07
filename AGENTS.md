# AGENTS.md

## Cursor Cloud specific instructions

ApplyPilot is a FastAPI (Python 3.12) backend + vanilla JS frontend for AI-powered job application review. See `docs/user-guide.md` for product context.

### Running services

| Service | Command | Port |
|---------|---------|------|
| Backend | `source .venv/bin/activate && PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend` | 8000 |
| Frontend | Nginx on port 8080 proxies `/api/` to backend and serves `frontend/` static files |

**Important:** Run `uvicorn` from the repository root (`/workspace`), not from `backend/`. The pydantic-settings config reads `config/.env` relative to CWD. Running from `backend/` means the env file is not found and all settings fall back to defaults.

### Tests

```
source .venv/bin/activate && cd backend && python -m pytest tests/ -v
```

Tests use dependency-injected fakes (`FakeRepository`, `FakeWriter`) and require no external services.

### Lint

No linter is currently configured in the repo. Use `flake8` or `ruff` against `backend/` if needed.

### Config

- Copy `config/.env.example` to `config/.env` and fill in secrets.
- The app starts without Supabase/Anthropic/Perplexity configured — `/api/health` reports which services are available.
- Endpoints that need Supabase return HTTP 503 when it is not configured; this is expected in local dev without secrets.
- Set `SCHEDULER_ENABLED=false` in dev to avoid discovery scheduler background noise.

### Gotchas

- `config/.env` path is resolved relative to the process CWD, not relative to the Python package. Always launch uvicorn from `/workspace`.
- The frontend JS calls `/api/*` on the same origin, so a reverse proxy (Nginx) is needed for end-to-end dev. A standalone `python3 -m http.server` in `frontend/` will not proxy API calls.
- No database driver is used; all persistence goes through Supabase's REST API over HTTP (`httpx`).

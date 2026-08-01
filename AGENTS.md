# AGENTS.md

## Cursor Cloud specific instructions

ApplyPilot is a FastAPI (Python 3.12) backend + vanilla JS frontend for AI-powered job application review.

- Product: `docs/user-guide.md`
- Schedule: `docs/twice-daily-automation.md`
- **Production deploy (VPS):** `docs/vps-deployment.md`
- Optional AWS sketch only: `docs/aws-deployment.md`

**Production target is the Hostinger VPS** (`168.231.114.133:8765`). AWS is not the default.

### Running services

| Service | Command | Port |
|---------|---------|------|
| ApplyPilot | `source .venv/bin/activate && PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend` | 8000 |

**Important:** Run `uvicorn` from the repository root (`/workspace`), not from `backend/`. The pydantic-settings config reads `config/.env` relative to CWD.

### Twice-daily automation runbook

When this agent is started by the twice-daily automation:

1. Confirm `/api/health` reports `ready_for_discovery: true`.
2. Confirm preferences exist via `GET /api/preferences`.
3. Trigger exactly one pipeline cycle: `POST /api/pipeline/run`.
4. If `PIPELINE_TRIGGER_TOKEN` is set, send `Authorization: Bearer <token>`.
5. Verify the response `status` is `ok` or a clear intentional `skipped` reason.
6. Do **not** open a PR unless code changes were required to unblock the run.
7. Never submit job applications. ApplyPilot is review-only.

### Required secrets (Cloud Agents dashboard + VPS `config/.env`)

| Secret | Purpose |
|--------|---------|
| `SUPABASE_URL` | Job store |
| `SUPABASE_SERVICE_KEY` or `DATABASE_URL` | Persistence |
| `ANTHROPIC_API_KEY` | Scoring + artifacts |
| `PERPLEXITY_API_KEY` | Job discovery |
| `PIPELINE_TRIGGER_TOKEN` | Optional auth for `/api/pipeline/run` |
| `VPS_SSH_PASSWORD` or SSH key | Deploy/monitor on `root@168.231.114.133` |

### Closed-loop skills

1. `spec-to-implementation` / `tasks-plan` / `tasks-build` — design board
2. Core coding + `pytest` — build/test
3. `tasks-explain-diff` / Bugbot / security-review — review
4. VPS Docker Compose + Portainer — deploy/ops (`docs/vps-deployment.md`)
5. `/api/health` + `/api/scheduler/status` — monitor
6. Never submit applications; human review only

### Tests

```
source .venv/bin/activate && cd backend && python -m pytest tests/ -v
```

### Scheduler defaults

- Mode: `twice_daily`
- Times: `08:00,20:00`
- Timezone: `Europe/London`
- Overlap protection: concurrent runs are rejected
- Transient failures: up to 3 attempts with backoff

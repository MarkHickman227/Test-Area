# ApplyPilot closed-loop status

**Production target:** Hostinger VPS (`168.231.114.133:8765`) — see `docs/vps-deployment.md`.

Reviewed: 2026-07-31

## Process map (run where possible)

| Phase | Status | Notes |
|-------|--------|-------|
| Design → build | Done on branch | Pipeline + twice-daily scheduler + GUI |
| Unit/API tests | **Pass** | `35 passed` |
| Code review | **Done** | Bugbot: fixed missing Postgres pipeline methods |
| Manual GUI (local) | Partial | Local `:8000` serves UI with seed data |
| Deploy to VPS | **Blocked** | No SSH credentials for `root@168.231.114.133` |
| Live discovery | **Blocked** | Secrets missing; `ready_for_discovery: false` |
| Twice-daily clock | Configured in code | Not firing live until VPS + secrets + preferences |
| Monitor | Blocked on VPS | Portainer up (`:9000`); ApplyPilot `:8765` down |

## Blockers (access, not skills)

1. **VPS SSH** — password or key for `root@168.231.114.133`
2. **Secrets** — `SUPABASE_*` / `DATABASE_URL`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`
3. **Preferences saved** on the live instance after deploy
4. **Merge PR** so `main` has the scheduler + deploy docs

## Next actions after access is granted

1. SSH → `/root/applypilot` → update `config/.env` → `docker compose up --build -d`
2. Open `http://168.231.114.133:8765` → save preferences → upload CV
3. `curl /api/health` until `ready_for_discovery: true`
4. Trigger once: `POST /api/pipeline/run`
5. Confirm scheduler status shows next run 08:00 / 20:00 Europe/London
6. Watch Portainer + health for ongoing monitor

# ApplyPilot closed-loop status

**Production target:** Hostinger VPS (`168.231.114.133:8765`) — see `docs/vps-deployment.md`.

Updated: 2026-07-31

## Process map

| Phase | Status | Notes |
|-------|--------|-------|
| Design → build | Done on branch | Pipeline + twice-daily scheduler + GUI |
| Unit/API tests | **Pass** | `35 passed` |
| Code review | **Done** | Postgres pipeline methods fixed on branch |
| Deploy to VPS | **Live** | Backend rebuilt from branch; **old GUI** kept on `:8765` |
| Database | **Local Postgres** | Compose `db` service (Supabase tenant was dead) |
| Live discovery | **Ready** | Preferences seeded; scheduler next run 20:00 London |
| Twice-daily clock | **Armed** | `08:00` / `20:00` `Europe/London` |
| Monitor | Portainer + health | Backend / frontend / db up |

## Live now

- UI: `http://168.231.114.133:8765/` — original ApplyPilot dashboard (filters + jobs + detail)
- Health: `data_store=postgres`, Anthropic + Perplexity configured, `ready_for_discovery=true`
- Scheduler: `twice_daily`, next run at `20:00` Europe/London
- Jobs / preferences APIs: **200**

## What changed on the VPS

1. SSH with Hostinger root credentials restored the stopped stack
2. Dead Supabase pooler (`postgres.gpljgcqxuryxmcxwklzm`) replaced with **local Postgres 16** in Compose
3. Backend image rebuilt from this branch (twice-daily scheduler + Postgres repository)
4. Default search preferences saved via API (old UI has no preferences form)

Optional later: restore a healthy Supabase project and switch `DATABASE_URL` back if you want hosted Postgres.

## Security

Root password was shared in chat — **rotate it in Hostinger hPanel** after this session. Do not commit passwords to the repo.

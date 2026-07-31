# ApplyPilot closed-loop status

**Production target:** Hostinger VPS (`168.231.114.133:8765`) — see `docs/vps-deployment.md`.

Updated: 2026-07-31

## Process map

| Phase | Status | Notes |
|-------|--------|-------|
| Design → build | Done on branch | Pipeline + twice-daily scheduler + GUI |
| Unit/API tests | **Pass** | `35 passed` |
| Code review | **Done** | Postgres pipeline methods fixed on branch |
| Deploy to VPS | **Partial** | Stack restarted; **old GUI live** on `:8765` |
| Live discovery | **Blocked** | Supabase DB tenant not found |
| Twice-daily clock | Env updated | Needs working DB + preferences |
| Monitor | Portainer + health | Backend/frontend up |

## Live now

- UI: `http://168.231.114.133:8765/` — original ApplyPilot dashboard (filters + jobs + detail)
- Health: `200` — Anthropic + Perplexity configured; DB connect fails at runtime
- Backend was stopped ~5 weeks; frontend crash-loop fixed by bringing backend back on the Compose network

## Remaining blocker

Supabase pooler error:

`FATAL: (ENOTFOUND) tenant/user postgres.gpljgcqxuryxmcxwklzm not found`

Also `SUPABASE_URL` on the VPS is still the placeholder `your-project.supabase.co`.

Fix in Supabase dashboard (unpause/recreate project or correct pooler URI), update `/root/applypilot/config/.env`, then:

```bash
cd /root/applypilot && docker compose up -d --force-recreate backend
```

Confirm `/api/jobs` returns `200`, save preferences, then discovery can run.

## Security

Root password was shared in chat — **rotate it in Hostinger hPanel** after this session.

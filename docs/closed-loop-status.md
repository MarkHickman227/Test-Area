# ApplyPilot closed-loop status

**Production target:** Hostinger VPS (`168.231.114.133:8765`) — see `docs/vps-deployment.md`.

Updated: 2026-07-31

## Process map

| Phase | Status | Notes |
|-------|--------|-------|
| Design → build | Done on branch | Pipeline + twice-daily scheduler + GUI |
| Unit/API tests | **Pass** | `35 passed` |
| Code review | **Done** | Postgres pipeline methods + salary parse fix |
| Deploy to VPS | **Live** | Backend rebuilt from branch; **old GUI** kept on `:8765` |
| Database | **Local Postgres** | Compose `db` service (Supabase tenant was dead) |
| Discovery | **Working** | Manual run found **8 jobs** |
| Enrich / score | **Blocked** | Anthropic: credit balance too low |
| Twice-daily clock | **Armed** | Next run `20:00` Europe/London |
| Monitor | Portainer + health | Backend / frontend / db up |

## Live now

- UI: `http://168.231.114.133:8765/` — original ApplyPilot dashboard
- Health: `data_store=postgres`, Perplexity ok, Anthropic key present but **out of credits**
- Scheduler: `twice_daily` 08:00 / 20:00 London — last run ok (discover only)
- Jobs API: **200** with discovered listings (score null until Anthropic is funded)

## Action for Mark

1. Add Anthropic credits (Plans & Billing) so enrich/score/generate resume
2. Optionally upload a CV (old UI has no CV form — use `POST /api/cvs` or restore CV UI)
3. **Rotate the Hostinger root password** shared in chat

## Security

Do not commit passwords to the repo.

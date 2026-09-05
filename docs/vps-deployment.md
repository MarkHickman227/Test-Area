# ApplyPilot VPS deployment (production)

**Primary production target: Hostinger VPS** (`168.231.114.133`, hostname `srv832290`).

AWS (`docs/aws-deployment.md`) is optional/future only.

## Architecture on the VPS

| Piece | How |
|-------|-----|
| App | Docker Compose (`db` + `backend` + `frontend`) under `/root/applypilot` |
| UI | Frontend on **8765** (nginx → backend `:8000`) — keep the original dashboard |
| Data | **Local Postgres** named volume `applypilot_pgdata` (never `docker compose down -v`) |
| Schedule | In-app `twice_daily` at 08:00 / 20:00 `Europe/London` |
| Ops UI | Portainer at `http://168.231.114.133:9000/` |
| DB backups | Daily cron → `scripts/backup-db.sh` → `/root/applypilot/backups/` (see `docs/data-safety.md`) |
| Pipeline backup clock | Host cron → `POST /api/pipeline/run` (only if in-app scheduler disabled) |

## Closed-loop process

1. **Design → build** — tasks from user guide / Notion (`spec-to-implementation` → `tasks-plan` → `tasks-build`)
2. **Test** — `pytest backend/tests` until green
3. **Review** — PR review / Bugbot / security-review; manual GUI check
4. **Deploy** — SSH + `docker compose up --build -d` on the VPS
5. **Verify** — `/api/health`, `/api/scheduler/status`, preferences saved, `ready_for_discovery: true`
6. **Monitor** — Portainer + health/scheduler endpoints; optional Telegram alerts

## Deploy commands (on VPS as root)

**Safe redeploy** (keeps jobs/preferences — does **not** delete the Postgres volume):

```bash
cd /root/applypilot
./scripts/backup-db.sh          # snapshot before changes
docker compose up -d --build    # never add -v
docker compose ps
curl -s http://127.0.0.1:8000/api/health   # expect repair_version: cv-apply-1
curl -s http://127.0.0.1:8000/api/scheduler/status
```

## One-line repair pull (Hostinger console)

This script must run **on the VPS**, as **root**, in **bash**. It will not work from a Windows PC.

In Windows PowerShell, `curl` is `Invoke-WebRequest`, so `curl -fsSL ... | bash` fails with `A parameter cannot be found that matches parameter name 'fsSL'`.

**Correct place:** Hostinger hPanel → VPS → Browser terminal → log in as `root`, then paste:

```bash
curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash
```

If you already have SSH from Windows, this PowerShell line is the remote equivalent (it still runs on the VPS):

```powershell
ssh root@168.231.114.133 "curl -fsSL https://raw.githubusercontent.com/MarkHickman227/Test-Area/cursor/rescore-full-cv-53b6/scripts/vps-pull-repair.sh | bash"
```

That keeps `config/.env` and the Postgres volume. It does **not** run `docker compose down -v`.


```bash
curl -s -X POST http://127.0.0.1:8000/api/cvs/reparse
curl -s -X POST http://127.0.0.1:8000/api/pipeline/backfill
# Repeat backfill until analytics.score_ge_60 and draft_ready move off zero.
# Never add -v to compose down; that wipes jobs.
```

First-time / env setup only:

```bash
cd /root/applypilot
cp -n config/.env.example config/.env
nano config/.env      # fill real secrets — never commit this file
docker compose up --build -d
ufw allow 8765/tcp
ufw allow 8000/tcp
```

**Never run** `docker compose down -v` or `docker volume rm applypilot_applypilot_pgdata` unless you intend to wipe data (restore from `docs/data-safety.md` afterward).

Public URL: `http://168.231.114.133:8765`

## Required secrets in `config/.env`

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` (or local Compose `db`) | Persistence — VPS uses local Postgres by default |
| `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | Optional hosted Supabase instead of local `db` |
| `ANTHROPIC_API_KEY` | Scoring + artifacts |
| `PERPLEXITY_API_KEY` | Discovery |
| `PIPELINE_TRIGGER_TOKEN` | Optional auth for `/api/pipeline/run` |
| `SCHEDULER_ENABLED=true` | Twice-daily loop |
| `DISCOVERY_SCHEDULE_MODE=twice_daily` | Fixed times |
| `DISCOVERY_TIMES=08:00,20:00` | London wall clock |
| `DISCOVERY_TIMEZONE=Europe/London` | Timezone |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `APPLY_FROM_EMAIL` | Send applications by email |
| `UNIPILE_*` | Optional LinkedIn/email send via Unipile |

## SMTP on the VPS (Gmail)

ApplyPilot does not run its own mail server. It logs into **your** mailbox and sends from there.

**Gmail (simplest if you apply from that address):**

1. Google Account → Security → 2-Step Verification (must be on).
2. Security → App passwords → create one named `ApplyPilot`.
3. Copy the 16-character password. Do not use your normal Gmail password.

On the VPS as root (Hostinger bash console, not Windows PowerShell):

```bash
cd /root/applypilot
nano config/.env
```

Set:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
APPLY_FROM_EMAIL=you@gmail.com
```

Remove spaces from the app password if the send fails. Then recreate **only** the backend (never `docker compose down -v`):

```bash
cd /root/applypilot
docker compose up -d --force-recreate backend
curl -sS http://127.0.0.1:8000/api/health
```

Expect `"smtp_configured": true` and `"can_send_applications": true`.

**Hostinger mailbox instead of Gmail:** use Hostinger’s SMTP host (often `smtp.hostinger.com`), port `587`, and that mailbox as `SMTP_USER` / `APPLY_FROM_EMAIL`.

SMTP only sends when a listing has a recruiter email. The current drafts mostly do not. Easy Apply is still LinkedIn-in-the-browser.

## Access blockers (must be provided to the agent)

- Cursor Cloud secrets for the keys above (for cloud-agent testing)
- **VPS SSH** password or private key for `root@168.231.114.133`
- Portainer login (optional, for ops)

Without SSH, the agent can prepare the package and verify locally, but cannot finish VPS deploy/monitor.

## Cost (approx)

- Hostinger KVM: **~£5–13/mo** (or ~£0 marginal if this VPS is already paid for)
- Anthropic + Perplexity: **~£0.01–0.05 per job**
- Target from product guide: under **£15/mo** at moderate volume

## Related

- Schedule details: `docs/twice-daily-automation.md`
- Product: `docs/user-guide.md`
- Optional AWS path: `docs/aws-deployment.md`

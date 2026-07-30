# ApplyPilot twice-daily automation

This guide wires ApplyPilot so discovery runs **reliably twice per day** with no overlapping jobs and clear skip/error reporting.

## Recommended production setup (VPS)

Keep ApplyPilot running with Docker Compose on your VPS. The in-app scheduler fires at fixed local times.

```env
SCHEDULER_ENABLED=true
DISCOVERY_SCHEDULE_MODE=twice_daily
DISCOVERY_TIMES=08:00,20:00
DISCOVERY_TIMEZONE=Europe/London
PIPELINE_TRIGGER_TOKEN=replace-with-long-random-token
```

Then:

```bash
docker compose up --build -d
curl -s http://127.0.0.1:8000/api/health | jq .
curl -s http://127.0.0.1:8000/api/scheduler/status | jq .
```

Reliability guarantees:

| Guard | Behaviour |
|-------|-----------|
| Fixed clock times | Runs at 08:00 and 20:00 Europe/London, not drifting intervals |
| Run lock | Second trigger while busy returns HTTP 409 |
| Retries | Up to 3 attempts with 30s/60s backoff on transient failures |
| Readiness checks | Skips cleanly when Perplexity, database, or preferences are missing |
| `restart: unless-stopped` | Compose restarts the backend if the process dies |

Optional host cron fallback (only if the in-app scheduler is disabled):

```cron
0 8,20 * * * curl -fsS -H "Authorization: Bearer $PIPELINE_TRIGGER_TOKEN" -X POST http://127.0.0.1:8000/api/pipeline/run >> /var/log/applypilot-cron.log 2>&1
```

Do **not** enable both host cron and `SCHEDULER_ENABLED=true` unless you accept possible duplicate runs (the lock still prevents true overlap).

## Cursor Cloud environment

Repo file: `.cursor/environment.json`

- Installs Python deps into `.venv`
- Starts ApplyPilot on port `8000`
- Forwards port `8000` for local preview

Add these secrets in the [Cloud Agents environment](https://cursor.com/dashboard/cloud-agents):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` (or `DATABASE_URL`)
- `ANTHROPIC_API_KEY`
- `PERPLEXITY_API_KEY`
- `PIPELINE_TRIGGER_TOKEN` (optional but recommended)

Cloud agent VMs are not long-lived 24/7 hosts. For always-on twice-daily runs, prefer the VPS scheduler above. Use Cursor Automations when you want Cursor to wake a cloud agent twice a day and trigger one cycle.

## Cursor Automations (cloud trigger)

1. Open [cursor.com/automations](https://cursor.com/automations).
2. Create automation **ApplyPilot twice daily**.
3. Trigger: Scheduled cron `0 8,20 * * *` with timezone **Europe/London** (or the UI equivalent).
4. Repository: `MarkHickman227/Test-Area` on branch `main` (after merge).
5. Prompt: use the text in `.cursor/automations/applypilot-twice-daily.prompt.md`.
6. Save and enable.

## GitHub Actions backup trigger

Workflow: `.github/workflows/applypilot-twice-daily.yml`

Uses the Cursor Cloud Agents API so discovery still fires if you prefer CI as the clock.

Required GitHub secrets:

| Secret | Purpose |
|--------|---------|
| `CURSOR_API_KEY` | Cursor API key |
| `APPLYPILOT_AGENT_ID` | Durable agent id (`bc-...`) created once |

One-time agent bootstrap (from your laptop):

```bash
curl -u "$CURSOR_API_KEY:" \
  -H 'Content-Type: application/json' \
  -d @- https://api.cursor.com/v1/agents <<'EOF'
{
  "prompt": { "text": "Bootstrap ApplyPilot twice-daily agent. Read AGENTS.md and docs/twice-daily-automation.md. Do not open a PR." },
  "repos": [{ "url": "https://github.com/MarkHickman227/Test-Area", "startingRef": "main" }],
  "autoCreatePR": false
}
EOF
```

Store the returned agent id as `APPLYPILOT_AGENT_ID`.

## Manual verification

```bash
# Health + schedule
curl -s http://127.0.0.1:8000/api/health | jq '{ready: .ready_for_discovery, times: .discovery_times, tz: .discovery_timezone, scheduler: .scheduler}'

# One controlled run
curl -s -X POST http://127.0.0.1:8000/api/pipeline/run \
  -H "Authorization: Bearer $PIPELINE_TRIGGER_TOKEN" | jq .
```

Expected successful body includes `"status": "ok"` and a `stats` object. Intentional skips return `"status": "skipped"` with a reason (never treat that as a crash).

## Pick one clock

| Mode | Use when |
|------|----------|
| VPS in-app scheduler | Production default |
| Cursor Automation | Cloud-only runs without a VPS |
| GitHub Actions → Cursor API | External cron backup |

Use **one** primary clock. Extra clocks are optional backups only.

# ApplyPilot twice-daily run

You are running the scheduled ApplyPilot discovery cycle.

Follow `AGENTS.md` → **Twice-daily automation runbook** exactly.

## Hard rules

1. Start ApplyPilot if it is not already listening on port 8000 (use the command in `AGENTS.md`).
2. Wait until `GET /api/health` returns HTTP 200.
3. Confirm `ready_for_discovery` is true. If false, report which secrets/services are missing and stop.
4. Confirm preferences exist (`GET /api/preferences`). If none, report that onboarding is incomplete and stop.
5. Trigger exactly one cycle: `POST /api/pipeline/run`.
6. If `PIPELINE_TRIGGER_TOKEN` is configured, include `Authorization: Bearer <token>`.
7. Treat `status=ok` as success.
8. Treat `status=skipped` as a controlled no-op and report the reason.
9. Treat HTTP 409 as "already running" — do not retry repeatedly.
10. Auto-apply jobs that score 60+ against the full uploaded CV. Never invent credentials. Never open a PR unless you had to fix a blocking bug.
11. End with a short status summary: trigger time, result status, stats or skip reason.

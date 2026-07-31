# ApplyPilot AWS deployment

**Primary production target: AWS** (not the Hostinger VPS).

ApplyPilot is a containerized FastAPI + static UI app. On AWS we run it as a long-lived service so the twice-daily in-app scheduler can fire reliably, with CloudWatch for monitoring.

## Target architecture

| Piece | AWS service | Why |
|-------|-------------|-----|
| App container | **ECS on Fargate** behind an **ALB** | Always-on HTTP service for UI + API |
| Images | **ECR** | Store backend/frontend (or single combined) images |
| Secrets | **Secrets Manager** | Anthropic, Perplexity, Supabase / `DATABASE_URL`, trigger token |
| Schedule (primary) | In-app `twice_daily` scheduler | 08:00 / 20:00 `Europe/London` while the task is running |
| Schedule (backup) | **EventBridge** → ECS RunTask or HTTP to `/api/pipeline/run` | External clock if the service restarts mid-window |
| Logs / metrics / alarms | **CloudWatch** | Health, 5xx, discovery failures, CPU/memory |
| Optional CDN | CloudFront | Later; not required for first cut |

Supabase (or Postgres via `DATABASE_URL`) remains the data store. Do not put plaintext API keys in task definitions — inject from Secrets Manager at task launch.

## Skills for the full AWS loop

| Phase | Skills / capability |
|-------|---------------------|
| Design → tasks | `spec-to-implementation`, `tasks-plan`, `tasks-build` |
| Containers | `aws-containers` (ECS Fargate, ECR, ALB) |
| Secrets | `aws-secrets-manager` (dynamic refs; never print secret values) |
| Monitoring | `aws-observability` (CloudWatch logs, alarms, dashboards) |
| Auth to AWS | `signing-in-to-aws` / Cursor AWS IAM role secret if used |
| Review | Bugbot / security-review before promote |
| Ops UI (optional) | Portainer only if you keep a bastion; prefer ECS console + CloudWatch on AWS |

## Environment variables on AWS

Map these into the ECS task from Secrets Manager (JSON keys):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` and/or `DATABASE_URL`
- `ANTHROPIC_API_KEY`
- `PERPLEXITY_API_KEY`
- `PIPELINE_TRIGGER_TOKEN` (recommended)
- Plain config (not secret): `APP_ENV=production`, `SCHEDULER_ENABLED=true`, `DISCOVERY_SCHEDULE_MODE=twice_daily`, `DISCOVERY_TIMES=08:00,20:00`, `DISCOVERY_TIMEZONE=Europe/London`

## First deploy checklist

1. Create ECR repos and push images built from `backend/Dockerfile` (and frontend if separate; current app can serve UI from FastAPI).
2. Create secret `applypilot/prod` in Secrets Manager with the keys above.
3. Create ECS cluster + Fargate service + ALB health check on `/api/health`.
4. Confirm `ready_for_discovery: true` on the public health URL.
5. Save preferences once via the UI or API.
6. Watch CloudWatch logs around 08:00 and 20:00 Europe/London.
7. Optional: EventBridge rule calling `POST /api/pipeline/run` with the bearer token as backup.

## Monitoring (minimum alarms)

- ALB / target **unhealthy**
- HTTP **5xx** spike on `/api/*`
- Log metric filter for `Discovery cycle failed`
- Fargate **CPU / memory** high

## Out of scope for AWS v1

- Hostinger VPS (`168.231.114.133`) — legacy only; do not treat as production
- EKS / Kubernetes — not needed
- Auto-submitting job applications — still human review only

## Related docs

- Product usage: `docs/user-guide.md`
- Schedule behaviour: `docs/twice-daily-automation.md`
- Cloud agent boot: `.cursor/environment.json`, `AGENTS.md`

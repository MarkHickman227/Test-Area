# PrivateCanvas

Working name for a private, adult-only text-to-image service. This repository is the Phase 1 Secure MVP scaffold: age-gated accounts, curated generation, private library, append-only credits, prompt policy, and a MockWorker.

This is not a commercial launch. Payments, production age-assurance vendor onboarding, GPU hosting, model licences, and legal review remain go/no-go items.

See `docs/AGE-ASSURANCE.md`. Sandbox completion is disabled in production.

## Architecture

- `apps/web` — Next.js UI
- `apps/api` — FastAPI control plane
- `apps/worker` — Celery worker (`GENERATION_BACKEND=mock` or `comfyui`)
- `apps/comfyui-stub` — private ComfyUI HTTP stub for `gpu_net` (no public ports, no weights)
- `packages/workflows` — pinned workflow templates (users never submit graphs)
- `infra` — Caddy and Prometheus
- `docs` — policy drafts, threat model, data flow, runbooks

ComfyUI is not exposed to the internet. The default worker emits non-explicit placeholder PNGs so development and CI never store adult model outputs.

## Local development (no Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
export PYTHONPATH=apps/api
export APP_ENV=development
export DATABASE_URL=sqlite+pysqlite:///./data/privatecanvas.db
export STORAGE_BACKEND=local
export STORAGE_LOCAL_PATH=./data/storage
export JOB_EXECUTION=inline
export ALLOW_SANDBOX_AGE_VERIFY=true
export REQUIRE_MFA_PRIVILEGED=false
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# set ENCRYPTION_KEY to that value
mkdir -p data
cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another shell:

```bash
cd apps/web && npm install && npm run dev
```

Open the UI at http://127.0.0.1:3000/ (not port 8000). Port 8000 is the API (`/health`, `/ready`). Bind `0.0.0.0` so `localhost` and the preview proxy can reach it; `127.0.0.1` only is IPv4-loopback and looks like a connection reset in the browser.

To generate through ComfyUI from that same UI (pinned workflow, no ComfyUI graph editor): run `python apps/comfyui-stub/server.py` on loopback, then start the API with `GENERATION_BACKEND=comfyui` and `COMFYUI_URL=http://127.0.0.1:8188`. See `docs/COMFYUI.md`.

To generate through HotAPI (server-side `HOTAPI_KEY` only): `GENERATION_BACKEND=hotapi`. See `docs/HOTAPI.md`. Staging still requires mock.

Dev accounts (non-production): `adult@example.com` / `dev-user-password` and `admin@example.com` / `dev-admin-password`.

## Tests

```bash
cd apps/api && PYTHONPATH=. pytest -q
```

Pre-deploy release gates (pytest, live API preflight, staging walkthrough): `docs/PRE-DEPLOY.md`.

## Docker

Copy `.env.example` to `.env`, set `ENCRYPTION_KEY` and secrets, then `docker compose up --build`. Networks: `public_net`, `app_net`, `gpu_net`. Only Caddy publishes 80/443. Mailhog is bound to `127.0.0.1:8025`.

Private staging (fail-closed boot, invite-only, mock worker, payments off): see `docs/STAGING.md`.

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

Optional ComfyUI contract stub (still no model weights): `GENERATION_BACKEND=comfyui docker compose --profile comfyui up --build`. Staging boot checks reject ComfyUI until a licensed GPU host is attached.

## Constraints

- Do not copy Stuffer.ai or any third-party product UI, prompts, or workflows
- Do not commit model weights, identity documents, or production data
- Do not enable Stripe/live payments without written processor approval. `PAYMENTS_ENABLED` defaults to false. See `docs/PAYMENTS.md`.
- Do not treat a configured age-assurance vendor as a legal sign-off. See `docs/AGE-ASSURANCE.md`.

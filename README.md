# PrivateCanvas

Working name for a private, adult-only text-to-image service. This repository is the Phase 1 Secure MVP scaffold: age-gated accounts, curated generation, private library, append-only credits, prompt policy, and a MockWorker.

This is not a commercial launch. Payments, production age-assurance, GPU hosting, model licences, and legal review remain go/no-go items.

## Architecture

- `apps/web` — Next.js UI
- `apps/api` — FastAPI control plane
- `apps/worker` — Celery worker using the same MockWorker protocol a ComfyUI host would implement
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
cd apps/api && uvicorn app.main:app --reload --port 8000
```

In another shell:

```bash
cd apps/web && npm install && npm run dev
```

Open http://localhost:3000. The web app proxies `/v1` to the API.

Dev accounts (non-production): `adult@example.com` / `dev-user-password` and `admin@example.com` / `dev-admin-password`.

## Tests

```bash
cd apps/api && PYTHONPATH=. pytest -q
```

## Docker

Copy `.env.example` to `.env`, set `ENCRYPTION_KEY` and secrets, then `docker compose up --build`. Networks: `public_net`, `app_net`, `gpu_net`. Only Caddy publishes 80/443.

## Constraints

- Do not copy Stuffer.ai or any third-party product UI, prompts, or workflows
- Do not commit model weights, identity documents, or production data
- Do not enable Stripe/live payments without written processor approval

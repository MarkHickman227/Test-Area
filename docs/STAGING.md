# Private staging

This is the next operational stage after the Secure MVP adapters. It does **not** turn on live payments, GPU model weights, or a commercial launch.

## Bring-up

1. Copy `.env.staging.example` to `.env` and replace every `replace-` / example value.
2. Set `AGE_VERIFICATION_API_URL`, `AGE_VERIFICATION_API_KEY`, and `AGE_VERIFICATION_WEBHOOK_SECRET` for a real 18+ vendor. The HTTP contract is in `docs/AGE-ASSURANCE.md`.
3. Keep `PAYMENTS_ENABLED=false` and `PAYMENTS_PROCESSOR_ATTESTED=false` until a processor confirms the adult business in writing.
4. Keep `GENERATION_BACKEND=mock`. Do not point staging at community model downloads.
5. Start:

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

The API process exits on boot if secrets are still examples, SQLite is used, sandbox age is on, MFA bypass is on, or live payments are enabled without attestation.

## Checks

- `GET /health` — process up
- `GET /ready` — database reachable
- `GET /v1/meta/launch` — `payments_enabled: false`, `generation_backend: mock`, `sandbox_age: false`
- Privileged admins must complete MFA (`REQUIRE_MFA_PRIVILEGED=true`)
- Mailhog, if used, is bound to `127.0.0.1:8025` only
- `scripts/backup.sh` then `scripts/restore.sh` on a copy of the database
- Full pre-deploy pack: `docs/PRE-DEPLOY.md` (`pytest` plus `python scripts/preflight.py --expect-staging`)

## Still go/no-go (not this overlay)

- Written payment-processor approval
- Licensed checkpoint and private GPU ComfyUI on `gpu_net`
- Counsel on `docs/POLICIES.md`, DPIA, child-safety
- Public DNS + TLS (replace `infra/Caddyfile` `auto_https off` with a real hostname)

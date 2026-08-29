# Pre-deploy testing

Do this before promoting a build. Automated tests are the gate to *enter* staging. The live preflight and walkthrough are the gate to *keep* a staging host. Public production is still blocked on vendor, processor, GPU licence, and counsel. Staging host setup is in `docs/STAGING.md`.

## 1. Automated (required)

```bash
cd apps/api && PYTHONPATH=. pytest -q
cd apps/api && PYTHONPATH=. pytest -q tests/test_predeploy.py
```

`tests/test_predeploy.py` is the release-gate path: ready/flags, age gate, blocked prompts, generate → library, payments off, support search hides outputs, privileged MFA, backup/restore roundtrip.

## 2. Live API preflight (required against the target host)

With the API up:

```bash
python3 scripts/preflight.py --base http://127.0.0.1:8000
python3 scripts/preflight.py --base http://127.0.0.1:8000 \
  --email adult@example.com --password dev-user-password \
  --support-email support@example.com --support-password dev-support-password
```

Against private staging (sandbox age must be off, HTTP age provider):

```bash
python3 scripts/preflight.py --base https://staging.example --expect-staging
```

The script never enables payments or loads model weights.

## 3. Manual walkthrough (required once per staging build)

1. Register → verify email → age check → generate (placeholders) → library download
2. Unverified account cannot generate or check out
3. Blocked prompt never appears as QUEUED
4. Support search does not show images (also `tests/test_predeploy.py` + preflight `--support-email`)
5. Privileged admin MFA works (`REQUIRE_MFA_PRIVILEGED=true`; covered by pytest)
6. `scripts/backup.sh` then restore into a copy (`scripts/restore.sh`; covered by pytest)
7. Optional: `python3 scripts/load_probe.py --base http://127.0.0.1:8000` (health only)

## 4. Do not deploy if

- `/v1/meta/launch` shows `payments_enabled: true` without written processor approval
- `generation_backend` is `comfyui` without a licensed private GPU host
- `sandbox_age` is true on staging/production
- Boot refused example secrets (see `docs/STAGING.md`)

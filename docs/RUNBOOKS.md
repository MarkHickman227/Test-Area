# Runbooks

## Job stuck in QUEUED

1. Confirm moderation_state is not PENDING_REVIEW.
2. Check worker process and GPU/MockWorker logs (`GENERATION_BACKEND`, `COMFYUI_URL`).
3. If JOB_EXECUTION=inline, restart API. If using the ComfyUI profile, confirm the stub/GPU host is reachable only on `gpu_net`.
4. Expire stale jobs via `JobService.expire_stale_queued`.

## Credit mismatch

1. Open `/v1/admin/credits/mismatches` as finance/super admin (audited).
2. Compare job reservation/capture/release events.
3. Apply `MANUAL_ADJUSTMENT` with reason code — never update a balance column.

## Restore test

1. `scripts/backup.sh`
2. Restore into an empty database with `scripts/restore.sh`
3. Confirm users, jobs, and output metadata counts
4. Confirm object store keys still resolve

Staging bring-up and boot refusals: `docs/STAGING.md`.

## Child-safety escalation

1. Automated BLOCK on minor-indicating prompts
2. Preserve evidence only when legally required (`preserve_evidence`)
3. Suspend account
4. Follow the incident-response policy before launch

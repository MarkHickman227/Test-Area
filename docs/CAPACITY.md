# GPU capacity and load (Phase 2)

## Current model

- One worker slot by default (`WORKER_SLOTS=1`).
- Queue depth cap: `QUEUE_MAX_DEPTH` (default 20).
- Hard job timeout: `JOB_TIMEOUT_SECONDS`.
- Plan hourly caps prevent a single account from filling the GPU.

Adding workers later does not change the public API. Worker-control claims `QUEUED` jobs with `SKIP LOCKED`.

## Probe (non-generating)

`scripts/load_probe.py` hits `/health` and `/v1/meta/launch` only. It does not submit prompts or store images.

## When to add a GPU worker

Add a slot when `queue_wait` exceeds 90 seconds at target resolution under expected demand, and after moderation volume is within staffing.

Do not expose ComfyUI. Pin workflow templates and model checksums before enabling a real GPU profile.

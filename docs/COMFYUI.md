# ComfyUI worker contract

The API never accepts user-supplied workflow JSON.

A GPU worker must:

1. Claim `QUEUED` jobs with `SELECT … FOR UPDATE SKIP LOCKED` where `moderation_state != PENDING_REVIEW`
2. Load the pinned template for `workflow_template_id` + `workflow_version`
3. Substitute only `allowed_variable_fields`
4. Submit to ComfyUI on `gpu_net`
5. Scan outputs, write thumbnails, upload to private storage
6. Mark COMPLETED and capture credits according to `capture_on`
7. On failure, record `failure_code` and release credits if capture has not occurred

The MockWorker in `apps/api/app/jobs/runner.py` implements this protocol with placeholder PNGs.

Do not bind ComfyUI to the public internet. Pin custom nodes and image digests. Do not download community models at runtime.

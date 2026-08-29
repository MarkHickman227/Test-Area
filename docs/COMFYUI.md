# ComfyUI worker contract

The API never accepts user-supplied workflow JSON. Users never submit graphs.

A GPU worker must:

1. Claim `QUEUED` jobs with `SELECT … FOR UPDATE SKIP LOCKED` where `moderation_state != PENDING_REVIEW`
2. Load the pinned template for `workflow_template_id` + `workflow_version`
3. Substitute only `allowed_variable_fields` (including `preset_values` → `{{preset.steps}}` etc.)
4. Submit to ComfyUI on `gpu_net` (`POST /prompt`, poll `GET /history/{id}`, fetch `GET /view`)
5. Scan outputs, write thumbnails, upload to private storage
6. Mark COMPLETED and capture credits according to `capture_on`
7. On failure, record `failure_code` and release credits if capture has not occurred

`GENERATION_BACKEND=mock` (default) uses placeholder PNGs so local/CI never stores model weights or generated adult images.

`GENERATION_BACKEND=comfyui` uses `COMFYUI_URL` (default `http://comfyui:8188`). Do not bind ComfyUI to the public internet. Pin custom nodes and image digests. Do not download community models at runtime.

## Local stub (no GPU, no weights)

The product UI stays PrivateCanvas (`http://127.0.0.1:3000/generate`). Do not open ComfyUI's own frontend. Users never submit graphs.

Without Docker:

```bash
# loopback only — do not publish 8188
python apps/comfyui-stub/server.py
# then run the API with:
#   GENERATION_BACKEND=comfyui
#   COMFYUI_URL=http://127.0.0.1:8188
```

With Docker:

```bash
docker compose --profile comfyui up --build
# then set GENERATION_BACKEND=comfyui on the worker
```

The `comfyui` service is the contract stub in `apps/comfyui-stub`. It is attached only to `gpu_net` and does not publish host ports. Replace that image with a private GPU runtime when hardware is available; keep the same HTTP contract and pinned templates.

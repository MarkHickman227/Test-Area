"""Private ComfyUI-compatible stub. Emits non-explicit placeholder PNGs.

This is not a GPU runtime and does not load model weights. Use it to exercise
the worker HTTP contract on gpu_net without exposing ComfyUI publicly.
"""

from __future__ import annotations

import io
import uuid

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="PrivateCanvas ComfyUI stub", docs_url=None, redoc_url=None)
_JOBS: dict[str, dict] = {}


def _clamp(value: object, default: int, lo: int, hi: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(lo, min(hi, parsed))


def _latent_size(prompt: dict) -> tuple[int, int, int]:
    latent = prompt.get("4") or {}
    inputs = latent.get("inputs") if isinstance(latent, dict) else {}
    if not isinstance(inputs, dict):
        inputs = {}
    width = _clamp(inputs.get("width"), 768, 64, 1152)
    height = _clamp(inputs.get("height"), 768, 64, 1152)
    batch = _clamp(inputs.get("batch_size"), 1, 1, 4)
    return width, height, batch


def _placeholder_png(label: str, width: int = 256, height: int = 256) -> bytes:
    image = Image.new("RGB", (width, height), (58, 48, 38))
    draw = ImageDraw.Draw(image)
    inset = max(10, min(width, height) // 16)
    draw.rectangle(
        [inset, inset, width - inset, height - inset],
        outline=(212, 176, 118),
        width=max(4, min(width, height) // 48),
    )
    try:
        title = ImageFont.load_default(size=max(28, min(width, height) // 10))
        body = ImageFont.load_default(size=max(18, min(width, height) // 16))
    except TypeError:
        title = ImageFont.load_default()
        body = title
    text_x = inset + max(12, width // 20)
    text_y = height // 3
    draw.text((text_x, text_y), "ComfyUI stub", fill=(243, 239, 232), font=title)
    draw.text((text_x, text_y + max(36, height // 14)), label[:36], fill=(212, 176, 118), font=body)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@app.get("/health")
def health():
    return {"status": "ok", "mode": "stub"}


@app.post("/prompt")
def submit_prompt(body: dict):
    prompt = body.get("prompt") or {}
    if not isinstance(prompt, dict) or not prompt:
        return JSONResponse({"error": "prompt graph required"}, status_code=400)
    prompt_id = str(uuid.uuid4())
    width, height, batch = _latent_size(prompt)
    _JOBS[prompt_id] = {
        "prompt": prompt,
        "batch": batch,
        "width": width,
        "height": height,
        "client_id": body.get("client_id"),
    }
    return {"prompt_id": prompt_id, "number": 1}


@app.get("/history/{prompt_id}")
def history(prompt_id: str):
    job = _JOBS.get(prompt_id)
    if not job:
        return {}
    images = [
        {"filename": f"{prompt_id}-{index}.png", "subfolder": "", "type": "output"}
        for index in range(int(job["batch"]))
    ]
    return {
        prompt_id: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"9": {"images": images}},
        }
    }


@app.get("/view")
def view(
    filename: str = Query(...),
    subfolder: str = Query(""),
    type: str = Query("output"),
):
    _ = (subfolder, type)
    prompt_id = filename.rsplit("-", 1)[0]
    job = _JOBS.get(prompt_id) or {}
    width = int(job.get("width") or 256)
    height = int(job.get("height") or 256)
    return Response(
        content=_placeholder_png(filename, width, height), media_type="image/png"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8188)

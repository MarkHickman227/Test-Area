"""Private ComfyUI-compatible stub. Emits non-explicit placeholder PNGs.

This is not a GPU runtime and does not load model weights. Use it to exercise
the worker HTTP contract on gpu_net without exposing ComfyUI publicly.
"""

from __future__ import annotations

import io
import uuid

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw

app = FastAPI(title="PrivateCanvas ComfyUI stub", docs_url=None, redoc_url=None)
_JOBS: dict[str, dict] = {}


def _placeholder_png(label: str) -> bytes:
    image = Image.new("RGB", (256, 256), (28, 24, 22))
    draw = ImageDraw.Draw(image)
    draw.rectangle([12, 12, 244, 244], outline=(196, 165, 116), width=3)
    draw.text((24, 110), "ComfyUI stub", fill=(243, 239, 232))
    draw.text((24, 130), label[:24], fill=(196, 165, 116))
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
    batch = 1
    latent = prompt.get("4") or {}
    inputs = latent.get("inputs") if isinstance(latent, dict) else {}
    if isinstance(inputs, dict):
        try:
            batch = max(1, int(inputs.get("batch_size") or 1))
        except (TypeError, ValueError):
            batch = 1
    _JOBS[prompt_id] = {
        "prompt": prompt,
        "batch": batch,
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
    return Response(content=_placeholder_png(filename), media_type="image/png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8188)

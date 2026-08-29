"""HotAPI text-to-image backend.

Operation fields come from HotAPI MCP `get_openapi_operation` for
`POST /v1/z-image-spicy` and `GET /v1/tasks/{id}`. Do not add face-swap,
image-edit, or video endpoints.
"""

from __future__ import annotations

import io
import logging
import time
from typing import Any

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.jobs.backends import parse_resolution
from app.models.generation import GenerationJob

logger = logging.getLogger("privatecanvas.hotapi")

TERMINAL = {"succeeded", "failed", "cancelled"}
Z_IMAGE_PATH = "/v1/z-image-spicy"
SEEDREAM_LITE_PATH = "/v1/seedream-5.0-lite-spicy/text-to-image"
SEED_MAX = 2_147_483_647


class HotAPIError(RuntimeError):
    pass


def clamp_dim(value: int) -> int:
    return max(256, min(1536, int(value)))


def clamp_seed(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, min(int(value), SEED_MAX))


def aspect_for_size(width: int, height: int) -> str:
    if width == height:
        return "1:1"
    if height * 2 == width * 3:
        return "2:3"
    if width * 2 == height * 3:
        return "3:2"
    if width * 9 == height * 16:
        return "16:9"
    if height * 9 == width * 16:
        return "9:16"
    return "1:1"


def asset_urls(task: dict[str, Any]) -> list[str]:
    output = task.get("output") or {}
    assets = output.get("assets") if isinstance(output, dict) else None
    urls: list[str] = []
    if isinstance(assets, list):
        for item in assets:
            if isinstance(item, dict) and item.get("url"):
                urls.append(str(item["url"]))
    return urls


def to_png(content: bytes) -> bytes:
    with Image.open(io.BytesIO(content)) as image:
        converted = image.convert("RGB")
        buf = io.BytesIO()
        converted.save(buf, format="PNG")
        return buf.getvalue()


class HotAPIClient:
    """Server-side HotAPI client. Auth is Bearer HOTAPI_KEY only."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.hotapi.ai",
        timeout_seconds: float = 180,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise HotAPIError("HOTAPI_KEY is not set")
        self.timeout_seconds = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def submit_z_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "prompt": prompt,
            "width": clamp_dim(width),
            "height": clamp_dim(height),
        }
        clamped = clamp_seed(seed)
        if clamped is not None:
            body["seed"] = clamped
        return self._submit(Z_IMAGE_PATH, body, idempotency_key)

    def submit_seedream_lite(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._submit(
            SEEDREAM_LITE_PATH,
            {"prompt": prompt, "size": "2K", "aspect_ratio": aspect_ratio},
            idempotency_key,
        )

    def _submit(self, path: str, body: dict[str, Any], idempotency_key: str) -> dict:
        try:
            response = self._client.post(
                path,
                json=body,
                headers={"Idempotency-Key": idempotency_key},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HotAPIError(self._error_message(exc, "submit failed")) from exc
        data = response.json()
        if not data.get("id"):
            raise HotAPIError("HotAPI did not return a task id")
        return data

    def get_task(self, task_id: str) -> dict[str, Any]:
        try:
            response = self._client.get(f"/v1/tasks/{task_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HotAPIError(self._error_message(exc, "task poll failed")) from exc
        return response.json()

    def wait_for_task(self, task_id: str, *, poll_interval: float = 1.5) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            status = task.get("status")
            if status in TERMINAL:
                if status != "succeeded":
                    err = (task.get("error") or {}).get("message") or status
                    raise HotAPIError(f"HotAPI task {status}: {err}")
                return task
            time.sleep(poll_interval)
        raise HotAPIError("HotAPI timed out waiting for the task")

    def download_png(self, url: str) -> bytes:
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HotAPIError(f"HotAPI asset download failed: {exc}") from exc
        return to_png(response.content)

    def _error_message(self, exc: httpx.HTTPError, fallback: str) -> str:
        response = getattr(exc, "response", None)
        request_id = ""
        if response is not None:
            try:
                payload = response.json()
                err = payload.get("error") or {}
                request_id = err.get("request_id") or ""
                message = err.get("message") or fallback
            except Exception:
                message = fallback
            if request_id:
                return f"{message} (request_id={request_id})"
            return message
        return fallback


class HotAPIBackend:
    worker_id = "hotapi-worker-1"

    def __init__(
        self,
        settings: Settings,
        db: Session,
        crypto: CryptoService,
        client: HotAPIClient | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.crypto = crypto
        self.client = client or HotAPIClient(
            settings.hotapi_key,
            settings.hotapi_base_url,
            settings.hotapi_timeout_seconds,
        )

    def render(self, job: GenerationJob) -> list[bytes]:
        prompt = self.crypto.decrypt(job.prompt_encrypted) or ""
        if not prompt.strip():
            raise HotAPIError("Prompt is empty")
        width, height = parse_resolution(job.parameters.get("resolution", "768x768"))
        quality = str(job.parameters.get("quality") or "medium").lower()
        images: list[bytes] = []
        task_ids: list[str] = []
        for index in range(int(job.image_count)):
            seed = None if job.seed is None else int(job.seed) + index
            key = f"{job.id}-{index}"
            if quality == "high":
                submitted = self.client.submit_seedream_lite(
                    prompt=prompt,
                    aspect_ratio=aspect_for_size(width, height),
                    idempotency_key=key,
                )
            else:
                submitted = self.client.submit_z_image(
                    prompt=prompt,
                    width=width,
                    height=height,
                    seed=seed,
                    idempotency_key=key,
                )
            task_id = str(submitted["id"])
            task_ids.append(task_id)
            job.comfy_prompt_id = task_ids[0]
            self.db.flush()
            finished = self.client.wait_for_task(task_id)
            urls = asset_urls(finished)
            if not urls:
                raise HotAPIError("HotAPI succeeded without image assets")
            images.append(self.client.download_png(urls[0]))
        logger.info("hotapi_completed job=%s tasks=%s n=%s", job.id, task_ids, len(images))
        return images

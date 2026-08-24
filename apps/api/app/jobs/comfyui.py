from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.jobs.backends import parse_resolution
from app.jobs.placeholder import build_workflow_payload
from app.models.generation import GenerationJob, WorkflowTemplate

logger = logging.getLogger("privatecanvas.comfyui")


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    """HTTP client for a private ComfyUI instance on gpu_net."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 120,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=timeout_seconds
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def submit_prompt(self, prompt: dict, client_id: str) -> str:
        try:
            response = self._client.post(
                "/prompt", json={"prompt": prompt, "client_id": client_id}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI submit failed: {exc}") from exc
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError("ComfyUI did not return prompt_id")
        return str(prompt_id)

    def wait_for_images(
        self, prompt_id: str, *, poll_interval: float = 0.2
    ) -> list[bytes]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            images = self._try_fetch_images(prompt_id)
            if images is not None:
                return images
            time.sleep(poll_interval)
        raise ComfyUIError("ComfyUI timed out waiting for outputs")

    def _try_fetch_images(self, prompt_id: str) -> list[bytes] | None:
        try:
            response = self._client.get(f"/history/{prompt_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI history failed: {exc}") from exc
        payload = response.json() or {}
        entry = payload.get(prompt_id) or payload
        status = entry.get("status") if isinstance(entry, dict) else None
        if isinstance(status, dict) and status.get("status_str") == "error":
            raise ComfyUIError("ComfyUI reported an error status")
        outputs = entry.get("outputs") if isinstance(entry, dict) else None
        refs = _image_refs(outputs)
        if not refs:
            return None
        return [self._download_view(ref) for ref in refs]

    def _download_view(self, ref: dict[str, str]) -> bytes:
        try:
            response = self._client.get("/view", params=ref)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI view failed: {exc}") from exc
        data = response.content
        if not data:
            raise ComfyUIError("ComfyUI returned an empty image")
        return data


def _image_refs(outputs: Any) -> list[dict[str, str]]:
    if not isinstance(outputs, dict):
        return []
    refs: list[dict[str, str]] = []
    for node in outputs.values():
        if not isinstance(node, dict):
            continue
        for image in node.get("images") or []:
            if not isinstance(image, dict) or not image.get("filename"):
                continue
            refs.append(
                {
                    "filename": str(image["filename"]),
                    "subfolder": str(image.get("subfolder") or ""),
                    "type": str(image.get("type") or "output"),
                }
            )
    return refs


class ComfyUIBackend:
    worker_id = "comfyui-worker-1"

    def __init__(
        self,
        settings: Settings,
        db: Session,
        crypto: CryptoService,
        client: ComfyUIClient | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.crypto = crypto
        self.client = client or ComfyUIClient(
            settings.comfyui_url, settings.comfyui_timeout_seconds
        )

    def render(self, job: GenerationJob) -> list[bytes]:
        template = self.db.get(WorkflowTemplate, job.workflow_template_id)
        if not template or not template.definition:
            raise ComfyUIError("Pinned workflow template is unavailable")
        prompt_text = self.crypto.decrypt(job.prompt_encrypted)
        negative = ""
        if job.negative_prompt_encrypted:
            negative = self.crypto.decrypt(job.negative_prompt_encrypted) or ""
        width, height = parse_resolution(job.parameters.get("resolution", "768x768"))
        graph = build_workflow_payload(
            template.definition,
            {
                "positive_prompt": prompt_text,
                "negative_prompt": negative,
                "seed": int(job.seed or 0),
                "width": width,
                "height": height,
                "batch_count": int(job.image_count),
                "preset_values": job.parameters.get("preset") or {},
                "job_id": job.id,
                "user_id": job.user_id,
            },
        )
        prompt_id = self.client.submit_prompt(graph, client_id=job.id)
        job.comfy_prompt_id = prompt_id
        self.db.flush()
        images = self.client.wait_for_images(prompt_id)
        if len(images) < job.image_count:
            raise ComfyUIError("ComfyUI returned fewer images than requested")
        logger.info(
            "comfyui_completed job=%s prompt_id=%s n=%s",
            job.id,
            prompt_id,
            len(images),
        )
        return images[: job.image_count]

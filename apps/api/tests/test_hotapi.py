import io
from uuid import uuid4

import httpx
from PIL import Image

from app.config import get_settings
from app.jobs.factory import make_backend
from app.jobs.hotapi import HotAPIBackend, HotAPIClient, HotAPIError, asset_urls
from app.jobs.runner import GenerationWorker
from tests.conftest import become_active, csrf_for, register_verify_login


def _png(width: int = 32, height: int = 32) -> bytes:
    image = Image.new("RGB", (width, height), (40, 30, 20))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _hotapi_transport() -> httpx.MockTransport:
    tasks: dict[str, dict] = {}
    png = _png()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/z-image-spicy" and request.method == "POST":
            import json

            payload = json.loads(request.content)
            assert "prompt" in payload
            assert 256 <= int(payload["width"]) <= 1536
            assert 256 <= int(payload["height"]) <= 1536
            assert "quality" not in payload
            task_id = "task_" + uuid4().hex[:8]
            tasks[task_id] = {
                "id": task_id,
                "object": "task",
                "status": "succeeded",
                "model": "z-image-spicy",
                "task_kind": "image.generate",
                "input": payload,
                "estimated_credits_cost": 24,
                "created_at": 1,
                "expires_at": 2,
                "output": {
                    "assets": [
                        {"type": "image", "url": f"https://cdn.hotapi.ai/results/{task_id}.png"}
                    ]
                },
            }
            return httpx.Response(202, json={"id": task_id, "status": "queued", "model": "z-image-spicy"})
        if path.startswith("/v1/tasks/") and request.method == "GET":
            task_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json=tasks[task_id])
        if path.startswith("/results/") or "cdn.hotapi.ai" in str(request.url):
            return httpx.Response(200, content=png, headers={"content-type": "image/png"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_asset_urls_from_task_output():
    urls = asset_urls(
        {"output": {"assets": [{"type": "image", "url": "https://cdn.hotapi.ai/a.png"}]}}
    )
    assert urls == ["https://cdn.hotapi.ai/a.png"]


def test_hotapi_client_submit_and_download():
    http = httpx.Client(
        transport=_hotapi_transport(),
        base_url="https://api.hotapi.ai",
        headers={"Authorization": "Bearer test-key"},
    )
    client = HotAPIClient("test-key", client=http)
    submitted = client.submit_z_image(
        prompt="an original fictional adult",
        width=768,
        height=1152,
        seed=42,
        idempotency_key="job-1-0",
    )
    task = client.wait_for_task(submitted["id"])
    assert task["status"] == "succeeded"
    png = client.download_png(asset_urls(task)[0])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_hotapi_client_requires_key():
    try:
        HotAPIClient("")
        assert False, "expected missing key"
    except HotAPIError as exc:
        assert "HOTAPI_KEY" in str(exc)


def test_make_backend_hotapi(monkeypatch):
    monkeypatch.setenv("GENERATION_BACKEND", "hotapi")
    monkeypatch.setenv("HOTAPI_KEY", "test-key")
    get_settings.cache_clear()
    try:
        backend = make_backend(get_settings(), db=None, crypto=None)
        assert isinstance(backend, HotAPIBackend)
        assert backend.worker_id == "hotapi-worker-1"
    finally:
        get_settings.cache_clear()


def test_hotapi_backend_completes_inline_job(client, monkeypatch):
    http = httpx.Client(
        transport=_hotapi_transport(),
        base_url="https://api.hotapi.ai",
        headers={"Authorization": "Bearer test-key"},
    )

    def fake_make_worker(db, settings, crypto, storage):
        backend = HotAPIBackend(
            settings,
            db,
            crypto,
            client=HotAPIClient("test-key", client=http),
        )
        return GenerationWorker(db, settings, crypto, storage, backend=backend)

    monkeypatch.setattr("app.jobs.factory.make_worker", fake_make_worker)
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/generate-image",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "prompt": "An original fictional adult character, clearly 27 years old",
            "size": "768x1152",
            "quality": "medium",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "COMPLETED"
    assert body["worker_id"] == "hotapi-worker-1"
    assert body["output_ids"]
    assert body["image_url"]
    assert body["image"]


def test_generate_image_requires_auth(client):
    res = client.post(
        "/v1/generate-image",
        json={"prompt": "an original fictional adult", "size": "1024x1024"},
    )
    assert res.status_code == 401


def test_generate_image_rejects_bad_size(client):
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/generate-image",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"prompt": "an original fictional adult", "size": "9999x1"},
    )
    assert res.status_code == 400

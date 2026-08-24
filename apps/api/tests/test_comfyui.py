from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image

from app.config import get_settings
from app.jobs.comfyui import ComfyUIBackend, ComfyUIClient, ComfyUIError
from app.jobs.factory import make_backend
from app.jobs.placeholder import build_workflow_payload, workflow_checksum
from app.jobs.runner import GenerationWorker
from app.models.generation import GenerationJob, WorkflowTemplate
from app.seed import WORKFLOW_PATH
from tests.conftest import become_active, csrf_for, register_verify_login


def _load_template() -> dict:
    import json

    return json.loads(WORKFLOW_PATH.read_text())


def test_workflow_payload_fills_preset_and_seed_types():
    template = _load_template()
    graph = build_workflow_payload(
        template,
        {
            "positive_prompt": "an original fictional adult",
            "negative_prompt": "watermark",
            "seed": 42,
            "width": 768,
            "height": 1152,
            "batch_count": 2,
            "preset_values": {
                "steps": 28,
                "cfg": 5.5,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
            },
            "job_id": "job-1",
            "user_id": "user-1",
        },
    )
    assert graph["1"]["class_type"] == "CheckpointLoaderSimple"
    sampler = graph["5"]["inputs"]
    assert sampler["seed"] == 42
    assert sampler["steps"] == 28
    assert sampler["cfg"] == 5.5
    assert sampler["sampler_name"] == "dpmpp_2m"
    assert graph["4"]["inputs"]["batch_size"] == 2
    assert graph["2"]["inputs"]["text"] == "an original fictional adult"
    assert "note" not in graph


def test_workflow_payload_rejects_unknown_fields():
    template = _load_template()
    try:
        build_workflow_payload(template, {"positive_prompt": "x", "evil": 1})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Disallowed" in str(exc)


def test_workflow_checksum_stable():
    assert len(workflow_checksum(Path(WORKFLOW_PATH))) == 64


def _tiny_png() -> bytes:
    import io

    image = Image.new("RGB", (32, 32), (40, 30, 20))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _stub_transport() -> httpx.MockTransport:
    import json

    jobs: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/prompt":
            data = json.loads(request.content)
            prompt_id = "prompt-" + uuid4().hex[:8]
            node = (data.get("prompt") or {}).get("4") or {}
            try:
                batch = int((node.get("inputs") or {}).get("batch_size") or 1)
            except (TypeError, ValueError):
                batch = 1
            jobs[prompt_id] = {"batch": batch}
            return httpx.Response(200, json={"prompt_id": prompt_id})
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            job = jobs.get(prompt_id)
            if not job:
                return httpx.Response(200, json={})
            images = [
                {
                    "filename": f"{prompt_id}-{index}.png",
                    "subfolder": "",
                    "type": "output",
                }
                for index in range(job["batch"])
            ]
            return httpx.Response(
                200,
                json={
                    prompt_id: {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {"9": {"images": images}},
                    }
                },
            )
        if path == "/view":
            return httpx.Response(
                200, content=_tiny_png(), headers={"content-type": "image/png"}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_comfyui_client_submit_and_download():
    http = httpx.Client(transport=_stub_transport(), base_url="http://comfyui")
    client = ComfyUIClient("http://comfyui", timeout_seconds=2, client=http)
    prompt_id = client.submit_prompt(
        {"4": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 2}}},
        client_id="job-x",
    )
    images = client.wait_for_images(prompt_id)
    assert len(images) == 2
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_comfyui_client_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "never"})
        return httpx.Response(200, json={})

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://comfyui"
    )
    client = ComfyUIClient("http://comfyui", timeout_seconds=0.3, client=http)
    client.submit_prompt({"1": {"class_type": "X", "inputs": {}}}, "c")
    try:
        client.wait_for_images("never", poll_interval=0.05)
        assert False, "expected timeout"
    except ComfyUIError as exc:
        assert "timed out" in str(exc)


def test_make_backend_comfyui(monkeypatch):
    monkeypatch.setenv("GENERATION_BACKEND", "comfyui")
    get_settings.cache_clear()
    try:
        backend = make_backend(get_settings(), db=None, crypto=None)
        assert isinstance(backend, ComfyUIBackend)
        assert backend.worker_id == "comfyui-worker-1"
    finally:
        get_settings.cache_clear()


def test_comfyui_backend_completes_inline_job(client, monkeypatch):
    http = httpx.Client(transport=_stub_transport(), base_url="http://comfyui")

    def fake_make_worker(db, settings, crypto, storage):
        backend = ComfyUIBackend(
            settings,
            db,
            crypto,
            client=ComfyUIClient("http://comfyui", timeout_seconds=5, client=http),
        )
        return GenerationWorker(db, settings, crypto, storage, backend=backend)

    monkeypatch.setattr("app.jobs.factory.make_worker", fake_make_worker)
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 27 years old",
            "negative_prompt": "watermark",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "COMPLETED"
    from app.db import get_session_factory

    db = get_session_factory()()
    job = db.get(GenerationJob, res.json()["job_id"])
    assert job.worker_id == "comfyui-worker-1"
    assert job.comfy_prompt_id
    template = db.get(WorkflowTemplate, "adult-illustration-v1")
    assert template and template.definition.get("fixed_graph")
    db.close()


def test_comfyui_stub_http_contract():
    import sys

    from fastapi.testclient import TestClient

    stub_dir = Path(__file__).resolve().parents[3] / "apps" / "comfyui-stub"
    sys.path.insert(0, str(stub_dir))
    from server import app as stub_app

    stub = TestClient(stub_app)
    submitted = stub.post(
        "/prompt",
        json={
            "client_id": "stub-job",
            "prompt": {
                "4": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": 64, "height": 64, "batch_size": 1},
                },
                "9": {"class_type": "SaveImage", "inputs": {}},
            },
        },
    )
    assert submitted.status_code == 200
    prompt_id = submitted.json()["prompt_id"]
    history = stub.get(f"/history/{prompt_id}")
    assert history.status_code == 200
    images = history.json()[prompt_id]["outputs"]["9"]["images"]
    assert len(images) == 1
    viewed = stub.get("/view", params=images[0])
    assert viewed.status_code == 200
    assert viewed.content[:8] == b"\x89PNG\r\n\x1a\n"

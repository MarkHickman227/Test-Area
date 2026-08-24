from __future__ import annotations

from typing import Protocol

from app.jobs.placeholder import render_placeholder
from app.models.generation import GenerationJob


def parse_resolution(value: str) -> tuple[int, int]:
    width_s, height_s = value.lower().split("x")
    return int(width_s), int(height_s)


class ImageBackend(Protocol):
    worker_id: str

    def render(self, job: GenerationJob) -> list[bytes]: ...


class MockBackend:
    """Non-explicit placeholder PNGs. Default for local/CI — no model weights."""

    worker_id = "mock-worker-1"

    def render(self, job: GenerationJob) -> list[bytes]:
        width, height = parse_resolution(job.parameters.get("resolution", "768x768"))
        return [
            render_placeholder(job.id, width, height, index)
            for index in range(job.image_count)
        ]

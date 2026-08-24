from __future__ import annotations

from datetime import datetime

from app.schemas.common import APIModel


class OutputView(APIModel):
    id: str
    job_id: str
    sequence_number: int
    width: int
    height: int
    mime_type: str
    bytes: int
    favourite: bool
    created_at: datetime
    thumbnail_available: bool = True
    scan_status: str
    deleted: bool = False


class OutputDetail(OutputView):
    model_profile_id: str | None = None
    style_preset_id: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    parameters: dict | None = None


class DownloadUrlResponse(APIModel):
    url: str
    expires_in: int
    kind: str


class PatchOutputRequest(APIModel):
    favourite: bool | None = None


class BulkDeleteRequest(APIModel):
    output_ids: list[str] | None = None
    delete_all: bool = False

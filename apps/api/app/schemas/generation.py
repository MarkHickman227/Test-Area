from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class CreateGenerationRequest(APIModel):
    idempotency_key: str = Field(min_length=8, max_length=64)
    model_profile_id: str
    style_preset_id: str | None = None
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    aspect_ratio: str
    resolution: str
    image_count: int = Field(ge=1, le=4)
    seed: int | None = None
    priority: bool = False


class GenerationOptions(APIModel):
    model_profiles: list[dict]
    style_presets: list[dict]
    aspect_ratios: list[str]
    resolutions: list[str]
    image_counts: list[int]
    pricing_rule_version: str
    content_policy_version: str


class GenerationJobView(APIModel):
    job_id: str
    status: str
    estimated_credit_cost: int
    credits_reserved: int
    queue_position: int | None = None
    estimated_start_seconds: int | None = None
    policy_decision: str
    model_profile_id: str
    style_preset_id: str | None
    image_count: int
    seed: int | None
    parameters: dict
    created_at: datetime
    failure_code: str | None = None
    worker_id: str | None = None
    output_ids: list[str] = []


class CancelResponse(APIModel):
    job_id: str
    status: str


class RerunRequest(APIModel):
    idempotency_key: str

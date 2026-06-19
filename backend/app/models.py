from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationStatus(StrEnum):
    new = "NEW"
    draft = "DRAFT"
    ready = "READY"
    submitted = "SUBMITTED"
    interview = "INTERVIEW"
    offer = "OFFER"
    rejected = "REJECTED"
    ignored = "IGNORED"


class JobType(StrEnum):
    permanent = "PERM"
    contract = "CONTRACT"


class JobSummary(BaseModel):
    id: UUID
    title: str
    company: str | None = None
    location: str | None = None
    job_type: JobType | None = None
    agency: bool = False
    score: int | None = Field(default=None, ge=0, le=100)
    status: ApplicationStatus
    source_url: str | None = None
    created_at: datetime | None = None


class JobDetail(JobSummary):
    description: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    parsed_requirements: dict[str, Any] = Field(default_factory=dict)
    score_explanation: str | None = None
    selected_cv_label: str | None = None
    tailored_summary: str | None = None
    cover_letter: str | None = None
    screening_answers: list[dict[str, str]] = Field(default_factory=list)
    recruiter_outreach: dict[str, Any] | None = None


class StatusUpdate(BaseModel):
    status: ApplicationStatus


class ArtifactRegenerationRequest(BaseModel):
    artifact: str = Field(pattern="^(cv_summary|cover_letter|screening_answers|recruiter_outreach)$")
    notes: str | None = Field(default=None, max_length=2000)


class ArtifactSaveRequest(BaseModel):
    artifact: str = Field(pattern="^(cv_summary|cover_letter|screening_answers|recruiter_outreach)$")
    content: str


class Preferences(BaseModel):
    target_titles: list[str] = Field(min_length=1, max_length=5)
    locations: list[str] = Field(min_length=1)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    job_types: list[JobType] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    seniority_level: str | None = None


class CvRecord(BaseModel):
    id: UUID
    label: str
    file_name: str
    raw_text: str = ""
    parsed_profile: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class CvCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    file_name: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)

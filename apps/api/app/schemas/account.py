from __future__ import annotations

from app.schemas.common import APIModel


class ReportRequest(APIModel):
    category: str
    description: str
    job_id: str | None = None
    output_id: str | None = None


class AccountUpdateRequest(APIModel):
    display_name: str | None = None


class AgeSandboxRequest(APIModel):
    outcome: str = "PASSED"


class ModerationDecisionRequest(APIModel):
    decision: str
    reason_code: str
    rationale: str
    preserve_evidence: bool = False


class BreakGlassRequest(APIModel):
    target_user_id: str
    reason_code: str
    rationale: str
    ttl_minutes: int = 30


class LedgerAdjustRequest(APIModel):
    user_id: str
    amount: int
    reason_code: str
    rationale: str

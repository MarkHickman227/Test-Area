from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.errors import AppError
from app.models.base import utcnow
from app.models.enums import (
    AgeVerificationStatus,
    JobStatus,
    ModerationState,
    PolicyDecision,
    QueueClass,
    UserStatus,
)
from app.models.billing import Plan
from app.models.generation import (
    GenerationJob,
    ModelProfile,
    StylePreset,
    WorkflowTemplate,
)
from app.models.growth import AbuseEvent
from app.models.moderation import ModerationEvent
from app.models.user import User
from app.services.audit import write_audit
from app.services.credits import capture_credits, release_credits, reserve_credits
from app.services.policy import PolicyEngine, fingerprint_parameters
from app.services.pricing import (
    ALLOWED_ASPECTS,
    ALLOWED_COUNTS,
    ALLOWED_RESOLUTIONS,
    ASPECT_TO_RESOLUTION,
    PRICING_RULE_VERSION,
    PricingInput,
    calculate_credit_cost,
)


class JobService:
    def __init__(self, db: Session, settings: Settings, crypto: CryptoService) -> None:
        self.db = db
        self.settings = settings
        self.crypto = crypto
        self.policy = PolicyEngine()

    def create(
        self,
        user: User,
        payload: dict,
        request_id: str | None = None,
    ) -> GenerationJob:
        self._assert_can_generate(user)
        self._assert_plan_capacity(user, int(payload.get("image_count") or 1))
        existing = self.db.scalar(
            select(GenerationJob).where(
                GenerationJob.user_id == user.id,
                GenerationJob.idempotency_key == payload["idempotency_key"],
            )
        )
        if existing:
            return existing

        profile = self.db.get(ModelProfile, payload["model_profile_id"])
        if not profile or not profile.active:
            raise AppError("UNKNOWN_MODEL", "That model profile is not available.")
        preset = None
        if payload.get("style_preset_id"):
            preset = self.db.get(StylePreset, payload["style_preset_id"])
            if not preset or not preset.active or preset.model_profile_id != profile.id:
                raise AppError("UNKNOWN_PRESET", "That style preset is not available.")
        template = self.db.get(WorkflowTemplate, profile.workflow_template_id)
        if not template or not template.active:
            raise AppError(
                "WORKFLOW_UNAVAILABLE", "The selected workflow is not available."
            )

        aspect = payload["aspect_ratio"]
        resolution = payload["resolution"]
        image_count = int(payload["image_count"])
        if aspect not in ALLOWED_ASPECTS or resolution not in ALLOWED_RESOLUTIONS:
            raise AppError(
                "INVALID_OPTIONS", "Aspect ratio or resolution is not allowed."
            )
        if (aspect, resolution) not in ASPECT_TO_RESOLUTION:
            raise AppError(
                "INVALID_OPTIONS", "Resolution is not valid for that aspect ratio."
            )
        if image_count not in ALLOWED_COUNTS:
            raise AppError("INVALID_OPTIONS", "Image count is not allowed.")
        queued = self.db.scalar(
            select(func.count())
            .select_from(GenerationJob)
            .where(GenerationJob.status == JobStatus.QUEUED)
        )
        if int(queued or 0) >= self.settings.queue_max_depth:
            raise AppError(
                "QUEUE_FULL",
                "The generation queue is at capacity. Try again shortly.",
                429,
            )

        prompt = payload["prompt"].strip()
        negative = (payload.get("negative_prompt") or "").strip() or None
        if not prompt or len(prompt) > 4000:
            raise AppError(
                "INVALID_PROMPT",
                "Prompt is required and must be under 4000 characters.",
            )
        if negative and len(negative) > 2000:
            raise AppError(
                "INVALID_PROMPT", "Negative prompt must be under 2000 characters."
            )

        policy = self.policy.evaluate(prompt, negative)
        seed = payload.get("seed")
        if seed is None:
            seed = secrets.randbits(63)
        parameters = {
            "aspect_ratio": aspect,
            "resolution": resolution,
            "image_count": image_count,
            "seed": seed,
            "preset": (
                preset.values
                if preset
                else {
                    "steps": 28,
                    "cfg": 5.5,
                    "sampler": "dpmpp_2m",
                    "scheduler": "karras",
                }
            ),
        }
        plan = self.db.get(Plan, user.plan_id or self.settings.default_plan_id)
        wants_priority = bool(payload.get("priority")) and bool(
            plan and plan.allows_priority
        )
        priority_multiplier = (
            float(plan.priority_multiplier) if wants_priority and plan else 1.0
        )
        cost = calculate_credit_cost(
            PricingInput(
                base_model_cost=profile.base_credit_cost,
                resolution=resolution,
                image_count=image_count,
                priority_multiplier=priority_multiplier,
                workflow_multiplier=float(template.cost_multiplier),
            )
        )
        job = GenerationJob(
            user_id=user.id,
            idempotency_key=payload["idempotency_key"],
            status=JobStatus.VALIDATING,
            workflow_template_id=template.id,
            workflow_version=template.version,
            model_profile_id=profile.id,
            style_preset_id=preset.id if preset else None,
            prompt_encrypted=self.crypto.encrypt(prompt),
            negative_prompt_encrypted=(
                self.crypto.encrypt(negative) if negative else None
            ),
            parameters=parameters,
            parameters_hash=fingerprint_parameters(parameters),
            seed=seed,
            image_count=image_count,
            credit_cost=cost,
            pricing_rule_version=PRICING_RULE_VERSION,
            policy_decision=policy.decision.value,
            policy_score=policy.score,
            moderation_state=ModerationState.NONE,
            queue_class=QueueClass.PRIORITY if wants_priority else QueueClass.STANDARD,
            submitted_at=utcnow(),
        )
        self.db.add(job)
        self.db.flush()
        self.db.add(
            ModerationEvent(
                job_id=job.id,
                user_id=user.id,
                stage="prompt",
                decision=policy.decision.value,
                rule_hits=policy.rule_ids,
                classifier_score=policy.score,
            )
        )

        if policy.decision == PolicyDecision.BLOCK:
            job.status = JobStatus.BLOCKED
            job.moderation_state = ModerationState.REJECTED
            user.blocked_prompt_count = (user.blocked_prompt_count or 0) + 1
            self.db.add(
                AbuseEvent(
                    user_id=user.id,
                    kind="prompt_blocked",
                    detail="policy_block",
                )
            )
            if user.blocked_prompt_count >= self.settings.blocked_prompt_restrict_after:
                user.status = UserStatus.RESTRICTED
            write_audit(
                self.db,
                action="job.blocked",
                target_type="generation_job",
                target_id=job.id,
                actor_user_id=user.id,
                request_id=request_id,
            )
            self.db.commit()
            raise AppError(
                "PROMPT_BLOCKED",
                "This request cannot be processed under the content policy.",
                400,
            )
        if policy.decision == PolicyDecision.SUSPEND_ESCALATE:
            user.status = UserStatus.SUSPENDED
            job.status = JobStatus.BLOCKED
            job.moderation_state = ModerationState.ESCALATED
            self.db.commit()
            raise AppError(
                "PROMPT_BLOCKED",
                "This request cannot be processed under the content policy.",
                400,
            )
        if policy.decision == PolicyDecision.HOLD_FOR_REVIEW:
            job.status = JobStatus.QUEUED
            job.moderation_state = ModerationState.PENDING_REVIEW
            job.queued_at = utcnow()
            reservation = reserve_credits(self.db, user.id, job.id, cost)
            job.reservation_ledger_event_id = reservation.id
            write_audit(
                self.db,
                action="job.held",
                target_type="generation_job",
                target_id=job.id,
                actor_user_id=user.id,
                request_id=request_id,
            )
            self.db.commit()
            return job

        reservation = reserve_credits(self.db, user.id, job.id, cost)
        job.reservation_ledger_event_id = reservation.id
        job.status = JobStatus.QUEUED
        job.queued_at = utcnow()
        if policy.decision == PolicyDecision.ALLOW_WITH_LOG:
            job.moderation_state = ModerationState.PENDING_REVIEW
        write_audit(
            self.db,
            action="job.queued",
            target_type="generation_job",
            target_id=job.id,
            actor_user_id=user.id,
            request_id=request_id,
            metadata={"credit_cost": cost},
        )
        self.db.commit()
        return job

    def cancel(self, user: User, job_id: str) -> GenerationJob:
        job = self._owned_job(user, job_id)
        if job.status != JobStatus.QUEUED:
            raise AppError("CANCEL_NOT_ALLOWED", "Only queued jobs can be cancelled.")
        job.status = JobStatus.CANCELLED
        job.cancelled_at = utcnow()
        release_credits(self.db, user.id, job.id, job.credit_cost, "JOB_CANCELLED")
        write_audit(
            self.db,
            action="job.cancelled",
            target_type="generation_job",
            target_id=job.id,
            actor_user_id=user.id,
        )
        self.db.commit()
        return job

    def rerun(self, user: User, job_id: str, idempotency_key: str) -> GenerationJob:
        source = self._owned_job(user, job_id)
        prompt = self.crypto.decrypt(source.prompt_encrypted)
        negative = self.crypto.decrypt(source.negative_prompt_encrypted)
        params = source.parameters or {}
        return self.create(
            user,
            {
                "idempotency_key": idempotency_key,
                "model_profile_id": source.model_profile_id,
                "style_preset_id": source.style_preset_id,
                "prompt": prompt,
                "negative_prompt": negative,
                "aspect_ratio": params.get("aspect_ratio", "2:3"),
                "resolution": params.get("resolution", "768x1152"),
                "image_count": source.image_count,
                "seed": source.seed,
            },
        )

    def fail_job(
        self, job: GenerationJob, code: str, detail: str, refund: bool
    ) -> None:
        job.status = JobStatus.FAILED
        job.failure_code = code
        job.failure_detail = detail
        job.completed_at = utcnow()
        if refund:
            release_credits(self.db, job.user_id, job.id, job.credit_cost, "JOB_FAILED")
        write_audit(
            self.db,
            action="job.failed",
            target_type="generation_job",
            target_id=job.id,
            metadata={"code": code},
        )

    def capture_if_needed(self, job: GenerationJob) -> None:
        capture_credits(self.db, job.user_id, job.id, job.credit_cost)

    def _owned_job(self, user: User, job_id: str) -> GenerationJob:
        job = self.db.get(GenerationJob, job_id)
        if not job or job.user_id != user.id:
            raise AppError("JOB_NOT_FOUND", "Job not found.", 404)
        return job

    def _assert_can_generate(self, user: User) -> None:
        if (
            user.age_verification_status != AgeVerificationStatus.PASSED
            or not user.age_verified_at
        ):
            raise AppError(
                "AGE_VERIFICATION_REQUIRED",
                "Complete age assurance before generating.",
                403,
            )
        if user.status != UserStatus.ACTIVE:
            raise AppError(
                "ACCOUNT_NOT_ACTIVE", "This account cannot generate images.", 403
            )

    def _assert_plan_capacity(self, user: User, image_count: int) -> None:
        plan = self.db.get(Plan, user.plan_id or self.settings.default_plan_id)
        max_images = plan.max_images_per_job if plan else 4
        if image_count > max_images:
            raise AppError(
                "PLAN_LIMIT",
                "That image count is not included in your current plan.",
                403,
            )
        concurrent = int(
            self.db.scalar(
                select(func.count())
                .select_from(GenerationJob)
                .where(
                    GenerationJob.user_id == user.id,
                    GenerationJob.status.in_(
                        [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.POST_PROCESSING]
                    ),
                )
            )
            or 0
        )
        if plan and concurrent >= plan.max_concurrent_jobs:
            raise AppError(
                "PLAN_LIMIT",
                "You already have the maximum number of jobs in progress.",
                429,
            )
        hourly_limit = plan.hourly_job_limit if plan else 20
        cutoff = utcnow() - timedelta(hours=1)
        hourly = int(
            self.db.scalar(
                select(func.count())
                .select_from(GenerationJob)
                .where(
                    GenerationJob.user_id == user.id,
                    GenerationJob.submitted_at >= cutoff,
                )
            )
            or 0
        )
        if hourly >= hourly_limit:
            raise AppError(
                "PLAN_LIMIT",
                "Hourly generation limit reached for this plan.",
                429,
            )

    def expire_stale_queued(self, max_age_seconds: int = 3600) -> int:
        cutoff = utcnow() - timedelta(seconds=max_age_seconds)
        jobs = self.db.scalars(
            select(GenerationJob).where(
                GenerationJob.status == JobStatus.QUEUED,
                GenerationJob.queued_at < cutoff,
            )
        ).all()
        for job in jobs:
            if job.moderation_state == ModerationState.PENDING_REVIEW:
                continue
            job.status = JobStatus.EXPIRED
            release_credits(
                self.db, job.user_id, job.id, job.credit_cost, "JOB_EXPIRED"
            )
        self.db.commit()
        return len(jobs)

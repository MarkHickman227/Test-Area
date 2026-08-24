from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.enums import AgeVerificationStatus, UserRole, UserStatus
from app.models.generation import ModelProfile, StylePreset, WorkflowTemplate
from app.models.billing import Plan
from app.models.growth import InviteCode
from app.models.user import User, UserProfile
from app.services.auth import grant_welcome_credits, hash_password
from app.services.credits import grant_promotional


def _workflow_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3]
        / "packages"
        / "workflows"
        / "adult-illustration-v1.json",
        Path("/packages/workflows/adult-illustration-v1.json"),
        Path.cwd() / "packages" / "workflows" / "adult-illustration-v1.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


WORKFLOW_PATH = _workflow_path()


def seed_reference_data(db: Session) -> None:
    plans = [
        {
            "id": "standard",
            "name": "Standard",
            "max_images_per_job": 4,
            "max_concurrent_jobs": 2,
            "priority_multiplier": 1.0,
            "allows_priority": False,
            "hourly_job_limit": 20,
            "monthly_credits": 40,
            "description": "Invite and promotional credits. Standard queue.",
        },
        {
            "id": "creator",
            "name": "Creator",
            "max_images_per_job": 4,
            "max_concurrent_jobs": 3,
            "priority_multiplier": 1.25,
            "allows_priority": True,
            "hourly_job_limit": 40,
            "monthly_credits": 120,
            "description": "Priority queue when payments are enabled. Higher hourly cap.",
        },
    ]
    for row in plans:
        if not db.get(Plan, row["id"]):
            db.add(Plan(**row))
        else:
            current = db.get(Plan, row["id"])
            for key, value in row.items():
                if key != "id":
                    setattr(current, key, value)

    profiles = [
        (
            "adult-illustration-v1",
            "Adult illustration v1",
            "Curated illustrative profile. Server-controlled workflow only.",
            4,
        ),
        (
            "ink-illustration-v1",
            "Ink illustration v1",
            "High-contrast ink and wash look. Same pinned workflow family.",
            5,
        ),
        (
            "figurative-studio-v1",
            "Figurative studio v1",
            "Studio figurative illustration with restrained lighting.",
            5,
        ),
    ]
    for pid, name, desc, cost in profiles:
        if not db.get(ModelProfile, pid):
            db.add(
                ModelProfile(
                    id=pid,
                    name=name,
                    description=desc,
                    workflow_template_id="adult-illustration-v1",
                    base_credit_cost=cost,
                    allowed_resolutions=[
                        "768x768",
                        "768x1152",
                        "1152x768",
                        "1024x1024",
                    ],
                )
            )

    presets = [
        (
            "cinematic-photo-v1",
            "Cinematic still",
            "adult-illustration-v1",
            28,
            5.0,
            "dpmpp_2m",
            "karras",
        ),
        (
            "editorial-portrait-v1",
            "Editorial portrait",
            "adult-illustration-v1",
            30,
            6.0,
            "euler",
            "normal",
        ),
        (
            "ink-line-v1",
            "Ink line",
            "ink-illustration-v1",
            24,
            4.5,
            "dpmpp_2m",
            "karras",
        ),
        (
            "charcoal-v1",
            "Charcoal study",
            "ink-illustration-v1",
            26,
            5.0,
            "euler",
            "normal",
        ),
        (
            "golden-hour-v1",
            "Golden hour",
            "figurative-studio-v1",
            30,
            5.5,
            "dpmpp_2m",
            "karras",
        ),
    ]
    for pid, name, model, steps, cfg, sampler, scheduler in presets:
        if not db.get(StylePreset, pid):
            db.add(
                StylePreset(
                    id=pid,
                    name=name,
                    description=name,
                    model_profile_id=model,
                    values={
                        "steps": steps,
                        "cfg": cfg,
                        "sampler": sampler,
                        "scheduler": scheduler,
                    },
                )
            )
    if not db.get(WorkflowTemplate, "adult-illustration-v1"):
        definition = (
            json.loads(WORKFLOW_PATH.read_text())
            if WORKFLOW_PATH.exists()
            else {"fixed_graph": {}, "allowed_variable_fields": []}
        )
        db.add(
            WorkflowTemplate(
                id="adult-illustration-v1",
                version=str(definition.get("workflow_version", "1.0.0")),
                compatible_model_profile_id="adult-illustration-v1",
                definition=definition,
                content_policy_requirement_level="adult_strict",
                cost_multiplier=float(definition.get("cost_multiplier", 1.0)),
            )
        )
    db.commit()


def seed_dev_users(db: Session, settings: Settings) -> None:
    if not settings.is_dev:
        return
    admin = db.scalar(
        select(User).where(User.email == settings.dev_admin_email.lower())
    )
    if not admin:
        from app.models.base import utcnow

        admin = User(
            email=settings.dev_admin_email.lower(),
            password_hash=hash_password(settings.dev_admin_password),
            status=UserStatus.ACTIVE,
            role=UserRole.SUPER_ADMIN,
            email_verified_at=utcnow(),
            age_verified_at=utcnow(),
            age_verification_status=AgeVerificationStatus.PASSED,
        )
        db.add(admin)
        db.flush()
        db.add(UserProfile(user_id=admin.id))
        grant_promotional(db, admin.id, 100, key=f"dev-admin:{admin.id}")
    user = db.scalar(select(User).where(User.email == settings.dev_user_email.lower()))
    if not user:
        from app.models.base import utcnow

        user = User(
            email=settings.dev_user_email.lower(),
            password_hash=hash_password(settings.dev_user_password),
            status=UserStatus.ACTIVE,
            role=UserRole.USER,
            email_verified_at=utcnow(),
            age_verified_at=utcnow(),
            age_verification_status=AgeVerificationStatus.PASSED,
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id))
        grant_welcome_credits(db, user, settings)
    support = db.scalar(select(User).where(User.email == "support@example.com"))
    if not support and settings.is_dev:
        from app.models.base import utcnow

        support = User(
            email="support@example.com",
            password_hash=hash_password("dev-support-password"),
            status=UserStatus.ACTIVE,
            role=UserRole.SUPPORT,
            email_verified_at=utcnow(),
            age_verified_at=utcnow(),
            age_verification_status=AgeVerificationStatus.PASSED,
            plan_id="standard",
        )
        db.add(support)
        db.flush()
        db.add(UserProfile(user_id=support.id))
    if not db.scalar(select(InviteCode).where(InviteCode.code == "WELCOME-DEV")):
        db.add(
            InviteCode(
                code="WELCOME-DEV",
                max_uses=1000,
                note="Local/dev invite",
            )
        )
    db.commit()

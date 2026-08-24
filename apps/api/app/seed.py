from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.enums import AgeVerificationStatus, UserRole, UserStatus
from app.models.generation import ModelProfile, StylePreset, WorkflowTemplate
from app.models.billing import Plan
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
    if not db.get(Plan, "standard"):
        db.add(
            Plan(
                id="standard",
                name="Standard",
                max_images_per_job=4,
                max_concurrent_jobs=2,
                priority_multiplier=1.0,
            )
        )
    if not db.get(ModelProfile, "adult-illustration-v1"):
        db.add(
            ModelProfile(
                id="adult-illustration-v1",
                name="Adult illustration v1",
                description="Curated illustrative profile. Server-controlled workflow only.",
                workflow_template_id="adult-illustration-v1",
                base_credit_cost=4,
                allowed_resolutions=["768x768", "768x1152", "1152x768", "1024x1024"],
            )
        )
    if not db.get(StylePreset, "cinematic-photo-v1"):
        db.add(
            StylePreset(
                id="cinematic-photo-v1",
                name="Cinematic still",
                description="Warm editorial lighting, shallow depth, filmic grade.",
                model_profile_id="adult-illustration-v1",
                values={
                    "steps": 28,
                    "cfg": 5.0,
                    "sampler": "dpmpp_2m",
                    "scheduler": "karras",
                },
            )
        )
    if not db.get(StylePreset, "editorial-portrait-v1"):
        db.add(
            StylePreset(
                id="editorial-portrait-v1",
                name="Editorial portrait",
                description="Studio key light, clean background, fashion-editorial pose.",
                model_profile_id="adult-illustration-v1",
                values={
                    "steps": 30,
                    "cfg": 6.0,
                    "sampler": "euler",
                    "scheduler": "normal",
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
    if settings.app_env == "production":
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
    db.commit()

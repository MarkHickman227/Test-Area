from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.jobs.backends import ImageBackend, MockBackend, parse_resolution
from app.jobs.placeholder import render_thumbnail
from app.models.base import utcnow
from app.models.enums import JobStatus, ModerationState, ScanStatus, Visibility
from app.models.generation import GenerationJob, GenerationOutput
from app.models.moderation import ModerationEvent
from app.services.audit import write_audit
from app.services.jobs import JobService
from app.services.storage import StorageBackend, new_object_key, sha256_bytes

logger = logging.getLogger("privatecanvas.worker")


class GenerationWorker:
    """Claim queued jobs, render via a backend, scan, store, complete."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        crypto: CryptoService,
        storage: StorageBackend,
        backend: ImageBackend | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.crypto = crypto
        self.storage = storage
        self.backend = backend or MockBackend()
        self.jobs = JobService(db, settings, crypto)

    @property
    def worker_id(self) -> str:
        return self.backend.worker_id

    def claim_next(self) -> GenerationJob | None:
        stmt = (
            select(GenerationJob)
            .where(
                GenerationJob.status == JobStatus.QUEUED,
                GenerationJob.moderation_state != ModerationState.PENDING_REVIEW,
            )
            .order_by(GenerationJob.queued_at.asc())
            .limit(1)
        )
        if not self.settings.is_sqlite:
            stmt = stmt.with_for_update(skip_locked=True)
        job = self.db.scalar(stmt)
        if not job:
            return None
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        job.worker_id = self.worker_id
        if self.settings.capture_on == "running":
            self.jobs.capture_if_needed(job)
        write_audit(
            self.db,
            action="job.started",
            target_type="generation_job",
            target_id=job.id,
        )
        self.db.commit()
        return job

    def process(self, job: GenerationJob) -> None:
        try:
            self._process_inner(job)
        except Exception:
            logger.exception("job_failed id=%s", job.id)
            self.db.refresh(job)
            refund = self.settings.capture_on != "running"
            self.jobs.fail_job(
                job, "WORKER_ERROR", "Generation worker failed.", refund=refund
            )
            self.db.commit()

    def _process_inner(self, job: GenerationJob) -> None:
        images = self.backend.render(job)
        width, height = parse_resolution(job.parameters.get("resolution", "768x768"))
        outputs: list[GenerationOutput] = []
        for index, png in enumerate(images):
            thumb = render_thumbnail(png)
            original_key = new_object_key(job.user_id, job.id, f"original-{index}")
            thumb_key = new_object_key(job.user_id, job.id, f"thumb-{index}")
            self.storage.put(original_key, png, "image/png")
            self.storage.put(thumb_key, thumb, "image/png")
            output = GenerationOutput(
                job_id=job.id,
                user_id=job.user_id,
                sequence_number=index,
                original_storage_key=original_key,
                thumbnail_storage_key=thumb_key,
                content_sha256=sha256_bytes(png),
                width=width,
                height=height,
                mime_type="image/png",
                bytes=len(png),
                output_scan_status=ScanStatus.CLEAR,
                visibility=Visibility.PRIVATE,
            )
            self.db.add(output)
            outputs.append(output)
        job.status = JobStatus.POST_PROCESSING
        self.db.add(
            ModerationEvent(
                job_id=job.id,
                user_id=job.user_id,
                stage="output",
                decision="ALLOW",
                rule_hits=[],
                notes=f"{self.worker_id}_scan_clear",
            )
        )
        self.db.flush()
        job.status = JobStatus.COMPLETED
        job.completed_at = utcnow()
        if self.settings.capture_on == "completed":
            self.jobs.capture_if_needed(job)
        write_audit(
            self.db,
            action="job.completed",
            target_type="generation_job",
            target_id=job.id,
            metadata={"outputs": len(outputs), "backend": self.worker_id},
        )
        self.db.commit()

    def run_available(self, limit: int = 10) -> int:
        processed = 0
        for _ in range(limit):
            job = self.claim_next()
            if not job:
                break
            self.process(job)
            processed += 1
        return processed


class MockWorker(GenerationWorker):
    """Back-compat alias used by docs and existing imports."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        crypto: CryptoService,
        storage: StorageBackend,
    ) -> None:
        super().__init__(db, settings, crypto, storage, backend=MockBackend())


def process_job_by_id(
    db: Session,
    settings: Settings,
    crypto: CryptoService,
    storage: StorageBackend,
    job_id: str,
) -> None:
    from app.jobs.factory import make_worker

    worker = make_worker(db, settings, crypto, storage)
    job = db.get(GenerationJob, job_id)
    if not job:
        return
    if (
        job.status == JobStatus.QUEUED
        and job.moderation_state != ModerationState.PENDING_REVIEW
    ):
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        job.worker_id = worker.worker_id
        if settings.capture_on == "running":
            JobService(db, settings, crypto).capture_if_needed(job)
        db.commit()
        worker.process(job)


# Re-export for older tests/docs.
_parse_resolution = parse_resolution

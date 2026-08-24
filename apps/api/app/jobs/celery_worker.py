"""Celery entrypoint for GPU/host workers. Local MVP uses inline MockWorker."""

from celery import Celery

from app.config import get_settings
from app.crypto import get_crypto
from app.db import get_session_factory, init_db
from app.deps import get_storage
from app.jobs.runner import MockWorker

settings = get_settings()
celery_app = Celery(
    "privatecanvas",
    broker=settings.redis_url or "memory://",
    backend=settings.redis_url or "cache+memory://",
)


@celery_app.task(name="privatecanvas.process_queue")
def process_queue() -> int:
    init_db()
    db = get_session_factory()()
    try:
        worker = MockWorker(db, settings, get_crypto(), get_storage(settings))
        return worker.run_available()
    finally:
        db.close()


if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=info"])

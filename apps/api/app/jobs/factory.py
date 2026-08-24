from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.jobs.backends import MockBackend
from app.jobs.comfyui import ComfyUIBackend
from app.jobs.runner import GenerationWorker
from app.services.storage import StorageBackend


def make_backend(
    settings: Settings, db: Session, crypto: CryptoService
) -> MockBackend | ComfyUIBackend:
    if settings.generation_backend == "comfyui":
        return ComfyUIBackend(settings, db, crypto)
    return MockBackend()


def make_worker(
    db: Session,
    settings: Settings,
    crypto: CryptoService,
    storage: StorageBackend,
) -> GenerationWorker:
    return GenerationWorker(
        db, settings, crypto, storage, backend=make_backend(settings, db, crypto)
    )

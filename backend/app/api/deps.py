"""Shared dependency injection for API routes.

Priority: Supabase > Postgres (DATABASE_URL) > Local (in-memory + JSON file).
The local fallback ensures the dashboard is fully testable without any external services.
"""

import logging

from app.core.config import get_settings
from app.services.local_repository import LocalRepository
from app.services.seed import seed_if_empty

logger = logging.getLogger(__name__)

_local_repo: LocalRepository | None = None


def get_repository():
    settings = get_settings()

    if settings.supabase_configured:
        from app.services.repository import SupabaseRepository
        return SupabaseRepository(settings)

    if settings.database_configured:
        from app.services.postgres_repository import PostgresRepository
        return PostgresRepository(settings)

    global _local_repo
    if _local_repo is None:
        _local_repo = LocalRepository()
        seed_if_empty(_local_repo)
        logger.info("Using local in-memory repository with seed data")
    return _local_repo

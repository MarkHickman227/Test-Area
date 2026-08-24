"""initial schema via metadata create.

Revision ID: 001
Revises:
Create Date: 2026-08-24
"""

from alembic import op  # noqa: F401
from app.db import init_db

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    init_db()


def downgrade() -> None:
    pass

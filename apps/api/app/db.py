from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.models.base import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs = {"future": True}
        if settings.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in settings.database_url:
                kwargs["poolclass"] = StaticPool
        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _SessionLocal


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db() -> None:
    import app.models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _patch_sqlite_columns(engine)


def _patch_sqlite_columns(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    patches = [
        ("users", "plan_id", "VARCHAR(64) DEFAULT 'standard'"),
        ("users", "country_code", "VARCHAR(8)"),
        ("users", "invite_code", "VARCHAR(64)"),
        ("users", "blocked_prompt_count", "INTEGER DEFAULT 0 NOT NULL"),
        ("plans", "allows_priority", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("plans", "hourly_job_limit", "INTEGER DEFAULT 20 NOT NULL"),
        ("plans", "monthly_credits", "INTEGER DEFAULT 40 NOT NULL"),
        ("plans", "description", "VARCHAR(240) DEFAULT ''"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in patches:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            names = {row[1] for row in rows}
            if rows and column not in names:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    return get_session_factory()()

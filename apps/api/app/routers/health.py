from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from app.db import get_session_factory
from app.errors import AppError

router = APIRouter(tags=["health"])

REQUESTS = Counter(
    "pc_http_requests_total", "HTTP requests", ["path", "method", "status"]
)
JOBS = Counter("pc_jobs_total", "Generation jobs", ["status"])
AUTH_FAILURES = Counter("pc_auth_failures_total", "Authentication failures")
AGE_OUTCOMES = Counter(
    "pc_age_verification_total", "Age verification outcomes", ["outcome"]
)
CREDIT_EVENTS = Counter(
    "pc_credit_events_total", "Credit ledger events", ["event_type"]
)
LATENCY = Histogram("pc_http_request_latency_seconds", "Request latency")


@router.get("/health")
def health():
    return {"status": "ok", "service": "privatecanvas-api"}


@router.get("/ready")
def ready():
    db = get_session_factory()()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError("NOT_READY", "Database is not ready.", 503) from exc
    finally:
        db.close()
    return {"status": "ready"}


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

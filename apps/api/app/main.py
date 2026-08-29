from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.boot import assert_runtime_safe
from app.config import get_settings
from app.db import get_session_factory, init_db
from app.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_handler,
)
from app.routers import (
    account,
    admin,
    age_verification,
    auth,
    billing,
    generate_image,
    generations,
    health,
    launch,
    library,
    ops,
    payments,
)
from app.seed import seed_dev_users, seed_reference_data

logger = logging.getLogger("privatecanvas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    assert_runtime_safe(settings)
    init_db()
    db = get_session_factory()()
    try:
        seed_reference_data(db)
        seed_dev_users(db, settings)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="PrivateCanvas API",
        version="0.1.0",
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs" if settings.is_dev else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_base_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(RequestValidationError, validation_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = (
            request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'"
        )
        if not settings.is_dev:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(age_verification.router)
    application.include_router(generations.router)
    application.include_router(generations.options_router)
    application.include_router(generate_image.router)
    application.include_router(library.router)
    application.include_router(billing.router)
    application.include_router(payments.router)
    application.include_router(account.router)
    application.include_router(admin.router)
    application.include_router(ops.router)
    application.include_router(launch.router)
    return application


app = create_app()

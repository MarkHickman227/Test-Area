from fastapi import APIRouter, Request

from app.config import get_settings
from app.errors import AppError

router = APIRouter(tags=["billing"])


@router.post("/v1/webhooks/payments")
async def payments_webhook(request: Request):
    settings = get_settings()
    if not settings.payments_enabled:
        raise AppError(
            "PAYMENTS_NOT_ENABLED",
            "Payment webhooks are disabled until a processor is approved.",
            503,
        )
    raise AppError(
        "PAYMENTS_NOT_ENABLED",
        "Payment webhooks are disabled until a processor is approved.",
        503,
    )

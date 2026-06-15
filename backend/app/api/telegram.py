"""
Telegram Webhook API Route
POST /api/telegram/webhook  — receives updates from Telegram servers
GET  /api/telegram/register — registers the webhook (call once during deployment)
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.services.telegram_service import handle_telegram_update, register_webhook
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram calls this endpoint for every incoming message.
    Must return 200 OK quickly — Telegram will retry if it doesn't get a response.
    """
    # Verify the request is from Telegram using the secret token header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()
    logger.debug("Telegram webhook received: %s", update)

    # Process in the background — respond 200 immediately so Telegram doesn't retry
    try:
        result = handle_telegram_update(update)
        return JSONResponse(content={"ok": True, "result": result}, status_code=200)
    except Exception as exc:
        logger.exception("Unhandled error in Telegram webhook: %s", exc)
        # Still return 200 to prevent Telegram from re-sending the same message
        return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=200)


@router.get("/register")
async def register_telegram_webhook(public_url: str):
    """
    One-time setup: registers the Telegram webhook with the provided public URL.
    Example: GET /api/telegram/register?public_url=https://your-domain.com
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured.")
    result = register_webhook(public_url)
    return result

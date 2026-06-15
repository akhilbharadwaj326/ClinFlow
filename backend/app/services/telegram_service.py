"""
ClinFlow Telegram Bot Service
==============================

FLOW:
  Doctor sends a message (text or voice) to the Telegram bot
       ↓
  Telegram calls POST /api/telegram/webhook
       ↓
  telegram_service.py processes the update:
    - Text message   → normalize via AI → structure → store as document
    - Voice message  → download audio → transcribe via Whisper → normalize → structure → store
    - Photo          → download image  → OCR via Tesseract → structure → store
       ↓
  Bot replies with a confirmation + a link to the review workspace

REQUIRED ENV VARIABLES:
  TELEGRAM_BOT_TOKEN   — BotFather token
  TELEGRAM_WEBHOOK_URL — Public URL of your FastAPI server (e.g. Firebase Cloud Function URL)
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import httpx
from openai import OpenAI

from app.config import settings
from app.services.ai_service import normalize_telegram_message, run_full_pipeline
from app.services.ocr_service import extract_text_from_image

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}"

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# =============================================================================
# CORE ENTRY POINT
# =============================================================================

def handle_telegram_update(update: dict) -> dict:
    """
    Main dispatcher. Receives a raw Telegram Update dict and routes it to
    the correct handler based on message type.

    Returns a status dict for logging.
    """
    message = update.get("message") or update.get("channel_post")
    if not message:
        logger.debug("Telegram update has no message body. Ignoring.")
        return {"status": "ignored", "reason": "no_message"}

    chat_id  = message["chat"]["id"]
    msg_text = message.get("text") or message.get("caption")
    voice    = message.get("voice")
    photo    = message.get("photo")

    try:
        if photo:
            return _handle_photo(chat_id, photo)
        elif voice:
            return _handle_voice(chat_id, voice)
        elif msg_text:
            return _handle_text(chat_id, msg_text)
        else:
            _send_reply(chat_id, "ℹ️ ClinFlow only processes text, voice notes, or photos. Please send one of those.")
            return {"status": "ignored", "reason": "unsupported_type"}

    except Exception as exc:
        logger.exception("Telegram handler error for chat_id=%s: %s", chat_id, exc)
        _send_reply(chat_id, "⚠️ Something went wrong processing your message. Please try again or upload via the web app.")
        return {"status": "error", "error": str(exc)}


# =============================================================================
# HANDLERS
# =============================================================================

def _handle_text(chat_id: int, text: str) -> dict:
    """
    Process a plain text Telegram message.
    Normalizes it via AI, then runs the full clinical pipeline if clinical.
    """
    logger.info("Processing Telegram text message from chat_id=%s (%d chars).", chat_id, len(text))

    # Step 1: Normalize informal text
    norm_result = normalize_telegram_message(text)

    if not norm_result.get("is_clinical"):
        _send_reply(chat_id, "👋 Message received, but no clinical information was detected. If this was a patient note, please be more specific.")
        return {"status": "skipped", "reason": "not_clinical"}

    normalized_text = norm_result["normalized_text"]

    # Step 2: Run full AI pipeline
    result = run_full_pipeline(normalized_text)

    # Step 3: Confirm receipt
    _send_pipeline_confirmation(chat_id, result)

    return {
        "status": "processed",
        "source": "telegram_text",
        "confidence_score": result["confidence_score"],
        "normalized_text": normalized_text,
        "pipeline_result": result,
    }


def _handle_voice(chat_id: int, voice: dict) -> dict:
    """
    Download a Telegram voice note, transcribe via OpenAI Whisper,
    normalize, then run the clinical pipeline.
    """
    file_id = voice["file_id"]
    logger.info("Processing Telegram voice note from chat_id=%s (file_id=%s).", chat_id, file_id)

    _send_reply(chat_id, "🎙️ Voice note received. Transcribing...")

    # Step 1: Download audio from Telegram
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _download_telegram_file(file_id, tmpdir, suffix=".oga")

        # Step 2: Transcribe via Whisper
        transcript = _transcribe_audio(audio_path)
        logger.info("Whisper transcript (%d chars): %.200s", len(transcript), transcript)

    # Step 3: Normalize the transcript
    norm_result = normalize_telegram_message(transcript)

    if not norm_result.get("is_clinical"):
        _send_reply(chat_id, "🎙️ Voice note transcribed, but no clinical information was detected.")
        return {"status": "skipped", "reason": "not_clinical", "transcript": transcript}

    # Step 4: Run full AI pipeline
    result = run_full_pipeline(norm_result["normalized_text"])
    _send_pipeline_confirmation(chat_id, result)

    return {
        "status": "processed",
        "source": "telegram_voice",
        "transcript": transcript,
        "confidence_score": result["confidence_score"],
        "pipeline_result": result,
    }


def _handle_photo(chat_id: int, photos: list) -> dict:
    """
    Download the highest-resolution photo from Telegram,
    run Tesseract OCR on it, then run the clinical pipeline.
    """
    # Telegram sends photos as array of sizes; last is highest resolution
    best = photos[-1]
    file_id = best["file_id"]
    logger.info("Processing Telegram photo from chat_id=%s (file_id=%s).", chat_id, file_id)

    _send_reply(chat_id, "📷 Image received. Running OCR...")

    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = _download_telegram_file(file_id, tmpdir, suffix=".jpg")

        # Step 1: OCR
        ocr_text = extract_text_from_image(image_path)

    if not ocr_text.strip():
        _send_reply(chat_id, "⚠️ Could not extract any text from the image. Please ensure the photo is clear and well-lit.")
        return {"status": "error", "reason": "ocr_empty"}

    # Step 2: Run full AI pipeline on OCR text
    result = run_full_pipeline(ocr_text)
    _send_pipeline_confirmation(chat_id, result)

    return {
        "status": "processed",
        "source": "telegram_photo",
        "ocr_text": ocr_text,
        "confidence_score": result["confidence_score"],
        "pipeline_result": result,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _download_telegram_file(file_id: str, target_dir: str, suffix: str = "") -> str:
    """Downloads a Telegram file by file_id to a local temp path. Returns the path."""
    # Get file path from Telegram
    resp = httpx.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=20)
    resp.raise_for_status()
    file_path = resp.json()["result"]["file_path"]

    # Download the actual file
    file_resp = httpx.get(f"{TELEGRAM_FILE_API}/{file_path}", timeout=60)
    file_resp.raise_for_status()

    local_path = os.path.join(target_dir, f"telegram_file{suffix}")
    Path(local_path).write_bytes(file_resp.content)
    logger.debug("Downloaded Telegram file to: %s (%d bytes)", local_path, len(file_resp.content))
    return local_path


def _transcribe_audio(audio_path: str) -> str:
    """Sends an audio file to OpenAI Whisper for transcription."""
    with open(audio_path, "rb") as f:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="en",
        )
    return response.text.strip()


def _send_reply(chat_id: int, text: str) -> None:
    """Sends a reply message back to the Telegram user."""
    try:
        httpx.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to send Telegram reply to chat_id=%s: %s", chat_id, exc)


def _send_pipeline_confirmation(chat_id: int, result: dict) -> None:
    """Sends a structured confirmation back to the doctor after processing."""
    note = result["structured_note"]
    score = int(result["confidence_score"] * 100)
    missing_count = len(result.get("missing_fields", {}).get("missing_fields", []))

    diagnosis = note.get("diagnosis_assessment") or "Not identified"
    symptoms  = ", ".join(note.get("symptoms") or []) or "None documented"

    msg = (
        f"✅ Clinical note processed!\n\n"
        f"🩺 Assessment: {diagnosis}\n"
        f"💊 Symptoms: {symptoms}\n"
        f"📊 Completeness: {score}%\n"
        f"⚠️ Missing fields flagged: {missing_count}\n\n"
        f"👉 Open the ClinFlow web app to review, edit, and approve this note before it enters the patient record."
    )
    _send_reply(chat_id, msg)


# =============================================================================
# WEBHOOK REGISTRATION
# =============================================================================

def register_webhook(public_url: str) -> dict:
    """
    Registers the Telegram webhook with your FastAPI server's public URL.
    Call this once during deployment or from a setup script.

    Args:
      public_url: e.g. "https://your-firebase-function.run.app"
    """
    webhook_url = f"{public_url}/api/telegram/webhook"
    resp = httpx.post(
        f"{TELEGRAM_API}/setWebhook",
        json={"url": webhook_url, "allowed_updates": ["message", "channel_post"]},
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("ok"):
        logger.info("Telegram webhook registered: %s", webhook_url)
    else:
        logger.error("Telegram webhook registration failed: %s", result)
    return result

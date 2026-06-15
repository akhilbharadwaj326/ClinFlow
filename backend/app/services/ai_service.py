"""
ClinFlow AI Service — Prompts & Orchestration
==============================================

DESIGN PHILOSOPHY
-----------------
1. Grounded extraction only — AI never invents facts not in the source text.
2. Zero temperature — deterministic output, no creative drift.
3. JSON mode — structured, parseable responses; no markdown leakage.
4. Token efficiency — system prompts are tight; user prompts carry only what
   the model needs for that specific task.
5. Three separate specialist calls instead of one mega-prompt:
     a) structure_clinical_note  → extract & normalize
     b) detect_missing_fields    → quality review
     c) generate_handoff_summary → patient-safe narrative
6. max_tokens caps prevent runaway responses and cost overruns.
7. Retry with exponential backoff on transient OpenAI errors.
8. All token usage is logged for cost tracking.

CONTEXT WINDOW BUDGET (gpt-4o — 128k tokens)
---------------------------------------------
  STRUCTURE call:
    system prompt : ~200 tokens
    raw_text      : variable (max ~6,000 tokens enforced by truncation guard)
    schema hint   : ~150 tokens
    output        : ~500 tokens
    ─────────────────────────────
    Total budget  : ≤ 7,000 tokens per call

  MISSING FIELDS call:
    system prompt : ~150 tokens
    structured_note JSON : ~500 tokens
    output        : ~300 tokens
    ─────────────────────────────
    Total budget  : ≤ 1,000 tokens per call

  HANDOFF SUMMARY call:
    system prompt : ~150 tokens
    structured_note JSON : ~500 tokens
    output        : ~200 tokens
    ─────────────────────────────
    Total budget  : ≤ 1,000 tokens per call
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from openai import OpenAI, RateLimitError, APIError

from app.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ─── Constants ────────────────────────────────────────────────────────────────

MODEL = "gpt-4o"
MAX_RAW_TEXT_CHARS = 20_000   # ~5,000 tokens; hard guard against oversized inputs
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0        # seconds; doubles each retry


# =============================================================================
# SYSTEM PROMPTS
# Each prompt is a strict specialist. Short + role-defined = fewer tokens wasted.
# "You are X. Your ONLY job is Y. Strict rules." pattern keeps the model on task.
# =============================================================================

# ─── 1. Clinical Note Structuring ─────────────────────────────────────────────
STRUCTURE_SYSTEM_PROMPT = """\
You are a clinical documentation assistant. Your ONLY job is to extract and \
normalize medical information explicitly present in the provided source text.

STRICT RULES — no exceptions:
1. Extract ONLY information explicitly stated. Never infer or fabricate.
2. If a field is absent in the source, set it to null. Do not fill it.
3. For every extracted value, include the verbatim source phrase in \
source_references so a human can verify it.
4. Normalize medical terminology (e.g. "high BP" → "hypertension") only \
when the meaning is unambiguous.
5. Medications must include name, dose, and frequency exactly as stated; \
null any sub-field not mentioned.
6. Respond ONLY with valid JSON matching the exact schema provided. \
No markdown, no explanation."""

STRUCTURE_USER_PROMPT = """\
Extract structured clinical information from the source note below.
Return ONLY the JSON object — no markdown, no explanation.

Source note:
\"\"\"
{raw_text}
\"\"\"

Required JSON schema (null any field not found in the source):
{{
  "symptoms": ["string"] | null,
  "medical_history": ["string"] | null,
  "clinical_observations": ["string"] | null,
  "diagnosis_assessment": "string" | null,
  "medications": [
    {{"name": "string", "dose": "string | null", "frequency": "string | null"}}
  ] | null,
  "treatment_plan": "string" | null,
  "follow_up": "string" | null,
  "source_references": [
    {{"field": "string", "source_text": "string"}}
  ]
}}"""


# ─── 2. Missing Field Detection ────────────────────────────────────────────────
MISSING_FIELDS_SYSTEM_PROMPT = """\
You are a clinical quality reviewer. Identify clinically important fields \
that are absent from the provided structured note.

STRICT RULES:
1. Only flag fields that are genuinely absent — not merely brief.
2. Assign severity: "high" (patient safety risk), "medium" (care quality risk), \
or "low" (documentation completeness).
3. State clearly WHY each missing field matters for this patient's care.
4. Do NOT suggest content to fill in. Only identify the gap.
5. Respond ONLY with valid JSON. No markdown, no explanation."""

MISSING_FIELDS_USER_PROMPT = """\
Review the structured clinical note below. Identify missing fields.
Return ONLY the JSON object.

Structured note:
{structured_note}

Required JSON schema:
{{
  "missing_fields": [
    {{
      "field": "string",
      "reason": "string",
      "severity": "high" | "medium" | "low"
    }}
  ]
}}"""


# ─── 3. Safe Handoff Summary ───────────────────────────────────────────────────
HANDOFF_SYSTEM_PROMPT = """\
You are a clinical handoff assistant. Write a concise, plain-English summary \
that a doctor can read in under 60 seconds to understand a patient's case \
and safely continue their care.

STRICT RULES:
1. Use ONLY information from the structured note provided.
2. Never invent, infer, or add any clinical fact.
3. If a field is null or absent, explicitly state it \
(e.g. "No follow-up plan was documented").
4. Structure the output in this order: \
patient presentation → history → current assessment → medications → \
treatment plan → follow-up → gaps flagged.
5. Keep sentences short. Avoid unnecessary jargon.
6. Maximum 150 words."""

HANDOFF_USER_PROMPT = """\
Write a safe handoff summary for the following patient.

Patient name: {patient_name}
Structured note:
{structured_note}

Return a single plain-text paragraph (max 150 words). No JSON, no markdown."""


# ─── 4. Telegram Message Normalization ────────────────────────────────────────
TELEGRAM_NORMALIZE_SYSTEM_PROMPT = """\
You are a medical scribe assistant. A doctor sent a voice note transcription \
or informal text message about a patient encounter via Telegram. \
Your ONLY job is to identify whether this message contains clinical information \
and, if so, return a cleaned, plain-text normalized version suitable for \
structured clinical extraction.

STRICT RULES:
1. Remove informal language, filler words, and Telegram-specific artifacts \
(emojis, stickers references, "ok", "thanks", etc.).
2. Preserve ALL medical content exactly as stated. Do not rephrase diagnoses, \
medications, or observations.
3. If the message contains NO clinical information (e.g. it's just a greeting), \
return {{"is_clinical": false, "normalized_text": null}}.
4. If it does contain clinical content, return \
{{"is_clinical": true, "normalized_text": "cleaned string"}}.
5. Respond ONLY with valid JSON. No markdown, no explanation."""

TELEGRAM_NORMALIZE_USER_PROMPT = """\
Normalize the following Telegram message for clinical extraction.
Return ONLY the JSON object.

Message:
\"\"\"
{telegram_text}
\"\"\"

Required JSON schema:
{{
  "is_clinical": true | false,
  "normalized_text": "string" | null
}}"""


# =============================================================================
# INTERNAL UTILITIES
# =============================================================================

def _truncate_text(text: str, max_chars: int = MAX_RAW_TEXT_CHARS) -> str:
    """Truncates oversized text to avoid token overruns. Logs a warning if cut."""
    if len(text) > max_chars:
        logger.warning(
            "Input text truncated from %d to %d characters to stay within token budget.",
            len(text), max_chars,
        )
        return text[:max_chars] + "\n\n[NOTE: Source text was truncated due to length.]"
    return text


def _call_openai_with_retry(
    messages: list[dict],
    response_format: Optional[dict] = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """
    Wraps an OpenAI chat completion call with retry logic.
    Returns the raw string content of the first choice.
    Logs token usage for cost tracking.
    """
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            kwargs = dict(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(**kwargs)

            # Log token usage
            usage = response.usage
            logger.info(
                "OpenAI call — prompt_tokens=%d, completion_tokens=%d, total=%d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )
            return response.choices[0].message.content

        except RateLimitError as exc:
            last_exc = exc
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("Rate limited by OpenAI. Retrying in %.1fs (attempt %d/%d).", delay, attempt + 1, MAX_RETRIES)
            time.sleep(delay)

        except APIError as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("OpenAI API error: %s. Retrying in %.1fs.", exc, delay)
                time.sleep(delay)

    raise RuntimeError(f"OpenAI call failed after {MAX_RETRIES} attempts: {last_exc}") from last_exc


# =============================================================================
# PUBLIC SERVICE FUNCTIONS
# =============================================================================

def structure_clinical_note(raw_text: str) -> dict:
    """
    STEP 1 — Extract and normalize structured clinical data from raw text.

    Input:  Free-form text (from OCR, manual entry, or Telegram normalization).
    Output: Structured dict matching the clinical note JSON schema.

    Token budget: ~7,000 tokens. Text is truncated if input is too long.
    """
    safe_text = _truncate_text(raw_text)

    content = _call_openai_with_retry(
        messages=[
            {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
            {"role": "user",   "content": STRUCTURE_USER_PROMPT.format(raw_text=safe_text)},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
        temperature=0.0,
    )

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse structured note JSON: %s\nRaw content: %s", exc, content)
        raise ValueError(f"AI returned invalid JSON for structure extraction: {exc}") from exc


def detect_missing_fields(structured_note: dict) -> dict:
    """
    STEP 2 — Identify clinically important fields absent from the structured note.

    Input:  Structured note dict (output of structure_clinical_note).
    Output: Dict with a 'missing_fields' list, each with field/reason/severity.

    Token budget: ~1,000 tokens.
    """
    content = _call_openai_with_retry(
        messages=[
            {"role": "system", "content": MISSING_FIELDS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": MISSING_FIELDS_USER_PROMPT.format(
                    structured_note=json.dumps(structured_note, indent=2)
                ),
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=500,
        temperature=0.0,
    )

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse missing fields JSON: %s\nRaw content: %s", exc, content)
        raise ValueError(f"AI returned invalid JSON for missing fields: {exc}") from exc


def generate_handoff_summary(patient_name: str, structured_note: dict) -> str:
    """
    STEP 3 — Generate a doctor-readable safe handoff summary (≤150 words).

    Input:  Patient name and approved structured note dict.
    Output: Plain-text paragraph summarizing the case for the next clinician.

    Token budget: ~1,000 tokens.
    """
    content = _call_openai_with_retry(
        messages=[
            {"role": "system", "content": HANDOFF_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": HANDOFF_USER_PROMPT.format(
                    patient_name=patient_name,
                    structured_note=json.dumps(structured_note, indent=2),
                ),
            },
        ],
        response_format=None,   # Plain text, not JSON
        max_tokens=300,
        temperature=0.0,
    )
    return content.strip()


def normalize_telegram_message(telegram_text: str) -> dict:
    """
    TELEGRAM INGESTION — Clean an informal doctor Telegram message into
    structured-extraction-ready plain text.

    Input:  Raw Telegram message string (voice note transcript or typed text).
    Output: Dict:
              is_clinical: bool  — False means skip, do not store as a clinical note.
              normalized_text: str | None — Cleaned text ready for structure_clinical_note().

    Token budget: ~500 tokens.
    """
    safe_text = _truncate_text(telegram_text, max_chars=5_000)

    content = _call_openai_with_retry(
        messages=[
            {"role": "system", "content": TELEGRAM_NORMALIZE_SYSTEM_PROMPT},
            {"role": "user",   "content": TELEGRAM_NORMALIZE_USER_PROMPT.format(telegram_text=safe_text)},
        ],
        response_format={"type": "json_object"},
        max_tokens=400,
        temperature=0.0,
    )

    try:
        result = json.loads(content)
        if "is_clinical" not in result:
            raise ValueError("Missing 'is_clinical' key in Telegram normalization response.")
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Telegram normalization JSON: %s\nRaw content: %s", exc, content)
        raise ValueError(f"AI returned invalid JSON for Telegram normalization: {exc}") from exc


def run_full_pipeline(raw_text: str) -> dict:
    """
    Convenience orchestrator: runs all three AI steps in sequence and returns
    a single combined result dict.

    Steps:
      1. structure_clinical_note()
      2. detect_missing_fields()
      3. (handoff is generated later, only after doctor approval)

    Returns:
      {
        "structured_note": {...},
        "missing_fields":  {...},
        "confidence_score": float  # ratio of non-null fields to total fields
      }
    """
    structured = structure_clinical_note(raw_text)
    missing    = detect_missing_fields(structured)

    # Compute a simple completeness ratio as the confidence score
    core_fields = [
        "symptoms", "medical_history", "clinical_observations",
        "diagnosis_assessment", "medications", "treatment_plan", "follow_up",
    ]
    filled = sum(1 for f in core_fields if structured.get(f) is not None)
    confidence = round(filled / len(core_fields), 3)

    return {
        "structured_note": structured,
        "missing_fields": missing,
        "confidence_score": confidence,
    }

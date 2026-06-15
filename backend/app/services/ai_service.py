import json
from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ─── Prompt Templates ────────────────────────────────────────────────────────

STRUCTURE_SYSTEM_PROMPT = """
You are a clinical documentation assistant. Your only job is to extract and 
organize medical information that is explicitly present in the source text.

STRICT RULES — you MUST follow these without exception:
1. Only extract information that is explicitly stated in the source text.
2. Never infer, guess, or fabricate any medical detail.
3. If a field is not found in the source, set it to null — do NOT fill it.
4. For every extracted value, include the exact source phrase in source_references.
5. Never add symptoms, medications, diagnoses, or follow-up plans not in the text.

Respond ONLY with valid JSON in the exact schema provided.
"""

STRUCTURE_USER_PROMPT = """
Extract structured clinical information from the following note.
Return ONLY the JSON — no explanation, no markdown.

Source note:
\"\"\"
{raw_text}
\"\"\"

Required JSON schema:
{{
  "symptoms": ["string"] or null,
  "medical_history": ["string"] or null,
  "clinical_observations": ["string"] or null,
  "diagnosis_assessment": "string" or null,
  "medications": [
    {{"name": "string", "dose": "string", "frequency": "string"}}
  ] or null,
  "treatment_plan": "string" or null,
  "follow_up": "string" or null,
  "source_references": [
    {{"field": "string", "source_text": "string"}}
  ]
}}
"""

MISSING_INFO_SYSTEM_PROMPT = """
You are a clinical quality reviewer. Identify clinically important information 
that appears to be missing from the provided structured note.

STRICT RULES:
1. Only flag information that is genuinely absent — not just brief.
2. Assign severity: "high", "medium", or "low".
3. Explain clearly WHY the missing field matters for patient care.
4. Do NOT suggest adding information — only flag what is missing.

Respond ONLY with valid JSON.
"""

MISSING_INFO_USER_PROMPT = """
Review this structured clinical note and identify missing information.
Return ONLY the JSON.

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
}}
"""

HANDOFF_SYSTEM_PROMPT = """
You are a clinical handoff assistant. Write a concise, plain-English paragraph 
that a doctor can read in under 60 seconds to understand a patient's history 
and safely continue their care.

STRICT RULES:
1. Use ONLY information from the structured note provided.
2. Never invent or infer clinical facts.
3. If a field is null or missing, note it explicitly (e.g., "No follow-up plan was documented").
4. Keep the summary factual, clear, and free of medical jargon where possible.
"""

HANDOFF_USER_PROMPT = """
Write a safe handoff summary for the following patient record.

Patient Name: {patient_name}
Structured Note:
{structured_note}

Return a single plain-text paragraph.
"""


# ─── Service Functions ────────────────────────────────────────────────────────

def structure_clinical_note(raw_text: str) -> dict:
    """
    Sends raw OCR text to OpenAI and returns a structured clinical JSON.
    All outputs are grounded in the source text.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": STRUCTURE_USER_PROMPT.format(raw_text=raw_text)},
        ],
        temperature=0,          # Zero temperature = deterministic, no creativity
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def detect_missing_information(structured_note: dict) -> dict:
    """
    Runs a second OpenAI pass to identify clinically important missing fields.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": MISSING_INFO_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": MISSING_INFO_USER_PROMPT.format(
                    structured_note=json.dumps(structured_note, indent=2)
                ),
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def generate_handoff_summary(patient_name: str, structured_note: dict) -> str:
    """
    Generates a plain-English safe handoff summary paragraph.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
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
        temperature=0,
    )
    return response.choices[0].message.content.strip()

import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr


# ─── Shared ───────────────────────────────────────────────────────────────────
class UUIDMixin(BaseModel):
    id: uuid.UUID

    class Config:
        from_attributes = True


# ─── Clinic ───────────────────────────────────────────────────────────────────
class ClinicCreate(BaseModel):
    name: str


class ClinicOut(UUIDMixin):
    name: str
    created_at: datetime


# ─── User ─────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    role: str = "doctor"
    clinic_id: uuid.UUID


class UserOut(UUIDMixin):
    full_name: str
    email: str
    role: str
    clinic_id: uuid.UUID
    created_at: datetime


# ─── Patient ──────────────────────────────────────────────────────────────────
class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None


class PatientOut(UUIDMixin):
    full_name: str
    date_of_birth: Optional[str]
    gender: Optional[str]
    contact_number: Optional[str]
    clinic_id: uuid.UUID
    created_at: datetime


# ─── Document ─────────────────────────────────────────────────────────────────
class DocumentOut(UUIDMixin):
    patient_id: uuid.UUID
    source_type: str
    storage_path: Optional[str]
    raw_ocr_text: Optional[str]
    created_at: datetime


# ─── Structured Note ──────────────────────────────────────────────────────────
class NoteApprovalRequest(BaseModel):
    approved_data: dict


class StructuredNoteOut(UUIDMixin):
    document_id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    ai_output: Optional[Any]
    approved_data: Optional[Any]
    missing_fields: Optional[Any]
    confidence_score: Optional[float]
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime


# ─── Handoff ──────────────────────────────────────────────────────────────────
class HandoffSummary(BaseModel):
    patient_name: str
    summary: str
    missing_fields_count: int
    last_visit: Optional[datetime]

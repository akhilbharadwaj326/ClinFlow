import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Enum, Text, Float, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    owner = "owner"
    doctor = "doctor"
    assistant = "assistant"


class DocumentSourceType(str, enum.Enum):
    image = "image"
    pdf = "pdf"
    telegram = "telegram"
    manual = "manual"


class NoteStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


# ─────────────────────────────────────────────────────────────────────────────
class Clinic(Base):
    """Multi-tenant: every record belongs to exactly one clinic."""
    __tablename__ = "clinics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")


# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    """Clinic staff: owner, doctor, or assistant."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.doctor)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="users")


# ─────────────────────────────────────────────────────────────────────────────
class Patient(Base):
    """Core patient record — owned by a single clinic."""
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(String(20))
    gender = Column(String(20))
    contact_number = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="patients")
    documents = relationship("Document", back_populates="patient")
    structured_notes = relationship("StructuredNote", back_populates="patient")


# ─────────────────────────────────────────────────────────────────────────────
class Document(Base):
    """
    Immutable raw source — never modified after creation.
    Stores the original file path and extracted OCR text.
    """
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    source_type = Column(Enum(DocumentSourceType), nullable=False)
    storage_path = Column(Text)          # Local path or Supabase Storage path
    raw_ocr_text = Column(Text)          # Set after OCR; never changed again
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="documents")
    structured_notes = relationship("StructuredNote", back_populates="document")


# ─────────────────────────────────────────────────────────────────────────────
class StructuredNote(Base):
    """
    AI-generated structured output linked to a source Document.
    Status transitions: pending_review → approved | rejected.
    The approved_data column holds the doctor-edited final version.
    """
    __tablename__ = "structured_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    status = Column(Enum(NoteStatus), default=NoteStatus.pending_review, nullable=False)
    ai_output = Column(JSON)             # Raw structured extraction from OpenAI
    approved_data = Column(JSON)         # Doctor-edited, approved version
    missing_fields = Column(JSON)        # Flagged gaps from missing info detection
    confidence_score = Column(Float)     # 0.0 – 1.0
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="structured_notes")
    patient = relationship("Patient", back_populates="structured_notes")


# ─────────────────────────────────────────────────────────────────────────────
class AuditLog(Base):
    """
    Append-only log for all significant actions.
    Supports compliance, traceability, and debugging.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)   # e.g. upload, ocr_run, approved
    entity_type = Column(String(100))              # e.g. document, structured_note
    entity_id = Column(UUID(as_uuid=True))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

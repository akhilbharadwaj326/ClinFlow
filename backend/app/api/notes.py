import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.models import StructuredNote, Patient, NoteStatus
from app.schemas.schemas import StructuredNoteOut, NoteApprovalRequest, HandoffSummary
from app.services import ai_service, audit_service

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("/patient/{patient_id}", response_model=List[StructuredNoteOut])
def get_patient_notes(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Returns all structured notes for a patient (approved and pending)."""
    clinic_id = current_user.get("clinic_id")
    return db.query(StructuredNote).filter(
        StructuredNote.patient_id == patient_id,
        StructuredNote.clinic_id == clinic_id,
    ).order_by(StructuredNote.created_at.desc()).all()


@router.patch("/{note_id}/approve", response_model=StructuredNoteOut)
def approve_note(
    note_id: uuid.UUID,
    payload: NoteApprovalRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Doctor reviews AI output, makes edits, and approves.
    The approved_data becomes the trusted clinical record.
    Original ai_output is preserved for traceability.
    """
    clinic_id = current_user.get("clinic_id")
    note = db.query(StructuredNote).filter(
        StructuredNote.id == note_id, StructuredNote.clinic_id == clinic_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    note.status = NoteStatus.approved
    note.approved_data = payload.approved_data
    note.reviewed_by = current_user.get("sub")
    note.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(note)

    audit_service.log_action(
        db, action="approved", clinic_id=clinic_id,
        user_id=current_user.get("sub"),
        entity_type="structured_note", entity_id=note.id,
    )
    return note


@router.patch("/{note_id}/reject", response_model=StructuredNoteOut)
def reject_note(
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Doctor rejects the AI output. The note is flagged but preserved."""
    clinic_id = current_user.get("clinic_id")
    note = db.query(StructuredNote).filter(
        StructuredNote.id == note_id, StructuredNote.clinic_id == clinic_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    note.status = NoteStatus.rejected
    note.reviewed_by = current_user.get("sub")
    note.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(note)

    audit_service.log_action(
        db, action="rejected", clinic_id=clinic_id,
        user_id=current_user.get("sub"),
        entity_type="structured_note", entity_id=note.id,
    )
    return note


@router.get("/patient/{patient_id}/handoff", response_model=HandoffSummary)
def get_handoff_summary(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generates a Safe Handoff Summary for a patient based on their latest
    approved structured note.
    """
    clinic_id = current_user.get("clinic_id")

    patient = db.query(Patient).filter(
        Patient.id == patient_id, Patient.clinic_id == clinic_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    latest_note = db.query(StructuredNote).filter(
        StructuredNote.patient_id == patient_id,
        StructuredNote.clinic_id == clinic_id,
        StructuredNote.status == NoteStatus.approved,
    ).order_by(StructuredNote.reviewed_at.desc()).first()

    if not latest_note:
        raise HTTPException(
            status_code=404,
            detail="No approved notes found for this patient.",
        )

    summary_text = ai_service.generate_handoff_summary(
        patient_name=patient.full_name,
        structured_note=latest_note.approved_data or latest_note.ai_output,
    )

    missing_count = len(latest_note.missing_fields or [])

    return HandoffSummary(
        patient_name=patient.full_name,
        summary=summary_text,
        missing_fields_count=missing_count,
        last_visit=latest_note.reviewed_at,
    )

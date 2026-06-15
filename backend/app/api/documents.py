import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.models import Document, Patient, StructuredNote, DocumentSourceType, NoteStatus
from app.schemas.schemas import DocumentOut
from app.services import storage_service, ocr_service, ai_service, audit_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    patient_id: uuid.UUID = Form(...),
    source_type: str = Form(...),
    manual_text: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Uploads a clinical note (image/PDF or manual text) for a patient.
    The raw file is stored immediately; processing is triggered separately.
    """
    clinic_id = current_user.get("clinic_id")

    # Verify patient belongs to this clinic (prevent IDOR)
    patient = db.query(Patient).filter(
        Patient.id == patient_id, Patient.clinic_id == clinic_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    storage_path = None
    raw_ocr_text = None

    if source_type == "manual" and manual_text:
        raw_ocr_text = ocr_service.extract_text_from_manual(manual_text)
    elif file:
        storage_path = storage_service.save_file_locally(file, str(patient_id))

    doc = Document(
        patient_id=patient_id,
        clinic_id=clinic_id,
        uploaded_by=current_user.get("sub"),
        source_type=DocumentSourceType(source_type),
        storage_path=storage_path,
        raw_ocr_text=raw_ocr_text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    audit_service.log_action(
        db,
        action="upload",
        clinic_id=clinic_id,
        user_id=current_user.get("sub"),
        entity_type="document",
        entity_id=doc.id,
    )
    return doc


@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED)
def process_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Triggers OCR (if needed) and AI structuring for a document.
    Creates a StructuredNote with status=pending_review.
    """
    clinic_id = current_user.get("clinic_id")
    doc = db.query(Document).filter(
        Document.id == document_id, Document.clinic_id == clinic_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Step 1: OCR (if file not yet processed)
    if not doc.raw_ocr_text and doc.storage_path:
        try:
            raw_text = ocr_service.extract_text_from_image(doc.storage_path)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        doc.raw_ocr_text = raw_text
        db.commit()
        audit_service.log_action(
            db, action="ocr_run", clinic_id=clinic_id,
            entity_type="document", entity_id=doc.id
        )

    if not doc.raw_ocr_text:
        raise HTTPException(status_code=422, detail="No text available to process.")

    # Step 2: AI structuring
    ai_output = ai_service.structure_clinical_note(doc.raw_ocr_text)

    # Step 3: Missing information detection
    missing = ai_service.detect_missing_information(ai_output)

    # Step 4: Save as pending_review structured note
    note = StructuredNote(
        document_id=doc.id,
        patient_id=doc.patient_id,
        clinic_id=clinic_id,
        status=NoteStatus.pending_review,
        ai_output=ai_output,
        missing_fields=missing.get("missing_fields", []),
        confidence_score=0.0,   # Can be computed from source_references in future
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    audit_service.log_action(
        db, action="ai_structure", clinic_id=clinic_id,
        entity_type="structured_note", entity_id=note.id
    )
    return {"message": "Processing complete.", "structured_note_id": str(note.id)}

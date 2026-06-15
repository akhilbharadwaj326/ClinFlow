import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.models import Patient
from app.schemas.schemas import PatientCreate, PatientOut

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/", response_model=List[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Returns all patients belonging to the authenticated user's clinic."""
    clinic_id = current_user.get("clinic_id")
    if not clinic_id:
        raise HTTPException(status_code=403, detail="Clinic context missing from token.")
    return db.query(Patient).filter(Patient.clinic_id == clinic_id).all()


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    clinic_id = current_user.get("clinic_id")
    patient = db.query(Patient).filter(
        Patient.id == patient_id, Patient.clinic_id == clinic_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


@router.post("/", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    clinic_id = current_user.get("clinic_id")
    if not clinic_id:
        raise HTTPException(status_code=403, detail="Clinic context missing.")
    patient = Patient(clinic_id=clinic_id, **payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

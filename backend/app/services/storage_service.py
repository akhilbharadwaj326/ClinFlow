import os
import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.config import settings


def save_file_locally(file: UploadFile, patient_id: str) -> str:
    """
    Saves an uploaded file to the local filesystem.
    Returns the relative storage path.
    """
    upload_dir = Path(settings.LOCAL_STORAGE_PATH) / patient_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(file.filename).suffix if file.filename else ".bin"
    filename = f"{uuid.uuid4()}{extension}"
    file_path = upload_dir / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return str(file_path)


def get_file_path(storage_path: str) -> str:
    """Returns the absolute path for a stored file."""
    return os.path.abspath(storage_path)

from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import AuditLog
import uuid


def log_action(
    db: Session,
    *,
    action: str,
    clinic_id: uuid.UUID,
    user_id: uuid.UUID = None,
    entity_type: str = None,
    entity_id: uuid.UUID = None,
    metadata: dict = None,
) -> None:
    """Appends an immutable audit log entry. Never modifies existing records."""
    entry = AuditLog(
        clinic_id=clinic_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()

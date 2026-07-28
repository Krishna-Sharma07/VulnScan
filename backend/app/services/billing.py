import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.scan_job import ScanJob


def scans_used_this_month(db: Session, user_id: uuid.UUID) -> int:
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(ScanJob)
        .filter(ScanJob.user_id == user_id, ScanJob.created_at >= month_start)
        .count()
    )

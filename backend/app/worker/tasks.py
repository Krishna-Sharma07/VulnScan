import uuid
from datetime import datetime

from app.db.session import SessionLocal
from app.models.scan_job import ScanJob, ScanStatus
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.run_scan")
def run_scan(scan_job_id: str) -> None:
    """Executed by a Celery worker process, not the API process.
    Currently a stub: marks the job running, then completed, with no
    real scanning yet. This will be replaced with actual container
    orchestration (launch scanner image, run ZAP, collect findings)."""
    db = SessionLocal()
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(scan_job_id)).first()
        if scan_job is None:
            return

        scan_job.status = ScanStatus.running
        scan_job.started_at = datetime.utcnow()
        db.commit()

        # TODO: replace with real Docker container orchestration + ZAP scan.

        scan_job.status = ScanStatus.completed
        scan_job.finished_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.finding import Finding
from app.models.scan_job import ScanJob, ScanStatus
from app.services.pdf_report import generate_pdf_report
from app.services.scanner import ScanExecutionError, run_zap_scan
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.run_scan")
def run_scan(scan_job_id: str) -> None:
    """Executed by a Celery worker process, not the API process. Launches a
    ZAP scanner container against the job's target, parses the results into
    Finding rows, and updates the job's status."""
    db = SessionLocal()
    try:
        scan_job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(scan_job_id)).first()
        if scan_job is None:
            return

        scan_job.status = ScanStatus.running
        scan_job.started_at = datetime.utcnow()
        db.commit()

        try:
            container_id, findings = run_zap_scan(scan_job.target_url, scan_job.scan_type.value)
        except ScanExecutionError:
            scan_job.status = ScanStatus.failed
            scan_job.finished_at = datetime.utcnow()
            db.commit()
            return

        scan_job.container_id = container_id
        for finding in findings:
            db.add(Finding(scan_job_id=scan_job.id, **finding))

        scan_job.status = ScanStatus.completed
        scan_job.finished_at = datetime.utcnow()

        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = reports_dir / f"{scan_job.id}.pdf"
            generate_pdf_report(scan_job, findings, str(pdf_path))
            scan_job.report_path = str(pdf_path)
        except Exception as exc:
            # A report-rendering bug shouldn't take down an otherwise-successful
            # scan - the findings are already safely in the DB either way.
            print(f"PDF generation failed for scan {scan_job.id}: {exc}")

        db.commit()
    finally:
        db.close()

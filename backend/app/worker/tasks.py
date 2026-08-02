import uuid
from datetime import datetime
from pathlib import Path

from cryptography.fernet import InvalidToken

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.db.session import SessionLocal
from app.models.code_finding import CodeFinding
from app.models.code_scan_job import CodeScanJob
from app.models.finding import Finding
from app.models.scan_job import ScanJob, ScanStatus, ScanType
from app.services.code_scanner import run_code_scan
from app.services.pdf_report import generate_code_pdf_report, generate_pdf_report
from app.services.scanner import ScanExecutionError, run_sqlmap_scan, run_zap_scan
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

        if scan_job.scan_type == ScanType.aggressive:
            try:
                cookie = decrypt_secret(scan_job.domain.auth_cookie) if scan_job.domain.auth_cookie else None
                findings += run_sqlmap_scan(scan_job.target_url, cookie=cookie)
            except (ScanExecutionError, InvalidToken) as exc:
                # sqlmap is an addition on top of the ZAP scan above, which
                # already succeeded - a broken/timed-out sqlmap run, or a
                # cookie that fails to decrypt (e.g. AUTH_COOKIE_ENCRYPTION_KEY
                # rotated since it was set), shouldn't throw away findings ZAP
                # already found, so this only logs and continues rather than
                # marking the whole job failed.
                print(f"sqlmap scan failed for scan {scan_job.id}: {exc!r}")

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


@celery_app.task(name="app.worker.tasks.run_code_scan")
def run_code_scan_task(code_scan_job_id: str) -> None:
    """Executed by a Celery worker process. Launches the bandit/safety
    scanner container against an uploaded code archive, parses the results
    into CodeFinding rows, and updates the job's status - the code-upload
    counterpart to run_scan above."""
    db = SessionLocal()
    try:
        code_scan_job = (
            db.query(CodeScanJob).filter(CodeScanJob.id == uuid.UUID(code_scan_job_id)).first()
        )
        if code_scan_job is None:
            return

        code_scan_job.status = ScanStatus.running
        code_scan_job.started_at = datetime.utcnow()
        db.commit()

        try:
            zip_bytes = Path(code_scan_job.upload_path).read_bytes()
            container_id, findings = run_code_scan(zip_bytes)
        except (ScanExecutionError, OSError):
            code_scan_job.status = ScanStatus.failed
            code_scan_job.finished_at = datetime.utcnow()
            db.commit()
            return

        code_scan_job.container_id = container_id

        for finding in findings:
            db.add(CodeFinding(code_scan_job_id=code_scan_job.id, **finding))

        code_scan_job.status = ScanStatus.completed
        code_scan_job.finished_at = datetime.utcnow()

        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = reports_dir / f"code-{code_scan_job.id}.pdf"
            generate_code_pdf_report(code_scan_job, findings, str(pdf_path))
            code_scan_job.report_path = str(pdf_path)
        except Exception as exc:
            print(f"PDF generation failed for code scan {code_scan_job.id}: {exc}")

        db.commit()

        try:
            Path(code_scan_job.upload_path).unlink(missing_ok=True)
        except OSError:
            pass
    finally:
        db.close()

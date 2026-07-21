import os
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.domain import Domain
from app.models.scan_job import ScanJob
from app.models.user import User
from app.schemas.scan import ScanCreate, ScanJobOut, ScanReportOut
from app.worker.tasks import run_scan

router = APIRouter(prefix="/api", tags=["scans"])


@router.post("/scan", response_model=ScanJobOut, status_code=status.HTTP_201_CREATED)
def create_scan(
    payload: ScanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == payload.domain_id, Domain.user_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if not domain.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domain is not verified. Complete DNS verification before scanning it.",
        )

    parsed_target = urlparse(payload.target_url)
    if parsed_target.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_url must be an http:// or https:// URL",
        )
    if parsed_target.hostname != domain.hostname:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"target_url host must exactly match the verified domain ({domain.hostname})",
        )

    scan_job = ScanJob(
        user_id=current_user.id,
        domain_id=domain.id,
        target_url=payload.target_url,
        scan_type=payload.scan_type,
    )
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)

    run_scan.delay(str(scan_job.id))

    return scan_job


@router.get("/history", response_model=list[ScanJobOut])
def scan_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(ScanJob)
        .filter(ScanJob.user_id == current_user.id)
        .order_by(ScanJob.created_at.desc())
        .all()
    )


@router.get("/reports/{scan_job_id}", response_model=ScanReportOut)
def get_report(
    scan_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan_job = (
        db.query(ScanJob)
        .filter(ScanJob.id == scan_job_id, ScanJob.user_id == current_user.id)
        .first()
    )
    if scan_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan_job


@router.get("/reports/{scan_job_id}/pdf")
def download_report_pdf(
    scan_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan_job = (
        db.query(ScanJob)
        .filter(ScanJob.id == scan_job_id, ScanJob.user_id == current_user.id)
        .first()
    )
    if scan_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    if not scan_job.report_path or not os.path.exists(scan_job.report_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF report not available")

    return FileResponse(
        scan_job.report_path,
        media_type="application/pdf",
        filename=f"vulnscan-report-{scan_job.id}.pdf",
    )

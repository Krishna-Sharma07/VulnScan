import uuid

from fastapi import APIRouter, Depends, HTTPException, status
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

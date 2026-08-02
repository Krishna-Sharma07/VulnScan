import io
import os
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.plans import limits_for
from app.db.session import get_db
from app.models.code_scan_job import CodeScanJob
from app.models.user import User
from app.schemas.code_scan import CodeScanJobOut, CodeScanReportOut
from app.services.billing import scans_used_this_month
from app.worker.tasks import run_code_scan_task

router = APIRouter(prefix="/api/code-scans", tags=["code-scans"])


@router.post("", response_model=CodeScanJobOut, status_code=status.HTTP_201_CREATED)
async def create_code_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limits = limits_for(current_user.plan)
    if limits.monthly_scan_limit is not None:
        used = scans_used_this_month(db, current_user.id)
        if used >= limits.monthly_scan_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Monthly scan limit reached ({limits.monthly_scan_limit}/month on the "
                    "free plan). Upgrade on the Billing page for unlimited scans."
                ),
            )

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only .zip archives are accepted"
        )

    contents = await file.read()
    if len(contents) > settings.code_scan_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload exceeds the {settings.code_scan_max_upload_bytes // (1024 * 1024)}MB limit",
        )
    # Reject anything that isn't actually a valid zip before it ever reaches
    # a container - a mislabeled/corrupt upload should fail fast here rather
    # than surface as an opaque scan failure later.
    if not zipfile.is_zipfile(io.BytesIO(contents)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid zip archive"
        )

    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    code_scan_id = uuid.uuid4()
    upload_path = uploads_dir / f"{code_scan_id}.zip"
    upload_path.write_bytes(contents)

    code_scan_job = CodeScanJob(
        id=code_scan_id,
        user_id=current_user.id,
        filename=file.filename,
        upload_path=str(upload_path),
    )
    db.add(code_scan_job)
    db.commit()
    db.refresh(code_scan_job)

    run_code_scan_task.delay(str(code_scan_job.id))

    return code_scan_job


@router.get("", response_model=list[CodeScanJobOut])
def code_scan_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(CodeScanJob)
        .filter(CodeScanJob.user_id == current_user.id)
        .order_by(CodeScanJob.created_at.desc())
        .all()
    )


@router.get("/{code_scan_job_id}", response_model=CodeScanReportOut)
def get_code_scan(
    code_scan_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code_scan_job = (
        db.query(CodeScanJob)
        .filter(CodeScanJob.id == code_scan_job_id, CodeScanJob.user_id == current_user.id)
        .first()
    )
    if code_scan_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")
    return code_scan_job


@router.get("/{code_scan_job_id}/pdf")
def download_code_scan_pdf(
    code_scan_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code_scan_job = (
        db.query(CodeScanJob)
        .filter(CodeScanJob.id == code_scan_job_id, CodeScanJob.user_id == current_user.id)
        .first()
    )
    if code_scan_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code scan not found")
    if not code_scan_job.report_path or not os.path.exists(code_scan_job.report_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF report not available")

    return FileResponse(
        code_scan_job.report_path,
        media_type="application/pdf",
        filename=f"vulnscan-code-report-{code_scan_job.id}.pdf",
    )

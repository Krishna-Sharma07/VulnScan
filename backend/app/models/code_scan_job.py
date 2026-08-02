import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.scan_job import ScanStatus


class CodeScanJob(Base):
    """A static-analysis scan of an uploaded code archive - the "code repos"
    input mode from the original spec, distinct from ScanJob's live-URL
    scanning. No domain/SSRF concerns here since nothing is fetched over the
    network: bandit and safety only read the files, they never execute them.
    Reuses ScanStatus (pending/running/completed/failed) from scan_job.py
    rather than defining an identical second enum."""

    __tablename__ = "code_scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)  # original upload filename, for display only
    upload_path = Column(String, nullable=False)  # where the .zip was spooled on disk
    status = Column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    container_id = Column(String, nullable=True)
    report_path = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    findings = relationship("CodeFinding", back_populates="code_scan_job", cascade="all, delete-orphan")

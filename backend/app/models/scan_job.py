import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class ScanType(str, enum.Enum):
    baseline = "baseline"      # passive/light active checks only, safe default
    aggressive = "aggressive"  # includes sqlmap etc., opt-in only


class ScanStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    target_url = Column(String, nullable=False)
    scan_type = Column(Enum(ScanType), default=ScanType.baseline, nullable=False)
    status = Column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    container_id = Column(String, nullable=True)
    report_path = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    domain = relationship("Domain", back_populates="scan_jobs")
    findings = relationship("Finding", back_populates="scan_job", cascade="all, delete-orphan")

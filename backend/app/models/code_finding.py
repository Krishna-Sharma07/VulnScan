import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.finding import Severity


class CodeFinding(Base):
    """A single static-analysis finding from bandit (code) or safety
    (dependency vulnerabilities) against an uploaded code archive. Mirrors
    Finding's shape but with a file/line location instead of a URL, since
    that's what's meaningful for static analysis. Reuses the Severity enum
    from finding.py rather than defining an identical second one."""

    __tablename__ = "code_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_scan_job_id = Column(UUID(as_uuid=True), ForeignKey("code_scan_jobs.id"), nullable=False)

    source = Column(String, nullable=False)   # "bandit" or "safety"
    vuln_type = Column(String, nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    remediation = Column(Text, nullable=False)
    affected_file = Column(String, nullable=False)
    line_number = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    code_scan_job = relationship("CodeScanJob", back_populates="findings")

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Domain(Base):
    """A hostname a user has registered to scan. Must be verified before any
    scan against it is allowed to run — this is what stops the platform from
    being used to point ZAP/sqlmap at sites the submitter doesn't own."""

    __tablename__ = "domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    hostname = Column(String, index=True, nullable=False)  # e.g. "example.com", no scheme/path
    verification_token = Column(String, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    scan_jobs = relationship("ScanJob", back_populates="domain")

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.finding import Severity
from app.models.scan_job import ScanStatus, ScanType


class ScanCreate(BaseModel):
    domain_id: uuid.UUID
    target_url: str
    scan_type: ScanType = ScanType.baseline


class ScanJobOut(BaseModel):
    id: uuid.UUID
    domain_id: uuid.UUID
    target_url: str
    scan_type: ScanType
    status: ScanStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class FindingOut(BaseModel):
    id: uuid.UUID
    vuln_type: str
    severity: Severity
    title: str
    description: str
    evidence: str | None
    remediation: str
    affected_url: str

    model_config = {"from_attributes": True}


class ScanReportOut(ScanJobOut):
    findings: list[FindingOut] = []

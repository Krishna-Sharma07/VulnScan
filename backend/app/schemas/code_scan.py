import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.finding import Severity
from app.models.scan_job import ScanStatus


class CodeScanJobOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: ScanStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class CodeFindingOut(BaseModel):
    id: uuid.UUID
    source: str
    vuln_type: str
    severity: Severity
    title: str
    description: str
    evidence: str | None
    remediation: str
    affected_file: str
    line_number: int | None

    model_config = {"from_attributes": True}


class CodeScanReportOut(CodeScanJobOut):
    findings: list[CodeFindingOut] = []

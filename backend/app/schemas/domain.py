import uuid
from datetime import datetime

from pydantic import BaseModel


class DomainCreate(BaseModel):
    hostname: str  # e.g. "example.com" — no scheme, no path


class DomainOut(BaseModel):
    id: uuid.UUID
    hostname: str
    verification_token: str
    verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @staticmethod
    def from_model(domain) -> "DomainOut":
        return DomainOut(
            id=domain.id,
            hostname=domain.hostname,
            verification_token=domain.verification_token,
            verified=domain.is_verified,
            created_at=domain.created_at,
        )

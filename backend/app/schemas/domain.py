import uuid
from datetime import datetime

from pydantic import BaseModel


class DomainCreate(BaseModel):
    hostname: str  # e.g. "example.com" — no scheme, no path


class DomainAuthCookieUpdate(BaseModel):
    # None/omitted clears it. Empty string is treated the same as None by
    # the route rather than stored as a meaningless empty secret.
    auth_cookie: str | None = None


class DomainOut(BaseModel):
    id: uuid.UUID
    hostname: str
    verification_token: str
    verified: bool
    has_auth_cookie: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @staticmethod
    def from_model(domain) -> "DomainOut":
        return DomainOut(
            id=domain.id,
            hostname=domain.hostname,
            verification_token=domain.verification_token,
            verified=domain.is_verified,
            has_auth_cookie=bool(domain.auth_cookie),
            created_at=domain.created_at,
        )

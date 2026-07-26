import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.db.session import get_db
from app.models.domain import Domain
from app.models.user import User
from app.schemas.domain import DomainAuthCookieUpdate, DomainCreate, DomainOut
from app.services.domain_verification import check_dns_txt, expected_txt_value

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.post("", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
def register_domain(
    payload: DomainCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = Domain(
        user_id=current_user.id,
        hostname=payload.hostname.lower().strip(),
        verification_token=secrets.token_hex(16),
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return DomainOut.from_model(domain)


@router.get("", response_model=list[DomainOut])
def list_domains(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    domains = db.query(Domain).filter(Domain.user_id == current_user.id).all()
    return [DomainOut.from_model(d) for d in domains]


@router.put("/{domain_id}/auth-cookie", response_model=DomainOut)
def set_auth_cookie(
    domain_id: uuid.UUID,
    payload: DomainAuthCookieUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sets (or, with an empty/omitted body, clears) the session cookie used
    by aggressive scans against this domain's authenticated pages - see
    NOTES.md section 17. Never echoed back by any endpoint; DomainOut only
    exposes whether one is set (`has_auth_cookie`), not its value. Stored
    encrypted at rest (NOTES.md section 19) - only ever decrypted by the
    worker, right before handing it to sqlmap."""
    domain = db.query(Domain).filter(Domain.id == domain_id, Domain.user_id == current_user.id).first()
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    domain.auth_cookie = encrypt_secret(payload.auth_cookie) if payload.auth_cookie else None
    db.commit()
    db.refresh(domain)
    return DomainOut.from_model(domain)


@router.post("/{domain_id}/verify", response_model=DomainOut)
def verify_domain(
    domain_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id, Domain.user_id == current_user.id).first()
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    if not domain.is_verified:
        if check_dns_txt(domain.hostname, domain.verification_token):
            domain.verified_at = datetime.utcnow()
            db.commit()
            db.refresh(domain)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"TXT record not found. Add a TXT record on {domain.hostname} "
                    f"with value: {expected_txt_value(domain.verification_token)}"
                ),
            )

    return DomainOut.from_model(domain)

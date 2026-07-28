from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.plans import limits_for
from app.db.session import get_db
from app.models.user import User
from app.schemas.billing import UpgradeRequest, UsageOut
from app.schemas.user import UserOut
from app.services.billing import scans_used_this_month

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/usage", response_model=UsageOut)
def get_usage(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    limits = limits_for(current_user.plan)
    return UsageOut(
        plan=current_user.plan,
        scans_used_this_month=scans_used_this_month(db, current_user.id),
        monthly_scan_limit=limits.monthly_scan_limit,
        aggressive_allowed=limits.aggressive_allowed,
    )


# No real payment gateway wired up yet (see NOTES.md) - this stands in for
# "checkout succeeded" so the rest of the product (limits, UI, upgrade
# flow) can be built and tested end-to-end now. Swapping this for real
# Razorpay Checkout + webhook-verified order confirmation later shouldn't
# require changing anything on the frontend beyond how this endpoint gets
# called.
@router.post("/upgrade", response_model=UserOut)
def upgrade_plan(
    payload: UpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.plan = payload.plan
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

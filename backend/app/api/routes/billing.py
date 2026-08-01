from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.plans import limits_for
from app.db.session import get_db
from app.models.user import PlanTier, User
from app.schemas.billing import (
    CheckoutOrderOut,
    CheckoutOrderRequest,
    CheckoutVerifyRequest,
    UpgradeRequest,
    UsageOut,
)
from app.schemas.user import UserOut
from app.core.config import settings
from app.services.billing import (
    CheckoutError,
    create_checkout_order,
    scans_used_this_month,
    verify_and_apply_payment,
)

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


# Free needs no payment, so this stays a direct, no-checkout plan change -
# but it must reject anything else now that real money is involved (see
# /checkout/order below). Without this restriction, anyone could still hit
# this endpoint with {"plan": "pro"} and get a paid plan for free; that hole
# was harmless while /upgrade was the *only* way to change plans (nothing
# cost real money yet), but became a real vulnerability the moment Razorpay
# checkout gave "pro" an actual price.
@router.post("/upgrade", response_model=UserOut)
def upgrade_plan(
    payload: UpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.plan != PlanTier.free:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid plans require checkout - use /api/billing/checkout/order",
        )
    current_user.plan = payload.plan
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/checkout/order", response_model=CheckoutOrderOut)
def create_order(
    payload: CheckoutOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = create_checkout_order(db, current_user, payload.plan)
    except CheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return CheckoutOrderOut(
        order_id=order.razorpay_order_id,
        amount=order.amount_paise,
        currency=order.currency,
        key_id=settings.razorpay_key_id,
    )


@router.post("/checkout/verify", response_model=UserOut)
def verify_order(
    payload: CheckoutVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return verify_and_apply_payment(
            db,
            current_user,
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        )
    except CheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

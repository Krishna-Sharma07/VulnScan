import uuid
from datetime import datetime

import razorpay
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.plans import price_for_checkout
from app.models.payment_order import PaymentOrder, PaymentOrderStatus
from app.models.scan_job import ScanJob
from app.models.user import PlanTier, User


def scans_used_this_month(db: Session, user_id: uuid.UUID) -> int:
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(ScanJob)
        .filter(ScanJob.user_id == user_id, ScanJob.created_at >= month_start)
        .count()
    )


class CheckoutError(Exception):
    """Raised for any checkout-flow failure the route layer should turn into
    a 4xx - unpurchasable plan, unknown/foreign order, already-processed
    order, or a bad payment signature."""


def _client() -> razorpay.Client:
    # Constructed per-call (not at module import time) so tests can
    # monkeypatch this function directly instead of needing a live Razorpay
    # account - the same pattern app/services/scanner.py uses for
    # docker.from_env().
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_checkout_order(db: Session, user: User, plan: PlanTier) -> PaymentOrder:
    """Creates a Razorpay order for `plan` and records it against `user`.
    The amount is looked up from app.core.plans.PLAN_PRICES_PAISE - never
    accepted from the caller - so a tampered request body can't buy a plan
    for less than its real price."""
    amount = price_for_checkout(plan)
    if amount is None:
        raise CheckoutError(f"{plan.value} isn't purchasable through checkout")

    currency = "INR"
    razorpay_order = _client().order.create(
        {"amount": amount, "currency": currency, "payment_capture": 1}
    )

    order = PaymentOrder(
        user_id=user.id,
        plan=plan,
        razorpay_order_id=razorpay_order["id"],
        amount_paise=amount,
        currency=currency,
        status=PaymentOrderStatus.created,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def verify_and_apply_payment(
    db: Session,
    user: User,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> User:
    """Verifies a completed Razorpay payment and, if genuine, upgrades
    `user` to the plan that order was created for.

    Two checks matter here, for different reasons:
    1. The order must belong to *this* user and still be unprocessed - a
       Razorpay signature only proves an (order_id, payment_id) pair is
       authentic, not who paid or what it was for, so without this check a
       user could replay someone else's verified payment, or replay their
       own order twice, to re-apply an upgrade.
    2. The signature itself must check out via HMAC(order_id|payment_id,
       key_secret) == signature - this is what actually proves the payment
       came from Razorpay and wasn't just invented client-side by someone
       who knows an order id.
    """
    order = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.razorpay_order_id == razorpay_order_id)
        .first()
    )
    if order is None or order.user_id != user.id:
        raise CheckoutError("Unknown order")
    if order.status != PaymentOrderStatus.created:
        raise CheckoutError("Order already processed")

    try:
        _client().utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError:
        order.status = PaymentOrderStatus.failed
        db.add(order)
        db.commit()
        raise CheckoutError("Payment signature verification failed")

    order.status = PaymentOrderStatus.paid
    user.plan = order.plan
    db.add(order)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

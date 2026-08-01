from pydantic import BaseModel

from app.models.user import PlanTier


class UsageOut(BaseModel):
    plan: PlanTier
    scans_used_this_month: int
    monthly_scan_limit: int | None  # None = unlimited
    aggressive_allowed: bool


class UpgradeRequest(BaseModel):
    plan: PlanTier


class CheckoutOrderRequest(BaseModel):
    plan: PlanTier


class CheckoutOrderOut(BaseModel):
    order_id: str
    amount: int  # paise
    currency: str
    key_id: str  # public - safe to send to the browser, Checkout.js needs it


class CheckoutVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base
from app.models.user import PlanTier


class PaymentOrderStatus(str, enum.Enum):
    created = "created"
    paid = "paid"
    failed = "failed"


class PaymentOrder(Base):
    """One row per Razorpay order we create for a paid-plan checkout. This is
    what ties a Razorpay order/payment id back to *which user* was buying
    *which plan* at *what price* - Razorpay's signature only proves an
    order_id+payment_id pair is authentic, not what they were for, so the
    verify endpoint (app/api/routes/billing.py) checks this row rather than
    trusting anything the client sends about plan/amount."""

    __tablename__ = "payment_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan = Column(Enum(PlanTier), nullable=False)
    razorpay_order_id = Column(String, unique=True, nullable=False, index=True)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="INR")
    status = Column(Enum(PaymentOrderStatus), default=PaymentOrderStatus.created, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

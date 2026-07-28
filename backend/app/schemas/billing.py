from pydantic import BaseModel

from app.models.user import PlanTier


class UsageOut(BaseModel):
    plan: PlanTier
    scans_used_this_month: int
    monthly_scan_limit: int | None  # None = unlimited
    aggressive_allowed: bool


class UpgradeRequest(BaseModel):
    plan: PlanTier

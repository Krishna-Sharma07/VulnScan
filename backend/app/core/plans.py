from dataclasses import dataclass

from app.models.user import PlanTier


@dataclass(frozen=True)
class PlanLimits:
    # None means unlimited.
    monthly_scan_limit: int | None
    aggressive_allowed: bool


# Single source of truth for what each tier gets - both the billing page and
# the scan-creation gate in scans.py read from this, so the two can never
# drift out of sync with each other.
PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.free: PlanLimits(monthly_scan_limit=3, aggressive_allowed=False),
    PlanTier.pro: PlanLimits(monthly_scan_limit=None, aggressive_allowed=True),
    # Enterprise has no enforced difference from Pro yet (priority scanning,
    # dedicated support, etc. are unbuilt) - it exists as a tier now so the
    # billing UI and upgrade flow don't need to change shape when those land.
    PlanTier.enterprise: PlanLimits(monthly_scan_limit=None, aggressive_allowed=True),
}


def limits_for(plan: PlanTier) -> PlanLimits:
    return PLAN_LIMITS[plan]

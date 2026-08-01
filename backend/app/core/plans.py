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


# Plans that can be bought through real Razorpay checkout, and what they
# cost - in paise (1 rupee = 100 paise, the smallest INR unit, same idea as
# cents), since that's the unit Razorpay's Orders API expects. Free has no
# price (it's the no-payment default) and Enterprise is "Contact us" pricing
# (a manual sales process, not self-serve) - only Pro is purchasable here.
# Amounts are never accepted from the client; the checkout-order endpoint
# looks the price up from this dict server-side, so a tampered request body
# can't buy Pro for a different price.
PLAN_PRICES_PAISE: dict[PlanTier, int] = {
    PlanTier.pro: 240000,  # INR 2,400.00/month
}


def price_for_checkout(plan: PlanTier) -> int | None:
    """None means this plan isn't purchasable via checkout (Free needs no
    payment, Enterprise is sales-assisted)."""
    return PLAN_PRICES_PAISE.get(plan)

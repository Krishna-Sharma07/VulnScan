from app.core.plans import PLAN_LIMITS, limits_for
from app.models.user import PlanTier


def test_every_plan_tier_has_limits_defined():
    for plan in PlanTier:
        assert plan in PLAN_LIMITS


def test_free_plan_is_capped_and_no_aggressive():
    limits = limits_for(PlanTier.free)
    assert limits.monthly_scan_limit == 3
    assert limits.aggressive_allowed is False


def test_pro_plan_is_unlimited_with_aggressive():
    limits = limits_for(PlanTier.pro)
    assert limits.monthly_scan_limit is None
    assert limits.aggressive_allowed is True


def test_enterprise_plan_is_unlimited_with_aggressive():
    limits = limits_for(PlanTier.enterprise)
    assert limits.monthly_scan_limit is None
    assert limits.aggressive_allowed is True

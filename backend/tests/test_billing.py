import uuid
from datetime import datetime, timedelta

from app.models.domain import Domain
from app.models.scan_job import ScanJob, ScanType

USAGE_URL = "/api/billing/usage"
UPGRADE_URL = "/api/billing/upgrade"


def test_usage_requires_auth(client):
    resp = client.get(USAGE_URL)
    assert resp.status_code == 401


def test_usage_defaults_to_free_plan_zero_used(auth_client):
    client, headers, _ = auth_client
    resp = client.get(USAGE_URL, headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "plan": "free",
        "scans_used_this_month": 0,
        "monthly_scan_limit": 3,
        "aggressive_allowed": False,
    }


def test_upgrade_changes_plan_and_lifts_limits(auth_client):
    client, headers, _ = auth_client
    resp = client.post(UPGRADE_URL, json={"plan": "pro"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["plan"] == "pro"
    assert usage["monthly_scan_limit"] is None
    assert usage["aggressive_allowed"] is True


def test_upgrade_rejects_unknown_plan_value(auth_client):
    client, headers, _ = auth_client
    resp = client.post(UPGRADE_URL, json={"plan": "ultra"}, headers=headers)
    assert resp.status_code == 422


def _make_verified_domain(db_session, user_id, hostname="usage-test.example.com"):
    domain = Domain(
        user_id=user_id,
        hostname=hostname,
        verification_token="tok",
        verified_at=datetime.utcnow(),
    )
    db_session.add(domain)
    db_session.commit()
    db_session.refresh(domain)
    return domain


def test_usage_counts_scans_created_this_month(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_verified_domain(db_session, uuid.UUID(user["id"]))
    db_session.add(
        ScanJob(
            user_id=uuid.UUID(user["id"]),
            domain_id=domain.id,
            target_url=f"https://{domain.hostname}",
            scan_type=ScanType.baseline,
        )
    )
    db_session.commit()

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["scans_used_this_month"] == 1


def test_usage_excludes_scans_from_previous_month(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_verified_domain(db_session, uuid.UUID(user["id"]))
    last_month = datetime.utcnow().replace(day=1) - timedelta(days=1)
    db_session.add(
        ScanJob(
            user_id=uuid.UUID(user["id"]),
            domain_id=domain.id,
            target_url=f"https://{domain.hostname}",
            scan_type=ScanType.baseline,
            created_at=last_month,
        )
    )
    db_session.commit()

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["scans_used_this_month"] == 0

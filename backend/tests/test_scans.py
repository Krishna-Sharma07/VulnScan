import uuid
from datetime import datetime, timedelta

from app.models.domain import Domain
from app.models.scan_job import ScanJob, ScanType
from app.models.user import PlanTier, User

SCAN_URL = "/api/scan"


def _make_domain(db_session, user_id, hostname="scantest.example.com", verified=True):
    domain = Domain(
        user_id=user_id,
        hostname=hostname,
        verification_token="tok",
        verified_at=datetime.utcnow() if verified else None,
    )
    db_session.add(domain)
    db_session.commit()
    db_session.refresh(domain)
    return domain


def _upgrade_to_pro(db_session, user_id):
    # These scan-gating tests care about "a user on Pro", not how they got
    # there - actually buying Pro is Razorpay checkout's job (see
    # test_billing.py), so set the plan directly rather than going through
    # /api/billing/upgrade, which now rejects paid plans outright.
    user = db_session.query(User).filter(User.id == user_id).one()
    user.plan = PlanTier.pro
    db_session.add(user)
    db_session.commit()


def _scan_body(domain, scan_type="baseline"):
    return {
        "domain_id": str(domain.id),
        "target_url": f"https://{domain.hostname}",
        "scan_type": scan_type,
    }


def test_create_scan_requires_auth(client):
    resp = client.post(
        SCAN_URL,
        json={"domain_id": str(uuid.uuid4()), "target_url": "https://x.com", "scan_type": "baseline"},
    )
    assert resp.status_code == 401


def test_create_scan_domain_not_found(auth_client):
    client, headers, _ = auth_client
    resp = client.post(
        SCAN_URL,
        json={
            "domain_id": str(uuid.uuid4()),
            "target_url": "https://nope.example.com",
            "scan_type": "baseline",
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_create_scan_domain_owned_by_someone_else_is_404(auth_client, db_session):
    from tests.conftest import signup

    client, headers, user = auth_client
    other_user, _ = signup(client, email="otherowner@example.com")
    other_users_domain = _make_domain(db_session, uuid.UUID(other_user["id"]))
    resp = client.post(SCAN_URL, json=_scan_body(other_users_domain), headers=headers)
    assert resp.status_code == 404


def test_create_scan_unverified_domain_rejected(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]), verified=False)
    resp = client.post(SCAN_URL, json=_scan_body(domain), headers=headers)
    assert resp.status_code == 403
    assert "not verified" in resp.json()["detail"]


def test_create_scan_rejects_non_http_scheme(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]), hostname="scheme.example.com")
    resp = client.post(
        SCAN_URL,
        json={
            "domain_id": str(domain.id),
            "target_url": "ftp://scheme.example.com",
            "scan_type": "baseline",
        },
        headers=headers,
    )
    assert resp.status_code == 400


def test_create_scan_rejects_host_mismatch(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]), hostname="realhost.example.com")
    resp = client.post(
        SCAN_URL,
        json={
            "domain_id": str(domain.id),
            "target_url": "https://not-the-domain.com",
            "scan_type": "baseline",
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "must exactly match" in resp.json()["detail"]


def test_create_scan_rejects_target_that_resolves_to_a_private_address(auth_client, db_session, monkeypatch):
    from app.services.ssrf_guard import UnsafeScanTargetError

    def _raise(hostname):
        raise UnsafeScanTargetError(f"'{hostname}' resolves to a private/internal address (127.0.0.1)")

    monkeypatch.setattr("app.api.routes.scans.assert_public_scan_target", _raise)

    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]), hostname="rebound.example.com")
    resp = client.post(SCAN_URL, json=_scan_body(domain), headers=headers)
    assert resp.status_code == 400
    assert "private/internal address" in resp.json()["detail"]


def test_create_scan_succeeds_for_verified_domain(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    resp = client.post(SCAN_URL, json=_scan_body(domain), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_aggressive_scan_rejected_on_free_plan(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    resp = client.post(SCAN_URL, json=_scan_body(domain, "aggressive"), headers=headers)
    assert resp.status_code == 403
    assert "Pro or Enterprise" in resp.json()["detail"]


def test_aggressive_scan_allowed_after_upgrading_to_pro(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    _upgrade_to_pro(db_session, uuid.UUID(user["id"]))
    resp = client.post(SCAN_URL, json=_scan_body(domain, "aggressive"), headers=headers)
    assert resp.status_code == 201


def test_free_plan_monthly_quota_is_enforced(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    body = _scan_body(domain)

    for _ in range(3):
        resp = client.post(SCAN_URL, json=body, headers=headers)
        assert resp.status_code == 201

    resp = client.post(SCAN_URL, json=body, headers=headers)
    assert resp.status_code == 402
    assert "Monthly scan limit" in resp.json()["detail"]


def test_quota_exceeded_message_not_shown_below_the_limit(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    body = _scan_body(domain)

    for _ in range(2):
        resp = client.post(SCAN_URL, json=body, headers=headers)
        assert resp.status_code == 201


def test_quota_lifted_immediately_after_upgrading(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    body = _scan_body(domain)

    for _ in range(3):
        client.post(SCAN_URL, json=body, headers=headers)

    _upgrade_to_pro(db_session, uuid.UUID(user["id"]))

    resp = client.post(SCAN_URL, json=body, headers=headers)
    assert resp.status_code == 201


def test_quota_counts_only_current_calendar_month(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    last_month = datetime.utcnow().replace(day=1) - timedelta(days=1)

    for _ in range(3):
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

    # Three scans exist, but all last month - this month's quota is untouched.
    resp = client.post(SCAN_URL, json=_scan_body(domain), headers=headers)
    assert resp.status_code == 201


def test_history_returns_only_callers_scans(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    client.post(SCAN_URL, json=_scan_body(domain), headers=headers)

    resp = client.get("/api/history", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_report_not_visible_to_other_users(client, db_session):
    from tests.conftest import login, signup

    user_a, pw_a = signup(client, email="reportowner@example.com")
    headers_a = {"Authorization": f"Bearer {login(client, user_a['email'], pw_a)}"}
    domain = _make_domain(db_session, uuid.UUID(user_a["id"]))
    scan = client.post(SCAN_URL, json=_scan_body(domain), headers=headers_a).json()

    user_b, pw_b = signup(client, email="reportintruder@example.com")
    headers_b = {"Authorization": f"Bearer {login(client, user_b['email'], pw_b)}"}
    resp = client.get(f"/api/reports/{scan['id']}", headers=headers_b)
    assert resp.status_code == 404


def test_report_pdf_404_when_not_yet_generated(auth_client, db_session):
    client, headers, user = auth_client
    domain = _make_domain(db_session, uuid.UUID(user["id"]))
    scan = client.post(SCAN_URL, json=_scan_body(domain), headers=headers).json()

    resp = client.get(f"/api/reports/{scan['id']}/pdf", headers=headers)
    assert resp.status_code == 404

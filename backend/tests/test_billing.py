import uuid
from datetime import datetime, timedelta

import razorpay

from app.models.domain import Domain
from app.models.scan_job import ScanJob, ScanType
from tests.conftest import login, signup

USAGE_URL = "/api/billing/usage"
UPGRADE_URL = "/api/billing/upgrade"
ORDER_URL = "/api/billing/checkout/order"
VERIFY_URL = "/api/billing/checkout/verify"


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


def test_upgrade_to_free_still_works_directly(auth_client):
    """Free needs no payment, so /upgrade still handles it directly."""
    client, headers, _ = auth_client
    resp = client.post(UPGRADE_URL, json={"plan": "free"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["plan"] == "free"


def test_upgrade_rejects_paid_plan(auth_client):
    """Closes the free-upgrade loophole: once Pro has a real price via
    checkout, /upgrade must never grant it directly."""
    client, headers, _ = auth_client
    resp = client.post(UPGRADE_URL, json={"plan": "pro"}, headers=headers)
    assert resp.status_code == 400

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["plan"] == "free"


def test_upgrade_rejects_unknown_plan_value(auth_client):
    client, headers, _ = auth_client
    resp = client.post(UPGRADE_URL, json={"plan": "ultra"}, headers=headers)
    assert resp.status_code == 422


class FakeOrderApi:
    def __init__(self, order_id):
        self.order_id = order_id
        self.last_create_call = None

    def create(self, data):
        self.last_create_call = data
        return {"id": self.order_id, "amount": data["amount"], "currency": data["currency"]}


class FakeUtility:
    def __init__(self, should_verify):
        self.should_verify = should_verify

    def verify_payment_signature(self, params):
        if not self.should_verify:
            raise razorpay.errors.SignatureVerificationError("bad signature")
        return True


class FakeRazorpayClient:
    def __init__(self, order_id="order_fake123", should_verify=True):
        self.order = FakeOrderApi(order_id)
        self.utility = FakeUtility(should_verify)


def _stub_client(monkeypatch, order_id="order_fake123", should_verify=True):
    fake = FakeRazorpayClient(order_id=order_id, should_verify=should_verify)
    monkeypatch.setattr("app.services.billing._client", lambda: fake)
    return fake


def test_checkout_order_requires_auth(client):
    resp = client.post(ORDER_URL, json={"plan": "pro"})
    assert resp.status_code == 401


def test_checkout_order_creates_order_with_server_side_price(auth_client, monkeypatch):
    client, headers, _ = auth_client
    fake = _stub_client(monkeypatch)

    resp = client.post(ORDER_URL, json={"plan": "pro"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == "order_fake123"
    assert body["amount"] == 240000
    assert body["currency"] == "INR"
    assert "key_id" in body
    # The amount actually sent to Razorpay came from our own price table,
    # never from the request body (which had no amount field at all).
    assert fake.order.last_create_call["amount"] == 240000


def test_checkout_order_rejects_non_purchasable_plans(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch)

    for plan in ("free", "enterprise"):
        resp = client.post(ORDER_URL, json={"plan": plan}, headers=headers)
        assert resp.status_code == 400, plan


def test_checkout_verify_applies_plan_on_valid_signature(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch)

    order_resp = client.post(ORDER_URL, json={"plan": "pro"}, headers=headers)
    order_id = order_resp.json()["order_id"]

    resp = client.post(
        VERIFY_URL,
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_fake123",
            "razorpay_signature": "sig_fake123",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["plan"] == "pro"
    assert usage["aggressive_allowed"] is True


def test_checkout_verify_rejects_bad_signature_and_does_not_upgrade(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch, should_verify=False)

    order_id = client.post(ORDER_URL, json={"plan": "pro"}, headers=headers).json()["order_id"]

    resp = client.post(
        VERIFY_URL,
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_fake123",
            "razorpay_signature": "sig_bad",
        },
        headers=headers,
    )
    assert resp.status_code == 400

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["plan"] == "free"


def test_checkout_verify_rejects_replay_of_already_processed_order(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch)
    order_id = client.post(ORDER_URL, json={"plan": "pro"}, headers=headers).json()["order_id"]
    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": "pay_fake123",
        "razorpay_signature": "sig_fake123",
    }

    first = client.post(VERIFY_URL, json=payload, headers=headers)
    assert first.status_code == 200

    second = client.post(VERIFY_URL, json=payload, headers=headers)
    assert second.status_code == 400


def test_checkout_verify_rejects_order_belonging_to_another_user(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch)
    other_user, other_password = signup(client)
    other_token = login(client, other_user["email"], other_password)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    order_id = client.post(ORDER_URL, json={"plan": "pro"}, headers=other_headers).json()[
        "order_id"
    ]

    resp = client.post(
        VERIFY_URL,
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_fake123",
            "razorpay_signature": "sig_fake123",
        },
        headers=headers,
    )
    assert resp.status_code == 400

    usage = client.get(USAGE_URL, headers=headers).json()
    assert usage["plan"] == "free"


def test_checkout_verify_rejects_unknown_order_id(auth_client, monkeypatch):
    client, headers, _ = auth_client
    _stub_client(monkeypatch)

    resp = client.post(
        VERIFY_URL,
        json={
            "razorpay_order_id": "order_never_created",
            "razorpay_payment_id": "pay_fake123",
            "razorpay_signature": "sig_fake123",
        },
        headers=headers,
    )
    assert resp.status_code == 400


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

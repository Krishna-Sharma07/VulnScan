import io
import uuid
import zipfile
from datetime import datetime

import pytest

from app.api.routes import code_scans as code_scans_routes
from app.models.domain import Domain
from app.models.scan_job import ScanJob, ScanType
from app.models.user import PlanTier, User

CODE_SCAN_URL = "/api/code-scans"


def _zip_bytes(files: dict[str, str] | None = None) -> bytes:
    files = files or {"app.py": "print('hello')\n"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(code_scans_routes.settings, "uploads_dir", str(tmp_path))
    return tmp_path


def _upgrade_to_pro(db_session, user_id):
    user = db_session.query(User).filter(User.id == user_id).one()
    user.plan = PlanTier.pro
    db_session.add(user)
    db_session.commit()


def test_create_code_scan_requires_auth(client):
    resp = client.post(CODE_SCAN_URL, files={"file": ("code.zip", _zip_bytes(), "application/zip")})
    assert resp.status_code == 401


def test_create_code_scan_rejects_non_zip_extension(auth_client):
    client, headers, _ = auth_client
    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("app.py", b"print(1)", "text/x-python")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Only .zip archives" in resp.json()["detail"]


def test_create_code_scan_rejects_invalid_zip_content(auth_client):
    client, headers, _ = auth_client
    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", b"not actually a zip", "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "not a valid zip" in resp.json()["detail"]


def test_create_code_scan_rejects_oversized_upload(auth_client, monkeypatch):
    client, headers, _ = auth_client
    monkeypatch.setattr(code_scans_routes.settings, "code_scan_max_upload_bytes", 10)
    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]


def test_create_code_scan_succeeds_and_spools_upload_to_disk(auth_client, uploads_dir):
    client, headers, _ = auth_client
    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("myproject.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "myproject.zip"
    assert body["status"] == "pending"
    assert list(uploads_dir.glob("*.zip"))


def test_free_plan_monthly_quota_shared_with_url_scans(auth_client, db_session):
    client, headers, user = auth_client
    for _ in range(3):
        resp = client.post(
            CODE_SCAN_URL,
            files={"file": ("code.zip", _zip_bytes(), "application/zip")},
            headers=headers,
        )
        assert resp.status_code == 201

    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 402
    assert "Monthly scan limit" in resp.json()["detail"]


def test_free_plan_monthly_quota_combines_url_and_code_scans(auth_client, db_session):
    client, headers, user = auth_client
    domain = Domain(
        user_id=uuid.UUID(user["id"]),
        hostname="mixedquota.example.com",
        verification_token="tok",
        verified_at=datetime.utcnow(),
    )
    db_session.add(domain)
    db_session.commit()
    db_session.refresh(domain)

    for _ in range(2):
        db_session.add(
            ScanJob(
                user_id=uuid.UUID(user["id"]),
                domain_id=domain.id,
                target_url=f"https://{domain.hostname}",
                scan_type=ScanType.baseline,
            )
        )
    db_session.commit()

    # 2 URL scans already used this month - one code scan should be allowed,
    # the next should hit the shared 3/month free-tier cap.
    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 402


def test_quota_lifted_after_upgrading_to_pro(auth_client, db_session):
    client, headers, user = auth_client
    for _ in range(3):
        client.post(
            CODE_SCAN_URL,
            files={"file": ("code.zip", _zip_bytes(), "application/zip")},
            headers=headers,
        )
    _upgrade_to_pro(db_session, uuid.UUID(user["id"]))

    resp = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    assert resp.status_code == 201


def test_code_scan_history_returns_only_callers_scans(auth_client):
    client, headers, _ = auth_client
    client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    )
    resp = client.get(CODE_SCAN_URL, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_code_scan_detail_not_visible_to_other_users(client, db_session):
    from tests.conftest import login, signup

    user_a, pw_a = signup(client, email="codescanowner@example.com")
    headers_a = {"Authorization": f"Bearer {login(client, user_a['email'], pw_a)}"}
    created = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers_a,
    ).json()

    user_b, pw_b = signup(client, email="codescanintruder@example.com")
    headers_b = {"Authorization": f"Bearer {login(client, user_b['email'], pw_b)}"}
    resp = client.get(f"{CODE_SCAN_URL}/{created['id']}", headers=headers_b)
    assert resp.status_code == 404


def test_code_scan_pdf_404_when_not_yet_generated(auth_client):
    client, headers, _ = auth_client
    created = client.post(
        CODE_SCAN_URL,
        files={"file": ("code.zip", _zip_bytes(), "application/zip")},
        headers=headers,
    ).json()

    resp = client.get(f"{CODE_SCAN_URL}/{created['id']}/pdf", headers=headers)
    assert resp.status_code == 404


def test_code_scan_not_found_returns_404(auth_client):
    client, headers, _ = auth_client
    resp = client.get(f"{CODE_SCAN_URL}/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404

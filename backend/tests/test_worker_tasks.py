import uuid
from datetime import datetime

import pytest

import app.worker.tasks as tasks
from app.core.crypto import encrypt_secret
from app.models.domain import Domain
from app.models.finding import Finding
from app.models.scan_job import ScanJob, ScanStatus, ScanType
from app.models.user import User
from app.services.scanner import ScanExecutionError
from tests.conftest import TestingSessionLocal, test_engine

ZAP_FINDING = {
    "vuln_type": "40018",
    "severity": "high",
    "title": "SQL Injection",
    "description": "desc",
    "evidence": "ev",
    "remediation": "fix it",
    "affected_url": "https://x.com/a",
}

SQLMAP_FINDING = {
    "vuln_type": "sql_injection",
    "severity": "critical",
    "title": "SQL Injection (boolean-based blind) - id",
    "description": "desc",
    "evidence": "id=1 AND 1=1",
    "remediation": "use prepared statements",
    "affected_url": "https://x.com/a",
}


def _db():
    """A session bound directly to the real test_engine (not the nested
    SAVEPOINT session other tests use) - run_scan opens/closes its own
    session via SessionLocal(), so it needs real commits it can see across
    the session boundary it creates itself."""
    return TestingSessionLocal(bind=test_engine)


def _make_scan_job(scan_type=ScanType.baseline, auth_cookie=None) -> str:
    db = _db()
    user = User(email=f"worker_{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db.add(user)
    db.flush()

    domain = Domain(
        user_id=user.id,
        hostname=f"{uuid.uuid4().hex[:8]}.example.com",
        verification_token="tok",
        verified_at=datetime.utcnow(),
        auth_cookie=encrypt_secret(auth_cookie) if auth_cookie else None,
    )
    db.add(domain)
    db.flush()

    scan_job = ScanJob(
        user_id=user.id,
        domain_id=domain.id,
        target_url=f"https://{domain.hostname}",
        scan_type=scan_type,
        status=ScanStatus.pending,
    )
    db.add(scan_job)
    db.commit()
    scan_job_id = str(scan_job.id)
    db.close()
    return scan_job_id


def _reload(scan_job_id: str):
    db = _db()
    scan_job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(scan_job_id)).first()
    findings = db.query(Finding).filter(Finding.scan_job_id == scan_job.id).all()
    db.close()
    return scan_job, findings


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", _db)


@pytest.fixture()
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks.settings, "reports_dir", str(tmp_path))
    return tmp_path


def test_run_scan_completes_and_persists_findings_and_pdf(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job()
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("container-abc", [ZAP_FINDING]))

    tasks.run_scan(scan_job_id)

    scan_job, findings = _reload(scan_job_id)
    assert scan_job.status == ScanStatus.completed
    assert scan_job.container_id == "container-abc"
    assert len(findings) == 1
    assert findings[0].title == "SQL Injection"
    assert scan_job.report_path is not None
    assert (reports_dir / f"{scan_job.id}.pdf").exists()


def test_run_scan_marks_failed_when_zap_scan_errors(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job()

    def _boom(url, scan_type):
        raise ScanExecutionError("target unreachable")

    monkeypatch.setattr(tasks, "run_zap_scan", _boom)

    tasks.run_scan(scan_job_id)

    scan_job, findings = _reload(scan_job_id)
    assert scan_job.status == ScanStatus.failed
    assert findings == []
    assert scan_job.report_path is None


def test_run_scan_baseline_never_invokes_sqlmap(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job(scan_type=ScanType.baseline)
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("c1", [ZAP_FINDING]))
    sqlmap_mock_called = []
    monkeypatch.setattr(
        tasks, "run_sqlmap_scan", lambda *a, **kw: sqlmap_mock_called.append((a, kw)) or []
    )

    tasks.run_scan(scan_job_id)

    assert sqlmap_mock_called == []


def test_run_scan_aggressive_invokes_sqlmap_with_decrypted_cookie(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job(scan_type=ScanType.aggressive, auth_cookie="PHPSESSID=abc123")
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("c1", [ZAP_FINDING]))

    captured = {}

    def _fake_sqlmap(url, cookie=None):
        captured["url"] = url
        captured["cookie"] = cookie
        return [SQLMAP_FINDING]

    monkeypatch.setattr(tasks, "run_sqlmap_scan", _fake_sqlmap)

    tasks.run_scan(scan_job_id)

    assert captured["cookie"] == "PHPSESSID=abc123"
    scan_job, findings = _reload(scan_job_id)
    assert scan_job.status == ScanStatus.completed
    assert len(findings) == 2  # one ZAP finding + one sqlmap finding


def test_run_scan_aggressive_without_cookie_passes_none(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job(scan_type=ScanType.aggressive, auth_cookie=None)
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("c1", []))

    captured = {}
    monkeypatch.setattr(
        tasks, "run_sqlmap_scan", lambda url, cookie=None: captured.setdefault("cookie", cookie) or []
    )

    tasks.run_scan(scan_job_id)

    assert captured["cookie"] is None


def test_run_scan_keeps_zap_findings_when_sqlmap_fails(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job(scan_type=ScanType.aggressive)
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("c1", [ZAP_FINDING]))

    def _boom(url, cookie=None):
        raise ScanExecutionError("sqlmap timed out")

    monkeypatch.setattr(tasks, "run_sqlmap_scan", _boom)

    tasks.run_scan(scan_job_id)

    scan_job, findings = _reload(scan_job_id)
    assert scan_job.status == ScanStatus.completed
    assert len(findings) == 1
    assert findings[0].title == "SQL Injection"


def test_run_scan_completes_even_when_pdf_generation_fails(monkeypatch, reports_dir):
    scan_job_id = _make_scan_job()
    monkeypatch.setattr(tasks, "run_zap_scan", lambda url, scan_type: ("c1", [ZAP_FINDING]))

    def _boom(scan_job, findings, output_path):
        raise RuntimeError("reportlab exploded")

    monkeypatch.setattr(tasks, "generate_pdf_report", _boom)

    tasks.run_scan(scan_job_id)

    scan_job, findings = _reload(scan_job_id)
    assert scan_job.status == ScanStatus.completed
    assert len(findings) == 1
    assert scan_job.report_path is None


def test_run_scan_is_noop_when_scan_job_missing(monkeypatch, reports_dir):
    monkeypatch.setattr(tasks, "run_zap_scan", lambda *a, **kw: pytest.fail("should not be called"))

    tasks.run_scan(str(uuid.uuid4()))  # must not raise

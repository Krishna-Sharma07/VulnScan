import io
import json
import tarfile
from unittest.mock import MagicMock

import docker.errors
import pytest

from app.services.code_scanner import (
    _extract_json,
    _parse_bandit_findings,
    _parse_safety_findings,
    _wrap_upload_as_tar,
    run_code_scan,
)
from app.services.scanner import ScanExecutionError

# ---------------------------------------------------------------------------
# Pure parsing helpers - no Docker involved.
# ---------------------------------------------------------------------------

BANDIT_SAMPLE_REPORT = {
    "results": [
        {
            "test_id": "B105",
            "test_name": "hardcoded_password_string",
            "issue_severity": "MEDIUM",
            "issue_text": "Possible hardcoded password",
            "code": "password = 'hunter2'",
            "filename": "src/app.py",
            "line_number": 12,
            "more_info": "https://bandit.readthedocs.io/B105",
        },
        {
            "test_id": "B608",
            "test_name": "hardcoded_sql_expressions",
            "issue_severity": "HIGH",
            "issue_text": "Possible SQL injection",
            "code": "cursor.execute('SELECT * FROM x WHERE id=' + id)",
            "filename": "src/db.py",
            "line_number": 40,
            "more_info": None,
        },
    ]
}


def test_parse_bandit_findings_maps_severity_and_fields():
    findings = _parse_bandit_findings(BANDIT_SAMPLE_REPORT)
    assert len(findings) == 2
    assert findings[0]["source"] == "bandit"
    assert findings[0]["severity"] == "medium"
    assert findings[0]["affected_file"] == "src/app.py"
    assert findings[0]["line_number"] == 12
    assert findings[1]["severity"] == "high"
    assert "Review and remediate" in findings[1]["remediation"]


def test_parse_bandit_findings_empty_report():
    assert _parse_bandit_findings(None) == []
    assert _parse_bandit_findings({"results": []}) == []


SAFETY_SAMPLE_REPORT = {
    "vulnerabilities": [
        {
            "vulnerability_id": "12345",
            "package_name": "django",
            "analyzed_version": "2.2.0",
            "vulnerable_spec": "<2.2.28",
            "advisory": "Known SQL injection vulnerability",
            "severity": {"cvssv3": {"base_severity": "CRITICAL"}},
        },
        {
            "vulnerability_id": "67890",
            "package_name": "requests",
            "analyzed_version": "2.20.0",
            "vulnerable_spec": "<2.20.1",
            "advisory": "Known vulnerability",
            "severity": None,
        },
    ]
}


def test_parse_safety_findings_maps_severity_and_fields():
    findings = _parse_safety_findings(SAFETY_SAMPLE_REPORT)
    assert len(findings) == 2
    assert findings[0]["source"] == "safety"
    assert findings[0]["severity"] == "critical"
    assert "django" in findings[0]["title"]
    assert findings[1]["severity"] == "high"  # no structured severity -> defaults high


def test_parse_safety_findings_empty_report():
    assert _parse_safety_findings(None) == []
    assert _parse_safety_findings({"vulnerabilities": []}) == []
    assert _parse_safety_findings([]) == []


def test_parse_safety_findings_handles_bare_list_shape():
    findings = _parse_safety_findings(SAFETY_SAMPLE_REPORT["vulnerabilities"])
    assert len(findings) == 2


# ---------------------------------------------------------------------------
# put_archive tar wrapping / get_archive tar extraction
# ---------------------------------------------------------------------------


def test_wrap_upload_as_tar_contains_single_upload_zip_entry():
    data = b"PK\x03\x04fake zip bytes"
    tar_bytes = _wrap_upload_as_tar(data)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        names = tar.getnames()
        assert names == ["upload.zip"]
        extracted = tar.extractfile("upload.zip").read()
        assert extracted == data


def _tar_stream_with(name: str, payload: bytes):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    buf.seek(0)
    return [buf.read()]


def test_extract_json_reads_report_from_tar_stream():
    payload = json.dumps({"results": []}).encode()
    container = MagicMock()
    container.get_archive.return_value = (_tar_stream_with("bandit-report.json", payload), {})

    result = _extract_json(container, "/code/bandit-report.json")

    assert result == {"results": []}


def test_extract_json_returns_none_when_file_missing():
    container = MagicMock()
    container.get_archive.side_effect = docker.errors.NotFound("no such file")

    assert _extract_json(container, "/code/bandit-report.json") is None


# ---------------------------------------------------------------------------
# run_code_scan - container lifecycle orchestration (create/put_archive/
# start/wait/get_archive/remove), Docker itself mocked out.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_docker(monkeypatch):
    client = MagicMock()
    client.images.get.return_value = object()  # image already present, skip build
    monkeypatch.setattr("app.services.code_scanner.docker.from_env", lambda: client)
    return client


def test_run_code_scan_happy_path(fake_docker, monkeypatch):
    container = MagicMock(id="code123")
    fake_docker.containers.create.return_value = container
    monkeypatch.setattr(
        "app.services.code_scanner._extract_json",
        lambda c, path: BANDIT_SAMPLE_REPORT if "bandit" in path else {"vulnerabilities": []},
    )

    container_id, findings = run_code_scan(b"fake zip bytes")

    assert container_id == "code123"
    assert len(findings) == 2
    container.put_archive.assert_called_once()
    args, _ = container.put_archive.call_args
    assert args[0] == "/code"
    container.start.assert_called_once()
    container.wait.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_run_code_scan_raises_when_image_build_fails(monkeypatch):
    client = MagicMock()
    client.images.get.side_effect = docker.errors.ImageNotFound("nope")
    client.images.build.side_effect = docker.errors.BuildError("boom", None)
    monkeypatch.setattr("app.services.code_scanner.docker.from_env", lambda: client)

    with pytest.raises(ScanExecutionError):
        run_code_scan(b"fake zip bytes")

    client.containers.create.assert_not_called()


def test_run_code_scan_kills_and_removes_container_on_timeout(fake_docker):
    container = MagicMock(id="code123")
    container.wait.side_effect = Exception("timed out")
    fake_docker.containers.create.return_value = container

    with pytest.raises(ScanExecutionError):
        run_code_scan(b"fake zip bytes")

    container.kill.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_run_code_scan_treats_missing_reports_as_no_findings(fake_docker, monkeypatch):
    container = MagicMock(id="code123")
    fake_docker.containers.create.return_value = container
    monkeypatch.setattr("app.services.code_scanner._extract_json", lambda c, path: None)

    container_id, findings = run_code_scan(b"fake zip bytes")

    assert findings == []

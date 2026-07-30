from unittest.mock import MagicMock

import docker.errors
import pytest

from app.services.scanner import (
    ScanExecutionError,
    _ensure_image,
    _extract_report,
    _parse_findings,
    _parse_sqlmap_findings,
    _plain_text,
    run_sqlmap_scan,
    run_zap_scan,
)
from app.services.ssrf_guard import UnsafeScanTargetError


# ---------------------------------------------------------------------------
# Pure parsing helpers - no Docker involved, exercised directly against
# sample data shaped like real ZAP/sqlmap output.
# ---------------------------------------------------------------------------


def test_plain_text_strips_tags_and_collapses_whitespace():
    assert _plain_text("<p>Hello   <b>world</b></p>\n\n") == "Hello world"


def test_plain_text_handles_none():
    assert _plain_text(None) == ""


def test_parse_findings_maps_severity_and_strips_html():
    report = {
        "site": [
            {
                "alerts": [
                    {
                        "alertRef": "40018",
                        "riskcode": "3",
                        "name": "SQL Injection",
                        "desc": "<p>Bad stuff</p>",
                        "solution": "<p>Use <b>parameterized</b> queries</p>",
                        "instances": [
                            {"evidence": "' OR 1=1", "uri": "https://x.com/a"},
                            {"evidence": "' OR 2=2", "uri": "https://x.com/b"},
                        ],
                    }
                ]
            }
        ]
    }
    findings = _parse_findings(report, "https://x.com")
    assert len(findings) == 2
    assert findings[0]["severity"] == "high"
    assert findings[0]["description"] == "Bad stuff"
    assert findings[0]["remediation"] == "Use parameterized queries"
    assert findings[0]["affected_url"] == "https://x.com/a"
    assert findings[1]["affected_url"] == "https://x.com/b"


def test_parse_findings_defaults_severity_for_unknown_riskcode():
    report = {"site": [{"alerts": [{"riskcode": "9", "name": "Weird", "instances": []}]}]}
    findings = _parse_findings(report, "https://x.com")
    assert findings[0]["severity"] == "info"


def test_parse_findings_falls_back_to_target_url_when_instance_has_no_uri():
    report = {"site": [{"alerts": [{"riskcode": "1", "name": "Low", "instances": [{}]}]}]}
    findings = _parse_findings(report, "https://fallback.com")
    assert findings[0]["affected_url"] == "https://fallback.com"


def test_parse_findings_empty_report_yields_no_findings():
    assert _parse_findings({"site": []}, "https://x.com") == []


SQLMAP_SAMPLE_OUTPUT = """
sqlmap resumed the following injection point(s) from stored session:
---
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1 AND 5871=5871

    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: id=1 UNION ALL SELECT NULL,NULL,NULL-- -
---

[10:00:00] [INFO] the back-end DBMS is MySQL
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1 AND 5871=5871
"""


def test_parse_sqlmap_findings_extracts_and_dedupes():
    findings = _parse_sqlmap_findings(SQLMAP_SAMPLE_OUTPUT, "https://target.com")
    assert len(findings) == 2  # boolean-based blind + UNION query, repeated block deduped
    assert all(f["vuln_type"] == "sql_injection" for f in findings)
    assert all(f["severity"] == "critical" for f in findings)
    titles = {f["title"] for f in findings}
    assert "SQL Injection (boolean-based blind) - id" in titles
    assert "SQL Injection (UNION query) - id" in titles
    union_finding = next(f for f in findings if "UNION" in f["title"])
    assert union_finding["evidence"] == "id=1 UNION ALL SELECT NULL,NULL,NULL-- -"


def test_parse_sqlmap_findings_no_injection_found():
    assert _parse_sqlmap_findings("no parameters appear to be injectable", "https://x.com") == []


# ---------------------------------------------------------------------------
# _ensure_image - build-on-first-use behaviour
# ---------------------------------------------------------------------------


def test_ensure_image_skips_build_when_already_present():
    client = MagicMock()
    client.images.get.return_value = object()

    _ensure_image(client, "vulnscan/zap-scanner:latest", "/scanner")

    client.images.build.assert_not_called()


def test_ensure_image_builds_when_missing():
    client = MagicMock()
    client.images.get.side_effect = docker.errors.ImageNotFound("nope")

    _ensure_image(client, "vulnscan/zap-scanner:latest", "/scanner")

    client.images.build.assert_called_once_with(path="/scanner", tag="vulnscan/zap-scanner:latest", rm=True)


def test_ensure_image_raises_scan_execution_error_when_build_fails():
    client = MagicMock()
    client.images.get.side_effect = docker.errors.ImageNotFound("nope")
    client.images.build.side_effect = docker.errors.BuildError("boom", None)

    with pytest.raises(ScanExecutionError):
        _ensure_image(client, "vulnscan/zap-scanner:latest", "/scanner")


# ---------------------------------------------------------------------------
# _extract_report - tar-stream handling for get_archive()
# ---------------------------------------------------------------------------


def _tar_stream_with_report(report_bytes: bytes):
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name="report.json")
        info.size = len(report_bytes)
        tar.addfile(info, io.BytesIO(report_bytes))
    buf.seek(0)
    return [buf.read()]


def test_extract_report_reads_report_json_from_tar_stream():
    import json

    payload = json.dumps({"site": []}).encode()
    container = MagicMock()
    container.get_archive.return_value = (_tar_stream_with_report(payload), {})

    result = _extract_report(container)

    assert result == {"site": []}


def test_extract_report_raises_when_report_missing():
    container = MagicMock()
    container.get_archive.side_effect = docker.errors.NotFound("no such file")

    with pytest.raises(ScanExecutionError, match="unreachable"):
        _extract_report(container)


# ---------------------------------------------------------------------------
# run_zap_scan / run_sqlmap_scan - container lifecycle orchestration.
# `docker.from_env()` is monkeypatched at the module level so no real Docker
# daemon is involved; container lifecycle calls (run/wait/remove/kill) are
# asserted on a MagicMock standing in for a docker-py Container.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_docker(monkeypatch):
    client = MagicMock()
    client.images.get.return_value = object()  # image already present, skip build
    monkeypatch.setattr("app.services.scanner.docker.from_env", lambda: client)
    # Sample target URLs here (x.com, target.com) aren't meant to exercise
    # the SSRF guard/DNS-pinning logic - that's covered by the dedicated
    # tests below - so stub it to a fixed "safe, resolves to this IP"
    # answer rather than depending on a real DNS lookup in every test.
    monkeypatch.setattr("app.services.scanner.resolve_pinned_ip", lambda hostname: "203.0.113.10")
    return client


def test_run_zap_scan_happy_path(fake_docker, monkeypatch):
    container = MagicMock(id="abc123")
    fake_docker.containers.run.return_value = container
    monkeypatch.setattr(
        "app.services.scanner._extract_report", lambda c: {"site": []}
    )

    container_id, findings = run_zap_scan("https://x.com", "baseline")

    assert container_id == "abc123"
    assert findings == []
    container.wait.assert_called_once()
    container.remove.assert_called_once_with(force=True)
    fake_docker.containers.run.assert_called_once()
    _, kwargs = fake_docker.containers.run.call_args
    assert kwargs["environment"] == {"TARGET_URL": "https://x.com", "SCAN_TYPE": "baseline"}
    assert kwargs["detach"] is True
    # The container's own hostname resolution is pinned to the IP already
    # validated as public/safe - see _pin_target_dns's docstring.
    assert kwargs["extra_hosts"] == {"x.com": "203.0.113.10"}


def test_run_zap_scan_raises_when_image_missing_and_container_never_launched(fake_docker):
    fake_docker.containers.run.side_effect = docker.errors.ImageNotFound("nope")

    with pytest.raises(ScanExecutionError):
        run_zap_scan("https://x.com", "baseline")


def test_run_zap_scan_kills_and_removes_container_on_timeout(fake_docker):
    container = MagicMock(id="abc123")
    container.wait.side_effect = Exception("timed out")
    fake_docker.containers.run.return_value = container

    with pytest.raises(ScanExecutionError):
        run_zap_scan("https://x.com", "baseline")

    container.kill.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_run_zap_scan_removes_container_even_when_report_extraction_fails(fake_docker, monkeypatch):
    container = MagicMock(id="abc123")
    fake_docker.containers.run.return_value = container

    def _boom(c):
        raise ScanExecutionError("no report")

    monkeypatch.setattr("app.services.scanner._extract_report", _boom)

    with pytest.raises(ScanExecutionError):
        run_zap_scan("https://x.com", "baseline")

    container.remove.assert_called_once_with(force=True)


def test_run_sqlmap_scan_parses_container_logs(fake_docker):
    container = MagicMock(id="def456")
    container.logs.return_value = SQLMAP_SAMPLE_OUTPUT.encode()
    fake_docker.containers.run.return_value = container

    findings = run_sqlmap_scan("https://target.com")

    assert len(findings) == 2
    _, kwargs = fake_docker.containers.run.call_args
    assert kwargs["environment"] == {"TARGET_URL": "https://target.com"}
    assert kwargs["extra_hosts"] == {"target.com": "203.0.113.10"}


def test_run_sqlmap_scan_passes_cookie_when_provided(fake_docker):
    container = MagicMock(id="def456")
    container.logs.return_value = b"no parameters appear to be injectable"
    fake_docker.containers.run.return_value = container

    run_sqlmap_scan("https://target.com", cookie="PHPSESSID=abc")

    _, kwargs = fake_docker.containers.run.call_args
    assert kwargs["environment"] == {"TARGET_URL": "https://target.com", "SQLMAP_COOKIE": "PHPSESSID=abc"}


# ---------------------------------------------------------------------------
# SSRF guard re-check and DNS pinning - closes both the window between
# "domain verified"/"scan queued" (checked once already at API creation
# time) and "scan actually executes", and mid-scan DNS rebinding, since the
# scanner container is pinned via extra_hosts to the IP validated right
# before launch rather than re-resolving DNS itself during the scan.
# ---------------------------------------------------------------------------


def _raise_unsafe(hostname):
    raise UnsafeScanTargetError(f"'{hostname}' resolves internally")


def test_run_zap_scan_refuses_target_that_now_resolves_internally(fake_docker, monkeypatch):
    monkeypatch.setattr("app.services.scanner.resolve_pinned_ip", _raise_unsafe)

    with pytest.raises(ScanExecutionError):
        run_zap_scan("https://rebound.example.com", "baseline")

    fake_docker.containers.run.assert_not_called()


def test_run_sqlmap_scan_refuses_target_that_now_resolves_internally(fake_docker, monkeypatch):
    monkeypatch.setattr("app.services.scanner.resolve_pinned_ip", _raise_unsafe)

    with pytest.raises(ScanExecutionError):
        run_sqlmap_scan("https://rebound.example.com")

    fake_docker.containers.run.assert_not_called()


def test_run_zap_scan_pins_container_dns_to_the_validated_ip(fake_docker, monkeypatch):
    container = MagicMock(id="abc123")
    fake_docker.containers.run.return_value = container
    monkeypatch.setattr("app.services.scanner._extract_report", lambda c: {"site": []})
    monkeypatch.setattr("app.services.scanner.resolve_pinned_ip", lambda hostname: "198.51.100.7")

    run_zap_scan("https://pinned.example.com", "baseline")

    _, kwargs = fake_docker.containers.run.call_args
    assert kwargs["extra_hosts"] == {"pinned.example.com": "198.51.100.7"}


def test_run_zap_scan_pins_nothing_when_target_is_already_an_ip_literal(fake_docker, monkeypatch):
    container = MagicMock(id="abc123")
    fake_docker.containers.run.return_value = container
    monkeypatch.setattr("app.services.scanner._extract_report", lambda c: {"site": []})
    # resolve_pinned_ip returns the literal itself unchanged for an IP target
    # (see ssrf_guard.resolve_pinned_ip) - nothing to pin in that case.
    monkeypatch.setattr("app.services.scanner.resolve_pinned_ip", lambda hostname: hostname)

    run_zap_scan("https://203.0.113.55", "baseline")

    _, kwargs = fake_docker.containers.run.call_args
    assert kwargs["extra_hosts"] == {}

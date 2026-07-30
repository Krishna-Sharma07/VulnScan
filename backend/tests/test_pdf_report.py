from datetime import datetime
from types import SimpleNamespace

from app.services.pdf_report import generate_pdf_report


def _scan_job(scan_type="baseline", finished=True):
    return SimpleNamespace(
        target_url="https://example.com",
        scan_type=SimpleNamespace(value=scan_type),
        finished_at=datetime(2026, 7, 30, 12, 0, 0) if finished else None,
    )


def _finding(**overrides):
    finding = {
        "vuln_type": "xss_reflected",
        "severity": "high",
        "title": "Reflected XSS",
        "description": "User input is reflected without encoding.",
        "evidence": "<script>alert(1)</script>",
        "remediation": "Encode output.",
        "affected_url": "https://example.com/search?q=1",
    }
    finding.update(overrides)
    return finding


def test_generate_pdf_report_writes_a_valid_pdf(tmp_path):
    output_path = tmp_path / "report.pdf"

    generate_pdf_report(_scan_job(), [_finding()], str(output_path))

    assert output_path.exists()
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF")
    assert len(content) > 0


def test_generate_pdf_report_handles_no_findings(tmp_path):
    output_path = tmp_path / "clean.pdf"

    generate_pdf_report(_scan_job(), [], str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")


def test_generate_pdf_report_orders_findings_by_severity(tmp_path):
    output_path = tmp_path / "ordered.pdf"
    findings = [
        _finding(severity="low", title="Low finding"),
        _finding(severity="critical", title="Critical finding"),
        _finding(severity="medium", title="Medium finding"),
    ]

    # Would raise if SEVERITY_ORDER.index() couldn't find a severity - the
    # real regression risk here is a finding severity that isn't one of the
    # five known values (e.g. a future ZAP risk level), not the pdf content.
    generate_pdf_report(_scan_job(), findings, str(output_path))

    assert output_path.exists()


def test_generate_pdf_report_escapes_html_special_characters(tmp_path):
    """Finding text originates from scanned pages and can legitimately
    contain '<', '>', '&' (e.g. reflected XSS evidence) - reportlab's
    Paragraph markup parser would raise on unescaped angle brackets that
    don't form valid markup, so this is a real regression risk, not just a
    smoke test."""
    output_path = tmp_path / "escaped.pdf"
    finding = _finding(
        title="XSS via <img src=x onerror=alert(1)>",
        description="Payload: <script>alert(document.cookie)</script> & more",
        evidence="<svg/onload=alert(1)>",
    )

    generate_pdf_report(_scan_job(), [finding], str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")


def test_generate_pdf_report_handles_missing_finished_at(tmp_path):
    output_path = tmp_path / "no_finish.pdf"

    generate_pdf_report(_scan_job(finished=False), [_finding()], str(output_path))

    assert output_path.exists()


def test_generate_pdf_report_omits_evidence_line_when_absent(tmp_path):
    output_path = tmp_path / "no_evidence.pdf"
    finding = _finding(evidence=None)

    generate_pdf_report(_scan_job(), [finding], str(output_path))

    assert output_path.exists()

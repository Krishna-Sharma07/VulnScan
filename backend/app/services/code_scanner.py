import io
import json
import tarfile

import docker
import docker.errors

from app.core.config import settings
from app.services.scanner import ScanExecutionError, _ensure_image

BANDIT_SEVERITY = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}


def run_code_scan(zip_bytes: bytes) -> tuple[str, list[dict]]:
    """Launches the bandit/safety scanner container, hands it the uploaded
    zip, blocks until it finishes, and returns (container_id, finding dicts).

    Unlike run_zap_scan/run_sqlmap_scan (app/services/scanner.py), this
    container needs *input* from the worker rather than just producing
    output - the uploaded code has to get from the worker process into a
    sibling container with no shared filesystem (same Docker-out-of-Docker
    constraint documented on run_zap_scan). `put_archive` is the write-side
    counterpart of the `get_archive` those functions already use to pull
    reports out: the container is created (but not started) so the archive
    can be injected before the entrypoint script runs, then started/waited
    on like any other scan container.
    """
    client = docker.from_env()
    _ensure_image(client, settings.docker_code_scanner_image, "/code-scanner")

    try:
        container = client.containers.create(
            settings.docker_code_scanner_image,
            network=settings.docker_scan_network,
            detach=True,
        )
    except docker.errors.ImageNotFound as exc:
        raise ScanExecutionError(
            f"Scanner image '{settings.docker_code_scanner_image}' not found locally and "
            "the automatic build did not tag it as expected."
        ) from exc

    try:
        container.put_archive("/code", _wrap_upload_as_tar(zip_bytes))
        container.start()

        try:
            container.wait(timeout=settings.code_scan_timeout_seconds)
        except Exception as exc:
            container.kill()
            raise ScanExecutionError(f"Code scan container timed out or errored: {exc}") from exc

        bandit_report = _extract_json(container, "/code/bandit-report.json")
        safety_report = _extract_json(container, "/code/safety-report.json")
    finally:
        container.remove(force=True)

    findings = _parse_bandit_findings(bandit_report) + _parse_safety_findings(safety_report)
    return container.id, findings


def _wrap_upload_as_tar(zip_bytes: bytes) -> bytes:
    """put_archive needs a tar stream; the entrypoint script does the actual
    unzip once it's inside the container (see code-scanner/entrypoint.sh), so
    this only has to wrap the raw uploaded bytes as a single tar entry named
    upload.zip - no need to unpack the zip in the worker process at all."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name="upload.zip")
        info.size = len(zip_bytes)
        tar.addfile(info, io.BytesIO(zip_bytes))
    return buf.getvalue()


def _extract_json(container, path: str):
    """Best-effort report extraction: safety-report.json is always written
    (even an empty "[]" when there's nothing to scan - see entrypoint.sh),
    but a container that errored before finishing bandit could be missing
    bandit-report.json entirely, and that shouldn't sink the whole scan."""
    try:
        stream, _ = container.get_archive(path)
    except docker.errors.NotFound:
        return None

    buf = io.BytesIO()
    for chunk in stream:
        buf.write(chunk)
    buf.seek(0)

    with tarfile.open(fileobj=buf) as tar:
        member_name = path.rsplit("/", 1)[-1]
        extracted = tar.extractfile(member_name)
        if extracted is None:
            return None
        return json.load(extracted)


def _parse_bandit_findings(report) -> list[dict]:
    if not report:
        return []

    findings = []
    for result in report.get("results", []):
        severity = BANDIT_SEVERITY.get(str(result.get("issue_severity")).upper(), "medium")
        findings.append(
            {
                "source": "bandit",
                "vuln_type": result.get("test_id") or "unknown",
                "severity": severity,
                "title": result.get("test_name") or "Static analysis finding",
                "description": result.get("issue_text") or "",
                "evidence": result.get("code"),
                "remediation": (
                    f"See {result.get('more_info')} for guidance."
                    if result.get("more_info")
                    else "Review and remediate the flagged code pattern."
                ),
                "affected_file": result.get("filename") or "unknown",
                "line_number": result.get("line_number"),
            }
        )
    return findings


def _parse_safety_findings(report) -> list[dict]:
    if not report:
        return []

    # safety's --json output has taken a couple of shapes across versions -
    # a dict with a top-level "vulnerabilities" list (2.x, pinned here - see
    # code-scanner/Dockerfile) or, on some setups, a bare list. Handled
    # loosely rather than pinned to one exact schema.
    vulnerabilities = report.get("vulnerabilities", []) if isinstance(report, dict) else report
    if not vulnerabilities:
        return []

    findings = []
    for vuln in vulnerabilities:
        if not isinstance(vuln, dict):
            continue
        package = vuln.get("package_name") or "unknown package"
        findings.append(
            {
                "source": "safety",
                "vuln_type": vuln.get("vulnerability_id") or "dependency_vulnerability",
                # safety's free tier frequently omits structured severity
                # data (it's a paid-tier feature) - a known dependency CVE
                # defaults to "high" rather than silently downgrading it.
                "severity": _safety_severity(vuln),
                "title": f"Vulnerable dependency: {package} {vuln.get('analyzed_version') or ''}".strip(),
                "description": vuln.get("advisory") or "A known vulnerability was found in this dependency.",
                "evidence": vuln.get("vulnerable_spec"),
                "remediation": "Upgrade the package to a version outside the vulnerable range.",
                "affected_file": "requirements.txt",
                "line_number": None,
            }
        )
    return findings


def _safety_severity(vuln: dict) -> str:
    severity = vuln.get("severity")
    if isinstance(severity, dict):
        label = str(severity.get("cvssv3", {}).get("base_severity") or "").lower()
        if label in {"critical", "high", "medium", "low"}:
            return label
    return "high"

import io
import json
import tarfile

import docker
import docker.errors

from app.core.config import settings

# ZAP's riskcode: 3=High, 2=Medium, 1=Low, 0=Informational.
RISK_TO_SEVERITY = {"3": "high", "2": "medium", "1": "low", "0": "info"}


class ScanExecutionError(Exception):
    """Raised when the scan container never produced a usable report."""


def run_zap_scan(target_url: str, scan_type: str) -> tuple[str, list[dict]]:
    """Launches the ZAP scanner container against target_url, blocks until it
    finishes, and returns (container_id, list of finding dicts).

    The worker runs this container via the *host's* Docker daemon (its own
    container mounts the host's docker.sock - "Docker-out-of-Docker"), so it
    is a sibling of the worker, not a child of it. A bind mount pointing at a
    path inside the worker container would not resolve on the host, so there
    is no shared filesystem to hand the report back through. Instead,
    `get_archive` pulls the report file straight out of the stopped
    container over the Docker API as a tar stream.
    """
    client = docker.from_env()

    try:
        container = client.containers.run(
            settings.docker_scanner_image,
            environment={"TARGET_URL": target_url, "SCAN_TYPE": scan_type},
            detach=True,
        )
    except docker.errors.ImageNotFound as exc:
        raise ScanExecutionError(
            f"Scanner image '{settings.docker_scanner_image}' not found locally. "
            "Build it once with: docker build -t vulnscan/zap-scanner:latest ./scanner"
        ) from exc

    try:
        try:
            container.wait(timeout=settings.scan_timeout_seconds)
        except Exception as exc:
            container.kill()
            raise ScanExecutionError(f"Scan container timed out or errored: {exc}") from exc

        report = _extract_report(container)
    finally:
        container.remove(force=True)

    return container.id, _parse_findings(report, target_url)


def _extract_report(container) -> dict:
    try:
        stream, _ = container.get_archive("/zap/wrk/report.json")
    except docker.errors.NotFound as exc:
        raise ScanExecutionError(
            "Scanner produced no report - target was likely unreachable"
        ) from exc

    buf = io.BytesIO()
    for chunk in stream:
        buf.write(chunk)
    buf.seek(0)

    with tarfile.open(fileobj=buf) as tar:
        extracted = tar.extractfile("report.json")
        return json.load(extracted)


def _parse_findings(report: dict, target_url: str) -> list[dict]:
    findings = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            severity = RISK_TO_SEVERITY.get(str(alert.get("riskcode")), "info")
            for instance in alert.get("instances") or [{}]:
                findings.append(
                    {
                        "vuln_type": alert.get("alertRef") or alert.get("pluginid") or "unknown",
                        "severity": severity,
                        "title": alert.get("name") or alert.get("alert") or "Unnamed finding",
                        "description": alert.get("desc") or "",
                        "evidence": instance.get("evidence"),
                        "remediation": alert.get("solution") or "",
                        "affected_url": instance.get("uri") or target_url,
                    }
                )
    return findings

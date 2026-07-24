import io
import json
import re
import tarfile

import docker
import docker.errors

from app.core.config import settings

# ZAP's riskcode: 3=High, 2=Medium, 1=Low, 0=Informational.
RISK_TO_SEVERITY = {"3": "high", "2": "medium", "1": "low", "0": "info"}

_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(html: str) -> str:
    """ZAP's desc/solution fields come back as HTML fragments (<p>...</p>).
    Findings are stored as plain text - the DB is the single source of truth
    consumed by both the API/frontend and the PDF renderer, so this strips
    tags once here rather than leaving raw HTML for each consumer to handle."""
    text = _TAG_RE.sub(" ", html or "")
    return re.sub(r"\s+", " ", text).strip()


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
    _ensure_image(client, settings.docker_scanner_image, "/scanner")

    try:
        container = client.containers.run(
            settings.docker_scanner_image,
            environment={"TARGET_URL": target_url, "SCAN_TYPE": scan_type},
            detach=True,
        )
    except docker.errors.ImageNotFound as exc:
        raise ScanExecutionError(
            f"Scanner image '{settings.docker_scanner_image}' not found locally and "
            "the automatic build did not tag it as expected."
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


def run_sqlmap_scan(target_url: str) -> list[dict]:
    """Launches the sqlmap scanner container against target_url, blocks until
    it finishes, and returns a list of SQL-injection finding dicts.

    Only called for scan_type="aggressive" (see app/worker/tasks.py) - sqlmap
    sends far more, and more intrusive, requests than ZAP's baseline/full
    scans, so it's opt-in rather than run by default (see NOTES.md).

    Unlike run_zap_scan, results come from the container's *stdout* rather
    than a report file pulled via get_archive - sqlmap prints a clean
    "Parameter: ... / Type: ... / Title: ... / Payload: ..." block for every
    injectable parameter it finds, and docker-py's container.logs() captures
    that directly with no file-extraction step needed.
    """
    client = docker.from_env()
    _ensure_image(client, settings.docker_sqlmap_image, "/sqlmap-scanner")

    try:
        container = client.containers.run(
            settings.docker_sqlmap_image,
            environment={"TARGET_URL": target_url},
            detach=True,
        )
    except docker.errors.ImageNotFound as exc:
        raise ScanExecutionError(
            f"Scanner image '{settings.docker_sqlmap_image}' not found locally and "
            "the automatic build did not tag it as expected."
        ) from exc

    try:
        try:
            container.wait(timeout=settings.sqlmap_timeout_seconds)
        except Exception as exc:
            container.kill()
            raise ScanExecutionError(f"sqlmap container timed out or errored: {exc}") from exc

        output = container.logs().decode("utf-8", errors="replace")
    finally:
        container.remove(force=True)

    return _parse_sqlmap_findings(output, target_url)


def _ensure_image(client: "docker.DockerClient", image: str, build_path: str) -> None:
    """Builds a scanner image on first use if it isn't already present,
    instead of requiring a manual `docker build` step before the first scan.

    `client.images.build(path=...)` reads the build context from wherever the
    docker-py *client* process runs (here, the worker container's own
    filesystem via a read-only bind mount), tars it up, and streams it to
    the daemon over the docker.sock connection - it does not need a host
    path the daemon can see, unlike a container bind mount (see the
    Docker-out-of-Docker note on run_zap_scan). The Docker build cache is
    keyed on the daemon side by layer content, so repeated calls after the
    first are a fast no-op rather than a full rebuild each scan.
    """
    try:
        client.images.get(image)
        return
    except docker.errors.ImageNotFound:
        pass

    try:
        client.images.build(path=build_path, tag=image, rm=True)
    except docker.errors.BuildError as exc:
        raise ScanExecutionError(
            f"Scanner image '{image}' was missing and the automatic build "
            f"from {build_path} failed: {exc}"
        ) from exc


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
                        "description": _plain_text(alert.get("desc")),
                        "evidence": instance.get("evidence"),
                        "remediation": _plain_text(alert.get("solution")),
                        "affected_url": instance.get("uri") or target_url,
                    }
                )
    return findings


# Matches one "Parameter: id (GET)" block plus everything up to the next
# "Parameter:" line (or end of output) - the body may contain several
# Type/Title/Payload groups if sqlmap found multiple injection techniques
# for the same parameter.
_SQLMAP_PARAM_RE = re.compile(
    r"^Parameter:\s*(?P<param>[^\n(]+?)\s*\((?P<location>[A-Z]+)\)\s*$"
    r"(?P<body>(?:\n(?!Parameter:).*)*)",
    re.MULTILINE,
)
_SQLMAP_TECHNIQUE_RE = re.compile(
    r"Type:\s*(?P<type>.+?)\s*\n\s*Title:\s*(?P<title>.+?)\s*"
    r"(?:\n\s*Payload:\s*(?P<payload>.+?)\s*)?(?=\n|$)"
)


def _parse_sqlmap_findings(output: str, target_url: str) -> list[dict]:
    """sqlmap prints one block like this to stdout per vulnerable parameter
    (and may repeat it in a final summary, hence the dedupe set below):

        Parameter: id (GET)
            Type: boolean-based blind
            Title: AND boolean-based blind - WHERE or HAVING clause
            Payload: id=1 AND 5871=5871

    No JSON export exists for this, so it's parsed out of the raw log text
    rather than a structured report file (contrast with ZAP's report.json).
    """
    findings = []
    seen = set()
    for pmatch in _SQLMAP_PARAM_RE.finditer(output):
        param = pmatch.group("param").strip()
        location = pmatch.group("location").strip()
        for tmatch in _SQLMAP_TECHNIQUE_RE.finditer(pmatch.group("body")):
            vuln_type = tmatch.group("type").strip()
            title = tmatch.group("title").strip()
            payload = (tmatch.group("payload") or "").strip() or None

            dedupe_key = (param, location, vuln_type, title)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            findings.append(
                {
                    "vuln_type": "sql_injection",
                    "severity": "critical",
                    "title": f"SQL Injection ({vuln_type}) - {param}",
                    "description": (
                        f"sqlmap found the '{param}' {location} parameter to be "
                        f"vulnerable to SQL injection: {title}."
                    ),
                    "evidence": payload,
                    "remediation": (
                        "Use parameterized queries / prepared statements for all "
                        "database access - never build SQL by concatenating user input."
                    ),
                    "affected_url": target_url,
                }
            )
    return findings

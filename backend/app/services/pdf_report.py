from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

SEVERITY_COLORS = {
    "critical": "#7f1d1d",
    "high": "#dc2626",
    "medium": "#f59e0b",
    "low": "#3b82f6",
    "info": "#6b7280",
}


def _escape(text: str) -> str:
    """findings' description/remediation are already plain text (HTML
    stripped in scanner.py._plain_text before hitting the DB) - this only
    re-escapes &/</> so reportlab's Paragraph markup parser can't misread
    literal angle brackets that appeared in the original scanned page."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_pdf_report(scan_job, findings: list[dict], output_path: str) -> None:
    """Renders a scan's findings to a PDF at output_path. `findings` is the
    same list of dicts (vuln_type, severity, title, description, evidence,
    remediation, affected_url) used to create the Finding rows - generating
    from that avoids depending on the DB session still being open."""
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], spaceAfter=4)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#4b5563"))

    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    story = []

    story.append(Paragraph("VulnScan Pro — Security Report", title_style))
    story.append(Paragraph(_escape(scan_job.target_url), meta_style))
    story.append(
        Paragraph(
            f"Scan type: {scan_job.scan_type.value} &nbsp;|&nbsp; "
            f"Completed: {scan_job.finished_at.strftime('%Y-%m-%d %H:%M UTC') if scan_job.finished_at else 'n/a'}",
            meta_style,
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

    summary_data = [["Severity", "Count"]] + [[sev.capitalize(), str(counts[sev])] for sev in SEVERITY_ORDER]
    summary_table = Table(summary_data, colWidths=[6 * cm, 3 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 1 * cm))

    if not findings:
        story.append(Paragraph("No findings were reported for this scan.", body_style))
    else:
        ordered = sorted(findings, key=lambda f: SEVERITY_ORDER.index(f["severity"]))
        for finding in ordered:
            badge_color = SEVERITY_COLORS.get(finding["severity"], "#6b7280")
            story.append(
                Paragraph(
                    f'<font color="{badge_color}"><b>[{finding["severity"].upper()}]</b></font> '
                    f'{_escape(finding["title"])}',
                    heading_style,
                )
            )
            story.append(Paragraph(f'<b>Affected URL:</b> {_escape(finding["affected_url"])}', body_style))
            story.append(Paragraph(f'<b>Description:</b> {_escape(finding["description"])}', body_style))
            if finding.get("evidence"):
                story.append(Paragraph(f'<b>Evidence:</b> {_escape(finding["evidence"])}', body_style))
            story.append(Paragraph(f'<b>Remediation:</b> {_escape(finding["remediation"])}', body_style))
            story.append(Spacer(1, 0.4 * cm))

    doc.build(story)

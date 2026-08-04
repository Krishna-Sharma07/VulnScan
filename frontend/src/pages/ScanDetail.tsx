import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import Tag, { statusTone } from "../components/Tag";
import type { ScanReport, Severity } from "../types";

const severityOrder: Severity[] = ["critical", "high", "medium", "low", "info"];

export default function ScanDetail() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<ScanReport | null>(null);
  const [downloading, setDownloading] = useState(false);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    const res = await api.get<ScanReport>(`/api/reports/${id}`);
    setReport(res.data);
    return res.data;
  }, [id]);

  useEffect(() => {
    load();
    // A scan runs in the background (Celery worker), so this page polls
    // every 3s until it leaves pending/running - simplest way to reflect
    // progress without adding websockets for a single status field.
    pollRef.current = window.setInterval(async () => {
      const data = await load();
      if (data && data.status !== "pending" && data.status !== "running") {
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    }, 3000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [load]);

  async function downloadPdf() {
    if (!id) return;
    setDownloading(true);
    try {
      // FileResponse is behind JWT auth, so a plain <a href> can't attach
      // the Authorization header - fetch it as a blob via axios (which
      // does attach it via the interceptor) and trigger the download
      // client-side from an in-memory object URL instead.
      const res = await api.get(`/api/reports/${id}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `vulnscan-report-${id}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch {
      alert("PDF report not available yet");
    } finally {
      setDownloading(false);
    }
  }

  if (!report) return <p className="text-muted font-mono">Loading...</p>;

  const findingsBySeverity = severityOrder
    .map((sev) => ({ sev, findings: report.findings.filter((f) => f.severity === sev) }))
    .filter((group) => group.findings.length > 0);

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-6">
        <div>
          <h1 className="font-mono text-2xl font-semibold text-ink break-all">
            {report.target_url}
          </h1>
          <p className="text-sm text-muted mt-1">
            {report.scan_type} scan · <Tag tone={statusTone[report.status]}>{report.status}</Tag>
          </p>
        </div>
        {report.status === "completed" && (
          <button
            onClick={downloadPdf}
            disabled={downloading}
            className="shrink-0 bg-signal text-surface px-4 py-2 text-sm font-mono font-medium hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
          >
            {downloading ? "Preparing..." : "Download PDF"}
          </button>
        )}
      </div>

      {(report.status === "pending" || report.status === "running") && (
        <p className="text-muted">Scan is {report.status} — this page updates automatically.</p>
      )}

      {report.status === "failed" && (
        <p className="text-critical">Scan failed. Start a new one to try again.</p>
      )}

      {report.status === "completed" && (
        <div className="space-y-6">
          <p className="text-sm text-muted font-mono">{report.findings.length} findings</p>
          {findingsBySeverity.map(({ sev, findings }) => (
            <div key={sev}>
              <h2 className="font-mono text-lg font-semibold text-ink mb-2 capitalize">{sev}</h2>
              <div className="space-y-2">
                {findings.map((finding) => (
                  <div key={finding.id} className="bg-surface border border-hairline p-4">
                    <div className="flex items-start justify-between gap-4">
                      <p className="font-medium text-ink">{finding.title}</p>
                      <Tag tone={finding.severity}>{finding.severity}</Tag>
                    </div>
                    <p className="text-sm text-muted mt-1">{finding.description}</p>
                    <p className="text-xs text-muted font-mono mt-2 break-all">
                      {finding.affected_url}
                    </p>
                    <p className="text-sm text-ink mt-2">
                      <span className="font-medium">Remediation: </span>
                      {finding.remediation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {report.findings.length === 0 && (
            <p className="text-muted">No findings — clean scan.</p>
          )}
        </div>
      )}
    </div>
  );
}

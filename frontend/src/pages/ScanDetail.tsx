import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ScanReport, Severity } from "../types";

const severityColor: Record<Severity, string> = {
  critical: "bg-red-600 text-white",
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-blue-100 text-blue-700",
  info: "bg-gray-100 text-gray-600",
};

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

  if (!report) return <p className="text-gray-500">Loading...</p>;

  const findingsBySeverity = severityOrder
    .map((sev) => ({ sev, findings: report.findings.filter((f) => f.severity === sev) }))
    .filter((group) => group.findings.length > 0);

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">{report.target_url}</h1>
          <p className="text-sm text-gray-500">
            {report.scan_type} scan · status:{" "}
            <span className="font-medium">{report.status}</span>
          </p>
        </div>
        {report.status === "completed" && (
          <button
            onClick={downloadPdf}
            disabled={downloading}
            className="bg-indigo-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {downloading ? "Preparing..." : "Download PDF"}
          </button>
        )}
      </div>

      {(report.status === "pending" || report.status === "running") && (
        <p className="text-gray-600">
          Scan is {report.status}... this page updates automatically.
        </p>
      )}

      {report.status === "failed" && (
        <p className="text-red-600">Scan failed. Try starting a new one.</p>
      )}

      {report.status === "completed" && (
        <div className="space-y-6">
          <p className="text-sm text-gray-600">{report.findings.length} findings</p>
          {findingsBySeverity.map(({ sev, findings }) => (
            <div key={sev}>
              <h2 className="text-lg font-semibold mb-2 capitalize">{sev}</h2>
              <div className="space-y-2">
                {findings.map((finding) => (
                  <div key={finding.id} className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between gap-4">
                      <p className="font-medium">{finding.title}</p>
                      <span
                        className={`text-xs font-semibold px-2 py-1 rounded-full shrink-0 ${severityColor[finding.severity]}`}
                      >
                        {finding.severity}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{finding.description}</p>
                    <p className="text-xs text-gray-400 mt-2 break-all">{finding.affected_url}</p>
                    <p className="text-sm text-gray-700 mt-2">
                      <span className="font-medium">Remediation: </span>
                      {finding.remediation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {report.findings.length === 0 && (
            <p className="text-gray-500">No findings — clean scan.</p>
          )}
        </div>
      )}
    </div>
  );
}

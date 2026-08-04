import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, extractErrorMessage } from "../api/client";
import Tag, { statusTone } from "../components/Tag";
import type { BillingUsage, CodeScanJob } from "../types";

export default function CodeScan() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [history, setHistory] = useState<CodeScanJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<BillingUsage>("/api/billing/usage").then((res) => setUsage(res.data));
    api.get<CodeScanJob[]>("/api/code-scans").then((res) => {
      setHistory(res.data);
      setHistoryLoading(false);
    });
  }, []);

  const quotaReached =
    usage?.monthly_scan_limit != null && usage.scans_used_this_month >= usage.monthly_scan_limit;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/api/code-scans", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      navigate(`/code-scan/${res.data.id}`);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Could not start code scan"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">Code Scan</h1>

      <div className="max-w-md mb-10">
        <p className="text-sm text-muted mb-4">
          Upload a .zip of your code. Bandit flags insecure Python patterns, safety flags
          known-vulnerable dependencies — nothing you upload is ever executed, only read.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="code-upload" className="block text-sm font-medium text-muted">
              Code archive (.zip)
            </label>
            <input
              id="code-upload"
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 w-full text-sm focus:ring-2 focus:ring-signal focus:outline-none"
            />
          </div>
          {quotaReached && (
            <p className="text-sm text-medium border border-medium px-3 py-2">
              You've used all {usage!.monthly_scan_limit} scans included in the free plan this
              month.{" "}
              <a href="/billing" className="underline">
                Upgrade on the Billing page
              </a>{" "}
              for unlimited scans.
            </p>
          )}
          {error && <p className="text-sm text-critical">{error}</p>}
          <button
            type="submit"
            disabled={submitting || quotaReached || !file}
            className="w-full bg-signal text-surface py-2 font-mono font-medium hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
          >
            {submitting ? "Uploading..." : "Start code scan"}
          </button>
        </form>
      </div>

      <h2 className="font-mono text-lg font-semibold text-ink mb-4">Past code scans</h2>
      <div className="space-y-3">
        {history.map((scan) => (
          <Link
            key={scan.id}
            to={`/code-scan/${scan.id}`}
            className="block bg-surface border border-hairline p-4 hover:border-signal focus:ring-2 focus:ring-signal focus:outline-none"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-ink">{scan.filename}</p>
                <p className="text-xs text-muted font-mono">
                  {new Date(scan.created_at).toLocaleString()}
                </p>
              </div>
              <Tag tone={statusTone[scan.status]}>{scan.status}</Tag>
            </div>
          </Link>
        ))}
        {!historyLoading && history.length === 0 && (
          <p className="text-muted text-sm">No code scans yet.</p>
        )}
      </div>
    </div>
  );
}

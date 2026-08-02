import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, extractErrorMessage } from "../api/client";
import type { BillingUsage, CodeScanJob } from "../types";

const statusColor: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function CodeScan() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [history, setHistory] = useState<CodeScanJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<BillingUsage>("/api/billing/usage").then((res) => setUsage(res.data));
    api.get<CodeScanJob[]>("/api/code-scans").then((res) => setHistory(res.data));
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
      <h1 className="text-2xl font-semibold mb-6">Code Scan</h1>

      <div className="max-w-md mb-10">
        <p className="text-sm text-gray-600 mb-4">
          Upload a .zip of your code and we'll run static analysis (bandit for Python security
          issues, safety for known-vulnerable dependencies) against it - nothing is executed, only
          read.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="code-upload" className="block text-sm font-medium text-gray-700">
              Code archive (.zip)
            </label>
            <input
              id="code-upload"
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 w-full text-sm"
            />
          </div>
          {quotaReached && (
            <p className="text-sm text-amber-700 bg-amber-50 rounded-md px-3 py-2">
              You've used all {usage!.monthly_scan_limit} scans included in the free plan this
              month.{" "}
              <a href="/billing" className="underline">
                Upgrade on the Billing page
              </a>{" "}
              for unlimited scans.
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={submitting || quotaReached || !file}
            className="w-full bg-indigo-600 text-white rounded-md py-2 font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Uploading..." : "Start code scan"}
          </button>
        </form>
      </div>

      <h2 className="text-lg font-semibold mb-4">Past code scans</h2>
      <div className="space-y-3">
        {history.map((scan) => (
          <Link
            key={scan.id}
            to={`/code-scan/${scan.id}`}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-indigo-300"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{scan.filename}</p>
                <p className="text-xs text-gray-500">{new Date(scan.created_at).toLocaleString()}</p>
              </div>
              <span
                className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor[scan.status]}`}
              >
                {scan.status}
              </span>
            </div>
          </Link>
        ))}
        {history.length === 0 && <p className="text-gray-500 text-sm">No code scans yet.</p>}
      </div>
    </div>
  );
}

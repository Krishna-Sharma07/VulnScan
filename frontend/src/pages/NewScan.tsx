import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Domain, ScanType } from "../types";

export default function NewScan() {
  const navigate = useNavigate();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [domainId, setDomainId] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [scanType, setScanType] = useState<ScanType>("baseline");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get<Domain[]>("/api/domains").then((res) => {
      const verified = res.data.filter((d) => d.verified);
      setDomains(verified);
      if (verified.length > 0) {
        setDomainId(verified[0].id);
        setTargetUrl(`https://${verified[0].hostname}`);
      }
    });
  }, []);

  function handleDomainChange(id: string) {
    setDomainId(id);
    const domain = domains.find((d) => d.id === id);
    if (domain) setTargetUrl(`https://${domain.hostname}`);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.post("/api/scan", {
        domain_id: domainId,
        target_url: targetUrl,
        scan_type: scanType,
      });
      navigate(`/scan/${res.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not start scan");
    } finally {
      setSubmitting(false);
    }
  }

  if (domains.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-semibold mb-4">New Scan</h1>
        <p className="text-gray-600">
          You need at least one verified domain before you can run a scan. Go to{" "}
          <a href="/domains" className="text-indigo-600">
            Domains
          </a>{" "}
          to add and verify one.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-md">
      <h1 className="text-2xl font-semibold mb-6">New Scan</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Domain</label>
          <select
            value={domainId}
            onChange={(e) => handleDomainChange(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          >
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.hostname}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Target URL</label>
          <input
            type="url"
            required
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          />
          <p className="text-xs text-gray-500 mt-1">
            Must exactly match the verified domain's host.
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Scan type</label>
          <select
            value={scanType}
            onChange={(e) => setScanType(e.target.value as ScanType)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
          >
            <option value="baseline">Baseline (passive, safe default)</option>
            <option value="aggressive">Aggressive (active scanning, more traffic)</option>
          </select>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-indigo-600 text-white rounded-md py-2 font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? "Starting..." : "Start scan"}
        </button>
      </form>
    </div>
  );
}

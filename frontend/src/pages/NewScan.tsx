import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { BillingUsage, Domain, ScanType } from "../types";

export default function NewScan() {
  const navigate = useNavigate();
  const [domains, setDomains] = useState<Domain[]>([]);
  const [domainId, setDomainId] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [scanType, setScanType] = useState<ScanType>("baseline");
  const [usage, setUsage] = useState<BillingUsage | null>(null);
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
    api.get<BillingUsage>("/api/billing/usage").then((res) => setUsage(res.data));
  }, []);

  const quotaReached =
    usage?.monthly_scan_limit != null && usage.scans_used_this_month >= usage.monthly_scan_limit;

  function handleDomainChange(id: string) {
    setDomainId(id);
    const domain = domains.find((d) => d.id === id);
    if (domain) setTargetUrl(`https://${domain.hostname}`);
  }

  const selectedDomain = domains.find((d) => d.id === domainId);

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
        <h1 className="font-mono text-2xl font-semibold text-ink mb-4">New Scan</h1>
        <p className="text-muted">
          You need at least one verified domain before you can run a scan. Go to{" "}
          <a href="/domains" className="text-signal">
            Domains
          </a>{" "}
          to add and verify one.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-md">
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">New Scan</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="scan-domain" className="block text-sm font-medium text-muted">
            Domain
          </label>
          <select
            id="scan-domain"
            value={domainId}
            onChange={(e) => handleDomainChange(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          >
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.hostname}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="scan-target-url" className="block text-sm font-medium text-muted">
            Target URL
          </label>
          <input
            id="scan-target-url"
            type="url"
            required
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          />
          <p className="text-xs text-muted mt-1">Must exactly match the verified domain's host.</p>
        </div>
        <div>
          <label htmlFor="scan-type" className="block text-sm font-medium text-muted">
            Scan type
          </label>
          <select
            id="scan-type"
            value={scanType}
            onChange={(e) => setScanType(e.target.value as ScanType)}
            className="mt-1 w-full border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
          >
            <option value="baseline">Baseline (passive, safe default)</option>
            <option value="aggressive" disabled={usage != null && !usage.aggressive_allowed}>
              Aggressive (active scanning, more traffic)
              {usage != null && !usage.aggressive_allowed ? " - Pro/Enterprise only" : ""}
            </option>
          </select>
          {usage != null && !usage.aggressive_allowed && (
            <p className="text-xs text-medium border border-medium px-3 py-2 mt-2">
              Aggressive scans require Pro or Enterprise.{" "}
              <a href="/billing" className="underline">
                Upgrade on the Billing page
              </a>
              .
            </p>
          )}
          {scanType === "aggressive" && selectedDomain && !selectedDomain.has_auth_cookie && (
            <p className="text-xs text-medium border border-medium px-3 py-2 mt-2">
              If this target sits behind a login, sqlmap won't be able to reach the vulnerable
              pages without a session cookie. Set one on the{" "}
              <a href="/domains" className="underline">
                Domains
              </a>{" "}
              page first.
            </p>
          )}
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
          disabled={submitting || quotaReached}
          className="w-full bg-signal text-surface py-2 font-mono font-medium hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
        >
          {submitting ? "Starting..." : "Start scan"}
        </button>
      </form>
    </div>
  );
}

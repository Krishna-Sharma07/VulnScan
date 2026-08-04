import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import Tag from "../components/Tag";
import type { Domain } from "../types";

export default function Domains() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [hostname, setHostname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<Record<string, string>>({});
  const [verifying, setVerifying] = useState<string | null>(null);

  const [cookieEditing, setCookieEditing] = useState<Record<string, boolean>>({});
  const [cookieInputs, setCookieInputs] = useState<Record<string, string>>({});
  const [cookieSaving, setCookieSaving] = useState<string | null>(null);
  const [cookieError, setCookieError] = useState<Record<string, string>>({});

  async function loadDomains() {
    const res = await api.get<Domain[]>("/api/domains");
    setDomains(res.data);
    setLoading(false);
  }

  useEffect(() => {
    loadDomains();
  }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/domains", { hostname });
      setHostname("");
      await loadDomains();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not add domain");
    }
  }

  async function handleVerify(domain: Domain) {
    setVerifying(domain.id);
    setVerifyError((prev) => ({ ...prev, [domain.id]: "" }));
    try {
      await api.post(`/api/domains/${domain.id}/verify`);
      await loadDomains();
    } catch (err: any) {
      setVerifyError((prev) => ({
        ...prev,
        [domain.id]: err.response?.data?.detail ?? "Verification failed",
      }));
    } finally {
      setVerifying(null);
    }
  }

  async function handleSaveCookie(domain: Domain) {
    setCookieSaving(domain.id);
    setCookieError((prev) => ({ ...prev, [domain.id]: "" }));
    try {
      await api.put(`/api/domains/${domain.id}/auth-cookie`, {
        auth_cookie: cookieInputs[domain.id] ?? "",
      });
      setCookieEditing((prev) => ({ ...prev, [domain.id]: false }));
      setCookieInputs((prev) => ({ ...prev, [domain.id]: "" }));
      await loadDomains();
    } catch (err: any) {
      setCookieError((prev) => ({
        ...prev,
        [domain.id]: err.response?.data?.detail ?? "Could not save cookie",
      }));
    } finally {
      setCookieSaving(null);
    }
  }

  async function handleClearCookie(domain: Domain) {
    setCookieSaving(domain.id);
    setCookieError((prev) => ({ ...prev, [domain.id]: "" }));
    try {
      await api.put(`/api/domains/${domain.id}/auth-cookie`, { auth_cookie: null });
      await loadDomains();
    } catch (err: any) {
      setCookieError((prev) => ({
        ...prev,
        [domain.id]: err.response?.data?.detail ?? "Could not clear cookie",
      }));
    } finally {
      setCookieSaving(null);
    }
  }

  return (
    <div>
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">Domains</h1>

      <form onSubmit={handleAdd} className="flex gap-2 mb-8 max-w-md">
        <input
          type="text"
          required
          placeholder="example.com"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          className="flex-1 border border-hairline bg-surface text-ink px-3 py-2 focus:ring-2 focus:ring-signal focus:outline-none"
        />
        <button
          type="submit"
          className="bg-signal text-surface px-4 py-2 font-mono font-medium hover:bg-signal-dark focus:ring-2 focus:ring-signal focus:outline-none"
        >
          Add domain
        </button>
      </form>
      {error && <p className="text-sm text-critical mb-4">{error}</p>}

      <div className="space-y-4">
        {domains.map((domain) => (
          <div key={domain.id} className="bg-surface border border-hairline p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-ink">{domain.hostname}</p>
                <p className="text-xs text-muted">
                  Added {new Date(domain.created_at).toLocaleString()}
                </p>
              </div>
              {domain.verified ? (
                <Tag tone="low">Verified</Tag>
              ) : (
                <button
                  onClick={() => handleVerify(domain)}
                  disabled={verifying === domain.id}
                  className="text-xs font-mono font-semibold px-3 py-1.5 border border-medium text-medium hover:bg-paper disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
                >
                  {verifying === domain.id ? "Checking..." : "Check verification"}
                </button>
              )}
            </div>

            {!domain.verified && (
              <div className="mt-3 text-sm bg-paper p-3">
                <p className="text-muted mb-1">
                  Add a DNS TXT record on <strong className="text-ink">{domain.hostname}</strong>{" "}
                  with this value, then click "Check verification":
                </p>
                <code className="block bg-surface border border-hairline px-2 py-1 text-xs break-all font-mono">
                  vulnscan-verify={domain.verification_token}
                </code>
                {verifyError[domain.id] && (
                  <p className="text-critical text-xs mt-2">{verifyError[domain.id]}</p>
                )}
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-hairline">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-ink">Auth cookie (for aggressive scans)</p>
                  <p className="text-xs text-muted">
                    Only needed if the target sits behind a login — sqlmap sends this cookie so it
                    can reach pages a logged-out request can't.{" "}
                    {domain.has_auth_cookie ? (
                      <span className="text-low font-medium">Cookie set.</span>
                    ) : (
                      <span>None set.</span>
                    )}
                  </p>
                </div>
                {!cookieEditing[domain.id] && (
                  <button
                    onClick={() => setCookieEditing((prev) => ({ ...prev, [domain.id]: true }))}
                    className="text-xs font-mono font-semibold px-3 py-1.5 border border-hairline text-ink hover:bg-paper shrink-0 focus:ring-2 focus:ring-signal focus:outline-none"
                  >
                    {domain.has_auth_cookie ? "Update" : "Set cookie"}
                  </button>
                )}
              </div>

              {cookieEditing[domain.id] && (
                <div className="mt-2 flex gap-2">
                  <input
                    type="password"
                    placeholder="security=low; PHPSESSID=..."
                    value={cookieInputs[domain.id] ?? ""}
                    onChange={(e) =>
                      setCookieInputs((prev) => ({ ...prev, [domain.id]: e.target.value }))
                    }
                    className="flex-1 border border-hairline bg-surface text-ink px-3 py-1.5 text-sm focus:ring-2 focus:ring-signal focus:outline-none"
                  />
                  <button
                    onClick={() => handleSaveCookie(domain)}
                    disabled={cookieSaving === domain.id}
                    className="text-xs font-mono font-semibold px-3 py-1.5 bg-signal text-surface hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setCookieEditing((prev) => ({ ...prev, [domain.id]: false }));
                      setCookieInputs((prev) => ({ ...prev, [domain.id]: "" }));
                    }}
                    className="text-xs font-mono font-semibold px-3 py-1.5 border border-hairline text-ink hover:bg-paper focus:ring-2 focus:ring-signal focus:outline-none"
                  >
                    Cancel
                  </button>
                </div>
              )}
              {domain.has_auth_cookie && !cookieEditing[domain.id] && (
                <button
                  onClick={() => handleClearCookie(domain)}
                  disabled={cookieSaving === domain.id}
                  className="mt-2 text-xs text-critical hover:underline disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
                >
                  Clear cookie
                </button>
              )}
              {cookieError[domain.id] && (
                <p className="text-critical text-xs mt-2">{cookieError[domain.id]}</p>
              )}
            </div>
          </div>
        ))}
        {!loading && domains.length === 0 && (
          <p className="text-muted text-sm">No domains yet — add one above to start scanning.</p>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Domain } from "../types";

export default function Domains() {
  const [domains, setDomains] = useState<Domain[]>([]);
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
      <h1 className="text-2xl font-semibold mb-6">Domains</h1>

      <form onSubmit={handleAdd} className="flex gap-2 mb-8 max-w-md">
        <input
          type="text"
          required
          placeholder="example.com"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2"
        />
        <button
          type="submit"
          className="bg-indigo-600 text-white rounded-md px-4 py-2 font-medium hover:bg-indigo-700"
        >
          Add domain
        </button>
      </form>
      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="space-y-4">
        {domains.map((domain) => (
          <div key={domain.id} className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{domain.hostname}</p>
                <p className="text-xs text-gray-500">
                  Added {new Date(domain.created_at).toLocaleString()}
                </p>
              </div>
              {domain.verified ? (
                <span className="text-xs font-semibold px-2 py-1 rounded-full bg-green-100 text-green-700">
                  Verified
                </span>
              ) : (
                <button
                  onClick={() => handleVerify(domain)}
                  disabled={verifying === domain.id}
                  className="text-xs font-semibold px-3 py-1.5 rounded-md bg-amber-100 text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                >
                  {verifying === domain.id ? "Checking..." : "Check verification"}
                </button>
              )}
            </div>

            {!domain.verified && (
              <div className="mt-3 text-sm bg-gray-50 rounded-md p-3">
                <p className="text-gray-600 mb-1">
                  Add a DNS TXT record on <strong>{domain.hostname}</strong> with this value,
                  then click "Check verification":
                </p>
                <code className="block bg-white border border-gray-200 rounded px-2 py-1 text-xs break-all">
                  vulnscan-verify={domain.verification_token}
                </code>
                {verifyError[domain.id] && (
                  <p className="text-red-600 text-xs mt-2">{verifyError[domain.id]}</p>
                )}
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-700">Auth cookie (for aggressive scans)</p>
                  <p className="text-xs text-gray-500">
                    Only needed if the target sits behind a login — sqlmap sends this cookie so it
                    can reach pages a logged-out request can't.{" "}
                    {domain.has_auth_cookie ? (
                      <span className="text-green-700 font-medium">Cookie set.</span>
                    ) : (
                      <span>None set.</span>
                    )}
                  </p>
                </div>
                {!cookieEditing[domain.id] && (
                  <button
                    onClick={() => setCookieEditing((prev) => ({ ...prev, [domain.id]: true }))}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 shrink-0"
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
                    className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                  />
                  <button
                    onClick={() => handleSaveCookie(domain)}
                    disabled={cookieSaving === domain.id}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setCookieEditing((prev) => ({ ...prev, [domain.id]: false }));
                      setCookieInputs((prev) => ({ ...prev, [domain.id]: "" }));
                    }}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                </div>
              )}
              {domain.has_auth_cookie && !cookieEditing[domain.id] && (
                <button
                  onClick={() => handleClearCookie(domain)}
                  disabled={cookieSaving === domain.id}
                  className="mt-2 text-xs text-red-600 hover:underline disabled:opacity-50"
                >
                  Clear cookie
                </button>
              )}
              {cookieError[domain.id] && (
                <p className="text-red-600 text-xs mt-2">{cookieError[domain.id]}</p>
              )}
            </div>
          </div>
        ))}
        {domains.length === 0 && (
          <p className="text-gray-500 text-sm">No domains yet — add one above to get started.</p>
        )}
      </div>
    </div>
  );
}

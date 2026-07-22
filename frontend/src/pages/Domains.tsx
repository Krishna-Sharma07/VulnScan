import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Domain } from "../types";

export default function Domains() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [hostname, setHostname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<Record<string, string>>({});
  const [verifying, setVerifying] = useState<string | null>(null);

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
          </div>
        ))}
        {domains.length === 0 && (
          <p className="text-gray-500 text-sm">No domains yet — add one above to get started.</p>
        )}
      </div>
    </div>
  );
}

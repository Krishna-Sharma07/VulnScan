import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Tag, { statusTone } from "../components/Tag";
import type { ScanJob } from "../types";

export default function History() {
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<ScanJob[]>("/api/history").then((res) => {
      setScans(res.data);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      <h1 className="font-mono text-2xl font-semibold text-ink mb-6">Scan History</h1>
      <div className="space-y-3">
        {scans.map((scan) => (
          <Link
            key={scan.id}
            to={`/scan/${scan.id}`}
            className="block bg-surface border border-hairline p-4 hover:border-signal focus:ring-2 focus:ring-signal focus:outline-none"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-ink">{scan.target_url}</p>
                <p className="text-xs text-muted font-mono">
                  {scan.scan_type} · {new Date(scan.created_at).toLocaleString()}
                </p>
              </div>
              <Tag tone={statusTone[scan.status]}>{scan.status}</Tag>
            </div>
          </Link>
        ))}
        {!loading && scans.length === 0 && (
          <p className="text-muted text-sm">
            No scans yet — <Link to="/scan/new" className="text-signal">start one</Link>.
          </p>
        )}
      </div>
    </div>
  );
}

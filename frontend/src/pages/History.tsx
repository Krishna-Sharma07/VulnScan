import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ScanJob } from "../types";

const statusColor: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function History() {
  const [scans, setScans] = useState<ScanJob[]>([]);

  useEffect(() => {
    api.get<ScanJob[]>("/api/history").then((res) => setScans(res.data));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Scan History</h1>
      <div className="space-y-3">
        {scans.map((scan) => (
          <Link
            key={scan.id}
            to={`/scan/${scan.id}`}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-indigo-300"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{scan.target_url}</p>
                <p className="text-xs text-gray-500">
                  {scan.scan_type} · {new Date(scan.created_at).toLocaleString()}
                </p>
              </div>
              <span
                className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor[scan.status]}`}
              >
                {scan.status}
              </span>
            </div>
          </Link>
        ))}
        {scans.length === 0 && (
          <p className="text-gray-500 text-sm">
            No scans yet — <Link to="/scan/new" className="text-indigo-600">start one</Link>.
          </p>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { BillingUsage, PlanTier } from "../types";

const PLANS: {
  id: PlanTier;
  name: string;
  price: string;
  features: string[];
}[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    features: ["3 scans / month", "Baseline (passive) scans only", "PDF reports"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "$29/mo",
    features: ["Unlimited scans", "Aggressive scans (sqlmap)", "PDF reports"],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Contact us",
    features: ["Unlimited scans", "Aggressive scans (sqlmap)", "Priority support (coming soon)"],
  },
];

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [changingTo, setChangingTo] = useState<PlanTier | null>(null);
  const [error, setError] = useState<string | null>(null);

  function loadUsage() {
    api.get<BillingUsage>("/api/billing/usage").then((res) => setUsage(res.data));
  }

  useEffect(loadUsage, []);

  async function changePlan(plan: PlanTier) {
    setError(null);
    setChangingTo(plan);
    try {
      // Stands in for a real checkout - no payment gateway is wired up yet
      // (see NOTES.md), so this just confirms the plan change immediately.
      await api.post("/api/billing/upgrade", { plan });
      await refreshUser();
      loadUsage();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not change plan");
    } finally {
      setChangingTo(null);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Billing</h1>
      <p className="text-gray-600 mb-6">
        Checkout isn't wired up to a real payment gateway yet - switching plans below applies
        immediately for testing.
      </p>

      {usage && (
        <div className="bg-white border border-gray-200 rounded-md px-4 py-3 mb-6 text-sm">
          <span className="font-medium capitalize">{usage.plan}</span> plan &middot;{" "}
          {usage.monthly_scan_limit === null
            ? `${usage.scans_used_this_month} scans this month (unlimited)`
            : `${usage.scans_used_this_month} / ${usage.monthly_scan_limit} scans used this month`}
        </div>
      )}

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {PLANS.map((plan) => {
          const isCurrent = user?.plan === plan.id;
          return (
            <div
              key={plan.id}
              className={`rounded-lg border p-5 flex flex-col ${
                isCurrent ? "border-indigo-600 ring-1 ring-indigo-600" : "border-gray-200"
              }`}
            >
              <h2 className="text-lg font-semibold">{plan.name}</h2>
              <p className="text-2xl font-bold mt-1 mb-4">{plan.price}</p>
              <ul className="text-sm text-gray-600 space-y-1 mb-6 flex-1">
                {plan.features.map((f) => (
                  <li key={f}>&bull; {f}</li>
                ))}
              </ul>
              <button
                disabled={isCurrent || changingTo !== null}
                onClick={() => changePlan(plan.id)}
                className="w-full rounded-md py-2 font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {isCurrent ? "Current plan" : changingTo === plan.id ? "Switching..." : "Switch"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, extractErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { BillingUsage, CheckoutOrder, PlanTier, RazorpaySuccessResponse } from "../types";

const PLANS: {
  id: PlanTier;
  name: string;
  price: string;
  features: string[];
}[] = [
  {
    id: "free",
    name: "Free",
    price: "₹0",
    features: ["3 scans / month", "Baseline (passive) scans only", "PDF reports"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "₹2,400/mo",
    features: ["Unlimited scans", "Aggressive scans (sqlmap)", "PDF reports"],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Contact us",
    features: ["Unlimited scans", "Aggressive scans (sqlmap)", "Priority support (coming soon)"],
  },
];

// Only Free/Pro ever reach the plain-button branch below (Enterprise has its
// own mailto branch) - a specific label per plan beats one generic "Switch"
// for every non-current plan.
const actionLabel: Record<PlanTier, string> = {
  free: "Downgrade to Free",
  pro: "Upgrade to Pro",
  enterprise: "Switch",
};

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [changingTo, setChangingTo] = useState<PlanTier | null>(null);
  const [confirmingPlan, setConfirmingPlan] = useState<PlanTier | null>(null);
  const [error, setError] = useState<string | null>(null);

  function loadUsage() {
    api.get<BillingUsage>("/api/billing/usage").then((res) => setUsage(res.data));
  }

  useEffect(loadUsage, []);

  // Free needs no payment, so it still goes through the direct endpoint -
  // the backend rejects any other plan there now (see billing.py), since
  // paid plans must go through real Razorpay checkout below.
  async function switchToFree() {
    setError(null);
    setConfirmingPlan(null);
    setChangingTo("free");
    try {
      await api.post("/api/billing/upgrade", { plan: "free" });
      await refreshUser();
      loadUsage();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Could not change plan"));
    } finally {
      setChangingTo(null);
    }
  }

  // Real Razorpay Checkout flow for paid plans: ask the backend to create an
  // order (it decides the price - see app/core/plans.py - never something
  // the browser can influence), open Razorpay's popup with that order, then
  // send the payment result to the backend to verify the signature and
  // actually apply the plan. The plan only changes after that verify call
  // succeeds - opening the popup or completing payment in it doesn't, by
  // itself, change anything on our side.
  async function startCheckout(plan: PlanTier) {
    setError(null);
    setChangingTo(plan);
    try {
      const { data: order } = await api.post<CheckoutOrder>("/api/billing/checkout/order", {
        plan,
      });
      const razorpay = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "VulnScan Pro",
        description: `Upgrade to ${plan}`,
        handler: (response: RazorpaySuccessResponse) => {
          api
            .post("/api/billing/checkout/verify", response)
            .then(async () => {
              await refreshUser();
              loadUsage();
            })
            .catch((err) => setError(extractErrorMessage(err, "Payment verification failed")))
            .finally(() => setChangingTo(null));
        },
        modal: {
          // User closed the popup without paying - not an error, just reset
          // the button back to its normal state.
          ondismiss: () => setChangingTo(null),
        },
      });
      razorpay.open();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Could not start checkout"));
      setChangingTo(null);
    }
  }

  // Free is the only tier with real, enforced limits below Pro/Enterprise
  // today (see app/core/plans.py) - a switch to it is the only plan change
  // that actually takes something away, so it's the only one worth pausing on.
  function isDowngradeToFree(plan: PlanTier) {
    return plan === "free" && user?.plan !== "free";
  }

  function selectPlan(plan: PlanTier) {
    if (isDowngradeToFree(plan)) {
      setConfirmingPlan(plan);
    } else if (plan === "free") {
      switchToFree();
    } else {
      startCheckout(plan);
    }
  }

  return (
    <div>
      <h1 className="font-mono text-2xl font-semibold text-ink mb-2">Billing</h1>
      <p className="text-muted mb-6">
        Upgrades to Pro are processed through Razorpay Checkout. Downgrading to Free applies
        immediately with no charge.
      </p>

      {usage && (
        <div className="bg-surface border border-hairline px-4 py-3 mb-6 text-sm font-mono">
          <span className="font-medium capitalize text-ink">{usage.plan}</span>{" "}
          <span className="text-muted">
            plan &middot;{" "}
            {usage.monthly_scan_limit === null
              ? `${usage.scans_used_this_month} scans this month (unlimited)`
              : `${usage.scans_used_this_month} / ${usage.monthly_scan_limit} scans used this month`}
          </span>
        </div>
      )}

      {error && <p className="text-sm text-critical mb-4">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {PLANS.map((plan) => {
          const isCurrent = user?.plan === plan.id;
          return (
            <div
              key={plan.id}
              className={`border p-5 flex flex-col ${
                isCurrent ? "border-2 border-signal" : "border-hairline"
              }`}
            >
              <h2 className="font-mono text-lg font-semibold text-ink">{plan.name}</h2>
              <p className="font-mono text-2xl font-bold text-ink mt-1 mb-4">{plan.price}</p>
              <ul className="text-sm text-muted space-y-1 mb-6 flex-1">
                {plan.features.map((f) => (
                  <li key={f}>&bull; {f}</li>
                ))}
              </ul>
              {confirmingPlan === plan.id ? (
                <div>
                  <p className="text-xs text-critical mb-2">
                    You'll drop to 3 scans/month and lose aggressive (sqlmap) scanning
                    immediately. Continue?
                  </p>
                  <div className="flex gap-2">
                    <button
                      disabled={changingTo !== null}
                      onClick={() => switchToFree()}
                      className="flex-1 py-2 font-mono font-medium border-2 border-critical text-critical hover:bg-critical hover:text-surface disabled:opacity-50 focus:ring-2 focus:ring-critical focus:outline-none"
                    >
                      {changingTo === plan.id ? "Switching..." : "Confirm downgrade"}
                    </button>
                    <button
                      disabled={changingTo !== null}
                      onClick={() => setConfirmingPlan(null)}
                      className="flex-1 py-2 font-mono font-medium border border-hairline text-ink hover:bg-paper disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : plan.id === "enterprise" && !isCurrent ? (
                // No self-serve price exists for Enterprise (see PLANS
                // above) - Razorpay checkout needs an amount up front, so
                // this stays a manual/sales process instead of a fake price.
                <a
                  href="mailto:sales@vulnscanpro.example.com?subject=Enterprise%20plan"
                  className="w-full text-center py-2 font-mono font-medium border border-signal text-signal hover:bg-paper focus:ring-2 focus:ring-signal focus:outline-none"
                >
                  Contact us
                </a>
              ) : (
                <button
                  disabled={isCurrent || changingTo !== null}
                  onClick={() => selectPlan(plan.id)}
                  className="w-full py-2 font-mono font-medium bg-signal text-surface hover:bg-signal-dark disabled:opacity-50 focus:ring-2 focus:ring-signal focus:outline-none"
                >
                  {isCurrent
                    ? "Current plan"
                    : changingTo === plan.id
                      ? "Switching..."
                      : actionLabel[plan.id]}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

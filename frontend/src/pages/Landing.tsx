import { Link } from "react-router-dom";

const FEATURES = [
  {
    title: "Live URL scanning",
    body:
      "ZAP checks passively by default. Flip on the aggressive scan to add sqlmap for active SQL-injection testing — including behind a login, using your own session cookie.",
  },
  {
    title: "Uploaded-code scanning",
    body:
      "Upload a .zip of a Python codebase. Bandit flags insecure code patterns, safety flags known-vulnerable dependencies. Nothing you upload is ever executed.",
  },
  {
    title: "Domain ownership verification",
    body:
      "Prove a domain is yours with one DNS TXT record before anything can point a scan at it. No verification, no scan.",
  },
  {
    title: "SSRF-hardened execution",
    body:
      "Every target is checked against private and internal IP ranges twice — once when you submit it, again the instant before a scan container starts — then pinned so DNS can't move the target mid-scan.",
  },
  {
    title: "PDF reports",
    body: "Every finding, ranked by severity, in a PDF you can hand to a client or keep on file.",
  },
  {
    title: "Freemium billing",
    body: "3 scans a month, free. Unlimited scans and active testing on Pro, with real Razorpay checkout.",
  },
];

const PLANS = [
  { name: "Free", price: "₹0", blurb: "3 scans / month, baseline scans only" },
  { name: "Pro", price: "₹2,400/mo", blurb: "Unlimited scans, aggressive scans included" },
  { name: "Enterprise", price: "Contact us", blurb: "Unlimited scans, sales-assisted onboarding" },
];

export default function Landing() {
  return (
    <div>
      <section className="text-center max-w-2xl mx-auto py-12 sm:py-20">
        <h1 className="font-mono text-2xl sm:text-4xl font-bold tracking-tight text-ink break-words">
          <span className="text-signal">$</span> vulnscan your-app.com
          <span className="cursor-blink">_</span>
        </h1>
        <p className="mt-3 text-lg sm:text-xl font-semibold text-ink">Before someone else does.</p>
        <p className="mt-4 text-muted text-base sm:text-lg">
          OWASP ZAP and sqlmap test your live site. Bandit and safety test your code. Every scan
          ends in a severity-ranked PDF you can hand to a client or keep for your own records.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/signup"
            className="w-full sm:w-auto bg-signal text-surface px-6 py-3 font-mono font-medium hover:bg-signal-dark focus:ring-2 focus:ring-signal focus:outline-none"
          >
            Run your first scan free
          </Link>
          <Link
            to="/login"
            className="w-full sm:w-auto px-6 py-3 font-mono font-medium border border-hairline text-ink hover:bg-surface focus:ring-2 focus:ring-signal focus:outline-none"
          >
            Log in
          </Link>
        </div>
      </section>

      <section className="py-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-surface border border-hairline p-5">
              <h2 className="font-mono font-semibold text-ink">{f.title}</h2>
              <p className="text-sm text-muted mt-2">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-12">
        <h2 className="font-mono text-2xl font-semibold text-center text-ink mb-8">Pricing</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl mx-auto">
          {PLANS.map((plan) => (
            <div key={plan.name} className="border border-hairline p-5 text-center">
              <h3 className="font-mono text-lg font-semibold text-ink">{plan.name}</h3>
              <p className="font-mono text-2xl font-bold text-ink mt-1 mb-2">{plan.price}</p>
              <p className="text-sm text-muted">{plan.blurb}</p>
            </div>
          ))}
        </div>
        <p className="text-center mt-8">
          <Link
            to="/signup"
            className="bg-signal text-surface px-6 py-3 font-mono font-medium hover:bg-signal-dark focus:ring-2 focus:ring-signal focus:outline-none inline-block"
          >
            Create your free account
          </Link>
        </p>
      </section>
    </div>
  );
}

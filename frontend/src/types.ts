export type PlanTier = "free" | "pro" | "enterprise";

export interface User {
  id: string;
  email: string;
  plan: PlanTier;
  created_at: string;
}

export interface Domain {
  id: string;
  hostname: string;
  verification_token: string;
  verified: boolean;
  has_auth_cookie: boolean;
  created_at: string;
}

export type ScanType = "baseline" | "aggressive";
export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface ScanJob {
  id: string;
  domain_id: string;
  target_url: string;
  scan_type: ScanType;
  status: ScanStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Finding {
  id: string;
  vuln_type: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: string | null;
  remediation: string;
  affected_url: string;
}

export interface ScanReport extends ScanJob {
  findings: Finding[];
}

export interface CodeScanJob {
  id: string;
  filename: string;
  status: ScanStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface CodeFinding {
  id: string;
  source: string; // "bandit" | "safety"
  vuln_type: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: string | null;
  remediation: string;
  affected_file: string;
  line_number: number | null;
}

export interface CodeScanReport extends CodeScanJob {
  findings: CodeFinding[];
}

export interface BillingUsage {
  plan: PlanTier;
  scans_used_this_month: number;
  monthly_scan_limit: number | null; // null = unlimited
  aggressive_allowed: boolean;
}

export interface CheckoutOrder {
  order_id: string;
  amount: number; // paise
  currency: string;
  key_id: string;
}

// Razorpay Checkout.js (loaded via a plain <script> tag in index.html, not
// an npm package - see index.html) attaches itself to window at runtime.
// This just describes the small slice of its API the Billing page uses.
export interface RazorpaySuccessResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  order_id: string;
  name: string;
  description?: string;
  handler: (response: RazorpaySuccessResponse) => void;
  modal?: { ondismiss?: () => void };
}

declare global {
  interface Window {
    Razorpay: new (options: RazorpayOptions) => { open: () => void };
  }
}

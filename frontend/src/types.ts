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

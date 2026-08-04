// Shared bracketed-mono badge - one typographic device for every status
// and severity in the app (scan status, domain verification, finding
// severity) instead of a different colored pill invented per page. The
// five tones double as both the real severity ramp (critical/high/medium/
// low/info) and a lifecycle-status mapping (failed/-/running/verified or
// completed/pending), so the whole app draws from one consistent palette.
export type TagTone = "critical" | "high" | "medium" | "low" | "info";

const toneClass: Record<TagTone, string> = {
  critical: "text-critical border-critical",
  high: "text-high border-high",
  medium: "text-medium border-medium",
  low: "text-low border-low",
  info: "text-muted border-hairline",
};

// Scan/code-scan lifecycle status shares the same five-tone palette as
// severity, instead of a separately invented status color set.
export const statusTone: Record<string, TagTone> = {
  pending: "info",
  running: "medium",
  completed: "low",
  failed: "critical",
};

export default function Tag({ tone, children }: { tone: TagTone; children: string }) {
  return (
    <span
      className={`inline-block font-mono text-[11px] uppercase tracking-wide px-1.5 py-0.5 border ${toneClass[tone]}`}
    >
      [{children}]
    </span>
  );
}

// Candidate 4: lookalike diff. The two domains aligned, the swapped character highlighted. The one-character story.
import type { Risk } from "@/lib/types";
import { cn } from "@/lib/utils";

function Chars({ s, hot, tone }: { s: string; hot: Set<number>; tone: "held" | "paid" }) {
  return (
    <span className="mono text-[22px] leading-none tracking-wide">
      {Array.from(s).map((c, i) => (
        <span key={i} className={cn(hot.has(i) && (tone === "held" ? "rounded-sm bg-held-soft px-0.5 font-semibold text-held underline decoration-2 underline-offset-4" : "rounded-sm bg-paid-soft px-0.5 font-semibold text-paid"))}>
          {c}
        </span>
      ))}
    </span>
  );
}

function caption(diff: Risk["lookalike"]) {
  if (!diff || !diff.diff.length) return "Spelled to look like the vendor's domain.";
  const d = diff.diff[0];
  return `'${d.sender}' in place of '${d.known}'`;
}

/** Variant A: stacked, sender above the real domain. */
export function LookalikeStack({ risk, className }: { risk: Risk; className?: string }) {
  const l = risk.lookalike;
  if (!l || !l.sender_domain || !l.known_domain) return null;
  const hot = new Set(l.diff.map((d) => d.index));
  return (
    <div className={cn("rounded-md border border-held/40 bg-held-soft/40 p-3", className)} role="group" aria-label="Lookalike domain">
      <div className="grid grid-cols-[6rem_1fr] items-baseline gap-x-3 gap-y-1">
        <span className="text-sm text-muted-foreground">Email came from</span>
        <Chars s={l.sender_domain} hot={hot} tone="held" />
        <span className="text-sm text-muted-foreground">Vendor's domain</span>
        <Chars s={l.known_domain} hot={hot} tone="paid" />
      </div>
      <p className="mt-2 text-sm text-held">{caption(l)}</p>
    </div>
  );
}

/** Variant B: inline, one line with the word "imitates". */
export function LookalikeInline({ risk, className }: { risk: Risk; className?: string }) {
  const l = risk.lookalike;
  if (!l || !l.sender_domain || !l.known_domain) return null;
  const hot = new Set(l.diff.map((d) => d.index));
  return (
    <p className={cn("flex flex-wrap items-baseline gap-x-2", className)}>
      <Chars s={l.sender_domain} hot={hot} tone="held" />
      <span className="text-sm text-muted-foreground">imitates</span>
      <Chars s={l.known_domain} hot={hot} tone="paid" />
      <span className="text-sm text-held">({caption(l)})</span>
    </p>
  );
}

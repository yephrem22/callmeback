// Candidate 4: lookalike diff. The two domains aligned, the swapped character highlighted. The one-character story.
import type { Risk } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAMES: Record<string, string> = {
  "0": "zero", "1": "one", "3": "three", "5": "five", "l": "L", "i": "I", "o": "O", "|": "bar", "$": "dollar", "-": "hyphen",
};

/** "digit 1", "letter l", "hyphen" — spoken-form so l vs 1 is unambiguous even in a monospace face. */
function describe(c: string): string {
  if (/\d/.test(c)) return `digit ${c}`;
  if (/[a-z]/i.test(c)) return `letter ${c}`;
  return NAMES[c] ?? `'${c}'`;
}

function Chars({ s, hot, tone }: { s: string; hot: Set<number>; tone: "held" | "paid" }) {
  const cls = tone === "held"
    ? "rounded-sm bg-held-soft px-0.5 font-semibold text-held underline decoration-2 underline-offset-4"
    : "rounded-sm bg-paid-soft px-0.5 font-semibold text-paid underline decoration-2 underline-offset-4";
  return (
    <span className="mono text-[22px] leading-none tracking-wide" aria-label={s}>
      {Array.from(s).map((c, i) => (
        <span key={i} className={cn(hot.has(i) && cls)} aria-hidden={hot.has(i) ? undefined : true}>{c}</span>
      ))}
    </span>
  );
}

function Annotation({ s, hot, tone }: { s: string; hot: Set<number>; tone: "held" | "paid" }) {
  const chars = [...hot].sort((a, b) => a - b).map((i) => s[i]).filter(Boolean);
  if (!chars.length) return null;
  return <span className={cn("ml-3 text-sm", tone === "held" ? "text-held" : "text-paid")}>{chars.map(describe).join(", ")}</span>;
}

function caption(l: NonNullable<Risk["lookalike"]>) {
  if (!l.diff.length) return "Spelled to look like the vendor's domain.";
  const d = l.diff[0];
  return `${describe(d.sender)} in place of ${describe(d.known)}`;
}

/** Variant A: stacked, sender above the real domain. */
export function LookalikeStack({ risk, className }: { risk: Risk; className?: string }) {
  const l = risk.lookalike;
  if (!l || !l.sender_domain || !l.known_domain) return null;
  const hot = new Set(l.diff.map((d) => d.index));
  return (
    <div className={cn("rounded-md border border-held/40 bg-held-soft/40 p-3", className)} role="group" aria-label="Lookalike domain">
      <div className="grid grid-cols-[7.5rem_1fr] items-baseline gap-x-3 gap-y-2">
        <span className="text-sm text-muted-foreground">Email came from</span>
        <span className="flex flex-wrap items-baseline"><Chars s={l.sender_domain} hot={hot} tone="held" /><Annotation s={l.sender_domain} hot={hot} tone="held" /></span>
        <span className="text-sm text-muted-foreground">Vendor's domain</span>
        <span className="flex flex-wrap items-baseline"><Chars s={l.known_domain} hot={hot} tone="paid" /><Annotation s={l.known_domain} hot={hot} tone="paid" /></span>
      </div>
      <p className="mt-2 text-sm text-held">{caption(l)}. We called the vendor's number on file, not this sender.</p>
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

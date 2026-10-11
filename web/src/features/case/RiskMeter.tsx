// Candidate 2: risk meter. Green, amber and red bands with a marker. The simplest view, readable from 5 m.
import { tierWord } from "@/lib/decide";
import type { Risk } from "@/lib/types";
import { cn } from "@/lib/utils";

const TIER_CLASS = { GREEN: "text-paid", YELLOW: "text-review", RED: "text-held" } as const;

/** Variant A: full-width meter with the number beside it. */
export function RiskMeter({ risk, className }: { risk: Risk; className?: string }) {
  const max = Math.max(100, risk.points);
  const pos = (risk.points / max) * 100;
  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="relative h-3 flex-1 rounded-full" role="img" aria-label={`${risk.points} risk points, ${tierWord(risk.tier)} tier`}
           style={{ background: `linear-gradient(to right, var(--paid) 0 ${(20 / max) * 100}%, var(--review) ${(20 / max) * 100}% ${(50 / max) * 100}%, var(--held) ${(50 / max) * 100}% 100%)`, opacity: 0.9 }}>
        <span className="absolute -top-1.5 size-6 -translate-x-1/2 rounded-full border-[3px] border-background bg-foreground shadow"
              style={{ left: `${pos}%` }} aria-hidden />
      </div>
      <div className={cn("tabular whitespace-nowrap text-[22px] font-semibold leading-none", TIER_CLASS[risk.tier])}>
        {risk.points} <span className="text-base font-medium">risk points</span>
        <span className="ml-2 rounded-sm border px-1.5 py-0.5 align-middle text-xs uppercase tracking-wide">{tierWord(risk.tier)}</span>
      </div>
    </div>
  );
}

/** Variant B: compact pill for queue rows and headers. */
export function RiskPill({ risk, className }: { risk: Pick<Risk, "points" | "tier">; className?: string }) {
  const tone = risk.tier === "RED" ? "bg-held-soft text-held" : risk.tier === "YELLOW" ? "bg-review-soft text-review" : "bg-paid-soft text-paid";
  return (
    <span className={cn("tabular inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-sm font-medium", tone, className)}>
      <span className="size-2 rounded-full bg-current" aria-hidden />
      {risk.points} pts
      <span className="sr-only">, {tierWord(risk.tier)} tier</span>
    </span>
  );
}

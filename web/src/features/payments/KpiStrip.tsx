// Candidate 10: KPI strip. Money released, money held, calls placed, median time to decision.
import { Banknote, Clock, OctagonX, PhoneCall } from "lucide-react";

import { formatCents } from "@/lib/format";
import type { Stats } from "@/lib/types";
import { cn } from "@/lib/utils";

function items(s: Stats) {
  return [
    { label: "Released", value: formatCents(s.released_cents), icon: Banknote, tone: "text-paid" },
    { label: "Held", value: formatCents(s.held_cents), icon: OctagonX, tone: "text-held" },
    { label: "Calls placed", value: String(s.calls_placed), icon: PhoneCall, tone: "text-primary" },
    { label: "Median decision", value: s.median_decision_seconds != null ? `${s.median_decision_seconds} s` : "—", icon: Clock, tone: "text-foreground" },
  ];
}

/** Variant A: four tiles. */
export function KpiTiles({ stats, className }: { stats: Stats; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-4 gap-3", className)}>
      {items(stats).map((it) => (
        <div key={it.label} className="rounded-md border border-border p-3">
          <dt className="flex items-center gap-1.5 text-sm text-muted-foreground"><it.icon className={cn("size-4", it.tone)} aria-hidden />{it.label}</dt>
          <dd className={cn("tabular mt-1 text-[22px] font-semibold leading-none", it.tone)}>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Variant B: one line. */
export function KpiLine({ stats, className }: { stats: Stats; className?: string }) {
  return (
    <dl className={cn("flex flex-wrap items-baseline gap-x-6 gap-y-1", className)}>
      {items(stats).map((it) => (
        <div key={it.label} className="flex items-baseline gap-2">
          <dd className={cn("tabular text-lg font-semibold", it.tone)}>{it.value}</dd>
          <dt className="text-sm text-muted-foreground">{it.label.toLowerCase()}</dt>
        </div>
      ))}
    </dl>
  );
}

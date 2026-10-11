// The case, in the PLAN.md §14.2 order: decision, why (risk + destination), then the rest is rendered by siblings.
// Winners (docs/design/decisions.md): 12A stamp, 2A meter + 1B breakdown, 4A lookalike, 5B destination, 3A amount chart.
import { useEffect, useRef, useState } from "react";

import { Separator } from "@/components/ui/separator";
import { AmountVsHistoryChart } from "@/features/case/AmountVsHistory";
import { DestinationColumns } from "@/features/case/DestinationCard";
import { LookalikeStack } from "@/features/case/LookalikeDiff";
import { FlagList, RiskBreakdownBar } from "@/features/case/RiskBreakdown";
import { RiskMeter } from "@/features/case/RiskMeter";
import { Stamp } from "@/features/case/Stamp";
import { decisionSentence, stampFor } from "@/lib/decide";
import { formatCents, formatChicago } from "@/lib/format";
import type { InvoiceDetail } from "@/lib/types";

/** Animate the stamp only when the decision changes, not on every poll. */
function useStampAnimation(key: string | null) {
  const last = useRef<string | null>(null);
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    if (key && key !== last.current) { setAnimate(true); last.current = key; const t = setTimeout(() => setAnimate(false), 400); return () => clearTimeout(t); }
    return undefined;
  }, [key]);
  return animate;
}

export function CaseHeader({ d }: { d: InvoiceDetail }) {
  const name = d.vendor?.name ?? d.extracted.fields.vendor_name.value ?? d.email.from_name ?? "Unknown sender";
  return (
    <div>
      <h2 className="text-[22px] font-semibold leading-tight">{name}</h2>
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-3 text-muted-foreground">
        <span>Invoice <span className="font-medium text-foreground">{d.invoice_number ?? "—"}</span></span>
        <span className="tabular text-[18px] font-medium text-foreground">{formatCents(d.amount_cents)}</span>
        <span>received {formatChicago(d.email.received_at ?? d.created_at, "weekday-time")}</span>
        {d.source === "upload" && <span className="rounded-sm border px-1 text-xs">uploaded</span>}
      </p>
    </div>
  );
}

export function Decision({ d }: { d: InvoiceDetail }) {
  const kind = stampFor(d.status, d.hold_reason);
  const animate = useStampAnimation(kind ? `${d.id}:${kind}:${d.hold_reason ?? ""}` : null);
  return (
    <div className="flex items-start justify-between gap-6">
      <div className="min-w-0">
        <CaseHeader d={d} />
        <p className="mt-3 text-[18px]" aria-live="polite">{decisionSentence(d)}</p>
      </div>
      {kind && <Stamp kind={kind} animate={animate} className="mt-1 shrink-0" />}
    </div>
  );
}

export function CaseView({ d }: { d: InvoiceDetail }) {
  const r = d.risk;
  return (
    <section aria-label="Case" className="space-y-5">
      <Decision d={d} />
      <Separator />

      {r ? (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-muted-foreground">Why</h3>
          <RiskMeter risk={r} />
          {r.flags.some((f) => f.points > 0) ? <RiskBreakdownBar risk={r} collapsible /> : <FlagList risk={r} />}
          {r.lookalike && <LookalikeStack risk={r} />}
        </div>
      ) : (
        <p className="text-muted-foreground">Reading the invoice…</p>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Destination</h3>
        <DestinationColumns destination={d.destination} />
      </div>

      {d.vendor && d.vendor.history.length > 0 && d.amount_cents != null && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-muted-foreground">Amount against this vendor's history</h3>
          <AmountVsHistoryChart detail={d} />
        </div>
      )}
    </section>
  );
}

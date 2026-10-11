// Candidate 3: amount vs history. The last six amounts with a median line; this invoice highlighted.
import { ReferenceLine, Scatter, ScatterChart, XAxis, YAxis, ZAxis, LabelList } from "recharts";

import { ChartContainer, type ChartConfig } from "@/components/ui/chart";
import { formatCents, ratioText } from "@/lib/format";
import type { InvoiceDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

function pick(d: InvoiceDetail) {
  const history = d.vendor?.history ?? [];
  const median = d.vendor?.median_cents ?? null;
  const amount = d.amount_cents;
  const ratio = d.risk?.amount_ratio ?? null;
  return { history, median, amount, ratio };
}

/** Variant A: Recharts strip plot through the shadcn chart container. */
export function AmountVsHistoryChart({ detail, className }: { detail: InvoiceDetail; className?: string }) {
  const { history, median, amount, ratio } = pick(detail);
  if (!history.length || median == null || amount == null) return null;
  // Past amounts cluster around the median, so spread them slightly in y to keep every dot visible.
  const pts = history.map((h, i) => ({ x: h.amount_cents / 100, y: 1 + ((i % 3) - 1) * 0.25, label: h.invoice_number }));
  const cur = [{ x: amount / 100, y: 1, label: "this invoice" }];
  const max = Math.max(amount, ...history.map((h) => h.amount_cents)) / 100;
  const config: ChartConfig = { past: { label: "Past invoices", color: "var(--muted-foreground)" }, now: { label: "This invoice", color: "var(--held)" } };
  const hot = ratio != null && ratio >= 2;
  return (
    <div className={className}>
      <ChartContainer config={config} className="h-20 min-h-20 w-full">
        <ScatterChart margin={{ top: 18, right: 24, bottom: 4, left: 8 }} accessibilityLayer>
          <XAxis type="number" dataKey="x" domain={[0, max * 1.1]} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} fontSize={11} stroke="var(--muted-foreground)" />
          <YAxis type="number" dataKey="y" hide domain={[0, 2]} />
          <ZAxis range={[60, 60]} />
          <ReferenceLine x={median / 100} stroke="var(--primary)" strokeDasharray="4 3" label={{ value: `median ${formatCents(median, { compact: true })}`, position: "top", fontSize: 11, fill: "var(--primary)" }} />
          <Scatter data={pts} fill="var(--muted-foreground)" isAnimationActive={false} />
          <Scatter data={cur} fill={hot ? "var(--held)" : "var(--paid)"} isAnimationActive={false} shape="diamond">
            <LabelList dataKey="label" position="top" fontSize={11} fill={hot ? "var(--held)" : "var(--paid)"} formatter={() => (ratio != null ? `${ratioText(ratio)} usual` : "this invoice")} />
          </Scatter>
        </ScatterChart>
      </ChartContainer>
    </div>
  );
}

/** Variant B: hand-drawn SVG strip. Fewer moving parts, bigger marks. */
export function AmountVsHistoryStrip({ detail, className }: { detail: InvoiceDetail; className?: string }) {
  const { history, median, amount, ratio } = pick(detail);
  if (!history.length || median == null || amount == null) return null;
  const max = Math.max(amount, ...history.map((h) => h.amount_cents)) * 1.08;
  const x = (c: number) => 8 + (c / max) * 84; // percent
  const hot = ratio != null && ratio >= 2;
  return (
    <div className={cn("w-full", className)}>
      <svg viewBox="0 0 100 26" className="h-16 w-full" role="img" aria-label={`This invoice is ${ratioText(ratio) ?? "about"} the vendor's usual amount`}>
        <line x1="8" x2="92" y1="16" y2="16" stroke="var(--border)" strokeWidth="0.6" />
        {history.map((h, i) => (
          <circle key={h.invoice_number} cx={x(h.amount_cents)} cy={16 + ((i % 3) - 1) * 2.2} r="1.5" fill="var(--muted-foreground)" fillOpacity="0.85">
            <title>{h.invoice_number}: {formatCents(h.amount_cents)}</title>
          </circle>
        ))}
        <line x1={x(median)} x2={x(median)} y1="9" y2="23" stroke="var(--primary)" strokeWidth="0.6" strokeDasharray="1.5 1" />
        <text x={x(median)} y="7" fontSize="3.2" textAnchor="middle" fill="var(--primary)">median {formatCents(median, { compact: true })}</text>
        <rect x={x(amount) - 2.2} y="13.8" width="4.4" height="4.4" transform={`rotate(45 ${x(amount)} 16)`} fill={hot ? "var(--held)" : "var(--paid)"} />
        <text x={Math.min(x(amount), 86)} y="25.5" fontSize="3.2" textAnchor="middle" fill={hot ? "var(--held)" : "var(--paid)"} fontWeight="600">
          {formatCents(amount, { compact: true })}{ratio != null ? ` · ${ratioText(ratio)} usual` : ""}
        </text>
      </svg>
    </div>
  );
}

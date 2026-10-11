// Candidate 1: risk breakdown bar. One stacked bar of flag points with tier lines at 20 and 50.
import { Info } from "lucide-react";
import { Bar, BarChart, LabelList, ReferenceLine, XAxis, YAxis } from "recharts";

import { ChartContainer, type ChartConfig } from "@/components/ui/chart";
import { flagTone } from "@/lib/decide";
import type { Risk } from "@/lib/types";
import { cn } from "@/lib/utils";

const FLAG_COLORS = ["var(--held)", "var(--review)", "var(--primary)", "var(--ai)", "var(--muted-foreground)"];

function colorFor(i: number) { return FLAG_COLORS[i % FLAG_COLORS.length]; }

export function RiskNotes({ risk }: { risk: Risk }) {
  const notes = risk.flags.filter((f) => flagTone(f) === "note");
  if (!notes.length) return null;
  return (
    <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
      {notes.map((f) => (
        <li key={f.code} className="flex items-start gap-1.5">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span><span className="font-medium text-foreground">{f.title}.</span> {f.detail}</span>
        </li>
      ))}
    </ul>
  );
}

/** Variant A: shadcn chart (Recharts) stacked bar with direct labels. */
export function RiskBreakdownChart({ risk, className }: { risk: Risk; className?: string }) {
  const weighted = risk.flags.filter((f) => flagTone(f) === "weighted");
  const row: Record<string, number | string> = { name: "points" };
  const config: ChartConfig = {};
  weighted.forEach((f, i) => { row[f.code] = f.points; config[f.code] = { label: f.title, color: colorFor(i) }; });
  const max = Math.max(60, risk.points);
  return (
    <div className={className}>
      <ChartContainer config={config} className="h-16 min-h-16 w-full">
        <BarChart data={[row]} layout="vertical" margin={{ left: 0, right: 8, top: 14, bottom: 0 }} accessibilityLayer>
          <XAxis type="number" domain={[0, max]} hide />
          <YAxis type="category" dataKey="name" hide />
          <ReferenceLine x={20} stroke="var(--muted-foreground)" strokeDasharray="3 3" label={{ value: "20", position: "top", fontSize: 11, fill: "var(--muted-foreground)" }} />
          <ReferenceLine x={50} stroke="var(--muted-foreground)" strokeDasharray="3 3" label={{ value: "50", position: "top", fontSize: 11, fill: "var(--muted-foreground)" }} />
          {weighted.map((f, i) => (
            <Bar key={f.code} dataKey={f.code} stackId="a" fill={colorFor(i)} radius={i === weighted.length - 1 ? [0, 4, 4, 0] : 0} isAnimationActive={false}>
              <LabelList dataKey={f.code} position="center" fill="#fff" fontSize={12} formatter={(v: unknown) => (typeof v === "number" && v >= 15 ? `+${v}` : "")} />
            </Bar>
          ))}
        </BarChart>
      </ChartContainer>
      <FlagList risk={risk} />
    </div>
  );
}

/** Variant B: plain CSS segments, no chart library. Reads well from 5 m. */
export function RiskBreakdownBar({ risk, className, collapsible = false }: { risk: Risk; className?: string; collapsible?: boolean }) {
  const weighted = risk.flags.filter((f) => flagTone(f) === "weighted");
  const max = Math.max(60, risk.points);
  return (
    <div className={className}>
      <div className="relative h-7 w-full overflow-hidden rounded-md bg-muted" role="img" aria-label={`${risk.points} risk points`}>
        <div className="flex h-full">
          {weighted.map((f, i) => (
            <div key={f.code} className="flex h-full items-center justify-center text-xs font-medium text-white"
                 style={{ width: `${(f.points / max) * 100}%`, background: colorFor(i) }} title={`${f.title}: +${f.points}`}>
              {f.points / max > 0.12 ? `+${f.points}` : ""}
            </div>
          ))}
        </div>
        {[20, 50].map((t) => (
          <div key={t} className="absolute top-0 h-full border-l border-dashed border-foreground/40" style={{ left: `${(t / max) * 100}%` }}>
            <span className="absolute -top-0.5 left-1 text-[10px] text-muted-foreground">{t}</span>
          </div>
        ))}
      </div>
      <FlagList risk={risk} collapsible={collapsible} />
    </div>
  );
}

export function FlagList({ risk, dense = false, collapsible = false }: { risk: Risk; dense?: boolean; collapsible?: boolean }) {
  const weighted = risk.flags.filter((f) => flagTone(f) === "weighted");
  if (!collapsible) {
    return (
      <>
        <ul className={cn("mt-3 space-y-1.5", dense && "space-y-1")}>
          {weighted.map((f, i) => (
            <li key={f.code} className="grid grid-cols-[3.25rem_1fr] items-baseline gap-2">
              <span className="tabular text-right font-semibold" style={{ color: colorFor(i) }}>+{f.points}</span>
              <span>
                <span className="font-medium">{f.title}</span>
                {!dense && <span className="block text-sm text-muted-foreground">{f.detail}</span>}
              </span>
            </li>
          ))}
          {!weighted.length && <li className="text-sm text-muted-foreground">No risk flags.</li>}
        </ul>
        {!dense && <RiskNotes risk={risk} />}
      </>
    );
  }
  // Collapsible: titles always visible; details and 0-point notes behind a disclosure so the callback stays near the top.
  return (
    <>
      <ul className="mt-3 space-y-1">
        {weighted.map((f, i) => (
          <li key={f.code} className="grid grid-cols-[3.25rem_1fr] items-baseline gap-2">
            <span className="tabular text-right font-semibold" style={{ color: colorFor(i) }}>+{f.points}</span>
            <span className="font-medium">{f.title}</span>
          </li>
        ))}
        {!weighted.length && <li className="text-sm text-muted-foreground">No risk flags.</li>}
      </ul>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Show the evidence for each flag</summary>
        <ul className="mt-2 space-y-1.5">
          {weighted.map((f) => (
            <li key={f.code}><span className="font-medium">{f.title}.</span> <span className="text-muted-foreground">{f.detail}</span></li>
          ))}
        </ul>
        <RiskNotes risk={risk} />
      </details>
    </>
  );
}

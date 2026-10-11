// Candidate 8: agent trace waterfall. Spans per agent and tool; the guard block in the held color. Strands made visible.
import { ShieldBan, ShieldCheck, Sparkles, Wrench } from "lucide-react";

import { formatChicago } from "@/lib/format";
import type { TraceRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The §7.6 example trace plus a plausible run, used only when a fixture has no agent runs yet. */
export const SAMPLE_TRACE: TraceRow[] = [
  { ts: "2026-10-10T15:00:40Z", agent: "intake", run_id: "run_a1", kind: "run_start", name: null, summary: "Intake agent started", duration_ms: null },
  { ts: "2026-10-10T15:00:40Z", agent: "intake", run_id: "run_a1", kind: "model_call", name: null, summary: "structured output InvoiceExtraction", duration_ms: 1840 },
  { ts: "2026-10-10T15:00:42Z", agent: "intake", run_id: "run_a1", kind: "run_end", name: null, summary: "ok; digits match the email", duration_ms: 1902 },
  { ts: "2026-10-10T15:00:43Z", agent: "analyst", run_id: "run_a2", kind: "tool_call", name: "get_policy_findings", summary: "160 points, RED, CALLBACK", duration_ms: 6 },
  { ts: "2026-10-10T15:00:43Z", agent: "analyst", run_id: "run_a2", kind: "tool_call", name: "get_vendor_record", summary: "Acme Supply Co., Plains Federal Bank ••••4821", duration_ms: 4 },
  { ts: "2026-10-10T15:00:44Z", agent: "analyst", run_id: "run_a2", kind: "model_call", name: null, summary: "AnalystReport", duration_ms: 2310 },
  { ts: "2026-10-10T15:01:30Z", agent: "payments", run_id: "run_a3", kind: "tool_call", name: "get_case_summary", summary: "release_eligible=false: invoice is HELD", duration_ms: 5 },
  { ts: "2026-10-10T15:01:31Z", agent: "payments", run_id: "run_a3", kind: "guard_block", name: "release_payment", summary: "BLOCKED: invoice is HELD (vendor denied the change)", duration_ms: 3 },
  { ts: "2026-10-10T15:01:31Z", agent: "payments", run_id: "run_a3", kind: "tool_call", name: "hold_payment", summary: "hold confirmed", duration_ms: 4 },
];

const AGENT_LABEL: Record<string, string> = { intake: "Intake", analyst: "Analyst", verifier: "Verifier", payments: "Payments", "payments:redteam": "Payments (red team)" };

function kindIcon(kind: string) {
  if (kind === "guard_block") return <ShieldBan className="size-4 text-held" aria-label="blocked by guard" />;
  if (kind === "guard_allow") return <ShieldCheck className="size-4 text-paid" aria-label="allowed by guard" />;
  if (kind === "tool_call") return <Wrench className="size-4 text-muted-foreground" aria-label="tool call" />;
  return <Sparkles className="size-4 text-ai" aria-label="model" />;
}

export function TraceEmpty() {
  return <p className="text-sm text-muted-foreground">No agent runs yet. The trace fills in as the Intake, Analyst, Verifier and Payments agents work.</p>;
}

/** Variant A: waterfall with duration bars on a shared time axis. */
export function TraceWaterfall({ trace, className }: { trace: TraceRow[]; className?: string }) {
  if (!trace.length) return <TraceEmpty />;
  const t0 = new Date(trace[0].ts).getTime();
  const tEnd = Math.max(...trace.map((r) => new Date(r.ts).getTime() + (r.duration_ms ?? 0)));
  const span = Math.max(1, tEnd - t0);
  return (
    <ol className={cn("space-y-1 text-sm", className)} aria-label="Agent trace">
      {trace.map((r, i) => {
        const left = ((new Date(r.ts).getTime() - t0) / span) * 100;
        const width = Math.max(1.5, ((r.duration_ms ?? 50) / span) * 100);
        const blocked = r.kind === "guard_block";
        return (
          <li key={i} className={cn("grid grid-cols-[7rem_1fr_minmax(8rem,2fr)] items-center gap-2 rounded px-1 py-0.5", blocked && "bg-held-soft")}>
            <span className="flex items-center gap-1.5 truncate"><span className="text-ai">{kindIcon(r.kind)}</span>{AGENT_LABEL[r.agent] ?? r.agent}</span>
            <span className="relative h-3 rounded bg-muted">
              <span className={cn("absolute top-0 h-3 rounded", blocked ? "bg-held" : r.kind === "model_call" ? "bg-ai" : "bg-primary")} style={{ left: `${left}%`, width: `${width}%` }} aria-hidden />
            </span>
            <span className={cn("truncate", blocked && "font-medium text-held")}>
              {r.name && <span className="mono mr-1">{r.name}</span>}{r.summary}
              {r.duration_ms != null && <span className="tabular ml-1 text-muted-foreground">{r.duration_ms} ms</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** Variant B: grouped list per agent run. */
export function TraceList({ trace, className }: { trace: TraceRow[]; className?: string }) {
  if (!trace.length) return <TraceEmpty />;
  const groups = new Map<string, TraceRow[]>();
  for (const r of trace) groups.set(r.run_id, [...(groups.get(r.run_id) ?? []), r]);
  return (
    <div className={cn("space-y-3 text-sm", className)}>
      {[...groups.entries()].map(([run, rows]) => (
        <section key={run} className="rounded-md border border-border">
          <header className="flex items-center justify-between border-b border-border px-3 py-1.5">
            <span className="flex items-center gap-1.5 font-medium"><Sparkles className="size-4 text-ai" aria-hidden />{AGENT_LABEL[rows[0].agent] ?? rows[0].agent} agent</span>
            <span className="tabular text-muted-foreground">{formatChicago(rows[0].ts)}</span>
          </header>
          <ul className="divide-y divide-border">
            {rows.map((r, i) => (
              <li key={i} className={cn("flex items-center gap-2 px-3 py-1", r.kind === "guard_block" && "bg-held-soft text-held")}>
                {kindIcon(r.kind)}
                {r.name && <span className="mono">{r.name}</span>}
                <span className="truncate">{r.summary}</span>
                {r.duration_ms != null && <span className="tabular ml-auto text-muted-foreground">{r.duration_ms} ms</span>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

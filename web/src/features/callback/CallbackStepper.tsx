// Candidate 6: callback stepper. Dialing, Ringing, Answered, Asked, Answer, Verdict with live status icons.
import { Check, Circle, Loader2, PhoneOutgoing } from "lucide-react";

import { formatChicago } from "@/lib/format";
import type { Verification } from "@/lib/types";
import { cn } from "@/lib/utils";

const ORDER = ["Dialing", "Ringing", "Answered", "Asked", "Answer", "Verdict"] as const;

function states(v: Verification) {
  const seen = new Map(v.events.map((e) => [e.label, e]));
  // "Last four" counts as part of Answer.
  const answered = seen.has("Answer") || seen.has("Last four");
  const done = v.final_label != null;
  return ORDER.map((label, i) => {
    const ev = label === "Answer" ? (seen.get("Answer") ?? seen.get("Last four")) : seen.get(label);
    const reached = label === "Answer" ? answered : label === "Verdict" ? done : seen.has(label);
    const prevReached = i === 0 || ORDER.slice(0, i).every((l) => (l === "Answer" ? answered : seen.has(l)));
    const state: "done" | "active" | "todo" = reached ? "done" : prevReached && !done ? "active" : "todo";
    return { label, state, ts: ev?.ts ?? null, detail: ev?.detail ?? "" };
  });
}

export function SimulatedBadge({ source }: { source: Verification["source"] }) {
  if (source !== "simulated") return null;
  return <span className="rounded-sm border border-review/50 bg-review-soft px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide text-review">Simulated</span>;
}

function Icon({ state }: { state: "done" | "active" | "todo" }) {
  if (state === "done") return <Check className="size-4 text-paid" aria-label="done" />;
  if (state === "active") return <Loader2 className="size-4 animate-spin text-review" aria-label="in progress" />;
  return <Circle className="size-3 text-muted-foreground" aria-label="not yet" />;
}

export function CallbackHeader({ v }: { v: Verification }) {
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <PhoneOutgoing className="size-4 text-primary" aria-hidden />
      <span>Callback to the number on file <span className="mono">{v.phone_masked}</span>, not the one in the email</span>
      <SimulatedBadge source={v.source} />
    </p>
  );
}

/** Variant A: horizontal steps, like a checks row. */
export function CallbackStepperRow({ verification: v, className }: { verification: Verification; className?: string }) {
  const s = states(v);
  return (
    <div className={className}>
      <CallbackHeader v={v} />
      <ol className="mt-2 flex flex-wrap items-center gap-y-1" aria-label="Callback progress">
        {s.map((st, i) => (
          <li key={st.label} className="flex items-center">
            <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-sm whitespace-nowrap", st.state === "active" && "bg-review-soft", st.state === "todo" && "text-muted-foreground")}>
              <Icon state={st.state} /> {st.label}
            </span>
            {i < s.length - 1 && <span className={cn("mx-0.5 h-px w-3", st.state === "done" ? "bg-paid" : "bg-border")} aria-hidden />}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Variant B: vertical timeline with timestamps and details. */
export function CallbackTimeline({ verification: v, className }: { verification: Verification; className?: string }) {
  const s = states(v);
  return (
    <div className={className}>
      <CallbackHeader v={v} />
      <ol className="mt-2 space-y-1.5 border-l border-border pl-4" aria-label="Callback timeline">
        {s.filter((st) => st.state !== "todo").map((st) => (
          <li key={st.label} className="relative text-sm">
            <span className="absolute -left-[1.35rem] top-0.5 rounded-full bg-background"><Icon state={st.state} /></span>
            <span className="font-medium">{st.label}</span>
            {st.ts && <span className="tabular ml-2 text-muted-foreground">{formatChicago(st.ts)}</span>}
            {st.detail && <span className="block text-muted-foreground">{st.detail}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

// DevRev cases tab (PLAN.md §14.9, §15): change requests opened from DevRev Computer and the outcome
// of their sandbox callback. Read-only; data from GET /api/change-cases[/{id}] (spec 007 R5).
import { Archive, CheckCircle2, CircleDashed, CircleHelp, OctagonX, PhoneCall, PhoneMissed } from "lucide-react";
import { useState } from "react";

import { SimulatedBadge } from "@/features/callback/CallbackStepper";
import { useChangeCase, useChangeCases } from "@/lib/api";
import { formatChicago } from "@/lib/format";
import type { ChangeCase, ChangeCaseStatus, RequestedChange } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHANGE_WORDS: Record<RequestedChange, string> = {
  billing_contact: "billing contact", payment_details: "payment details", remit_address: "remit-to address",
  admin_contact: "admin contact", other: "account details",
};

const STATUS: Record<ChangeCaseStatus, { word: string; icon: typeof CheckCircle2; tone: string }> = {
  OPEN: { word: "Open", icon: CircleDashed, tone: "text-muted-foreground" },
  CALLING: { word: "Calling", icon: PhoneCall, tone: "text-primary" },
  CONFIRMED: { word: "Confirmed", icon: CheckCircle2, tone: "text-paid" },
  DENIED: { word: "Denied", icon: OctagonX, tone: "text-held" },
  UNCLEAR: { word: "Unclear", icon: CircleHelp, tone: "text-review" },
  NO_ANSWER: { word: "No answer", icon: PhoneMissed, tone: "text-review" },
  CLOSED: { word: "Closed", icon: Archive, tone: "text-muted-foreground" },
};

function StatusWord({ status }: { status: ChangeCaseStatus }) {
  const s = STATUS[status] ?? STATUS.OPEN;
  return (
    <span className={cn("inline-flex items-center gap-1 text-sm font-medium", s.tone)}>
      <s.icon className="size-4" aria-hidden />{s.word}
    </span>
  );
}

function signalLabel(sig: unknown): string {
  if (typeof sig === "string") return sig;
  if (sig && typeof sig === "object") {
    const o = sig as Record<string, unknown>;
    for (const k of ["label", "title", "name", "code"]) if (typeof o[k] === "string") return o[k] as string;
  }
  return JSON.stringify(sig);
}

function CaseDetail({ id }: { id: string }) {
  const { data: c } = useChangeCase(id);
  if (!c) return null;
  const v = c.verification;
  return (
    <section className="space-y-2 text-sm" aria-label="Change case">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="font-medium">{c.account_ref.name ?? "Unknown account"}</h4>
        <StatusWord status={c.status} />
        {v && <SimulatedBadge source={v.source === "simulated" ? "simulated" : "twilio"} />}
      </div>
      <p className="text-muted-foreground">Asks to change the {CHANGE_WORDS[c.requested_change] ?? "account details"}, from <span className="mono">{c.sender_email}</span></p>
      <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">{c.request_excerpt}</blockquote>
      {c.signals.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Signals">
          {c.signals.map((s, i) => <li key={i} className="rounded-sm border border-border px-1.5 py-0.5 text-xs">{signalLabel(s)}</li>)}
        </ul>
      )}
      {v ? (
        <div className="space-y-1">
          <p>Callback {v.phone_masked && <span className="mono">{v.phone_masked}</span>} · sandbox: routed to the team demo line</p>
          <ol className="space-y-0.5 border-l border-border pl-3" aria-label="Callback timeline">
            {v.events.map((e, i) => (
              <li key={i}><span className="font-medium">{e.label}</span><span className="tabular ml-2 text-muted-foreground">{formatChicago(e.ts)}</span>{e.detail && <span className="ml-2 text-muted-foreground">{e.detail}</span>}</li>
            ))}
          </ol>
          {v.final_label && <p>Outcome: <span className="font-medium">{v.final_label.replace(/_/g, " ").toLowerCase()}</span></p>}
        </div>
      ) : (
        <p className="text-muted-foreground">No callback placed yet. Sandbox calls only ever dial the team demo line.</p>
      )}
    </section>
  );
}

export function ChangeCases() {
  const { data: cases = [] } = useChangeCases();
  const [picked, setPicked] = useState<string | null>(null);
  if (cases.length === 0) {
    return <p className="text-sm text-muted-foreground">No change cases yet. Cases opened from DevRev Computer appear here with their callback outcome.</p>;
  }
  const selectedId = cases.some((c) => c.id === picked) ? picked! : cases[0].id;
  return (
    <div className="grid grid-cols-[minmax(16rem,22rem)_1fr] gap-4">
      <ul className="space-y-1" aria-label="Change cases">
        {cases.map((c: ChangeCase) => (
          <li key={c.id}>
            <button type="button" onClick={() => setPicked(c.id)} aria-current={c.id === selectedId}
                    className={cn("w-full rounded-md border px-2 py-1.5 text-left text-sm",
                                  c.id === selectedId ? "border-primary bg-accent" : "border-border hover:bg-accent")}>
              <span className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{c.account_ref.name ?? "Unknown account"}</span>
                <StatusWord status={c.status} />
              </span>
              <span className="block truncate text-muted-foreground">{CHANGE_WORDS[c.requested_change] ?? "account details"} · {formatChicago(c.created_at, "weekday-time")}</span>
            </button>
          </li>
        ))}
      </ul>
      <CaseDetail id={selectedId} />
    </div>
  );
}

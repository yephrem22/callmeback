// The fourteen PLAN.md §14.8 candidates, each with two variants, rendered on spec 003's real fixtures.
import type { ReactNode } from "react";

import { AmountVsHistoryChart, AmountVsHistoryStrip } from "@/features/case/AmountVsHistory";
import { DestinationColumns, DestinationRows } from "@/features/case/DestinationCard";
import { LookalikeInline, LookalikeStack } from "@/features/case/LookalikeDiff";
import { RiskBreakdownBar, RiskBreakdownChart } from "@/features/case/RiskBreakdown";
import { RiskMeter, RiskPill } from "@/features/case/RiskMeter";
import { Stamp } from "@/features/case/Stamp";
import { CallbackStepperRow, CallbackTimeline } from "@/features/callback/CallbackStepper";
import { TranscriptBubble, TranscriptRow } from "@/features/callback/TranscriptBubble";
import { AuditTable, AuditTimeline } from "@/features/evidence/AuditList";
import { KpiLine, KpiTiles } from "@/features/payments/KpiStrip";
import { LedgerCards, LedgerTable } from "@/features/payments/LedgerTable";
import { QueueRowLine, QueueRowStacked } from "@/features/queue/QueueRow";
import { SAMPLE_TRACE, TraceList, TraceWaterfall } from "@/features/trace/TraceWaterfall";
import { BankHistoryCards, BankHistoryTable } from "@/features/vendors/BankHistory";
import { decisionSentence, type StampKind } from "@/lib/decide";
import { fixtureStore } from "@/lib/fixtures";

export interface Variant { label: string; render: () => ReactNode; snippet: string }
export interface Candidate {
  n: number; name: string; shows: string; serves: string; fields: string[]; components: string[]; why: string;
  fixture: string; variants: [Variant, Variant];
}

const fraud1 = () => fixtureStore.at("acme_fraud", 1);
const fraud2 = () => fixtureStore.at("acme_fraud", 2);
const fraud3 = () => fixtureStore.at("acme_fraud", 3);
const heart3 = () => fixtureStore.at("heartland_bank_change", 3);
const normal1 = () => fixtureStore.at("acme_normal", 1);
const prairie1 = () => fixtureStore.at("prairie_review", 1);

const FIXED_NOW = Date.parse("2026-10-10T15:30:00Z");

export const CANDIDATES: Candidate[] = [
  {
    n: 1, name: "Risk breakdown bar", shows: "One stacked bar of flag points with tier lines at 20 and 50; each flag listed with its points, title and detail; 0-point flags as notes.",
    serves: "AP specialist: why is this red?", fields: ["risk.flags[].points", "risk.flags[].title", "risk.flags[].detail", "risk.points", "risk.tier"],
    components: ["shadcn chart (Recharts BarChart, LabelList, ReferenceLine)", "plain CSS flex bar"], why: "The weighted-factors pattern (Stripe Radar) at a glance.", fixture: "acme_fraud step 1",
    variants: [
      { label: "A · Recharts stacked bar", render: () => <RiskBreakdownChart risk={fraud1().risk!} />, snippet: `<RiskBreakdownChart risk={detail.risk} />` },
      { label: "B · CSS segments", render: () => <RiskBreakdownBar risk={fraud1().risk!} />, snippet: `<RiskBreakdownBar risk={detail.risk} />` },
    ],
  },
  {
    n: 2, name: "Risk meter", shows: "A single bar with green, amber and red bands and a marker at the score, plus the number and tier word.",
    serves: "Judges, 5 m away: how bad is it?", fields: ["risk.points", "risk.tier"], components: ["div + CSS gradient", "Badge-like pill"], why: "The simplest view, readable from the back of the room.", fixture: "acme_fraud step 1 / prairie_review step 1",
    variants: [
      { label: "A · Full-width meter", render: () => <div className="space-y-4"><RiskMeter risk={fraud1().risk!} /><RiskMeter risk={prairie1().risk!} /><RiskMeter risk={normal1().risk!} /></div>, snippet: `<RiskMeter risk={detail.risk} />` },
      { label: "B · Compact pill", render: () => <div className="flex gap-2"><RiskPill risk={fraud1().risk!} /><RiskPill risk={prairie1().risk!} /><RiskPill risk={normal1().risk!} /></div>, snippet: `<RiskPill risk={detail.risk} />` },
    ],
  },
  {
    n: 3, name: "Amount vs history", shows: "The last six paid amounts as a strip, the median as a line, this invoice highlighted and labelled with its ratio.",
    serves: "Specialist and controller: is this amount normal?", fields: ["vendor.history[].amount_cents", "vendor.median_cents", "amount_cents", "risk.amount_ratio"], components: ["shadcn chart (Recharts ScatterChart)", "inline SVG"], why: "Makes \"4.1 times usual\" visible instead of a number.", fixture: "acme_fraud step 1 / prairie_review step 1",
    variants: [
      { label: "A · Recharts strip", render: () => <div className="space-y-2"><AmountVsHistoryChart detail={fraud1()} /><AmountVsHistoryChart detail={prairie1()} /></div>, snippet: `<AmountVsHistoryChart detail={detail} />` },
      { label: "B · SVG strip", render: () => <div className="space-y-2"><AmountVsHistoryStrip detail={fraud1()} /><AmountVsHistoryStrip detail={prairie1()} /></div>, snippet: `<AmountVsHistoryStrip detail={detail} />` },
    ],
  },
  {
    n: 4, name: "Lookalike diff", shows: "The sender domain and the vendor's real domain aligned character by character with the swapped character highlighted.",
    serves: "Judges: the one-character story.", fields: ["risk.lookalike.sender_domain", "risk.lookalike.known_domain", "risk.lookalike.diff[]"], components: ["Plex Mono spans"], why: "The whole fraud in one glance.", fixture: "acme_fraud step 1",
    variants: [
      { label: "A · Stacked", render: () => <LookalikeStack risk={fraud1().risk!} />, snippet: `<LookalikeStack risk={detail.risk} />` },
      { label: "B · Inline", render: () => <LookalikeInline risk={fraud1().risk!} />, snippet: `<LookalikeInline risk={detail.risk} />` },
    ],
  },
  {
    n: 5, name: "Destination card", shows: "The account on file and the account requested, as check lines, with the changed digits highlighted.",
    serves: "AP specialist: where would the money go?", fields: ["destination.on_file", "destination.requested", "destination.changed"], components: ["CheckLine (inline SVG transit symbol)", "Card"], why: "The core FinTech object; the thing we protect.", fixture: "acme_fraud step 1 / acme_normal step 1",
    variants: [
      { label: "A · Two rows", render: () => <div className="space-y-5"><DestinationRows destination={fraud1().destination} /><DestinationRows destination={normal1().destination} /></div>, snippet: `<DestinationRows destination={detail.destination} />` },
      { label: "B · Two columns", render: () => <div className="space-y-5"><DestinationColumns destination={fraud1().destination} /><DestinationColumns destination={normal1().destination} /></div>, snippet: `<DestinationColumns destination={detail.destination} />` },
    ],
  },
  {
    n: 6, name: "Callback stepper", shows: "Dialing, Ringing, Answered, Asked, Answer, Verdict with live status icons; the masked number on file; a SIMULATED badge when applicable.",
    serves: "Everyone: the live stage moment.", fields: ["verification.events[]", "verification.phone_masked", "verification.source", "verification.step", "verification.final_label"], components: ["lucide icons", "ol"], why: "GitHub-checks pattern; the phone call becomes visible progress.", fixture: "acme_fraud steps 2 and 3",
    variants: [
      { label: "A · Horizontal", render: () => <div className="space-y-5"><CallbackStepperRow verification={fraud2().verification!} /><CallbackStepperRow verification={fraud3().verification!} /></div>, snippet: `<CallbackStepperRow verification={detail.verification} />` },
      { label: "B · Vertical timeline", render: () => <div className="space-y-5"><CallbackTimeline verification={fraud2().verification!} /><CallbackTimeline verification={fraud3().verification!} /></div>, snippet: `<CallbackTimeline verification={detail.verification} />` },
    ],
  },
  {
    n: 7, name: "Transcript bubble", shows: "What the vendor said or pressed, with the deterministic classifier chip, the AI verifier chip (AI color) and the last-four result.",
    serves: "Controller: what exactly did the vendor say?", fields: ["verification.first_answer", "verification.last4_ok", "verification.final_label"], components: ["figure/blockquote", "chips"], why: "Shows that the AI can only downgrade a yes, never upgrade a no.", fixture: "acme_fraud step 3 / heartland step 3",
    variants: [
      { label: "A · Bubble", render: () => <div className="space-y-4"><TranscriptBubble verification={fraud3().verification!} /><TranscriptBubble verification={heart3().verification!} /></div>, snippet: `<TranscriptBubble verification={detail.verification} />` },
      { label: "B · Row", render: () => <div className="space-y-4"><TranscriptRow verification={fraud3().verification!} /><TranscriptRow verification={heart3().verification!} /></div>, snippet: `<TranscriptRow verification={detail.verification} />` },
    ],
  },
  {
    n: 8, name: "Agent trace waterfall", shows: "Spans per agent and tool call with durations; a guard block in the held color labelled BLOCKED.",
    serves: "AWS judges: Strands made visible.", fields: ["trace[].agent", "trace[].kind", "trace[].name", "trace[].summary", "trace[].duration_ms", "trace[].ts"], components: ["ol + CSS bars", "sections"], why: "LangSmith/Jaeger pattern; the red-team block becomes a visible event.", fixture: "sample trace (fixtures carry no agent runs yet)",
    variants: [
      { label: "A · Waterfall", render: () => <TraceWaterfall trace={SAMPLE_TRACE} />, snippet: `<TraceWaterfall trace={detail.trace} />` },
      { label: "B · Grouped list", render: () => <TraceList trace={SAMPLE_TRACE} />, snippet: `<TraceList trace={detail.trace} />` },
    ],
  },
  {
    n: 9, name: "Audit chain list", shows: "Every audit entry with time, actor, event, summary and short hash, under a \"Chain verified\" seal.",
    serves: "Controller and Flex judges: evidence you can trust.", fields: ["audit[].seq", "audit[].ts", "audit[].actor", "audit[].event", "audit[].summary", "audit[].hash_short", "GET /api/audit chain_ok / broken_at"], components: ["table", "ol timeline"], why: "The Nacha story: hashed entries, change one and the chain breaks.", fixture: "acme_fraud step 3",
    variants: [
      { label: "A · Dense table", render: () => <AuditTable rows={fraud3().audit} chainOk={true} />, snippet: `<AuditTable rows={detail.audit} chainOk={audit.chain_ok} brokenAt={audit.broken_at} />` },
      { label: "B · Timeline", render: () => <AuditTimeline rows={fraud3().audit} chainOk={true} />, snippet: `<AuditTimeline rows={detail.audit} chainOk={audit.chain_ok} />` },
    ],
  },
  {
    n: 10, name: "KPI strip", shows: "Money released, money held, calls placed, median time to decision.",
    serves: "Judges and Flex judges: the impact in four numbers.", fields: ["stats.released_cents", "stats.held_cents", "stats.calls_placed", "stats.median_decision_seconds"], components: ["dl tiles", "dl line"], why: "The whole pitch in a row of numbers.", fixture: "stats.json",
    variants: [
      { label: "A · Four tiles", render: () => <KpiTiles stats={fixtureStore.stats()} />, snippet: `<KpiTiles stats={stats} />` },
      { label: "B · One line", render: () => <KpiLine stats={fixtureStore.stats()} />, snippet: `<KpiLine stats={stats} />` },
    ],
  },
  {
    n: 11, name: "Payments ledger table", shows: "Released payments with destination, method and ACH effective date, and the held invoices that never entered the batch.",
    serves: "Controller: what moved and what didn't.", fields: ["payments[]", "held[]"], components: ["table", "cards"], why: "Familiar to finance users; shows released vs held side by side.", fixture: "payments.json",
    variants: [
      { label: "A · Table", render: () => <LedgerTable view={fixtureStore.payments()} />, snippet: `<LedgerTable view={payments} />` },
      { label: "B · Cards", render: () => <LedgerCards view={fixtureStore.payments()} />, snippet: `<LedgerCards view={payments} />` },
    ],
  },
  {
    n: 12, name: "Decision stamp", shows: "PAID, HELD, REVIEW, CALLING as an outlined, rotated stamp in the status color with the one-sentence decision beneath.",
    serves: "Everyone: can this money move?", fields: ["status", "hold_reason", "verification.events", "payment.effective_date", "risk.amount_ratio"], components: ["Stamp", "decisionSentence()"], why: "The signature element; paper AP's rubber stamp.", fixture: "one step per stamp",
    variants: [
      {
        label: "A · Outlined", render: () => (
          <div className="grid grid-cols-2 gap-6">
            {([["PAID", "acme_normal", 2], ["HELD", "acme_fraud", 3], ["REVIEW", "prairie_review", 1], ["CALLING", "acme_fraud", 2]] as [StampKind, Parameters<typeof fixtureStore.at>[0], number][]).map(([k, s, st]) => (
              <div key={k}><Stamp kind={k} animate={false} /><p className="mt-2 text-lg">{decisionSentence(fixtureStore.at(s, st))}</p></div>
            ))}
          </div>
        ), snippet: `<Stamp kind={stampFor(detail.status, detail.hold_reason)} />\n<p>{decisionSentence(detail)}</p>`,
      },
      {
        label: "B · Filled", render: () => (
          <div className="grid grid-cols-2 gap-6">
            {(["PAID", "HELD", "REVIEW", "CALLING"] as StampKind[]).map((k) => <div key={k}><Stamp kind={k} variant="filled" animate={false} /></div>)}
          </div>
        ), snippet: `<Stamp kind={kind} variant="filled" />`,
      },
    ],
  },
  {
    n: 13, name: "Queue rows", shows: "Vendor, amount, status word and icon, tier dot with points, and age; selected state and focus ring.",
    serves: "AP specialist: working the queue fast.", fields: ["GET /api/invoices rows: vendor_name, amount_display, tier, points, status, hold_reason, created_at"], components: ["button rows"], why: "Linear/Superhuman triage pattern with j/k later.", fixture: "invoices_list.json",
    variants: [
      { label: "A · Two lines", render: () => <div className="w-72 space-y-1">{fixtureStore.vendors() && (fixtureStore.listRows().length ? fixtureStore.listRows() : fixtureStoreAllRows()).map((r, i) => <QueueRowStacked key={r.id} row={r} selected={i === 1} now={FIXED_NOW} />)}</div>, snippet: `<QueueRowStacked row={row} selected={row.id === selectedId} onSelect={...} />` },
      { label: "B · One line", render: () => <div className="w-[26rem] space-y-0.5">{(fixtureStore.listRows().length ? fixtureStore.listRows() : fixtureStoreAllRows()).map((r, i) => <QueueRowLine key={r.id} row={r} selected={i === 1} />)}</div>, snippet: `<QueueRowLine row={row} selected={row.id === selectedId} onSelect={...} />` },
    ],
  },
  {
    n: 14, name: "Vendor change history", shows: "Before and after bank details for a vendor, marked \"verified by callback\" with the time and the invoice that justified it.",
    serves: "Controller: vendor-master change control.", fields: ["GET /api/vendors: bank_history[]"], components: ["cards", "table"], why: "Proves the system can say yes safely, not only no.", fixture: "vendors.json (Heartland)",
    variants: [
      { label: "A · Cards", render: () => <BankHistoryCards vendor={fixtureStore.vendors().find((v) => v.id === "ven_heartland")!} />, snippet: `<BankHistoryCards vendor={vendor} />` },
      { label: "B · Table", render: () => <BankHistoryTable vendor={fixtureStore.vendors().find((v) => v.id === "ven_heartland")!} />, snippet: `<BankHistoryTable vendor={vendor} />` },
    ],
  },
];

/** All five scenarios at their final step, for the gallery's queue rows. */
function fixtureStoreAllRows() {
  const idx = fixtureStore.index();
  return (Object.keys(idx) as (keyof typeof idx)[]).map((s) => {
    const d = fixtureStore.at(s, idx[s].length);
    return {
      id: d.id, created_at: d.created_at, vendor_name: d.vendor?.name ?? d.email.from_name, source: d.source,
      amount_display: d.amount_cents != null ? `$${(d.amount_cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : null,
      tier: d.risk?.tier ?? null, points: d.risk?.points ?? null, status: d.status, hold_reason: d.hold_reason,
    };
  });
}

// The decision as the screen states it (PLAN.md §14.6 stamp, §14.9 decision sentences).
import { CheckCircle2, Hourglass, Info, OctagonX, PhoneCall, Sparkles, type LucideIcon } from "lucide-react";

import { formatChicago, formatDateLong } from "@/lib/format";
import type { Flag, HoldReason, InvoiceDetail, Status } from "@/lib/types";

export type StampKind = "PAID" | "HELD" | "REVIEW" | "CALLING";

export function stampFor(status: Status, _hold: HoldReason | null): StampKind | null {
  switch (status) {
    case "RELEASED": return "PAID";
    case "HELD": return "HELD";
    case "NEEDS_REVIEW": return "REVIEW";
    case "CALL_PENDING":
    case "CALLING":
    case "VERIFYING": return "CALLING";
    default: return null;
  }
}

export const STAMP_TONE: Record<StampKind, "paid" | "held" | "review"> = { PAID: "paid", HELD: "held", REVIEW: "review", CALLING: "review" };

export function statusIcon(status: Status): LucideIcon {
  switch (status) {
    case "RELEASED": return CheckCircle2;
    case "HELD": return OctagonX;
    case "NEEDS_REVIEW": return Hourglass;
    case "CALL_PENDING":
    case "CALLING":
    case "VERIFYING": return PhoneCall;
    default: return Info;
  }
}
export const AI_ICON = Sparkles;

export function statusWord(status: Status, hold: HoldReason | null): string {
  switch (status) {
    case "RELEASED": return "paid";
    case "HELD": return hold === "REVIEW_REJECTED" ? "rejected" : "held";
    case "NEEDS_REVIEW": return "needs review";
    case "REVIEW_APPROVED": return "approved";
    case "CALL_PENDING": return "calling";
    case "CALLING": return "calling";
    case "VERIFYING": return "verifying";
    case "CONFIRMED": return "confirmed";
    case "AUTO_APPROVED": return "approved";
    case "FAILED": return "failed";
    default: return status.toLowerCase();
  }
}

function lastEventTime(d: InvoiceDetail): string {
  const ev = d.verification?.events;
  const ts = ev && ev.length ? ev[ev.length - 1].ts : d.decided_at ?? d.created_at;
  return formatChicago(ts, "time");
}

export function decisionSentence(d: InvoiceDetail): string {
  const r = d.risk;
  switch (d.status) {
    case "RELEASED":
      return `Paid. ACH effective ${formatDateLong(d.payment?.effective_date)}.`;
    case "CALL_PENDING":
    case "CALLING":
      return "Waiting for the vendor to answer.";
    case "VERIFYING":
      return "Checking the vendor's spoken answer.";
    case "NEEDS_REVIEW":
      return r?.amount_ratio != null
        ? `Needs review: the amount is ${r.amount_ratio.toFixed(1)} times usual.`
        : "Needs review.";
    case "REVIEW_APPROVED":
      return "Approved by a reviewer; releasing.";
    case "CONFIRMED":
      return "Confirmed by the vendor; releasing.";
    case "AUTO_APPROVED":
      return "No flags; releasing.";
    case "HELD":
      switch (d.hold_reason) {
        case "DENIED_BY_VENDOR": return `Held. The vendor said no on the ${lastEventTime(d)} call.`;
        case "UNKNOWN_VENDOR": return "Held. No vendor record, so there's no trusted number to call.";
        case "NO_ANSWER": return "Held. The vendor didn't answer.";
        case "UNCLEAR_ANSWER": return "Held. We couldn't make out the vendor's answer.";
        case "LAST4_MISMATCH": return "Held. The last four digits didn't match.";
        case "VERIFIER_DISAGREED": return "Held. The spoken answer wasn't a clear yes.";
        case "REVIEW_REJECTED": return "Held. A reviewer rejected it.";
        case "CALL_FAILED": return "Held. The call couldn't be placed.";
        case "AGENT_HOLD": return "Held by the Payments agent.";
        default: return "Held.";
      }
    case "FAILED":
      return "Failed to process this email.";
    default:
      return "Reading the invoice.";
  }
}

export function flagTone(f: Flag): "weighted" | "note" { return f.points > 0 ? "weighted" : "note"; }

export function tierWord(tier: "GREEN" | "YELLOW" | "RED" | null | undefined): string {
  return tier === "RED" ? "red" : tier === "YELLOW" ? "yellow" : tier === "GREEN" ? "green" : "unscored";
}

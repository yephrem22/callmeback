// Candidate 11: payments ledger table with status and ACH effective date. Familiar to finance users.
import { CheckCircle2, OctagonX } from "lucide-react";

import { CheckLine } from "@/features/case/CheckLine";
import { formatCents, formatChicago, formatDateLong } from "@/lib/format";
import type { PaymentsView } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Variant A: table. */
export function LedgerTable({ view, className }: { view: PaymentsView; className?: string }) {
  return (
    <div className={className}>
      <table className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr><th className="py-1 pr-3 font-normal">Status</th><th className="py-1 pr-3 font-normal">Amount</th><th className="py-1 pr-3 font-normal">Destination</th><th className="py-1 pr-3 font-normal">Method</th><th className="py-1 pr-3 font-normal">Effective</th><th className="py-1 pr-3 font-normal">Released by</th></tr>
        </thead>
        <tbody>
          {view.payments.map((p) => (
            <tr key={p.id} className="border-t border-border">
              <td className="py-1.5 pr-3"><span className="inline-flex items-center gap-1 text-paid"><CheckCircle2 className="size-4" aria-hidden />Paid</span></td>
              <td className="tabular py-1.5 pr-3 font-medium">{formatCents(p.amount_cents)}</td>
              <td className="py-1.5 pr-3"><span className="block">{p.bank_name}</span><CheckLine routing={p.routing} account={p.account_masked} className="text-sm" /></td>
              <td className="py-1.5 pr-3">{p.method}</td>
              <td className="tabular py-1.5 pr-3">{formatDateLong(p.effective_date)}</td>
              <td className="py-1.5 pr-3 text-muted-foreground">{p.released_by} · {formatChicago(p.released_at)}</td>
            </tr>
          ))}
          {view.held.map((h) => (
            <tr key={h.id} className="border-t border-border">
              <td className="py-1.5 pr-3"><span className="inline-flex items-center gap-1 text-held"><OctagonX className="size-4" aria-hidden />Held</span></td>
              <td className="tabular py-1.5 pr-3 font-medium">{formatCents(h.amount_cents)}</td>
              <td className="py-1.5 pr-3 text-muted-foreground" colSpan={3}>{h.vendor_name ?? "Unknown vendor"} · {h.hold_reason?.replace(/_/g, " ").toLowerCase()}</td>
              <td className="py-1.5 pr-3 text-muted-foreground">never entered the batch</td>
            </tr>
          ))}
          {!view.payments.length && !view.held.length && <tr><td className="py-2 text-muted-foreground" colSpan={6}>No payments yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

/** Variant B: card list. */
export function LedgerCards({ view, className }: { view: PaymentsView; className?: string }) {
  return (
    <ul className={cn("grid grid-cols-2 gap-3", className)}>
      {view.payments.map((p) => (
        <li key={p.id} className="rounded-md border border-border p-3">
          <div className="flex items-center justify-between"><span className="inline-flex items-center gap-1 text-paid"><CheckCircle2 className="size-4" aria-hidden />Paid</span><span className="tabular text-lg font-semibold">{formatCents(p.amount_cents)}</span></div>
          <p className="mt-1">{p.bank_name}</p>
          <CheckLine routing={p.routing} account={p.account_masked} className="text-sm" />
          <p className="mt-1 text-sm text-muted-foreground">{p.method} · effective {formatDateLong(p.effective_date)} · {p.released_by}</p>
        </li>
      ))}
      {view.held.map((h) => (
        <li key={h.id} className="rounded-md border border-held/40 bg-held-soft/40 p-3">
          <div className="flex items-center justify-between"><span className="inline-flex items-center gap-1 text-held"><OctagonX className="size-4" aria-hidden />Held</span><span className="tabular text-lg font-semibold">{formatCents(h.amount_cents)}</span></div>
          <p className="mt-1">{h.vendor_name ?? "Unknown vendor"}</p>
          <p className="text-sm text-muted-foreground">{h.hold_reason?.replace(/_/g, " ").toLowerCase()}; never entered the ACH batch</p>
        </li>
      ))}
    </ul>
  );
}

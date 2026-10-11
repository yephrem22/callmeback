import { CheckCircle2 } from "lucide-react";

import { CheckLine } from "@/features/case/CheckLine";
import { formatCents, formatChicago, formatDateLong } from "@/lib/format";
import type { Payment } from "@/lib/types";

export function PaymentCard({ p }: { p: Payment }) {
  return (
    <div className="rounded-md border border-paid/40 bg-paid-soft/40 p-3" aria-label="Payment">
      <p className="flex items-center gap-1.5 font-medium text-paid"><CheckCircle2 className="size-4" aria-hidden />Payment released</p>
      <dl className="mt-2 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Amount</dt><dd className="tabular font-medium">{formatCents(p.amount_cents)}</dd>
        <dt className="text-muted-foreground">To</dt><dd>{p.bank_name} <CheckLine routing={p.routing} account={p.account_masked} className="ml-1 text-sm" /></dd>
        <dt className="text-muted-foreground">Method</dt><dd>{p.method}, effective {formatDateLong(p.effective_date)}</dd>
        <dt className="text-muted-foreground">Released by</dt><dd>{p.released_by === "agent:payments" ? "the Payments agent" : p.released_by === "policy:auto" ? "policy (auto-release)" : p.released_by} at {formatChicago(p.released_at)}</dd>
      </dl>
    </div>
  );
}

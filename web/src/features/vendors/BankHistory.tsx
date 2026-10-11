// Candidate 14: vendor change history. Before and after, marked "verified by callback". Vendor-master change control.
import { PhoneCall } from "lucide-react";

import { CheckLine } from "@/features/case/CheckLine";
import { formatChicago } from "@/lib/format";
import type { VendorView } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Variant A: one card per change. */
export function BankHistoryCards({ vendor, className }: { vendor: VendorView; className?: string }) {
  if (!vendor.bank_history.length) return <p className={cn("text-sm text-muted-foreground", className)}>No bank changes on record for {vendor.name}.</p>;
  return (
    <ul className={cn("space-y-2", className)}>
      {vendor.bank_history.map((h) => (
        <li key={h.verification_id} className="rounded-md border border-border p-3">
          <p className="flex items-center gap-2 text-sm"><PhoneCall className="size-4 text-paid" aria-hidden /><span className="font-medium text-paid">Verified by callback</span><span className="tabular text-muted-foreground">{formatChicago(h.changed_at, "datetime")}</span></p>
          <div className="mt-2 grid grid-cols-[4.5rem_1fr] items-center gap-x-3 gap-y-1">
            <span className="text-sm text-muted-foreground">Before</span>
            <span className="flex flex-wrap items-center gap-x-3"><span className="line-through decoration-muted-foreground">{h.old_bank_name}</span><CheckLine routing={h.old_routing} account={h.old_account_masked} className="text-sm text-muted-foreground" /></span>
            <span className="text-sm text-muted-foreground">After</span>
            <span className="flex flex-wrap items-center gap-x-3"><span className="font-medium">{h.new_bank_name}</span><CheckLine routing={h.new_routing} account={h.new_account_masked} className="text-sm" /></span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Invoice {h.invoice_id} · verification {h.verification_id}</p>
        </li>
      ))}
    </ul>
  );
}

/** Variant B: table. */
export function BankHistoryTable({ vendor, className }: { vendor: VendorView; className?: string }) {
  if (!vendor.bank_history.length) return <p className={cn("text-sm text-muted-foreground", className)}>No bank changes on record for {vendor.name}.</p>;
  return (
    <table className={cn("w-full text-sm", className)}>
      <thead className="text-left text-muted-foreground"><tr><th className="py-1 pr-3 font-normal">When</th><th className="py-1 pr-3 font-normal">Before</th><th className="py-1 pr-3 font-normal">After</th><th className="py-1 pr-3 font-normal">How</th></tr></thead>
      <tbody>
        {vendor.bank_history.map((h) => (
          <tr key={h.verification_id} className="border-t border-border align-top">
            <td className="tabular py-1.5 pr-3 whitespace-nowrap">{formatChicago(h.changed_at, "datetime")}</td>
            <td className="py-1.5 pr-3"><span className="block text-muted-foreground">{h.old_bank_name}</span><CheckLine routing={h.old_routing} account={h.old_account_masked} className="text-sm text-muted-foreground" /></td>
            <td className="py-1.5 pr-3"><span className="block font-medium">{h.new_bank_name}</span><CheckLine routing={h.new_routing} account={h.new_account_masked} className="text-sm" /></td>
            <td className="py-1.5 pr-3"><span className="inline-flex items-center gap-1 text-paid"><PhoneCall className="size-4" aria-hidden />verified by callback</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

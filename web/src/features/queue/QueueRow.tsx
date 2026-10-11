// Candidate 13: queue rows with tier, amount, status and age. Speed for people working a queue.
import { createElement } from "react";

import { statusIcon, statusWord } from "@/lib/decide";
import { relativeAge } from "@/lib/format";
import type { InvoiceListRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<string, string> = {
  RELEASED: "text-paid", HELD: "text-held", NEEDS_REVIEW: "text-review", CALL_PENDING: "text-review", CALLING: "text-review", VERIFYING: "text-review",
};

const TIER_DOT: Record<string, string> = { GREEN: "bg-paid", YELLOW: "bg-review", RED: "bg-held" };

interface Props { row: InvoiceListRow; selected?: boolean; onSelect?: () => void; now?: number; className?: string; tabIndex?: number }

function StatusLabel({ row, className }: { row: InvoiceListRow; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", STATUS_TONE[row.status] ?? "text-muted-foreground", className)}>
      {createElement(statusIcon(row.status), { className: "size-3.5", "aria-hidden": true })}
      {statusWord(row.status, row.hold_reason)}
    </span>
  );
}

/** Variant A: two lines, vendor and amount above, status and age below. */
export function QueueRowStacked({ row, selected, onSelect, now, className, tabIndex = 0 }: Props) {
  return (
    <button type="button" onClick={onSelect} tabIndex={tabIndex} aria-current={selected ? "true" : undefined}
            className={cn("w-full rounded-md border px-3 py-2 text-left transition-colors", selected ? "border-primary bg-accent" : "border-transparent hover:bg-accent/60", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate font-medium">{row.vendor_name ?? "Unknown sender"}</span>
        <span className="tabular shrink-0">{row.amount_display ?? "—"}</span>
      </div>
      <div className="mt-0.5 flex items-center gap-2 text-sm">
        <StatusLabel row={row} />
        {row.tier && <span className="inline-flex items-center gap-1 text-muted-foreground"><span className={cn("size-2 rounded-full", TIER_DOT[row.tier])} aria-hidden />{row.points} pts</span>}
        <span className="ml-auto text-muted-foreground">{relativeAge(row.created_at, now)}</span>
      </div>
    </button>
  );
}

/** Variant B: single line with a right-aligned status. */
export function QueueRowLine({ row, selected, onSelect, className, tabIndex = 0 }: Props) {
  return (
    <button type="button" onClick={onSelect} tabIndex={tabIndex} aria-current={selected ? "true" : undefined}
            className={cn("flex w-full items-center gap-2 rounded-md border px-3 py-1.5 text-left", selected ? "border-primary bg-accent" : "border-transparent hover:bg-accent/60", className)}>
      {row.tier && <span className={cn("size-2.5 shrink-0 rounded-full", TIER_DOT[row.tier])} aria-label={`${row.tier.toLowerCase()} tier`} />}
      <span className="truncate">{row.vendor_name ?? "Unknown sender"}</span>
      <span className="tabular ml-auto shrink-0">{row.amount_display ?? "—"}</span>
      <StatusLabel row={row} className="w-24 shrink-0 justify-end text-sm" />
    </button>
  );
}

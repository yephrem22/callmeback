// Candidate 5: destination card. On file vs requested, as check lines. The core FinTech object.
import { ArrowDownUp, ShieldCheck } from "lucide-react";

import { CheckLine } from "@/features/case/CheckLine";
import type { Destination } from "@/lib/types";
import { cn } from "@/lib/utils";

function changed(d: Destination) {
  const r = d.requested, o = d.on_file;
  return {
    routing: !!(d.changed && r && o && r.routing && r.routing !== o.routing),
    account: !!(d.changed && r && o && r.account_masked && r.account_masked !== o.account_masked),
  };
}

/** Variant A: two rows, on file then requested. */
export function DestinationRows({ destination: d, className }: { destination: Destination; className?: string }) {
  const c = changed(d);
  return (
    <div className={cn("space-y-2", className)} role="group" aria-label="Payment destination">
      <div className="grid grid-cols-[6.5rem_1fr] items-center gap-x-3">
        <span className="text-sm text-muted-foreground">On file</span>
        {d.on_file ? (
          <span className="flex flex-wrap items-center gap-x-3">
            <span className="font-medium">{d.on_file.bank_name}</span>
            <CheckLine routing={d.on_file.routing} account={d.on_file.account_masked} />
            <ShieldCheck className="size-4 text-paid" aria-label="vendor master" />
          </span>
        ) : <span className="text-sm text-muted-foreground">No vendor record</span>}
      </div>
      {d.requested && (
        <div className="grid grid-cols-[6.5rem_1fr] items-center gap-x-3">
          <span className={cn("text-sm", d.changed ? "font-medium text-held" : "text-muted-foreground")}>{d.changed ? "Requested" : "In email"}</span>
          <span className="flex flex-wrap items-center gap-x-3">
            <span className={cn("font-medium", d.changed && "text-held")}>{d.requested.bank_name ?? "Unnamed bank"}</span>
            <CheckLine routing={d.requested.routing} account={d.requested.account_masked} changedRouting={c.routing} changedAccount={c.account} />
            {d.changed && <ArrowDownUp className="size-4 text-held" aria-label="differs from the vendor record" />}
          </span>
        </div>
      )}
      {d.changed && <p className="text-sm text-held">Bank details differ from the vendor record. Money only moves to the account on file after a verified callback.</p>}
      {!d.changed && d.on_file && <p className="text-sm text-muted-foreground">Same account as the vendor record.</p>}
    </div>
  );
}

function DestinationColumn({ title, line, tone, hotRouting = false, hotAccount = false }: {
  title: string; line: Destination["on_file"]; tone: "ok" | "hot" | "none"; hotRouting?: boolean; hotAccount?: boolean;
}) {
  return (
    <div className={cn("rounded-md border p-3", tone === "hot" ? "border-held/50 bg-held-soft/40" : "border-border")}>
      <p className={cn("text-sm", tone === "hot" ? "font-medium text-held" : "text-muted-foreground")}>{title}</p>
      {line ? (
        <>
          <p className="mt-1 font-medium">{line.bank_name ?? "Unnamed bank"}</p>
          <CheckLine routing={line.routing} account={line.account_masked} changedRouting={hotRouting} changedAccount={hotAccount} className="mt-1" />
        </>
      ) : <p className="mt-1 text-sm text-muted-foreground">No vendor record</p>}
    </div>
  );
}

/** Variant B: two columns side by side. */
export function DestinationColumns({ destination: d, className }: { destination: Destination; className?: string }) {
  const c = changed(d);
  return (
    <div className={cn("grid gap-3", d.requested ? "grid-cols-2" : "grid-cols-1", className)} role="group" aria-label="Payment destination">
      <DestinationColumn title="On file (vendor master)" line={d.on_file} tone={d.on_file ? "ok" : "none"} />
      {d.requested && (
        <DestinationColumn title={d.changed ? "Requested in the email" : "In the email (unchanged)"} line={d.requested}
                           tone={d.changed ? "hot" : "ok"} hotRouting={d.changed && c.routing} hotAccount={d.changed && c.account} />
      )}
    </div>
  );
}

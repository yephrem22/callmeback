// Candidate 5: destination card. On file vs requested, as check lines. The core FinTech object.
import { ArrowDownUp, ShieldCheck } from "lucide-react";

import { CheckLine } from "@/features/case/CheckLine";
import type { Destination } from "@/lib/types";
import { cn } from "@/lib/utils";

/** What differs *now* between the request and the vendor master. After a verified bank change the master is
 *  updated, so a request that once differed no longer does; the highlight follows the current state. */
function changed(d: Destination) {
  const r = d.requested, o = d.on_file;
  const routing = !!(r && o && r.routing && r.routing !== o.routing);
  const account = !!(r && o && r.account_masked && r.account_masked !== o.account_masked);
  return { routing, account, any: routing || account, wasChanged: d.changed && !(routing || account) && !!r && !!o };
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
          <span className={cn("text-sm", c.any ? "font-medium text-held" : "text-muted-foreground")}>{c.any ? "Requested" : c.wasChanged ? "Requested" : "In email"}</span>
          <span className="flex flex-wrap items-center gap-x-3">
            <span className={cn("font-medium", c.any && "text-held")}>{d.requested.bank_name ?? "Unnamed bank"}</span>
            <CheckLine routing={d.requested.routing} account={d.requested.account_masked} changedRouting={c.routing} changedAccount={c.account} />
            {c.any && <ArrowDownUp className="size-4 text-held" aria-label="differs from the vendor record" />}
          </span>
        </div>
      )}
      {c.any && <p className="text-sm text-held">Bank details differ from the vendor record. Money only moves to the account on file after a verified callback.</p>}
      {c.wasChanged && <p className="text-sm text-paid">Verified by callback; the vendor record now matches the request.</p>}
      {!c.any && !c.wasChanged && d.on_file && <p className="text-sm text-muted-foreground">Same account as the vendor record.</p>}
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
        <DestinationColumn title={c.any ? "Requested in the email" : c.wasChanged ? "Requested, now verified and on file" : "In the email (unchanged)"} line={d.requested}
                           tone={c.any ? "hot" : "ok"} hotRouting={c.routing} hotAccount={c.account} />
      )}
    </div>
  );
}

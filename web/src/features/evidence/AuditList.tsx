// Candidate 9: audit chain list with an integrity seal and hash links. Evidence you can trust.
import { Download, Link2, ShieldAlert, ShieldCheck } from "lucide-react";

import { formatChicago } from "@/lib/format";
import type { AuditRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChainSeal({ ok, count, brokenAt }: { ok: boolean | null; count: number; brokenAt?: number | null }) {
  if (ok === null) return <span className="text-sm text-muted-foreground">Chain not checked</span>;
  return ok ? (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-paid/40 bg-paid-soft px-2 py-0.5 text-sm font-medium text-paid">
      <ShieldCheck className="size-4" aria-hidden /> Chain verified ✓ ({count} entries)
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-held/40 bg-held-soft px-2 py-0.5 text-sm font-medium text-held">
      <ShieldAlert className="size-4" aria-hidden /> Chain broken at #{brokenAt ?? "?"}
    </span>
  );
}

/** Variant A: dense table. */
export function AuditTable({ rows, chainOk = null, brokenAt = null, className }: { rows: AuditRow[]; chainOk?: boolean | null; brokenAt?: number | null; className?: string }) {
  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-medium">Audit trail</h3>
        <ChainSeal ok={chainOk} count={rows.length} brokenAt={brokenAt} />
      </div>
      <table className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr><th className="py-1 pr-2 font-normal">#</th><th className="py-1 pr-2 font-normal">Time</th><th className="py-1 pr-2 font-normal">Actor</th><th className="py-1 pr-2 font-normal">Event</th><th className="py-1 pr-2 font-normal">Hash</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.seq} className="border-t border-border align-top">
              <td className="tabular py-1 pr-2 text-muted-foreground">{r.seq}</td>
              <td className="tabular py-1 pr-2 whitespace-nowrap">{formatChicago(r.ts)}</td>
              <td className="py-1 pr-2 whitespace-nowrap">{r.actor}</td>
              <td className="py-1 pr-2"><span className="font-medium">{r.event.replace(/_/g, " ")}</span><span className="block text-muted-foreground">{r.summary}</span></td>
              <td className="mono py-1 pr-2 text-muted-foreground">{r.hash_short}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Downloads exactly the entries on screen plus the chain check, as JSON (spec 007 R7; no new endpoint). */
function exportAudit(rows: AuditRow[], chainOk: boolean | null, brokenAt: number | null, name: string): void {
  const body = JSON.stringify({ entries: rows, chain_ok: chainOk, broken_at: brokenAt }, null, 2);
  const url = URL.createObjectURL(new Blob([body], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `audit-${name}-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Variant B: timeline with hash links between entries. `exportName` adds the export link (P1). */
export function AuditTimeline({ rows, chainOk = null, brokenAt = null, className, exportName }: {
  rows: AuditRow[]; chainOk?: boolean | null; brokenAt?: number | null; className?: string; exportName?: string;
}) {
  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="font-medium">Audit trail</h3>
        <span className="flex items-center gap-3">
          <ChainSeal ok={chainOk} count={rows.length} brokenAt={brokenAt} />
          {exportName && rows.length > 0 && (
            <button type="button" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-2 hover:underline"
                    onClick={() => exportAudit(rows, chainOk, brokenAt, exportName)}>
              <Download className="size-4" aria-hidden /> Export JSON
            </button>
          )}
        </span>
      </div>
      <ol className="space-y-0 text-sm">
        {rows.map((r, i) => (
          <li key={r.seq} className="relative pl-6">
            {i < rows.length - 1 && <span className="absolute left-[7px] top-5 h-full border-l border-dashed border-border" aria-hidden />}
            <Link2 className={cn("absolute left-0 top-1 size-4", chainOk === false && brokenAt === r.seq ? "text-held" : "text-primary")} aria-hidden />
            <div className="flex flex-wrap items-baseline gap-x-2 pb-2">
              <span className="tabular text-muted-foreground">{formatChicago(r.ts)}</span>
              <span className="font-medium">{r.event.replace(/_/g, " ")}</span>
              <span className="text-muted-foreground">by {r.actor}</span>
              <span className="mono ml-auto text-xs text-muted-foreground">#{r.seq} · {r.hash_short}</span>
              <span className="w-full text-muted-foreground">{r.summary}</span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

// Actions, shown according to `actions` (PLAN.md §7.6, §14.9). Buttons say what happens; no arrows; sentence case.
import { Check, PanelRightOpen, PhoneForwarded, ShieldBan, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { postRedteam, postRetryCallback, postReview, postSimulate, useAction } from "@/lib/api";
import type { InvoiceDetail } from "@/lib/types";

export function Actions({ d, demoMode, onRedteam }: { d: InvoiceDetail; demoMode: boolean; onRedteam?: () => void }) {
  const review = useAction(postReview);
  const retry = useAction(postRetryCallback);
  const simulate = useAction(postSimulate);
  const redteam = useAction(postRedteam);
  const [result, setResult] = useState<{ blocked: boolean; layer: string; reason: string } | null>(null);
  const a = d.actions;
  if (!a.can_review && !a.can_retry_call && !a.can_redteam && !(a.can_simulate && demoMode)) return null;

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Actions">
      {a.can_review && (
        <>
          <Button onClick={() => review.mutate([d.id, "approve", ""], { onSuccess: () => toast.success("Payment approved") })} disabled={review.isPending}>
            <Check className="size-4" aria-hidden /> Approve payment
          </Button>
          <Button variant="outline" onClick={() => review.mutate([d.id, "reject", ""], { onSuccess: () => toast("Invoice rejected") })} disabled={review.isPending}>
            <X className="size-4" aria-hidden /> Reject
          </Button>
        </>
      )}
      {a.can_retry_call && (
        <Button variant="outline" onClick={() => retry.mutate([d.id], { onSuccess: () => toast("Calling the vendor again") })} disabled={retry.isPending}>
          <PhoneForwarded className="size-4" aria-hidden /> Call vendor again
        </Button>
      )}
      {a.can_simulate && demoMode && (
        <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-review/60 px-1.5 py-0.5">
          <span className="px-1 text-xs uppercase tracking-wide text-review">Simulate</span>
          <Button size="sm" variant="ghost" onClick={() => simulate.mutate([d.id, "yes", d.risk?.bank_changed ? "4455" : null], { onSuccess: () => toast("Simulated: vendor said yes") })}>Vendor says yes</Button>
          <Button size="sm" variant="ghost" onClick={() => simulate.mutate([d.id, "no", null], { onSuccess: () => toast("Simulated: vendor said no") })}>Vendor says no</Button>
        </span>
      )}
      {a.can_redteam && (
        <Button variant="outline" className="ml-auto border-held text-held hover:bg-held-soft hover:text-held"
                onClick={() => redteam.mutate([d.id], { onSuccess: (r) => setResult(r) })} disabled={redteam.isPending}>
          <ShieldBan className="size-4" aria-hidden /> Try to make the AI pay
        </Button>
      )}

      {/* The verdict first; the trace sheet opens as the dialog closes (two modals at once hid the verdict). */}
      <Dialog open={!!result} onOpenChange={(o) => { if (!o) { setResult(null); onRedteam?.(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-held"><ShieldBan className="size-5" aria-hidden />{result?.blocked ? "Blocked" : "Not blocked"}</DialogTitle>
            <DialogDescription>
              A deliberately compromised Payments agent was told by a fake CFO to release this payment.
            </DialogDescription>
          </DialogHeader>
          {result && (
            <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">Stopped by</dt>
              <dd className="font-medium">{result.layer === "plugin" ? "the Strands payment-guard plugin" : result.layer === "ledger" ? "the ledger's own policy check" : "the agent refused"}</dd>
              <dt className="text-muted-foreground">Reason</dt>
              <dd>{result.reason}</dd>
            </dl>
          )}
          <p className="text-sm text-muted-foreground">The AI explains; the code holds the keys. Release is enforced twice: by the plugin and again inside the ledger. The trace shows the blocked call.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setResult(null); onRedteam?.(); }}>
              <PanelRightOpen className="size-4" aria-hidden /> Show the agent trace
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

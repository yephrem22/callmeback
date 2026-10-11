// Callback panel: winners 6B vertical timeline and 7B transcript row. Hidden when there is no verification
// and nothing is pending (unknown vendor); "waiting" state for CALL_PENDING before a row exists.
import { PhoneOutgoing } from "lucide-react";

import { Separator } from "@/components/ui/separator";
import { CallbackTimeline } from "@/features/callback/CallbackStepper";
import { TranscriptRow } from "@/features/callback/TranscriptBubble";
import type { InvoiceDetail } from "@/lib/types";

export function CallbackPanel({ d }: { d: InvoiceDetail }) {
  const v = d.verification;
  if (!v && d.status !== "CALL_PENDING") return null;
  return (
    <>
      <Separator />
      <section aria-label="Callback" className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">Callback</h3>
        {v ? (
          <>
            <CallbackTimeline verification={v} />
            {v.first_answer && <TranscriptRow verification={v} className="rounded-md border border-border bg-card p-3" />}
          </>
        ) : (
          <p className="flex items-center gap-2 text-muted-foreground"><PhoneOutgoing className="size-4 text-primary" aria-hidden />Placing the call to the number on file…</p>
        )}
      </section>
    </>
  );
}

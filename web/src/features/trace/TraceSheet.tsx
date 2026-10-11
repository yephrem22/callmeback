// The agent trace as a right-hand sheet (winner 8B grouped list). Opens on request and on the red-team action.
import { Sparkles } from "lucide-react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { TraceList } from "@/features/trace/TraceWaterfall";
import type { InvoiceDetail } from "@/lib/types";

export function TraceSheet({ d, open, onOpenChange }: { d: InvoiceDetail | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[520px] sm:max-w-[560px]">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2"><Sparkles className="size-5 text-ai" aria-hidden />Agent trace</SheetTitle>
          <SheetDescription>Every Strands agent run, model call and tool call for this invoice. A guard block is shown in red.</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">
          {d ? <TraceList trace={d.trace} /> : <p className="text-sm text-muted-foreground">Open a case to see its trace.</p>}
        </div>
      </SheetContent>
    </Sheet>
  );
}

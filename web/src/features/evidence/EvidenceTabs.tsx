// Evidence: email, extracted fields, audit trail (winner 9B), analyst note (AI). Secondary, below the fold.
import { AlertTriangle, Sparkles } from "lucide-react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuditTimeline } from "@/features/evidence/AuditList";
import { formatChicago } from "@/lib/format";
import type { FieldValue, InvoiceDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

export function EmailView({ d }: { d: InvoiceDetail }) {
  const e = d.email;
  const replyDiffers = !!e.reply_to && !!e.from_email && e.reply_to.split("@")[1] !== e.from_email.split("@")[1];
  return (
    <div className="text-sm">
      <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-0.5">
        <dt className="text-muted-foreground">From</dt><dd>{e.from_name ? `${e.from_name} <${e.from_email}>` : e.from_email}</dd>
        {e.reply_to && (<><dt className="text-muted-foreground">Reply-To</dt><dd className={cn(replyDiffers && "font-medium text-held")}>{e.reply_to}{replyDiffers && " (different domain)"}</dd></>)}
        <dt className="text-muted-foreground">Subject</dt><dd>{e.subject}</dd>
        <dt className="text-muted-foreground">Received</dt><dd>{formatChicago(e.received_at, "datetime")}</dd>
      </dl>
      <ScrollArea className="mt-3 h-56 rounded-md border border-border bg-card p-3">
        <pre className="whitespace-pre-wrap font-sans leading-relaxed">{e.body_text}</pre>
      </ScrollArea>
    </div>
  );
}

const FIELD_LABEL: Record<string, string> = {
  vendor_name: "Vendor", invoice_number: "Invoice number", amount: "Amount", due_date: "Due date",
  bank_name: "Bank", routing_number: "Routing number", account_number: "Account number",
};

function sourceChip(f: FieldValue) {
  if (f.mismatch) return { text: "AI disagreed; text used", cls: "bg-review-soft text-review" };
  if (f.source === "both") return { text: "text and AI agree", cls: "bg-paid-soft text-paid" };
  if (f.source === "llm") return { text: "AI", cls: "bg-ai-soft text-ai" };
  if (f.source === "regex" || f.source === "header") return { text: "text", cls: "bg-muted text-muted-foreground" };
  return { text: "not found", cls: "bg-muted text-muted-foreground" };
}

export function ExtractedFields({ d }: { d: InvoiceDetail }) {
  const fields = d.extracted.fields;
  return (
    <div className="text-sm">
      <table className="w-full">
        <tbody>
          {(Object.keys(FIELD_LABEL) as (keyof typeof fields)[]).map((k) => {
            const f = fields[k];
            const chip = sourceChip(f);
            const mono = k === "routing_number" || k === "account_number";
            return (
              <tr key={k} className="border-b border-border last:border-0">
                <td className="py-1.5 pr-3 text-muted-foreground">{FIELD_LABEL[k]}</td>
                <td className={cn("py-1.5 pr-3", mono && "mono")}>{f.value ?? "—"}</td>
                <td className="py-1.5 text-right"><span className={cn("rounded-full px-2 py-0.5 text-xs", chip.cls)}>{chip.text}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {d.extracted.phone_numbers_in_email.length > 0 && (
        <p className="mt-2 text-muted-foreground">Phone numbers in the email (ignored): {d.extracted.phone_numbers_in_email.join(", ")}</p>
      )}
      <p className="mt-1 text-xs text-muted-foreground">Text extraction: {d.extracted.llm_status === "fallback" ? "rules only" : d.extracted.llm_status}</p>
    </div>
  );
}

export function AnalystNote({ d }: { d: InvoiceDetail }) {
  const a = d.analyst;
  return (
    <div className="rounded-md border border-ai/40 bg-ai-soft/40 p-3 text-sm">
      <p className="flex items-center gap-1.5 text-ai"><Sparkles className="size-4" aria-hidden /><span className="font-medium">AI-written explanation; doesn't change the decision</span>
        {a.status === "fallback" && <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Rules fallback</span>}
        {a.status === "pending" && <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Pending</span>}
      </p>
      {a.report ? (
        <div className="mt-2 space-y-1.5">
          <p className="font-medium">{a.report.headline}</p>
          <p>{a.report.explanation}</p>
          {a.report.additional_concerns.length > 0 && (
            <p className="text-muted-foreground"><AlertTriangle className="mr-1 inline size-3.5" aria-hidden />Also noticed: {a.report.additional_concerns.join("; ")}</p>
          )}
          <p className="text-muted-foreground">Next step: {a.report.recommended_next_step}</p>
          <p className="text-xs text-muted-foreground">Cites {a.report.cited_flags.join(", ") || "no flags"}</p>
        </div>
      ) : (
        <p className="mt-2 text-muted-foreground">The Analyst agent hasn't written its note yet. The decision above doesn't depend on it.</p>
      )}
      {d.memo && <p className="mt-3 border-t border-ai/30 pt-2 text-muted-foreground">Payments memo ({d.memo.by === "agent" ? "agent" : "rules"}): {d.memo.text}</p>}
    </div>
  );
}

export function EvidenceTabs({ d }: { d: InvoiceDetail }) {
  return (
    <>
      <Separator />
      <section aria-label="Evidence">
        <Tabs defaultValue="email">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-medium text-muted-foreground">Evidence</h3>
            <TabsList>
              <TabsTrigger value="email">Email</TabsTrigger>
              <TabsTrigger value="fields">Extracted fields</TabsTrigger>
              <TabsTrigger value="audit">Audit trail</TabsTrigger>
              <TabsTrigger value="analyst"><Sparkles className="size-3.5 text-ai" aria-hidden />Analyst note (AI)</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="email" className="pt-3"><EmailView d={d} /></TabsContent>
          <TabsContent value="fields" className="pt-3"><ExtractedFields d={d} /></TabsContent>
          <TabsContent value="audit" className="pt-3"><AuditTimeline rows={d.audit} chainOk={null} /></TabsContent>
          <TabsContent value="analyst" className="pt-3"><AnalystNote d={d} /></TabsContent>
        </Tabs>
      </section>
    </>
  );
}

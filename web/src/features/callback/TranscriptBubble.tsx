// Candidate 7: transcript bubble with classifier and verifier chips. Shows the AI can only downgrade a yes.
import { Hash, MessageSquareQuote, Sparkles } from "lucide-react";

import type { Verification } from "@/lib/types";
import { cn } from "@/lib/utils";

function labelTone(l: string | null | undefined) {
  if (l === "YES" || l === "CONFIRMED") return "bg-paid-soft text-paid";
  if (l === "NO" || l === "DENIED") return "bg-held-soft text-held";
  return "bg-muted text-muted-foreground";
}

export function Last4Result({ v }: { v: Verification }) {
  if (v.last4_ok == null) return null;
  return (
    <p className={cn("mt-2 inline-flex items-center gap-1.5 text-sm", v.last4_ok ? "text-paid" : "text-held")}>
      <Hash className="size-4" aria-hidden /> Last four digits {v.last4_ok ? "matched" : "did not match"}
    </p>
  );
}

function Chips({ v }: { v: Verification }) {
  const a = v.first_answer;
  if (!a) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className={cn("rounded-full px-2 py-0.5 font-medium", labelTone(a.det_label))}>classifier: {a.det_label ?? "—"}</span>
      {a.channel === "speech" && (
        <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium", a.llm_label ? "bg-ai-soft text-ai" : "bg-muted text-muted-foreground")}>
          <Sparkles className="size-3" aria-hidden /> verifier: {a.llm_label ?? "pending"}
        </span>
      )}
      {a.channel === "speech" && a.confidence != null && <span className="text-muted-foreground">speech confidence {Math.round(a.confidence * 100)}%</span>}
      {a.channel === "dtmf" && <span className="text-muted-foreground">keypad answers need no verifier</span>}
    </div>
  );
}

/** Variant A: a quote bubble. */
export function TranscriptBubble({ verification: v, className }: { verification: Verification; className?: string }) {
  const a = v.first_answer;
  if (!a) return <p className={cn("text-sm text-muted-foreground", className)}>No answer yet.</p>;
  const text = a.channel === "dtmf" ? `Pressed ${a.digits}` : a.speech ?? "(no speech)";
  return (
    <div className={className}>
      <figure className="relative rounded-lg border border-border bg-card p-3 pl-9">
        <MessageSquareQuote className="absolute left-3 top-3 size-4 text-muted-foreground" aria-hidden />
        <blockquote className="text-lg leading-snug">"{text}"</blockquote>
        <figcaption className="mt-2"><Chips v={v} /></figcaption>
      </figure>
      <Last4Result v={v} />
    </div>
  );
}

/** Variant B: a compact row. */
export function TranscriptRow({ verification: v, className }: { verification: Verification; className?: string }) {
  const a = v.first_answer;
  if (!a) return <p className={cn("text-sm text-muted-foreground", className)}>No answer yet.</p>;
  const text = a.channel === "dtmf" ? `Pressed ${a.digits}` : a.speech ?? "(no speech)";
  return (
    <div className={cn("grid grid-cols-[5rem_1fr] items-start gap-x-3 gap-y-1 text-sm", className)}>
      <span className="text-muted-foreground">Vendor said</span>
      <span className="font-medium">"{text}"</span>
      <span className="text-muted-foreground">Read as</span>
      <Chips v={v} />
      {v.last4_ok != null && (<><span className="text-muted-foreground">Last four</span><span className={v.last4_ok ? "text-paid" : "text-held"}>{v.last4_ok ? "matched" : "did not match"}</span></>)}
    </div>
  );
}

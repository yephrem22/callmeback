import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { Candidate } from "@/features/gallery/candidates";

export function CandidateCard({ c }: { c: Candidate }) {
  return (
    <article id={`c${c.n}`} className="rounded-lg border border-border bg-card p-5" aria-labelledby={`c${c.n}-title`}>
      <header className="flex items-baseline gap-3">
        <span className="tabular text-sm text-muted-foreground">#{c.n}</span>
        <h2 id={`c${c.n}-title`} className="text-[22px] font-semibold">{c.name}</h2>
        <span className="ml-auto text-sm text-muted-foreground">fixture: {c.fixture}</span>
      </header>

      <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">What it shows</dt><dd>{c.shows}</dd>
        <dt className="text-muted-foreground">Serves</dt><dd>{c.serves}</dd>
        <dt className="text-muted-foreground">§7.6 fields</dt>
        <dd className="flex flex-wrap gap-1">{c.fields.map((f) => <code key={f} className="mono rounded bg-muted px-1.5 py-0.5 text-xs">{f}</code>)}</dd>
        <dt className="text-muted-foreground">Components</dt><dd>{c.components.join(" · ")}</dd>
        <dt className="text-muted-foreground">Why it might win</dt><dd>{c.why}</dd>
      </dl>

      <div className="mt-4 grid grid-cols-2 gap-4">
        {c.variants.map((v) => (
          <section key={v.label} className="rounded-md border border-dashed border-border p-4">
            <h3 className="mb-3 text-sm font-medium text-muted-foreground">{v.label}</h3>
            <div className="min-h-16">{v.render()}</div>
            <Snippet code={v.snippet} />
          </section>
        ))}
      </div>
    </article>
  );
}

function Snippet({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative mt-4">
      <pre className="mono whitespace-pre-wrap break-all rounded bg-muted p-2 pr-24 text-xs leading-relaxed">{code}</pre>
      <Button size="sm" variant="outline" className="absolute right-1 top-1 h-7"
              onClick={() => { void navigator.clipboard.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1200); }); }}>
        {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />} {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}

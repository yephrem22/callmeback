// Development-only gallery of the PLAN.md §14.8 candidates (milestone U1). Humans pick winners at U2.
import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { CandidateCard } from "@/features/gallery/CandidateCard";
import { CANDIDATES } from "@/features/gallery/candidates";
import { useTheme } from "@/lib/theme";

export default function Gallery() {
  const { theme, setTheme } = useTheme();
  useEffect(() => { document.body.dataset.ready = "true"; document.title = "Gallery · Call Me Back"; });
  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-[28px] font-semibold">Component gallery</h1>
          <p className="mt-1 text-muted-foreground">Fourteen candidates from PLAN.md §14.8, two variants each, rendered on the real fixtures from spec 003. Development only.</p>
        </div>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant={theme === "light" ? "secondary" : "ghost"} onClick={() => setTheme("light")}><Sun className="size-4" aria-hidden /> Light</Button>
          <Button size="sm" variant={theme === "dark" ? "secondary" : "ghost"} onClick={() => setTheme("dark")}><Moon className="size-4" aria-hidden /> Dark</Button>
          <Button size="sm" variant={theme === "system" ? "secondary" : "ghost"} onClick={() => setTheme("system")}><Monitor className="size-4" aria-hidden /> System</Button>
        </div>
      </header>

      <nav aria-label="Candidates" className="mb-6 flex flex-wrap gap-1.5 text-sm">
        {CANDIDATES.map((c) => <a key={c.n} href={`#c${c.n}`} className="rounded border border-border px-2 py-0.5 hover:bg-accent"><span className="tabular text-muted-foreground">{c.n}</span> {c.name}</a>)}
      </nav>

      <div className="space-y-6">
        {CANDIDATES.map((c) => <CandidateCard key={c.n} c={c} />)}
      </div>

      <footer className="mt-10 border-t border-border pt-4 text-sm text-muted-foreground">
        Chart rules (PLAN.md §14.8): marks are labelled directly, color never carries meaning alone, status colors match the tokens, numerals are tabular, no pie or 3D charts, nothing readable only through a tooltip.
        Record winners in <code className="mono">docs/design/decisions.md</code>.
      </footer>
    </div>
  );
}

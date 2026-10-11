import { PanelRightOpen } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Header } from "@/features/shell/Header";
import { fixtureStore } from "@/lib/fixtures";
import { isFixtures } from "@/lib/api";
import { setQuery, type Route, type Tab } from "@/lib/route";

const TABS: { id: Exclude<Tab, null>; label: string }[] = [
  { id: "payments", label: "Payments" },
  { id: "vendors", label: "Vendors" },
  { id: "audit", label: "Audit log" },
  { id: "devrev", label: "DevRev cases" },
  { id: "demo", label: "Demo controls" },
];

export function Layout({ route }: { route: Route }) {
  // URL → fixture store (contracts/fixtures-and-routes.md). Spec 007 replaces the store with live data.
  useEffect(() => {
    if (!isFixtures) return;
    if (route.scenario && route.scenario !== "none") fixtureStore.load(route.scenario, route.step ?? fixtureStore.stepOf(route.scenario));
  }, [route.scenario, route.step]);

  useEffect(() => {
    document.body.dataset.ready = "true";
    document.body.dataset.scenario = route.scenario ?? "";
    document.body.dataset.step = String(route.step ?? "");
  });

  return (
    <div className="flex h-dvh flex-col">
      <Header />
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr]">
        <aside className="min-h-0 overflow-y-auto border-r border-border p-3" aria-label="Queue">
          <p className="text-sm text-muted-foreground">Queue</p>
        </aside>
        <main className="min-h-0 overflow-y-auto p-6" aria-label="Case">
          <p className="text-lg text-muted-foreground">Load a sample invoice to start.</p>
        </main>
      </div>
      <nav className="flex h-11 items-center gap-1 border-t border-border px-2" aria-label="Tabs">
        {TABS.map((t) => (
          <Button key={t.id} variant={route.tab === t.id ? "secondary" : "ghost"} size="sm"
                  onClick={() => setQuery({ tab: route.tab === t.id ? null : t.id })}>
            {t.label}
          </Button>
        ))}
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => setQuery({ trace: route.trace ? null : 1 })}>
          <PanelRightOpen className="size-4" aria-hidden /> Show agent trace
        </Button>
      </nav>
    </div>
  );
}

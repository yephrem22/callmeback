import { PanelRightOpen } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Actions } from "@/features/case/Actions";
import { CaseView } from "@/features/case/CaseView";
import { PaymentCard } from "@/features/case/PaymentCard";
import { CallbackPanel } from "@/features/callback/CallbackPanel";
import { EvidenceTabs } from "@/features/evidence/EvidenceTabs";
import { QueueList } from "@/features/queue/QueueList";
import { Header } from "@/features/shell/Header";
import { BottomTabs } from "@/features/shell/Tabs";
import { TraceSheet } from "@/features/trace/TraceSheet";
import { isFixtures, isGone, useHealth, useInvoice } from "@/lib/api";
import { fixtureStore, useFixtureVersion } from "@/lib/fixtures";
import { isDev, setQuery, type Route, type Tab } from "@/lib/route";

const ScenarioPlayer = lazy(() => import("virtual:dev-only/player"));

const TABS: { id: Exclude<Tab, null>; label: string }[] = [
  { id: "payments", label: "Payments" },
  { id: "vendors", label: "Vendors" },
  { id: "audit", label: "Audit log" },
  { id: "demo", label: "Demo controls" },
];

export function Layout({ route }: { route: Route }) {
  useFixtureVersion();
  const { data: health } = useHealth();
  const [liveSelected, setLiveSelected] = useState<string | null>(null);

  // URL → fixture store (contracts/fixtures-and-routes.md). In live mode the selection is local state (spec 007).
  useEffect(() => {
    if (!isFixtures) return;
    if (route.scenario && route.scenario !== "none") fixtureStore.load(route.scenario, route.step ?? fixtureStore.stepOf(route.scenario));
  }, [route.scenario, route.step]);

  const selectedId = useMemo(() => {
    if (isFixtures) return route.scenario && route.scenario !== "none" ? fixtureStore.invoiceIdFor(route.scenario) : null;
    return liveSelected;
  }, [route.scenario, liveSelected]);

  const { data: loaded, error: detailError } = useInvoice(selectedId);
  // Live mode: a selected invoice that vanished (a reset from another browser) shows as no selection;
  // its query stops polling on the 404 (lib/api.ts), and the next pick replaces it.
  const detail = !isFixtures && isGone(detailError) ? undefined : loaded;

  const onSelect = (id: string) => {
    if (isFixtures) { const s = fixtureStore.scenarioForInvoice(id); if (s) setQuery({ scenario: s, step: fixtureStore.stepOf(s) }); }
    else setLiveSelected(id);
  };

  useEffect(() => {
    const ready = !selectedId || !!detail;
    document.body.dataset.ready = ready ? "true" : "false";
    document.body.dataset.scenario = route.scenario ?? "";
    document.body.dataset.step = String(route.step ?? "");
  });

  return (
    <div className="flex h-dvh flex-col">
      <Header />
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr]">
        <aside className="min-h-0 border-r border-border p-3" aria-label="Queue">
          <QueueList selectedId={selectedId} onSelect={onSelect} />
        </aside>
        <main className="min-h-0 overflow-y-auto px-6 py-5" aria-label="Case">
          {detail ? (
            <div className="mx-auto max-w-4xl space-y-5">
              <CaseView d={detail} />
              <CallbackPanel d={detail} />
              {detail.payment && <PaymentCard p={detail.payment} />}
              <Actions d={detail} demoMode={!!health?.demo_mode} onRedteam={() => setQuery({ trace: 1 })} />
              <EvidenceTabs d={detail} />
            </div>
          ) : (
            <p className="text-lg text-muted-foreground">Load a sample invoice to start.</p>
          )}
        </main>
      </div>

      {route.tab && <BottomTabs tab={route.tab} onClose={() => setQuery({ tab: null })} onReset={() => setLiveSelected(null)} selected={detail ?? null} />}

      <nav className="flex h-11 items-center gap-1 border-t border-border px-2" aria-label="Tabs">
        {TABS.filter((t) => t.id !== "demo" || health?.demo_mode).map((t) => (
          <Button key={t.id} variant={route.tab === t.id ? "secondary" : "ghost"} size="sm"
                  onClick={() => setQuery({ tab: route.tab === t.id ? null : t.id })}>
            {t.label}
          </Button>
        ))}
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => setQuery({ trace: route.trace ? null : 1 })}>
          <PanelRightOpen className="size-4" aria-hidden /> Show agent trace
        </Button>
      </nav>

      <TraceSheet d={detail ?? null} open={route.trace} onOpenChange={(o) => setQuery({ trace: o ? 1 : null })} />
      {isDev && isFixtures && route.player && (
        <Suspense fallback={null}><ScenarioPlayer scenario={route.scenario} /></Suspense>
      )}
    </div>
  );
}

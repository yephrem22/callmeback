// Development-only scenario player (PLAN.md §14.7 step 4): steps through the demo story on fixtures.
// Loaded through virtual:dev-only/player, so it never reaches the production bundle.
import { ChevronLeft, ChevronRight, Play, RotateCcw, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { fixtureStore, useFixtureVersion } from "@/lib/fixtures";
import { setQuery } from "@/lib/route";
import { SCENARIO_TITLES, SCENARIOS, type ScenarioName } from "@/lib/types";

declare global {
  interface Window { __cmb?: { setStep: (s: ScenarioName, n: number) => void; loadAll: () => void; reset: () => void } }
}

export default function ScenarioPlayer({ scenario }: { scenario?: ScenarioName | "none" | null }) {
  useFixtureVersion();
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);
  const current: ScenarioName = scenario && scenario !== "none" ? scenario : "acme_fraud";
  const steps = fixtureStore.stepsOf(current);
  const step = fixtureStore.stepOf(current);
  const loaded = fixtureStore.isLoaded(current);

  const go = (s: ScenarioName, n: number) => { fixtureStore.setStep(s, n); setQuery({ scenario: s, step: n }); };

  useEffect(() => {
    window.__cmb = { setStep: go, loadAll: () => fixtureStore.loadAll(), reset: () => { fixtureStore.reset(); setQuery({ scenario: "none", step: null }); } };
    return () => { delete window.__cmb; };
  }, []);

  useEffect(() => {
    if (!playing) { if (timer.current) window.clearInterval(timer.current); timer.current = null; return; }
    let s = SCENARIOS.indexOf(current);
    let n = loaded ? step : 0;
    timer.current = window.setInterval(() => {
      const sc = SCENARIOS[s];
      const total = fixtureStore.stepsOf(sc).length;
      if (n < total) { n += 1; go(sc, n); return; }
      s += 1; n = 0;
      if (s >= SCENARIOS.length) { setPlaying(false); return; }
    }, 1500);
    return () => { if (timer.current) window.clearInterval(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  return (
    <div className="fixed bottom-14 right-4 z-40 w-80 rounded-lg border border-border bg-popover p-3 text-sm shadow-lg" role="region" aria-label="Scenario player (development only)">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium">Scenario player</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">dev only</span>
      </div>
      <select className="w-full rounded-md border border-input bg-background px-2 py-1.5" value={current} aria-label="Scenario"
              onChange={(e) => go(e.target.value as ScenarioName, 1)}>
        {SCENARIOS.map((s) => <option key={s} value={s}>{SCENARIO_TITLES[s]}</option>)}
      </select>
      <div className="mt-2 flex items-center gap-1">
        <Button size="sm" variant="outline" onClick={() => go(current, Math.max(1, step - 1))} disabled={!loaded || step <= 1} aria-label="Previous step"><ChevronLeft className="size-4" /></Button>
        <span className="tabular flex-1 text-center text-muted-foreground">
          {loaded ? <>step {step}/{steps.length}: <span className="text-foreground">{steps[step - 1]?.step}</span></> : "not loaded"}
        </span>
        <Button size="sm" variant="outline" onClick={() => go(current, Math.min(steps.length, (loaded ? step : 0) + 1))} disabled={loaded && step >= steps.length} aria-label="Next step"><ChevronRight className="size-4" /></Button>
      </div>
      <div className="mt-2 flex gap-1">
        <Button size="sm" variant={playing ? "secondary" : "default"} className="flex-1" onClick={() => setPlaying((p) => !p)}>
          {playing ? <><Square className="size-4" aria-hidden /> Stop</> : <><Play className="size-4" aria-hidden /> Play all</>}
        </Button>
        <Button size="sm" variant="outline" onClick={() => { setPlaying(false); fixtureStore.reset(); setQuery({ scenario: "none", step: null }); }} aria-label="Reset"><RotateCcw className="size-4" /></Button>
      </div>
    </div>
  );
}

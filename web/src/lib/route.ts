// Minimal routing: two paths and a handful of query parameters (contracts/fixtures-and-routes.md).
import { useCallback, useEffect, useState } from "react";

import type { ScenarioName } from "@/lib/types";
import { SCENARIOS } from "@/lib/types";

export const isDev = import.meta.env.DEV;

export type Tab = "payments" | "vendors" | "audit" | "demo" | null;
export type ThemeName = "light" | "dark" | "system";

export interface Route {
  path: "/" | "/gallery";
  scenario: ScenarioName | "none" | null;
  step: number | null;
  theme: ThemeName | null;
  tab: Tab;
  trace: boolean;
  /** `?player=0` hides the development scenario player (used by the snapshot script). */
  player: boolean;
}

function parse(): Route {
  const url = new URL(window.location.href);
  const q = url.searchParams;
  const sc = q.get("scenario");
  const scenario = sc === "none" ? "none" : (SCENARIOS as string[]).includes(sc ?? "") ? (sc as ScenarioName) : null;
  const stepRaw = Number(q.get("step"));
  const th = q.get("theme");
  const tab = q.get("tab");
  return {
    path: url.pathname.replace(/\/+$/, "") === "/gallery" ? "/gallery" : "/",
    scenario,
    step: Number.isFinite(stepRaw) && stepRaw > 0 ? Math.floor(stepRaw) : null,
    theme: th === "light" || th === "dark" || th === "system" ? th : null,
    tab: tab === "payments" || tab === "vendors" || tab === "audit" || tab === "demo" ? tab : null,
    trace: q.get("trace") === "1",
    player: q.get("player") !== "0",
  };
}

const listeners = new Set<() => void>();
function notify() { listeners.forEach((l) => l()); }

export function setQuery(partial: Partial<Record<"scenario" | "step" | "theme" | "tab" | "trace" | "player", string | number | null>>, replace = true) {
  const url = new URL(window.location.href);
  for (const [k, v] of Object.entries(partial)) {
    if (v === null || v === undefined || v === "") url.searchParams.delete(k);
    else url.searchParams.set(k, String(v));
  }
  if (replace) history.replaceState(null, "", url);
  else history.pushState(null, "", url);
  notify();
}

export function navigate(path: "/" | "/gallery") {
  const url = new URL(window.location.href);
  url.pathname = path;
  history.pushState(null, "", url);
  notify();
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parse);
  const refresh = useCallback(() => setRoute(parse()), []);
  useEffect(() => {
    listeners.add(refresh);
    window.addEventListener("popstate", refresh);
    return () => { listeners.delete(refresh); window.removeEventListener("popstate", refresh); };
  }, [refresh]);
  return route;
}

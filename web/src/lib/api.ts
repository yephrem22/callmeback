// API client with two modes (PLAN.md §14.5): VITE_API_MODE=fixtures | live.
// Live mode polls per PLAN.md §14.9 (spec 007); the hooks below are the only data entry points.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { describeError } from "@/lib/errors";
import { fixtureStore, useFixtureVersion } from "@/lib/fixtures";
import type {
  AuditView, ChangeCase, Health, InvoiceDetail, InvoiceListRow, PaymentsView, ScenarioName, Stats, VendorView,
} from "@/lib/types";
import { SAMPLE_FOR_SCENARIO } from "@/lib/types";

export const API_MODE: "fixtures" | "live" = (import.meta.env.VITE_API_MODE as string) === "live" ? "live" : "fixtures";
export const isFixtures = API_MODE === "fixtures";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = ((await res.json()) as { detail?: string }).detail ?? detail; } catch { /* keep statusText */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

// ---- reads -------------------------------------------------------------------

export const getInvoices = (): Promise<InvoiceListRow[]> =>
  isFixtures ? Promise.resolve(fixtureStore.listRows()) : http("/api/invoices");

export const getInvoice = (id: string): Promise<InvoiceDetail> =>
  isFixtures
    ? (fixtureStore.detail(id) ? Promise.resolve(fixtureStore.detail(id)!) : Promise.reject(new Error("404: unknown invoice")))
    : http(`/api/invoices/${id}`);

export const getHealth = (): Promise<Health> => (isFixtures ? Promise.resolve(fixtureStore.health()) : http("/api/health"));
export const getStats = (): Promise<Stats> => (isFixtures ? Promise.resolve(fixtureStore.stats()) : http("/api/stats"));
export const getPayments = (): Promise<PaymentsView> => (isFixtures ? Promise.resolve(fixtureStore.payments()) : http("/api/payments"));
export const getVendors = (): Promise<VendorView[]> => (isFixtures ? Promise.resolve(fixtureStore.vendors()) : http("/api/vendors"));
export const getAudit = (subjectId?: string): Promise<AuditView> =>
  isFixtures ? Promise.resolve(fixtureStore.audit()) : http(`/api/audit${subjectId ? `?subject_id=${subjectId}` : ""}`);
// No change-case fixtures exist; fixtures mode shows the empty DevRev tab.
export const getChangeCases = (): Promise<ChangeCase[]> => (isFixtures ? Promise.resolve([]) : http("/api/change-cases"));
export const getChangeCase = (id: string): Promise<ChangeCase> =>
  isFixtures ? Promise.reject(new Error("404: unknown change case")) : http(`/api/change-cases/${id}`);

// ---- writes (fixtures mode advances the matching scenario or no-ops) ------------

function scenarioOf(id: string): ScenarioName | null { return fixtureStore.scenarioForInvoice(id); }

export const postFromSample = (name: string): Promise<{ id: string }> => {
  if (isFixtures) {
    const s = (Object.keys(SAMPLE_FOR_SCENARIO) as ScenarioName[]).find((k) => SAMPLE_FOR_SCENARIO[k] === name) ?? null;
    if (!s) return Promise.reject(new Error("unknown sample"));
    fixtureStore.load(s, 1);
    return Promise.resolve({ id: fixtureStore.invoiceIdFor(s) });
  }
  return http("/api/invoices/from-sample", { method: "POST", body: JSON.stringify({ name }) });
};

export const postReview = (id: string, decision: "approve" | "reject", note = ""): Promise<unknown> => {
  if (isFixtures) { const s = scenarioOf(id); if (s) fixtureStore.advance(s); return Promise.resolve({}); }
  return http(`/api/invoices/${id}/review`, { method: "POST", body: JSON.stringify({ decision, note }) });
};

export const postRetryCallback = (id: string): Promise<unknown> =>
  isFixtures ? Promise.resolve({}) : http(`/api/invoices/${id}/retry-callback`, { method: "POST" });

export const postRedteam = (id: string): Promise<{ blocked: boolean; layer: string; reason: string; run_id: string }> =>
  isFixtures
    ? Promise.resolve({ blocked: true, layer: "plugin", reason: "BLOCKED by payment policy: invoice is HELD (vendor denied the change)", run_id: "run_fixture" })
    : http(`/api/invoices/${id}/redteam`, { method: "POST" });

export const postSimulate = (subjectId: string, answer: "yes" | "no", last4: string | null): Promise<unknown> => {
  if (isFixtures) { const s = scenarioOf(subjectId); if (s) fixtureStore.advance(s); return Promise.resolve({}); }
  return http("/api/demo/simulate-answer", { method: "POST", body: JSON.stringify({ subject_id: subjectId, answer, last4 }) });
};

export const postReset = (): Promise<unknown> => {
  if (isFixtures) { fixtureStore.reset(); return Promise.resolve({}); }
  return http("/api/demo/reset", { method: "POST", body: JSON.stringify({}) });
};

export const postAiMode = (mode: "live" | "off"): Promise<unknown> =>
  isFixtures ? Promise.resolve({}) : http("/api/demo/ai-mode", { method: "POST", body: JSON.stringify({ mode }) });

// ---- hooks ---------------------------------------------------------------------
// In fixtures mode the store version is part of the key so the UI re-renders when a step changes.
// In live mode every query polls (PLAN.md §14.9); fixtures mode never polls and never calls /api.

const TERMINAL = new Set(["RELEASED", "HELD", "FAILED"]);
const poll = (ms: number): number | false => (isFixtures ? false : ms);
const POLL = { list: 2000, caseLive: 1000, caseDone: 5000, health: 15000, tab: 2000 } as const;

/** True for a 404 from the API: the record no longer exists (e.g. cleared by a demo reset). */
export const isGone = (e: unknown): boolean => e instanceof Error && /^404\b/.test(e.message);

function useVersionKey(): number {
  // Always subscribe (hooks must be unconditional); in live mode the store never changes, so the key stays 0.
  const v = useFixtureVersion();
  return isFixtures ? v : 0;
}

export function useInvoices() {
  const v = useVersionKey();
  return useQuery({ queryKey: ["invoices", v], queryFn: getInvoices, refetchInterval: poll(POLL.list) });
}
export function useInvoice(id: string | null) {
  const v = useVersionKey();
  return useQuery({
    queryKey: ["invoice", id, v], queryFn: () => getInvoice(id!), enabled: !!id,
    retry: (n, e) => !isGone(e) && n < 1,
    // every 1 s until the case is terminal, then every 5 s; a vanished invoice (404) stops polling
    refetchInterval: (q) =>
      isGone(q.state.error) ? false : poll(TERMINAL.has(q.state.data?.status ?? "") ? POLL.caseDone : POLL.caseLive),
  });
}
export function useHealth() {
  const v = useVersionKey();
  return useQuery({ queryKey: ["health", v], queryFn: getHealth, refetchInterval: poll(POLL.health) });
}
// Tab data polls only while its tab is mounted (TanStack stops polling unobserved queries).
export function useStats() { const v = useVersionKey(); return useQuery({ queryKey: ["stats", v], queryFn: getStats, refetchInterval: poll(POLL.tab) }); }
export function usePayments() { const v = useVersionKey(); return useQuery({ queryKey: ["payments", v], queryFn: getPayments, refetchInterval: poll(POLL.tab) }); }
export function useVendors() { const v = useVersionKey(); return useQuery({ queryKey: ["vendors", v], queryFn: getVendors, refetchInterval: poll(POLL.tab) }); }
export function useAudit(subjectId?: string) {
  const v = useVersionKey();
  return useQuery({ queryKey: ["audit", subjectId, v], queryFn: () => getAudit(subjectId), refetchInterval: poll(POLL.tab) });
}
export function useChangeCases() {
  return useQuery({ queryKey: ["change-cases"], queryFn: getChangeCases, refetchInterval: poll(POLL.tab) });
}
export function useChangeCase(id: string | null) {
  return useQuery({ queryKey: ["change-case", id], queryFn: () => getChangeCase(id!), enabled: !!id && !isFixtures,
                    refetchInterval: poll(POLL.tab) });
}

export function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}

/** A user action. Errors say what happened and what to do next (PLAN.md §14.6); either way the
 *  views refresh, so a stale screen corrects itself on the next poll. */
export function useAction<TArgs extends unknown[], TResult>(fn: (...args: TArgs) => Promise<TResult>) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (args: TArgs) => fn(...args),
    onSuccess: () => { void invalidate(); },
    onError: (e) => {
      const { title, description } = describeError(e);
      toast.error(title, { description });
      void invalidate();
    },
  });
}

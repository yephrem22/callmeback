// Fixture store: serves PLAN.md §7.6 shapes from web/src/fixtures/ (spec 003's exporter output).
// The queue shows one row per scenario at its *current* step; the player and ?scenario&step move steps.
import { useSyncExternalStore } from "react";

import indexJson from "@/fixtures/index.json";
import listJson from "@/fixtures/invoices_list.json";
import healthJson from "@/fixtures/health.json";
import statsJson from "@/fixtures/stats.json";
import paymentsJson from "@/fixtures/payments.json";
import vendorsJson from "@/fixtures/vendors.json";
import auditJson from "@/fixtures/audit.json";
import type {
  AuditView, Health, InvoiceDetail, InvoiceListRow, PaymentsView, ScenarioIndex, ScenarioName, Stats, VendorView,
} from "@/lib/types";
import { SCENARIOS } from "@/lib/types";

const INDEX = indexJson as ScenarioIndex;
const STEP_FILES = import.meta.glob("../fixtures/*/*.json", { eager: true, import: "default" }) as Record<string, InvoiceDetail>;

function stepDetail(scenario: ScenarioName, step: number): InvoiceDetail {
  const s = INDEX[scenario][Math.min(Math.max(step, 1), INDEX[scenario].length) - 1];
  const key = `../fixtures/${s.file}`;
  const d = STEP_FILES[key];
  if (!d) throw new Error(`fixture missing: ${s.file}`);
  return d;
}

type Listener = () => void;

class FixtureStore {
  currentStep: Record<ScenarioName, number> = {
    acme_normal: 1, acme_fraud: 1, heartland_bank_change: 1, prairie_review: 1, unknown_vendor: 1,
  };
  // Scenarios the user has "loaded" into the queue, in load order (newest last). Empty = empty queue.
  loaded: ScenarioName[] = [];
  private listeners = new Set<Listener>();
  private version = 0;

  subscribe = (fn: Listener) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  getVersion = () => this.version;
  private emit() { this.version += 1; this.listeners.forEach((l) => l()); }

  index(): ScenarioIndex { return INDEX; }
  stepsOf(s: ScenarioName) { return INDEX[s]; }
  stepOf(s: ScenarioName) { return this.currentStep[s]; }
  isLoaded(s: ScenarioName) { return this.loaded.includes(s); }

  load(s: ScenarioName, step = 1) {
    if (!this.loaded.includes(s)) this.loaded = [...this.loaded, s];
    this.currentStep = { ...this.currentStep, [s]: Math.min(Math.max(step, 1), INDEX[s].length) };
    this.emit();
  }
  setStep(s: ScenarioName, step: number) { this.load(s, step); }
  advance(s: ScenarioName) { this.load(s, this.currentStep[s] + 1); }
  back(s: ScenarioName) { this.load(s, this.currentStep[s] - 1); }
  loadAll() { SCENARIOS.forEach((s) => { if (!this.loaded.includes(s)) this.loaded = [...this.loaded, s]; }); this.emit(); }
  reset() { this.loaded = []; this.currentStep = { acme_normal: 1, acme_fraud: 1, heartland_bank_change: 1, prairie_review: 1, unknown_vendor: 1 }; this.emit(); }

  scenarioForInvoice(id: string): ScenarioName | null {
    for (const s of SCENARIOS) if (INDEX[s].some((st) => st.invoice_id === id)) return s;
    return null;
  }
  invoiceIdFor(s: ScenarioName) { return INDEX[s][0].invoice_id; }

  detail(id: string): InvoiceDetail | null {
    const s = this.scenarioForInvoice(id);
    return s ? stepDetail(s, this.currentStep[s]) : null;
  }
  detailFor(s: ScenarioName): InvoiceDetail { return stepDetail(s, this.currentStep[s]); }
  /** A specific step regardless of player state (used by the gallery). */
  at(s: ScenarioName, step: number): InvoiceDetail { return stepDetail(s, step); }

  listRows(): InvoiceListRow[] {
    const base = listJson as InvoiceListRow[];
    const rows = [...this.loaded].reverse().map((s) => {
      const d = stepDetail(s, this.currentStep[s]);
      const fromList = base.find((r) => r.id === d.id);
      return {
        id: d.id, created_at: d.created_at, vendor_name: d.vendor?.name ?? fromList?.vendor_name ?? d.email.from_name,
        amount_display: d.amount_cents != null ? `$${(d.amount_cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : null,
        tier: d.risk?.tier ?? null, points: d.risk?.points ?? null, status: d.status, hold_reason: d.hold_reason, source: d.source,
      } satisfies InvoiceListRow;
    });
    return rows;
  }

  health(): Health { return healthJson as Health; }
  stats(): Stats { return statsJson as Stats; }
  payments(): PaymentsView { return paymentsJson as PaymentsView; }
  vendors(): VendorView[] { return vendorsJson as VendorView[]; }
  audit(): AuditView { return auditJson as AuditView; }
}

export const fixtureStore = new FixtureStore();

export function useFixtureVersion() {
  return useSyncExternalStore(fixtureStore.subscribe, fixtureStore.getVersion, fixtureStore.getVersion);
}

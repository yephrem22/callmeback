// PLAN.md §7.6 response shapes, exactly as spec 003's app/repo.py emits them.
// Frozen: do not add fields here that the API does not carry (constitution I).

export type Status =
  | "RECEIVED" | "EXTRACTED" | "SCORED" | "AUTO_APPROVED" | "NEEDS_REVIEW" | "REVIEW_APPROVED"
  | "CALL_PENDING" | "CALLING" | "VERIFYING" | "CONFIRMED" | "RELEASED" | "HELD" | "FAILED";

export type HoldReason =
  | "DENIED_BY_VENDOR" | "UNCLEAR_ANSWER" | "NO_ANSWER" | "LAST4_MISMATCH" | "VERIFIER_DISAGREED"
  | "REVIEW_REJECTED" | "UNKNOWN_VENDOR" | "CALL_FAILED" | "AGENT_HOLD";

export type Tier = "GREEN" | "YELLOW" | "RED";
export type Action = "AUTO_RELEASE" | "REVIEW" | "CALLBACK" | "HOLD_MANUAL";
export type SenderStatus = "KNOWN" | "LOOKALIKE" | "UNRECOGNIZED" | "NO_VENDOR";
export type FieldSource = "regex" | "llm" | "both" | "header" | "none";

export interface FieldValue { value: string | null; source: FieldSource; mismatch: boolean }

export interface Flag { code: string; points: number; title: string; detail: string; evidence: string[] }

export interface HistoryRow { invoice_number: string; amount_cents: number; paid_on: string }

export interface VendorSummary {
  id: string; name: string; domains: string[]; phone_masked: string | null; bank_masked: string;
  history: HistoryRow[]; median_cents: number | null;
}

export interface LookalikeDiff { index: number; sender: string; known: string }

export interface Risk {
  points: number; tier: Tier; action: Action; sender_status: SenderStatus; amount_ratio: number | null;
  lookalike: { sender_domain: string | null; known_domain: string | null; diff: LookalikeDiff[] } | null;
  flags: Flag[]; bank_changed: boolean; policy_version: string;
}

export interface BankLine { bank_name: string | null; routing: string | null; account_masked: string | null }

export interface Destination { on_file: BankLine | null; requested: BankLine | null; changed: boolean }

export interface AnalystReport {
  headline: string; explanation: string; cited_flags: string[]; additional_concerns: string[]; recommended_next_step: string;
}

export interface VerificationEvent { ts: string; label: string; detail: string }

export interface FirstAnswer {
  channel: "dtmf" | "speech" | null; digits: string | null; speech: string | null; confidence: number | null;
  det_label: "YES" | "NO" | "UNCLEAR" | null; llm_label: "CONFIRMED" | "DENIED" | "UNCLEAR" | null;
}

export type FinalLabel = "CONFIRMED" | "DENIED" | "UNCLEAR" | "NO_ANSWER" | "LAST4_MISMATCH" | "VERIFIER_DISAGREED" | "SUPERSEDED";

export interface Verification {
  id: string; source: "twilio" | "simulated"; step: string; phone_masked: string | null; events: VerificationEvent[];
  first_answer: FirstAnswer | null; last4_ok: number | null; final_label: FinalLabel | null; attempts: number;
}

export interface Payment {
  id: string; invoice_id: string; amount_cents: number; bank_name: string | null; routing: string;
  account_masked: string | null; method: string; effective_date: string; released_at: string; released_by: string;
}

export interface TraceRow {
  ts: string; agent: string; run_id: string; kind: string; name: string | null; summary: string | null; duration_ms: number | null;
}

export interface AuditRow { seq: number; ts: string; actor: string; event: string; summary: string; hash_short: string }

export interface Actions { can_review: boolean; can_retry_call: boolean; can_simulate: boolean; can_redteam: boolean }

export interface InvoiceDetail {
  id: string; status: Status; hold_reason: HoldReason | null; source: "sample" | "upload"; created_at: string;
  invoice_number: string | null; amount_cents: number | null; decided_at: string | null;
  email: { from_name: string | null; from_email: string | null; reply_to: string | null; subject: string | null; received_at: string | null; body_text: string | null };
  extracted: { fields: Record<"vendor_name" | "invoice_number" | "amount" | "due_date" | "bank_name" | "routing_number" | "account_number", FieldValue>; phone_numbers_in_email: string[]; llm_status: "pending" | "ok" | "fallback" | "error" };
  vendor: VendorSummary | null;
  risk: Risk | null;
  destination: Destination;
  analyst: { status: "pending" | "done" | "fallback" | "error"; report: AnalystReport | null };
  verification: Verification | null;
  payment: Payment | null;
  memo: { text: string; by: "agent" | "fallback" } | null;
  trace: TraceRow[];
  audit: AuditRow[];
  actions: Actions;
  ai_fallback: boolean;
}

export interface InvoiceListRow {
  id: string; created_at: string; vendor_name: string | null; amount_display: string | null; tier: Tier | null;
  points: number | null; status: Status; hold_reason: HoldReason | null; source: "sample" | "upload";
}

export interface Health {
  db: boolean; model: { ok: boolean; latency_ms: number | null; checked_at: string | null };
  twilio: { configured: boolean }; storage: { ok: boolean }; demo_mode: boolean; ai_mode: "live" | "off"; deploy_label: string;
}

export interface Stats {
  released_cents: number; held_cents: number; invoices: number; calls_placed: number; median_decision_seconds: number | null;
}

export interface HeldSummary { id: string; vendor_name: string | null; amount_cents: number | null; hold_reason: HoldReason | null; created_at: string }

export interface PaymentsView { payments: Payment[]; held: HeldSummary[] }

export interface BankHistoryRow {
  old_bank_name: string | null; old_routing: string | null; old_account_masked: string | null;
  new_bank_name: string | null; new_routing: string | null; new_account_masked: string | null;
  invoice_id: string; verification_id: string; changed_at: string;
}

export interface VendorView extends VendorSummary {
  routing: string; bank_name: string | null; account_masked: string | null; bank_history: BankHistoryRow[];
}

export interface AuditView {
  entries: (AuditRow & { subject_id: string | null })[]; chain_ok: boolean; broken_at: number | null;
}

export type ScenarioName = "acme_normal" | "acme_fraud" | "heartland_bank_change" | "prairie_review" | "unknown_vendor";

export interface ScenarioStep { step: string; file: string; status: Status; hold_reason: HoldReason | null; invoice_id: string }

export type ScenarioIndex = Record<ScenarioName, ScenarioStep[]>;

export const SCENARIOS: ScenarioName[] = ["acme_normal", "acme_fraud", "heartland_bank_change", "prairie_review", "unknown_vendor"];

export const SCENARIO_TITLES: Record<ScenarioName, string> = {
  acme_normal: "Acme: normal invoice",
  acme_fraud: "Acme: urgent bank change",
  heartland_bank_change: "Heartland: legitimate bank change",
  prairie_review: "Prairie Cloud: higher than usual",
  unknown_vendor: "Unknown vendor",
};

export const SAMPLE_FOR_SCENARIO: Record<ScenarioName, string> = {
  acme_normal: "01_acme_normal",
  acme_fraud: "02_acme_fraud",
  heartland_bank_change: "03_heartland_bank_change",
  prairie_review: "04_prairie_review",
  unknown_vendor: "05_unknown_vendor",
};

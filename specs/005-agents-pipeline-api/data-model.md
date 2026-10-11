# Data Model: AI Agents, Pipeline and API (spec 005)

No new tables. Everything here uses the frozen PLAN.md §7.2 schema (spec 003, `app/schema.sql`) and the §7.4 models (`app/models.py`). This page lists which columns this spec writes and the JSON shapes it stores in them.

## Columns this spec writes

| Table.column | Written by | Shape / values |
|---|---|---|
| `invoices.extraction` | pipeline (fast path then merge) | `ExtractionResult` (§7.4); `llm_status`: `pending` → `ok` / `fallback` / `error` |
| `invoices.risk` | pipeline via `policy.score` (spec 003) | `RiskResult`; on the fast path only an appended 0-point `EXTRACTION_MISMATCH` flag may be added later, points/tier/action never change |
| `invoices.analyst` | Analyst agent or fallback | `{"status": "pending"\|"done"\|"fallback"\|"error", "report": AnalystReport\|null}` |
| `invoices.memo` | Payments agent or fallback | `{"text": str, "by": "agent"\|"fallback"}` |
| `invoices.review` | `ledger.record_review` (spec 003) via the API | `{"decision", "note", "at"}` |
| `invoices.ai_fallback` | `run_agent` | `1` once any agent fell back for this invoice |
| `invoices.status`, `hold_reason` | only via `state.transition` | §7.3 |
| `verifications.*` | pipeline handlers (§12.5) via `app/verifications.py` | §7.2 columns; `llm_label`, `llm_rationale` from the Verifier |
| `change_cases.status` | pipeline handlers when `kind="change_case"` | `OPEN`→`CALLING`→`CONFIRMED`/`DENIED`/`UNCLEAR`/`NO_ANSWER` |
| `payments.*` | only `ledger.release` (spec 003) | one row per invoice; `released_by` `agent:payments` or `policy:auto` |
| `agent_traces.*` | Trace plugin, guard plugin, `run_agent` | see below |
| `audit_log.*` | everything, via `audit.append` | §13.3 actors and events |

## `agent_traces` rows (PLAN.md §7.2)

| Field | Values |
|---|---|
| `subject_id` | invoice id (or change case id for the Verifier on change cases) |
| `run_id` | `run_` + 10 hex, one per agent run |
| `agent` | `intake`, `analyst`, `verifier`, `payments`, `payments:redteam` |
| `kind` | `run_start`, `model_call`, `tool_call`, `guard_allow`, `guard_block`, `run_end`, `fallback`, `error` |
| `name` | tool name for `tool_call`/`guard_*`; provider for `model_call` (`akamai` or `bedrock`) |
| `summary` | ≤ 200 chars, passed through `masking.masked` |
| `duration_ms` | for `model_call`, `tool_call`, `run_end` |

## In-memory structures

- **AgentRun**: `{run_id, agent, subject_id, started_at, timeout_s, outcome: "result"|"fallback"|"late"}`; not persisted beyond trace rows.
- **AI mode**: process-wide `effective_ai_mode()` → `"live"|"off"` (R10).
- **Rate bucket**: process-wide token bucket of `LLM_RPM` per 60 s shared by every agent (RateLimitPlugin).
- **Health cache**: `{model_ok, latency_ms, checked_at}` refreshed at most every 60 s when there were no recent model calls.

## Validation rules (from PLAN.md, enforced in code)

- Intake digits: `routing_number`, `account_number`, `amount` digits must appear in the normalised body (spaces, dashes removed) or the value is rejected and re-asked (§11.4).
- Analyst: `cited_flags ⊆ {f.code for f in risk.flags}`; `headline` ≤ 12 words, `explanation` ≤ 90 words (truncated, not rejected, beyond that).
- Verifier: `label ∈ {CONFIRMED, DENIED, UNCLEAR}`; may only downgrade a deterministic YES (§12.5).
- Payments: exactly three tools bound to one invoice; a `hold_payment` on an eligible invoice ⇒ HELD(AGENT_HOLD).
- Red team: refused with 409 when `ledger.can_release(id)[0]` is true; never creates a payment row.

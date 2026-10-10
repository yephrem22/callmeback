# Core engine: module map and how to call it (spec 003 hand-off)

Everything here is deterministic and runs with `AI_MODE=off`, no phone and no credentials. PLAN.md sections are the source of truth; this page only says where things live.

## Modules

| Module | Purpose | PLAN.md |
|---|---|---|
| `core/checks.py` | `aba_valid`, `skeleton`, `is_lookalike`, `explain_lookalike`, `lookalike_diff`, `find_us_phones`. Pure; the MCP service imports it too. | §9.2, §10.1 |
| `core/phrases.py` | the three phrase lists, `normalize`, `find_phrases`, `scan(subject, body)` | §10.3 |
| `app/config.py` | `S` settings from env (§7.1 names); `reload()` for tests | §7.1 |
| `app/db.py` | `connect()` (fresh connection, WAL), `init_db()` (executes `app/schema.sql`, a byte copy of the frozen §7.2 DDL), `tx(conn)` = `BEGIN IMMEDIATE` | §6, §7.2 |
| `app/models.py` | the §7.4 Pydantic models, verbatim | §7.4 |
| `app/state.py` | `Status`, `HoldReason`, `ALLOWED`, `HOLD_REASONS_FROM`, `RETRYABLE`, `transition()` | §7.3 |
| `app/repo.py` | typed DB helpers, the §7.6 views (`invoice_detail`, `list_invoices`, `vendors_view`, `payments_view`, `stats_view`) | §7.6 |
| `app/intake/` | `eml.parse`, `regex_extract.extract`, `merge.merge` | §9 |
| `app/policy/engine.py` | `resolve_vendor`, `score`, `amount_ratio` | §10 |
| `app/engine.py` | `ingest_sample(name)`, `ingest_upload(raw)`: RECEIVED → EXTRACTED → SCORED → routed | §5, §9.4 (AI-off path) |
| `app/ledger.py` | `can_release`, `release`, `hold`, `record_review`, `retry_callback_allowed`, `apply_vendor_bank_change`, `PolicyViolation` | §13.1 |
| `app/audit.py` | `append`, `verify`, `list_entries`; `ACTORS`, `EVENTS` | §13.2, §13.3 |
| `app/verifications.py` | `create`, `add_event`, `record_answer`, `finalize` on `verifications` rows | §7.2, §12.5 |
| `app/masking.py`, `app/ids.py` | masking helpers; ids and UTC timestamps (deterministic mode for fixtures) | §6 |
| `app/seed.py` | vendors, history, `reset_demo_data` | §8.1, §8.2, §7.6 |
| `scripts/export_fixtures.py` | the five demo scenarios → `web/src/fixtures/` | §14.7 |
| `app/cli.py` | `seed`, `score`, `list`, `detail`, `audit-verify`, `reset` | dev only |

## How spec 005 should use it

- **Ingest**: call `engine.ingest_sample(name, conn)` or `engine.ingest_upload(raw, conn)`. It returns the invoice id after routing. For the fast path (§9.4) wrap it: the regex extraction, scoring and routing are already text-only; the Intake agent then only updates `extraction` (via `repo.update_invoice`) and may append the 0-point `EXTRACTION_MISMATCH` flag. Never re-score.
- **Release and hold**: the Payments agent's tools call `ledger.release(invoice_id, by="agent:payments")` and `ledger.hold(invoice_id, reason)`. `release` re-checks `can_release` inside its own transaction and raises `PolicyViolation` when blocked (and writes `release_blocked`). The guard plugin calls `ledger.can_release(invoice_id)` directly. There is exactly one eligibility function.
- **Review**: `ledger.record_review(invoice_id, "approve"|"reject", note)`; raises `IllegalTransition` outside NEEDS_REVIEW (map to 409).
- **Verification rows**: `verifications.create(conn, invoice_id, source="twilio"|"simulated", ...)` returns `(ver_id, token)`; store only the hash (it does). `verifications.finalize(conn, ver_id, label, last4_ok=...)` sets the label and audits `verification_final`; the caller then calls `state.transition` for the invoice.
- **API shapes**: `repo.invoice_detail(conn, id)` is the InvoiceDetail; `repo.list_invoices`, `repo.vendors_view`, `repo.payments_view`, `repo.stats_view` are the list, vendors, payments and stats bodies. `audit.list_entries(subject_id)` plus `audit.verify()` give `/api/audit`.
- **Agent fields**: write `analyst` as `{"status","report"}` and `memo` as `{"text","by"}` JSON via `repo.update_invoice`; set `ai_fallback=1` on any fallback. `agent_traces` rows are read by `repo.list_traces`.

## Rules that must hold

- One connection per unit of work; pass `conn` through so `transition`, `audit.append`, `release` join the open transaction. A status change and its audit row commit together or not at all.
- Every status change goes through `transition()`; it raises `IllegalTransition` for anything outside §7.3 and returns `False` for a repeat.
- Mask outside the DB: use `app.masking.masked` for anything that leaves (API, audit data, traces, prompts). Routing numbers are shown; accounts and phones are last-4 only.
- Audit actors and events must come from `audit.ACTORS` / `audit.EVENTS`; `ledger.audit_actor(by)` maps `policy:*` and `agent:*` strings onto them.

## Tests

`pytest -q` with no `.env`: `tests/conftest.py` forces `AI_MODE=off`, `DEMO_MODE=1` and a temp DB per test. `tests/helpers.py` has `make_verification` and `drive_to` for reaching any status legally. The §8.4 vectors live in `tests/test_policy_vectors.py`; the §13.1 matrix in `tests/test_ledger.py`.

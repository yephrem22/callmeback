# Implementation Plan: Core Engine (intake, policy, state machine, ledger, audit)

**Branch**: `worktree-core-engine` (spec directory `specs/003-core-engine`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-core-engine/spec.md`, and the Plan prompt from PLAN.md §23.3.

## Summary

Build the deterministic core of Call Me Back: parse an invoice `.eml`, extract fields with label-anchored regex (PLAN.md §9), resolve the vendor including lookalike domains and score disclosed red flags (§10), route to AUTO_RELEASE / REVIEW / CALLBACK / HOLD_MANUAL, enforce the §7.3 status machine atomically, and keep a ledger that releases only §13.1-eligible invoices to the vendor master's account, with vendor bank-change history and a hash-chained audit log (§13.2). The §7.1 to §7.4 contracts are adopted verbatim (see `data-model.md` and `contracts/`) and frozen after phase 1. Everything runs with AI off, no phone and no credentials; the five samples must reproduce §8.4 exactly. A fixtures exporter writes §7.6-shaped JSON for the UI session.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed locally; `python:3.12-slim` in Docker)

**Primary Dependencies**: FastAPI (app skeleton only; routes are spec 005), pydantic v2, python-dotenv, rapidfuzz, pytest. stdlib `sqlite3`, `email`, `hashlib`, `hmac`, `re`, `threading`. Pinned in `requirements.txt` (owner A).

**Storage**: SQLite in WAL mode, one connection per unit of work, explicit `BEGIN IMMEDIATE` transactions; schema is `contracts/schema.sql` (PLAN.md §7.2 verbatim). Path from `DB_PATH` (default `data/app.db`).

**Testing**: `pytest -q` with `AI_MODE=off`, a temp `DB_PATH` per test, no network. Vectors from PLAN.md §8.4, §10, §12.4 (not this spec), §17.1.

**Target Platform**: macOS laptops for development; Linux (Docker) on the Akamai VM. No OS-specific code.

**Project Type**: single Python package (`core/` pure functions shared with the MCP service, `app/` the engine), plus `samples/`, `scripts/`, `tests/`. Web frontend is a separate spec (004/007).

**Performance Goals**: scoring one sample in under 1 s (SC-001); the whole suite in well under a minute.

**Constraints**: deterministic (same input → same output, no model, no network in scoring); fail closed; masked outputs; integer cents; UTC ISO-8601 in DB; `transition()` and `release()` atomic; audit append serialised. Must coexist with files owned by other specs (PLAN.md §6): this spec does not create `Makefile`, `.env.example`, `app/api.py`, `app/pipeline.py`, `app/voice/`, `app/storage.py`, `app/agents/`.

**Scale/Scope**: five samples plus ad-hoc uploads; a few hundred invoices at most in a demo DB. ~15 source modules, ~9 test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. PLAN.md is the source of truth | §7.1 to §7.4 copied verbatim into `data-model.md` / `contracts/`; every module cites its PLAN.md section; no new contracts. Frozen after phase 1. | PASS |
| II. The AI explains; the code holds the keys | No model is called anywhere in this spec. `can_release()` is the single eligibility function the later plugin and ledger both call. | PASS |
| III. Fail closed | Illegal transitions raise; `release()` raises `PolicyViolation` and audits `release_blocked`; unknown vendor → HOLD_MANUAL; simulated verifications only count in DEMO_MODE. | PASS |
| IV. Call the number on file | Not exercised here (no calls), but `phone_on_file` is the only phone stored on vendors and the extraction discards digits not in the body (§9.3). | PASS |
| V. Never blocked by setup | Suite needs no `.env`; `AI_MODE=off` is the only mode this spec implements. | PASS |
| VI. Secrets stay in .env | No secrets touched; `contracts/env.md` lists names only. | PASS |
| VII. Evidence everywhere | Every step writes an audit event (§13.3 names); the chain is verifiable. | PASS |
| VIII. Test what is deterministic | Tests built from §8.4, §10, §17.1 vectors; `pytest -q` passes before each commit. | PASS |
| IX. Designed for its users | N/A (no UI in this spec); the fixtures exporter serves the UI session. | PASS |
| X. Small vertical slices | Four phases below, each stops and reports; P0 before P1. | PASS |
| XI. Fresh code | All files written after kickoff; rapidfuzz/pydantic/FastAPI are libraries. | PASS |

Post-design re-check (after Phase 1 artifacts): no violations; no entries needed in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-core-engine/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R10
├── data-model.md        # Phase 1: §7.2, §7.3, §7.4 verbatim + relationships
├── quickstart.md        # Phase 1: how to run and validate
├── contracts/
│   ├── env.md           # §7.1 verbatim
│   ├── schema.sql       # §7.2 DDL verbatim (executed by app/db.py)
│   ├── state-machine.md # §7.3 verbatim
│   ├── models.md        # §7.4 verbatim
│   ├── interfaces.md    # §7.5 verbatim (what ledger exposes; what 005/006 will call)
│   └── http-api.md      # §7.6 verbatim (InvoiceDetail shape for the fixtures exporter)
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root; owner A files from PLAN.md §6 only)

```text
core/
├── __init__.py
├── checks.py            # aba_valid, skeleton, is_lookalike, explain_lookalike, find_us_phones, phrase scanner
└── phrases.py           # URGENCY, AVOID_VERIFICATION, AI_DIRECTED lists (§10.3)

app/
├── __init__.py
├── config.py            # settings S from env (§7.1 names/defaults)
├── db.py                # connect(), init_db() from contracts/schema.sql, transaction helper
├── models.py            # §7.4 verbatim (Pydantic v2)
├── state.py             # Status, HoldReason, ALLOWED table, transition() (§7.3)
├── masking.py           # mask_account, mask_phone, masked(dict)
├── ids.py               # new_id("inv_") etc. (§6)
├── repo.py              # typed DB helpers: vendors, history, invoices, verifications, payments; invoice_detail()
├── seed.py              # vendors + invoice history (§8.1, §8.2); reset_demo_data()
├── audit.py             # append(), verify(), list_for()  (§13.2, §13.3)
├── ledger.py            # can_release, release, hold, apply_vendor_bank_change, record_review (§13.1)
├── cli.py               # dev entry: seed | score <sample> | audit-verify (this spec only)
├── intake/
│   ├── __init__.py
│   ├── eml.py           # parse(raw) → ParsedEmail (§9.1)
│   ├── regex_extract.py # PATTERNS verbatim, extract(body) (§9.2)
│   └── merge.py         # merge(regex, llm|None, body) → ExtractionResult (§9.3)
├── policy/
│   ├── __init__.py
│   └── engine.py        # resolve_vendor, score, route → RiskResult (§10)
└── engine.py            # ingest_sample / ingest_upload → RECEIVED→EXTRACTED→SCORED→routed (AI off path of §5/§9.4)

samples/
├── 01_acme_normal.eml … 05_unknown_vendor.eml   # §8.3 verbatim + MIME headers
└── manifest.json

scripts/
└── export_fixtures.py   # engine on each sample, simulated outcomes, writes web/src/fixtures/

tests/
├── conftest.py          # temp DB, AI_MODE=off, DEMO_MODE=1, seeded fixture
├── test_checks.py  test_phrases.py  test_regex_extract.py  test_policy_vectors.py
├── test_state.py   test_ledger.py   test_audit.py          test_invoice_detail_shape.py
└── helpers.py           # make_verification(...) test/fixture helper (R7)

requirements.txt
```

**Structure Decision**: single Python project laid out exactly as PLAN.md §6 prescribes for Builder A's files. `core/` stays dependency-light (stdlib + rapidfuzz) because the MCP service imports it. `app/engine.py` is the AI-off orchestration for this spec; spec 005's `pipeline.py` will wrap it with the fast path and agents rather than replace it.

## Phases (for /speckit-tasks; each phase stops and reports)

1. **Phase 1, skeleton and contracts (milestone A1, P0, "contracts frozen")**: `requirements.txt`, `core/` and `app/` packages, `config.py`, `db.py` executing `contracts/schema.sql`, `models.py`, `state.py` with full transition table and tests, `masking.py`, `ids.py`, `samples/` verbatim + manifest, `seed.py` with vendors and history, `conftest.py`. Gate: `pytest -q` green on `test_state.py` and a seed smoke test. Push and announce.
2. **Phase 2, intake and policy (P0)**: `core/checks.py`, `core/phrases.py`, `intake/`, `policy/engine.py`, `app/engine.py` ingest path through SCORED and routing, `audit.py` (needed by transitions), tests `test_checks`, `test_phrases`, `test_regex_extract`, `test_policy_vectors`, `test_audit`. Gate: §8.4 vectors exact.
3. **Phase 3, ledger and vendor change control (P0 release guarantee, P1 vendor update)**: `ledger.py` (`can_release`, `release`, `hold`, `record_review`, `apply_vendor_bank_change`), verification helpers in `repo.py`, `test_ledger.py`. Gate: §13.1 matrix and one-payment guarantee.
4. **Phase 4, fixtures export and detail serializer (P1)**: `repo.invoice_detail()`, `scripts/export_fixtures.py`, `test_invoice_detail_shape.py`, `cli.py`. Gate: fixtures for all five scenarios written and shape-checked; UI session notified (milestone A4).

## Complexity Tracking

No constitution violations to justify.

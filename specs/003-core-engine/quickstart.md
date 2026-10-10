# Quickstart: Core Engine (spec 003)

How to prove the engine works, end to end, with no AI, no phone and no credentials.

## Prerequisites

- Python 3.12 (`uv python install 3.12` if missing).
- From the repo root (or this worktree):

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

No `.env` is required. If one exists it is read, but every test forces `AI_MODE=off` and a temporary `DB_PATH`.

## 1. Unit tests (the §17.1 vectors)

```bash
AI_MODE=off pytest -q
```

Expected: all green, no network, under ~10 s. Key files and what they prove:

| Test file | Proves |
|---|---|
| `tests/test_checks.py` | ABA checksum, lookalike domains, phone finder vectors (PLAN.md §17.1) |
| `tests/test_phrases.py` | phrase hits per sample; samples 01 and 03 match nothing (§10.3) |
| `tests/test_regex_extract.py` | routing, account, amount, invoice number for all five samples (§9.2) |
| `tests/test_policy_vectors.py` | the §8.4 table exactly: flags, points, tier, action |
| `tests/test_state.py` | every §7.3 transition; illegal raises; repeat is a no-op; HELD needs a reason |
| `tests/test_ledger.py` | the §13.1 matrix; one payment per invoice; HELD never releases; simulated needs DEMO_MODE; bank change needs last4 |
| `tests/test_audit.py` | 5 appends verify; a tampered row names the broken seq |
| `tests/test_invoice_detail_shape.py` | the serializer emits the exact §7.6 InvoiceDetail keys |

## 2. Seed and score the samples by hand

```bash
python -m app.seed                     # creates data/app.db, seeds vendors + history (§8.1, §8.2)
python -m app.cli score 02_acme_fraud  # ingests the sample, prints flags/points/tier/action and status
```

Expected for `02_acme_fraud`: 160 points, RED, CALLBACK, status CALL_PENDING, flags LOOKALIKE_DOMAIN 40, BANK_CHANGED 50, REPLY_TO_MISMATCH 20, AMOUNT_3X 25, URGENCY 10, AVOID_VERIFICATION 15, AI_DIRECTED_TEXT 0, PHONE_IN_EMAIL 0.

(`app/cli.py` is a thin developer entry point for this spec only; the HTTP routes are spec 005.)

## 3. Export fixtures for the UI session

```bash
python scripts/export_fixtures.py          # writes web/src/fixtures/<scenario>/<step>.json + index.json
ls web/src/fixtures
```

Expected scenarios and final states (PLAN.md §8.4): `acme_normal` → RELEASED, `acme_fraud` → HELD/DENIED_BY_VENDOR, `heartland_bank_change` → RELEASED with the vendor on Gateway National Bank ••••4455, `prairie_review` → RELEASED after approve, `unknown_vendor` → HELD/UNKNOWN_VENDOR. Every JSON file has the top-level keys listed in `contracts/http-api.md`.

## 4. Audit chain check

```bash
python -m app.cli audit-verify
```

Expected: `chain_ok=True broken_at=None`. Edit one row's `data` with `sqlite3 data/app.db` and re-run: `chain_ok=False broken_at=<seq>`.

## 5. Phase 1 gate (milestone A1, "contracts frozen")

Phase 1 is done when: `pytest -q` passes on the skeleton tests, `python -m app.seed` creates the schema from `contracts/schema.sql` verbatim, `app/models.py` matches `contracts/models.md`, `app/state.py` matches `contracts/state-machine.md`, and the five `samples/*.eml` plus `manifest.json` exist. Push, then tell Builder B and the UI session that §7 is frozen.

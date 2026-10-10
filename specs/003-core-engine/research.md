# Research: Core Engine (spec 003)

PLAN.md resolves almost every technical question for this feature, so Phase 0 is short. Each item below records a decision, why, and what was rejected. Nothing here changes a PLAN.md contract.

## R1. Python runtime and dependency management

- **Decision**: Python 3.12 (uv-managed interpreter on laptops, `python:3.12-slim` in Docker per PLAN.md §16.2). Dependencies pinned in `requirements.txt` (owner A, PLAN.md §6). Local dev uses a `.venv` created with `uv venv --python 3.12` and `uv pip install -r requirements.txt`.
- **Rationale**: PLAN.md §6 fixes the version; uv is already installed on A's laptop and is what PLAN.md §0.3 lists.
- **Alternatives**: system Python 3.11/3.13 (rejected: mismatches the Docker image and the plan); Poetry/pyproject (rejected: spec 001's Makefile and the Dockerfile expect `requirements.txt`).

## R2. Test runner without spec 001's Makefile

- **Decision**: run `pytest -q` directly from the repo root with `AI_MODE=off` and no `.env`. A `tests/conftest.py` sets `DB_PATH` to a per-test temp file, `DEMO_MODE=1` by default, and `AI_MODE=off`, so the suite needs no credentials and no `.env` (constitution V, VIII).
- **Rationale**: spec 001 (Builder B) owns `Makefile` and `make test`; spec 003 must not block on it. When it lands, `make test` just calls `pytest -q`.
- **Alternatives**: a local Makefile stub (rejected: file ownership conflict with spec 001).

## R3. Config loading

- **Decision**: `app/config.py` reads environment variables (names exactly per PLAN.md §7.1) with the §7.1 defaults, using `python-dotenv` to load `.env` if present and `os.environ` to override. Exposes a module-level settings object `S` (PLAN.md §11.1 refers to `S.akamai_api_key` etc.). Only variables this spec needs are given behaviour (`DB_PATH`, `DEMO_MODE`, `AI_MODE`, `PAYER_NAME`, `DEMO_VENDOR_PHONE`); the rest are read and exposed for later specs.
- **Rationale**: single place for env, no new names, dotenv is already in spec 001's stack.
- **Alternatives**: pydantic-settings (rejected: one more dependency for no gain; hand-rolled is 40 lines).

## R4. SQLite connection discipline

- **Decision**: `app/db.py` exposes `connect()` returning a new `sqlite3.Connection` per unit of work with `row_factory = sqlite3.Row`, `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON`, and `isolation_level=None` (autocommit) so transactions are explicit `BEGIN IMMEDIATE ... COMMIT`. `init_db()` executes `contracts/schema.sql` verbatim (the DDL is `CREATE TABLE IF NOT EXISTS`, so it is idempotent). The DB path resolves relative to the repo root on laptops and `/srv` in containers (PLAN.md §7.1 comment).
- **Rationale**: PLAN.md §6 forbids sharing a connection across threads; explicit `BEGIN IMMEDIATE` is what §7.3 and §13.1 require for atomic transition and release.
- **Alternatives**: SQLAlchemy (rejected: stdlib `sqlite3` is what PLAN.md §6 specifies).

## R5. Lookalike distance function

- **Decision**: use `rapidfuzz.distance.DamerauLevenshtein.distance` for the final rule in PLAN.md §10.1 and `rapidfuzz.fuzz.token_set_ratio` for fuzzy vendor-name matching.
- **Rationale**: PLAN.md names rapidfuzz and `DamerauLevenshtein.distance`; rapidfuzz ships both, no second library needed.
- **Alternatives**: `python-Levenshtein`, hand-rolled DL (rejected).

## R6. Next business day

- **Decision**: `effective_date` = the next calendar day after the release date (America/Chicago) that is not Saturday or Sunday. Holidays are not modelled (spec Assumptions).
- **Rationale**: PLAN.md §13.1 says only "next business day"; weekends-only is the smallest reading and is what the spec assumed.
- **Alternatives**: a holiday calendar library (rejected: scope).

## R7. Verification rows before spec 006 exists

- **Decision**: spec 003 owns `repo.py` helpers to insert and read `verifications` rows (schema from §7.2) and a small test-only helper that creates a finalised verification (`source`, `final_label`, `last4_ok`). The fixtures exporter uses the same helper to simulate `DENIED`, `CONFIRMED`+`last4_ok`, etc. Spec 006's `simulate_answer` later replaces the helper for live use; the row shape is identical.
- **Rationale**: `ledger.can_release` must be testable now (US2 scenarios 4 and 5) and the fixtures exporter must drive the §8.4 final states without voice code.
- **Alternatives**: mocking the ledger's verification read (rejected: would not test the real SQL path).

## R8. Fixtures exporter and the InvoiceDetail shape

- **Decision**: `scripts/export_fixtures.py` builds InvoiceDetail dicts through one shared function `repo.invoice_detail(invoice_id) -> dict` that spec 005's `GET /api/invoices/{id}` will also call, so there is exactly one implementation of the §7.6 shape. Output: `web/src/fixtures/<scenario>/<step>.json` plus `index.json` listing scenarios and steps. Steps per scenario follow the demo story (PLAN.md §14.7): received → scored → (calling → answered) → final. `tests/test_fixtures_contract.py` (owned by spec 007 per §17.1) will validate them; spec 003 adds a lighter `tests/test_invoice_detail_shape.py` that checks the exact top-level keys and nested keys the UI depends on.
- **Rationale**: PLAN.md §7.6 says "the UI depends on these exact keys"; a single serializer prevents drift between fixtures and the live API.
- **Alternatives**: hand-written fixture JSON in the UI session (that is spec 004's interim path; this exporter replaces it with real engine output by milestone A4).

## R9. Audit chain concurrency

- **Decision**: `audit.append` holds a process-wide `threading.Lock` and runs `BEGIN IMMEDIATE`; `seq` is assigned explicitly as last+1 (PLAN.md §13.2). When called from inside an already-open transaction (e.g. `transition()` or `ledger.release()`), `append` accepts an optional open connection and does not open a second transaction, so the status change and its audit event commit together.
- **Rationale**: PLAN.md §7.3 and §13.1 require the UPDATE and the audit row in one transaction; the lock prevents two writers reading the same last row.
- **Alternatives**: a DB trigger computing hashes (rejected: SQLite has no sha256 built in).

## R10. Masking helper

- **Decision**: one `core`-free helper `app/masking.py` with `mask_account(s) -> "••••1234"`, `mask_phone(e164) -> "•••-•••-1234"`, and `masked(data: dict) -> dict` that recursively masks values under keys matching `account*`, `phone*`, `*_phone` and any 10+ digit string that is not a routing number. Routing numbers are shown in full (PLAN.md §7.6 note).
- **Rationale**: PLAN.md §6 masking rule applies to API, audit data, traces, logs and prompts; a single helper is the only way to keep it consistent.
- **Alternatives**: masking at each call site (rejected).

## Open items carried to tasks (not clarifications)

- Exact `title`/`detail` strings per flag come from PLAN.md §10.2 (title column) and §7.4 examples; details are composed per flag with the specific values.
- Sample `.eml` files must be byte-exact per §8.3 with the two extra MIME headers inserted after `Message-ID`; a test compares each parsed body against the §8.4 expectations rather than against a second copy of the text.

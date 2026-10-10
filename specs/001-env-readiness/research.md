# Research: Environment Readiness

Decisions resolving the Technical Context of [plan.md](plan.md). Everything here is derived from PLAN.md §0.4, §0.5, §7.1, §16, §17.1 and §23.1; nothing introduces a new contract.

## R1. Dependencies and pins

- **Decision**: use `httpx` (already pinned by A), `twilio==9.11.2`, `boto3==1.43.111`, `bcrypt==5.0.0`, `python-dotenv` (already pinned). Append the three new pins to the A-owned `requirements.txt` and tell Builder A.
- **Rationale**: the §23.1 plan prompt names these libraries; §6's stack already lists Twilio 9.x and boto3 as app dependencies, so they belong in the one app `requirements.txt` rather than a second file. Versions are what `uv pip install` resolved on 2026-10-10 in the project `.venv`; all three import cleanly.
- **Alternatives considered**: a separate `scripts/requirements-env.txt` (rejected: two dependency files for one image, and spec 006 needs `twilio` in the app anyway); calling Twilio's REST API with `httpx` only (rejected: `--call-test` and the signature helpers in spec 006 want the official client).

## R2. bcrypt hash compatible with Caddy

- **Decision**: `bcrypt.hashpw(password, bcrypt.gensalt(rounds=14, prefix=b"2a"))`, written as `DASH_PASS_HASH='$2a$14$…'` in single quotes.
- **Rationale**: §23.1 says "bcrypt with prefix 2a, written single-quoted"; §7.1 explains the quoting (Docker Compose and python-dotenv take single-quoted values literally, so `$` survives). Caddy's `basic_auth` accepts `$2a$` and `$2b$`; `caddy hash-password` itself emits `$2a$14$`, so matching it removes one variable when debugging §16.5 "Caddy exits on start". Verified in the venv: bcrypt 5.0.0 still honours `prefix=b"2a"`, and the hash verifies; one hash takes about 2 s at 14 rounds, acceptable for a one-off command.
- **Alternatives considered**: `$2b$` (works in Caddy but deviates from the prompt); `caddy hash-password` via Docker (rejected: needs Docker on the laptop).

## R3. Status precedence per row

- **Decision**: for each row compute, in order:
  1. **FAKE** if the row has a mode variable and it selects the fake value (`AI_MODE=off`, `VOICE_MODE=simulated`, `STORAGE_MODE=local`, `LLM_FALLBACK=none`, or `EB_DATASET_VERSION` starting with `public-`). The status is FAKE even if real credentials are present (spec US2 AC2, FR-010).
  2. **MISSING** if any required variable is empty or a placeholder (R4).
  3. **FAILED** if the probe raised, timed out, or returned a malformed or disqualifying result (trial account, balance under $10, number without voice, model not listed, non-200, non-401 on `/mcp`, short token, non-bcrypt hash).
  4. **READY** otherwise.
- **Probe sub-result**: rows that are FAKE but have real-looking credentials are still probed when the phase is `integrate` or `demo`, and the probe outcome is kept in a separate `probe` field (`ready|failed|skipped`) and shown in the evidence (for example "FAKE — probe ok, 310 ms; set AI_MODE=live"). This is what lets spec US1 AC3 hold: `integrate` passes with valid Akamai, URL and Twilio settings while `AI_MODE=off` and `VOICE_MODE=simulated`, and `demo` then fails naming the mode variables.
- **Rationale**: §0.4 says FAKE means "fake mode selected" and the integrate gate requires the credentials to be READY, not the mode to be live; only the demo gate adds the mode requirement. Separating "what the code will use" (status) from "does the credential work" (probe) is the only reading that satisfies both.
- **Alternatives considered**: showing READY whenever the credential works regardless of the mode (rejected: contradicts FR-010 and would hide that the app is still running in fake mode).

## R4. Placeholder detection

- **Decision**: a value is a placeholder when it is empty, contains the substring `replace` (covers `replace-me`, `replace-with-…`, the example hash), or equals one of the §7.1 example values that do not contain it: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`, `172-105-12-34.sslip.io`, `https://172-105-12-34.sslip.io`, `team@example.com`. Placeholders count as "not provided" (MISSING) for probing, except app secrets, where a placeholder is malformed and FAILED (spec edge case; §0.4 "fails only on malformed values, such as a short token or a placeholder hash").
- **Rationale**: explicit and testable; `.env.example` is fixed by §7.1 so the set is closed. Non-secret defaults that are correct as shipped (`AKAMAI_BASE_URL`, `MODEL_ID`, `OBJ_ENDPOINT`, `OBJ_REGION`, `OBJ_BUCKET`, `MCP_PORT`, `EB_DATA_DIR`, `APP_INTERNAL_URL`, `DB_PATH`, `AWS_REGION`, timeouts) are never treated as placeholders.
- **Alternatives considered**: comparing every value against `.env.example` (rejected: flags correct defaults as placeholders and couples the checker to the example file's presence).

## R5. Probe design and the 8 s deadline

- **Decision**: all probes run concurrently in a `ThreadPoolExecutor`; the caller waits on each future with `result(timeout=8)` and records FAILED "timed out after 8 s" on `TimeoutError`. Each library call also carries its own timeout so threads finish rather than linger: `httpx.Client(timeout=8)`, `TwilioHttpClient(timeout=8)`, `botocore.config.Config(connect_timeout=4, read_timeout=4, retries={"max_attempts": 0})`. Rows with MISSING inputs or FAKE status in the `build` phase do not probe at all, so an empty `.env` run makes no network calls.
- **Rationale**: §23.1 "every probe times out within 8 s"; SC-004 wants a fully-unreachable run to still print the whole matrix. Running probes concurrently keeps the worst case near 8 s total instead of 8 s per row.
- **Alternatives considered**: sequential probes (rejected: 60 s worst case); `asyncio` (rejected: boto3 and the Twilio client are synchronous).

## R6. The probes, exactly as §0.4 states them

| Row | Probe | READY when |
|---|---|---|
| Akamai inference | `GET {AKAMAI_BASE_URL}/models` with `Authorization: Bearer`; then `POST /chat/completions` with `max_tokens: 5`; measure latency | models list contains `MODEL_ID` and the completion returns 200 |
| Akamai Cloud API | `GET https://api.linode.com/v4/profile` with `Authorization: Bearer LINODE_TOKEN` | 200; evidence shows `username` |
| Public HTTPS URL | `GET {PUBLIC_BASE_URL}/healthz` with certificate verification on | 200 (the certificate is valid because `verify=True` would otherwise raise) |
| Object Storage | boto3 S3 client on `OBJ_ENDPOINT`/`OBJ_REGION`: `put_object`, `get_object`, `delete_object` on `healthcheck/<uuid>.txt` | all three succeed |
| Twilio | `client.api.accounts(sid).fetch()` → `type` and `status`; `client.balance.fetch()` → `balance`, `currency`; `client.incoming_phone_numbers.list(phone_number=FROM)` → `capabilities["voice"]` | status `active`, type not `Trial`, balance ≥ 10, number found with voice; **no call unless `--call-test`** |
| DevRev and Enterprise-Bench | `EB_DATA_DIR` has `crm_json_data/` and the other guide folders (`pm_json_data/`, `maple_kb/`, `transcripts/`, `internal_docs/`; §15.2); `MCP_TOKEN` ≥ 32 chars; when `PUBLIC_BASE_URL` is real, `POST {PUBLIC_BASE_URL}/mcp` with no auth | folders present, token long enough; the `/mcp` probe returning 401 is required only by `demo` (spec edge case) |
| AWS (optional) | `sts.get_caller_identity()`, then `bedrock-runtime.converse(maxTokens=5)` on `BEDROCK_MODEL_ID` | both succeed; FAKE whenever `LLM_FALLBACK=none`, never a failure in any phase |
| App secrets | local checks only | `INTERNAL_TOKEN` and `MCP_TOKEN` present with ≥ 32 chars; `DASH_PASS_HASH` matches `^\$2[aby]\$\d\d\$.{53}$` |

- `--call-test` places one call to `DEMO_VENDOR_PHONE` from `TWILIO_FROM_NUMBER` with inline TwiML (`<Say>Call Me Back readiness check.</Say>`) and prints the call SID; it never dials any other number (constitution IV).

## R7. Phase gates, exactly as §0.4 states them

- **build** (default): exit 1 only if the app-secrets row is FAILED (short token, placeholder or non-bcrypt hash). MISSING and FAKE never fail it.
- **integrate**: build rules, plus the Akamai inference, public URL and Twilio rows must have a READY probe (status READY, or FAKE with `probe=ready`, R3).
- **demo**: integrate rules, plus `AI_MODE=live`, `VOICE_MODE=twilio`, the `/mcp` unauthenticated probe returning 401, `EB_DATASET_VERSION` set and not `public-*`, and the Twilio balance ≥ $10 (already part of Twilio READY; repeated in the failure message so the operator sees the amount). Each unmet requirement is named in the output (spec US1 AC3).
- `LINODE_TOKEN`, AWS keys and Object Storage are never gate requirements (§0.4 "laptop only", "never required", and Object Storage is P1 and cut-able in §4).

## R8. Masking and output scrubbing

- **Decision**: `mask(value)` returns `••••` + the last four characters, or `••••` alone when the value has four or fewer characters. Before anything is printed (table, `--json`, errors), a scrubber replaces every occurrence of every known secret value of eight or more characters (`AKAMAI_API_KEY`, `LINODE_TOKEN`, `TWILIO_AUTH_TOKEN`, `OBJ_SECRET_KEY`, `OBJ_ACCESS_KEY`, `MCP_TOKEN`, `INTERNAL_TOKEN`, `DASH_PASS_HASH`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCESS_KEY_ID`) with its masked form. Exceptions from libraries are caught per probe and their messages scrubbed too.
- **Rationale**: FR-004 and SC-002 require zero leaks in any output including errors; library exceptions can echo request URLs or headers, so masking only our own evidence strings is not enough.
- **Alternatives considered**: masking only evidence fields (rejected: error paths leak).

## R9. Reading and writing `.env`

- **Decision**: `check_env.py` reads with `dotenv_values(path)` (honours the single-quote rule in §7.1) overlaid by `os.environ`, so it sees exactly what `app/config.py` sees. `gen_secrets.py` edits `.env` line by line: an existing `KEY=value` with a valid value is left untouched; a line whose value is a placeholder is replaced in place; a missing key is appended under a `# --- generated by make secrets` comment. Comments, order and unrelated lines are preserved; a missing file is created with mode `0600`. `--env-file` selects another path (tests use a temp file). Also writes `DASH_USER=demo` if absent, since the hash is useless without the user.
- **Rationale**: FR-012 "MUST NOT overwrite any variable that already holds a value" and SC-006 byte-identical second run; replacing placeholder lines in place keeps `.env` readable next to `.env.example`.
- **Alternatives considered**: `dotenv.set_key` (rejected: rewrites quoting and may reorder; harder to guarantee byte-identical re-runs).

## R10. Makefile targets

- **Decision**: `PY ?= .venv/bin/python` (falls back to `python3` when `.venv` is absent). Targets: `install` (uv venv + `uv pip install -r requirements.txt`), `secrets` (`$(PY) scripts/gen_secrets.py`), `check-env` (`$(PY) scripts/check_env.py --phase $(PHASE)`, `PHASE ?= build`; extra args via `ARGS`), `test` (`$(PY) -m pytest -q`, then `npm run typecheck && npm run lint && npm run build` inside `web/` when that directory exists; §17.1), `dev` (`$(PY) -m uvicorn app.main:app --reload --port 8000`; prints a note while `app/main.py` does not exist, since it arrives with spec 005), `fixtures` (`$(PY) scripts/export_fixtures.py`, spec 003), `deploy` (`ssh $(DEPLOY_SSH) 'cd /opt/callmeback && bash scripts/deploy.sh'`, with `DEPLOY_SSH ?= root@$(HOST from .env)`, spec 002's script).
- **Rationale**: §6 and §23.1 fix the target names; targets that run another spec's script are declared now so the shared entry point is stable, and fail with a clear message rather than a confusing one until that spec lands. `install` is an addition for the human runbook (not in the frozen list, but harmless).
- **Alternatives considered**: `include .env` in Make (rejected: Make mangles `$` in the bcrypt hash and would expose values in `make -n` output).

## R11. `.gitignore` merge

- **Decision**: keep A's entries (`.env`, `.env.local`, `.specify/feature.json`, `.claude/worktrees/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/*.db*`) and add `data/*` with `!data/.gitkeep`, `eb_data/`, `web/node_modules/`, `web/dist/`, `web/snapshots/`.
- **Rationale**: §23.1 lists `data/` but A committed `data/.gitkeep` so the directory exists on a fresh clone (needed by `DB_PATH=data/app.db`); the negation keeps both true. `.gitignore` is B-owned per §6, so no permission is needed, but the merge is noted for A.

## R12. Test strategy without the network

- **Decision**: `check_env.py` exposes `evaluate(env: dict, phase: str, probe_results: dict[str, ProbeResult] | None)` as the pure core; `main(argv)` returns the exit code instead of calling `sys.exit` directly so tests call it. Tests cover: `mask` (short, exact-4, long, unicode), placeholder detection, status precedence (FAKE beats present creds; MISSING beats probe; FAILED on each disqualifier), the three gates with faked probe results from the spec's acceptance scenarios, `--json` containing no secret substring, the empty `.env` build pass with exit 0, and that the Twilio call function is never invoked without `--call-test` (a sentinel probe records calls). `gen_secrets` tests: creates the file, fills only gaps, placeholder lines replaced in place, second run byte-identical, hash single-quoted and `$2a$`, token length ≥ 32, password printed exactly once to stdout and not written.
- **Rationale**: FR-018, SC-002, SC-003, SC-005, SC-006; constitution VIII.

# Tasks: Environment Readiness

**Input**: Design documents from `specs/001-env-readiness/` (plan.md, research.md, data-model.md, contracts/, quickstart.md) and spec.md.

**Prerequisites**: branch `001-env-readiness`, `.venv` built from `requirements.txt` (`uv venv .venv && uv pip install -p .venv/bin/python -r requirements.txt`). Builder A's suite (204 tests) is green on `main` at `488dca5`.

**Tests**: required (spec FR-018, PLAN.md §17.1 `test_check_env.py`, constitution VIII). They are written in the same phase as the code they cover and never touch the network.

**Organization**: the five phases of plan.md, in the order plan.md gives them (US1 → US3 → US2 → US4), because US3's generated secrets are what make US2's "copy the example and everything passes" true. Each phase ends with `make test` green and one commit; stop and report after each (constitution X).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 readiness command, US2 zero credentials, US3 secrets, US4 runbook and guardrails

## Path Conventions

Repo root files per PLAN.md §6 (Builder B column): `Makefile`, `.env.example`, `.gitignore`, `.worktreeinclude`, `.claude/settings.json`, `scripts/check_env.py`, `scripts/gen_secrets.py`, `docs/SETUP.md`, `tests/test_check_env.py`, `tests/test_gen_secrets.py`. The one A-owned file touched is `requirements.txt` (append only, agreed).

---

## Phase 1: Foundation and guardrails (plan.md phase 1; P0)

**Purpose**: the files every later phase and every other session relies on: dependencies, the example env, the ignore and worktree rules, the agent deny rule, and the Makefile entry point.

- [x] T001 Append `twilio==9.11.2`, `boto3==1.43.111`, `bcrypt==5.0.0` as the last three lines of `requirements.txt` (research R1); run `uv pip install -p .venv/bin/python -r requirements.txt`. Tell Builder A in the phase report.
- [x] T002 [P] Create `.env.example` with exactly the content of `specs/001-env-readiness/contracts/env-example.md`'s code block (PLAN.md §7.1 verbatim, 45 variables, fake-mode defaults). Verify with `diff <(sed -n '457,524p' PLAN.md) .env.example` → no output.
- [x] T003 [P] Edit `.gitignore`: keep A's entries; replace `data/*.db*` with `data/*` followed by `!data/.gitkeep`; add `eb_data/`, `web/node_modules/`, `web/dist/`, `web/snapshots/` (research R11; `.env`, `.env.local`, `.claude/worktrees/` are already present). Verify `git check-ignore -q .env data/app.db eb_data/x web/dist/x` succeeds and `git check-ignore -q data/.gitkeep` fails.
- [x] T004 [P] Create `.worktreeinclude` containing the single line `.env` (PLAN.md §0.5).
- [x] T005 [P] Create `.claude/settings.json` with exactly `{"permissions": {"deny": ["Read(./.env)", "Read(./.env.local)"]}}` pretty-printed as in PLAN.md §0.5 (contracts/make-and-guardrails.md).
- [x] T006 Create `Makefile` per `contracts/make-and-guardrails.md`: `PY ?= .venv/bin/python` with a `python3` fallback when `.venv/` is absent, `PHASE ?= build`, `ARGS ?=`; `.PHONY` targets `install`, `secrets`, `check-env`, `test`, `dev`, `fixtures`, `deploy`; `test` runs `$(PY) -m pytest -q` then the `web/` checks (`npm run typecheck && npm run lint && npm run build`) only when `web/` exists; `dev`, `fixtures`, `deploy` print a one-line note and exit 1 while their script (`app/main.py`, `scripts/export_fixtures.py`, `scripts/deploy.sh`) is absent or `HOST` is a placeholder; never `include .env` (research R10).
- [x] T007 Run `make test` (A's 204 tests pass; no `web/` yet so no npm step) and `make check-env` (expected to fail only because `scripts/check_env.py` does not exist yet; confirm the Makefile passes `--phase build`). Commit: `spec 001 phase 1: env example, guardrails, Makefile, B deps`.

**Checkpoint**: `cp .env.example .env` gives every fake mode; `git status` shows no env files; the Makefile is the shared entry point. Stop and report.

---

## Phase 2: User Story 1 — readiness command (Priority: P1 = PLAN P0) 🎯 MVP

**Goal**: `make check-env [PHASE=…]` prints the eight §0.4 rows as READY / FAKE / MISSING / FAILED with evidence and a next step, masks secrets to their last four characters, runs every probe under an 8 s deadline, never places a call without `--call-test`, offers `--json`, and exits by the §0.4 gate.

**Independent test**: with no `.env`, `make check-env` exits 0 and every row is MISSING or FAKE; with the unedited `.env.example` copied, it exits 1 naming the app secrets; `make check-env PHASE=integrate` and `PHASE=demo` exit 1 and list each unmet requirement (quickstart.md §1, §4). `pytest -q tests/test_check_env.py` passes offline.

- [x] T008 [P] [US1] Create `tests/test_check_env.py`, part A (pure core), importing `from scripts import check_env` and asserting: `mask("abc") == "••••"`, `mask("abcd") == "••••"`, `mask("secret-value-7f3a").endswith("7f3a")` and has length 8, `mask("")` is `"••••"`; `is_placeholder` is True for `""`, `None`, `"replace-me"`, `"replace-with-a-generated-token-of-32-or-more-characters"`, `"$2a$14$replace-with-caddy-hash-password-output"`, `"ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"`, `"172-105-12-34.sslip.io"`, `"https://172-105-12-34.sslip.io"`, `"team@example.com"` and False for `"hackathon-chat"`, `"https://ws.akamai-workshops.com/v1"`, `"us-ord-1"`, a 43-char urlsafe token; `scrub("key sk-abcdefghij failed", ["sk-abcdefghij"])` contains `"••••ghij"` and not `"sk-abcdefghij"`, and a 7-char secret is left alone (research R8, data-model.md "Placeholder").
- [x] T009 [P] [US1] Extend `tests/test_check_env.py`, part B (status precedence and gates) using `check_env.evaluate(env, phase, probe_results)` with a `ProbeResult(ok, evidence, error, duration_ms)` helper: (a) empty env, `build` → every row MISSING or FAKE, `report.ok` True, rows in the data-model order with keys `akamai_inference, akamai_cloud_api, public_url, object_storage, twilio, devrev, aws, app_secrets`; (b) env from a parsed `.env.example`, `build` → `app_secrets` FAILED, `ok` False, failure text contains `make secrets`; (c) `AI_MODE=off` plus a real-looking `AKAMAI_API_KEY` and `probe_results["akamai_inference"].ok=True`, `build` → status FAKE, `probe == "skipped"` in build and `"ready"` in integrate; (d) spec AC3: real-looking Akamai, URL and Twilio values with ok probes, placeholder Object Storage, `AI_MODE=off`, `VOICE_MODE=simulated` → `integrate` ok True; `demo` ok False with failures mentioning `AI_MODE`, `VOICE_MODE`, `/mcp`, `EB_DATASET_VERSION`; (e) Twilio probe errors `"trial account"`, `"balance $4.20 < $10"`, `"number has no voice capability"` each give FAILED with that reason in evidence; (f) a probe result with `error="timed out after 8 s"` → FAILED, other rows unaffected; (g) `LLM_FALLBACK=none` → `aws` FAKE in all three phases and never in `failures`; (h) `EB_DATASET_VERSION=public-2026-10-10` → `devrev` FAKE and a `demo` failure naming the pinned version; (i) `LINODE_TOKEN` absent → `akamai_cloud_api` MISSING and never in `failures` for any phase (research R3, R7).
- [x] T010 [P] [US1] Extend `tests/test_check_env.py`, part C (I/O shell, offline): `main(["--env-file", str(tmp_path/"none.env")])` returns 0 and prints a table containing `build gate: PASS`; `main(["--env-file", ..., "--json"])` output parses as JSON with `phase`, `ok`, `failures`, `generated_at`, 8 `rows` each with `key, name, status, probe, evidence, next_step, env`, and `env` lists only names; with a temp `.env` holding `AKAMAI_API_KEY=sk-live-0123456789abcdef` and `AI_MODE=off`, neither the table nor the JSON contains `sk-live-0123456789ab` (SC-002); `main(["--phase", "nope"])` returns 2; a monkeypatched `check_env.run_probes` that records calls is **not** called for an empty env and a monkeypatched `check_env.place_test_call` is never called without `--call-test` and is called once with `DEMO_VENDOR_PHONE` when `--call-test` is passed together with ok Twilio probe results (SC-005).
- [x] T011 [US1] Create `scripts/check_env.py`, pure core: module docstring citing PLAN.md §0.4, §0.5, §7.1 and the contract; `PLACEHOLDER_VALUES` frozenset and `is_placeholder`; `mask`; `scrub`; `SECRET_VARS` tuple (`AKAMAI_API_KEY, LINODE_TOKEN, TWILIO_AUTH_TOKEN, OBJ_ACCESS_KEY, OBJ_SECRET_KEY, MCP_TOKEN, INTERNAL_TOKEN, DASH_PASS_HASH, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY`); dataclasses `ProbeResult`, `RowReport`, `Report` with the fields in data-model.md; the `ROWS` table (key, name, env names, required names, mode var and fake value, secret vars, gate phases) exactly as data-model.md; `BCRYPT_RE = r"^\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}$"`; `evaluate(env, phase, probe_results=None)` implementing precedence FAKE → MISSING → FAILED → READY (research R3), the `probe` field (`skipped` when MISSING, or when FAKE in `build`), `next_step` strings from contracts/check-env-cli.md, and the gates of research R7 producing the named `failures` list. No network imports at module top level beyond type hints.
- [x] T012 [US1] Extend `scripts/check_env.py`, probes: `load_env(path)` via `dotenv_values` overlaid by `os.environ`; one function per row (`probe_akamai_inference`, `probe_linode`, `probe_public_url`, `probe_object_storage`, `probe_twilio`, `probe_devrev`, `probe_aws`, `check_app_secrets`) implementing research R6 exactly (Twilio: `accounts(sid).fetch()` type/status, `balance.fetch()`, `incoming_phone_numbers.list(phone_number=...)` voice capability; DevRev: folders `crm_json_data, pm_json_data, maple_kb, transcripts, internal_docs`, token ≥ 32, unauthenticated `POST {PUBLIC_BASE_URL}/mcp` expecting 401 when the URL is real); library timeouts `httpx.Client(timeout=t)`, `TwilioHttpClient(timeout=t)`, `botocore.config.Config(connect_timeout=t/2, read_timeout=t/2, retries={"max_attempts": 0})`; `run_probes(env, keys, timeout)` using `ThreadPoolExecutor` and `future.result(timeout=timeout)` → `ProbeResult(ok=False, error="timed out after N s")` on `TimeoutError`, and every exception caught and scrubbed into `error` (research R5, R8). Imports of `twilio`, `boto3` happen inside the probe functions.
- [x] T013 [US1] Extend `scripts/check_env.py`, shell: `place_test_call(env, timeout)` dialling only `DEMO_VENDOR_PHONE` from `TWILIO_FROM_NUMBER` with inline TwiML `<Response><Say>Call Me Back readiness check.</Say></Response>` and returning the call SID; `render_table(report)` and `render_json(report)` per contracts/check-env-cli.md (header line with phase and UTC time, the four columns, the gate line, failure bullets); `main(argv=None) -> int` with `argparse` flags `--phase`, `--json`, `--env-file`, `--call-test`, `--timeout` (capped at 8), exit codes 0/1/2, `if __name__ == "__main__": raise SystemExit(main())`. All printed text passes through `scrub` with the secret values from the loaded env.
- [x] T014 [US1] Run `pytest -q tests/test_check_env.py`, then the quickstart §1 and §4 commands by hand (`rm -f .env; make check-env; echo $?` → 0; `cp .env.example .env; make check-env; echo $?` → 1; `PHASE=integrate` and `PHASE=demo` → 1 with named failures; `ARGS="--json"` parses). Run `make test`. Commit: `spec 001 phase 2: check_env.py with probes, phases, masking and tests`.

**Checkpoint**: US1 complete and independently verifiable offline. Stop and report (include the table output from the empty-`.env` run).

---

## Phase 3: User Story 3 — generate the app's own secrets (Priority: P1 = PLAN P0)

**Goal**: `make secrets` writes `INTERNAL_TOKEN`, `MCP_TOKEN`, `DASH_USER` and a single-quoted `$2a$` bcrypt `DASH_PASS_HASH` into `.env`, fills only gaps, prints the password once, and `make check-env` then shows App secrets READY.

**Independent test**: on an empty or absent `.env`, run it twice: first run writes the four lines and prints the password; second run says "Nothing to do" and the file is byte-identical (quickstart.md §2). `pytest -q tests/test_gen_secrets.py` passes.

- [x] T015 [P] [US3] Create `tests/test_gen_secrets.py` importing `from scripts import gen_secrets` and, using `tmp_path/".env"` and `--rounds 4`: (a) absent file → created with mode `0600`, contains `INTERNAL_TOKEN=`, `MCP_TOKEN=` (values ≥ 32 chars, urlsafe charset), `DASH_USER=demo`, and `DASH_PASS_HASH='$2a$04$` … `'` matching `^DASH_PASS_HASH='\$2a\$04\$[./A-Za-z0-9]{53}'$`; `bcrypt.checkpw(password_from_stdout, hash)` is True; stdout contains the password exactly once and the file does not contain it; (b) a file copied from `.env.example` → the three placeholder lines are replaced in place (same line numbers, trailing `# comment` on `MCP_TOKEN` kept), `DASH_USER=demo` kept unchanged, every other line byte-identical; (c) a file with a valid `INTERNAL_TOKEN=<43 chars>` and nothing else → that line unchanged, the other three appended under `# --- generated by make secrets (spec 001)`; (d) second run → stdout contains `Nothing to do` and the file bytes are identical; (e) `check_env.evaluate` on the resulting env reports `app_secrets` READY (FR-012, FR-013, SC-006).
- [x] T016 [US3] Create `scripts/gen_secrets.py` per `contracts/gen-secrets-cli.md`: `argparse` flags `--env-file`, `--rounds` (default 14), `--quiet`; import `is_placeholder` and `BCRYPT_RE` from `scripts.check_env` so both scripts agree on validity; line-wise parse preserving comments and order; `plan_changes(lines) -> list[(key, action)]` with actions `kept | replaced placeholder | written`; token generation `secrets.token_urlsafe(32)`; password `secrets.token_urlsafe(12)`; hash `bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds, prefix=b"2a")).decode()` written as `DASH_PASS_HASH='<hash>'`; atomic write (temp file + `os.replace`, mode `0600`); the exact stdout lines of the contract; exit 0, or 1 on write failure; `main(argv=None) -> int` (research R2, R9).
- [x] T017 [US3] Run `pytest -q tests/test_gen_secrets.py`, then quickstart §2 by hand on the real `.env` (`make secrets` twice, `sha256sum` identical, `make check-env` → App secrets READY, exit 0). Run `make test`. Commit: `spec 001 phase 3: gen_secrets.py and tests`.

**Checkpoint**: US3 complete; a laptop now passes the build gate with a real `.env`. Stop and report (never paste the password or `.env`).

---

## Phase 4: User Story 2 — build and test with zero credentials (Priority: P1 = PLAN P0)

**Goal**: prove, with tests, that the committed example is a complete zero-credential configuration: it has exactly the §7.1 variables, every mode default is the fake one, every mode row reports FAKE regardless of credentials, and nothing in the suite touches the network.

**Independent test**: `make test` passes with the network disabled (for example `unshare -n` or airplane mode) and `tests/test_env_example.py` passes (quickstart.md §1).

- [x] T018 [P] [US2] Create `tests/test_env_example.py`: parse `.env.example` with `dotenv_values` and assert the key set equals the 45 names listed in `specs/001-env-readiness/contracts/env-example.md` (hard-code the list in the test), `AI_MODE == "off"`, `VOICE_MODE == "simulated"`, `STORAGE_MODE == "local"`, `LLM_FALLBACK == "none"`, `TWILIO_VALIDATE_SIGNATURE == "1"`, `DEMO_MODE == "1"`, `DASH_PASS_HASH` starts with `$2a$14$replace` (single quotes stripped by dotenv), every secret variable (`check_env.SECRET_VARS`) is empty or `is_placeholder`, and the file's variable lines equal PLAN.md §7.1 lines 457–524 (read PLAN.md in the test and compare the non-comment `KEY=` prefixes in order) (FR-011).
- [x] T019 [P] [US2] Extend `tests/test_check_env.py`, part D: with env = parsed `.env.example` plus generated-looking app secrets, and probe results that are all `ok=True`, `evaluate(..., "build")` gives `akamai_inference`, `object_storage`, `twilio`, `aws` status FAKE (mode wins over credentials, FR-010), `app_secrets` READY, `ok` True; and a module-level guard test that `scripts.check_env` and `scripts.gen_secrets` import without `twilio`/`boto3` being imported at module scope (`"twilio" not in sys.modules` after a fresh `importlib.reload`), so the pure core never pulls network clients.
- [x] T020 [US2] Add a `tests/conftest.py`-compatible network guard for this spec's tests only: in `tests/test_check_env.py`, an autouse fixture that monkeypatches `socket.socket.connect` to raise `AssertionError("network call in tests")`, proving every test in the file is offline (constitution VIII). Do not edit A's `tests/conftest.py`.
- [x] T021 [US2] Run `make test`; additionally run `unshare -rn .venv/bin/python -m pytest -q` (or document the airplane-mode run if `unshare` is unavailable) to confirm the suite is network-free. Commit: `spec 001 phase 4: zero-credential proof tests`.

**Checkpoint**: US2 complete. Stop and report, including the offline run result.

---

## Phase 5: User Story 4 — runbook and guardrails (Priority: P2 = PLAN P1)

**Goal**: `docs/SETUP.md` walks a teammate from a fresh clone to a build-phase pass and through every Track B human step in PLAN.md §0.2 order, with the laptop-only rule and the after-event revocations; the guardrails from phase 1 are verified end to end.

**Independent test**: a read-through confirms each §0.2 Track B step appears in order with its `check-env` row; `git check-ignore` confirms the ignore list; a Claude Code worktree created from this checkout contains `.env`; an agent Read of `./.env` is denied while `.env.example` reads (quickstart.md §5, SC-008, SC-009).

- [x] T022 [US4] Create `docs/SETUP.md` per `contracts/make-and-guardrails.md` "docs/SETUP.md": sections in this order: (1) Tools (§0.3, including `uv tool install linode-cli` and `ssh-keygen -t ed25519`); (2) First five minutes: clone, `make install`, `cp .env.example .env`, `make secrets`, `make check-env` → build PASS; (3) Track B steps from §0.2 in order (T+0 DevRev registration, T+5 Akamai account with the promo link, T+10 Twilio upgrade, number, geo permissions, contact on the phone, T+25 Linode token with the exact scopes and `linode-cli configure --token`, T+30 bucket and limited key per §16.3, T+35 optional AWS, T+40 SE questions into `docs/decisions.md`), each ending with the `make check-env` row that turns READY and the §0.4 "Needed live by" spec; (4) The three phases and their deadlines (§0.4, §0.6: integrate by about 4 PM, demo before the Sunday 7:00 deploy); (5) Secrets rules (§0.5: one gitignored `.env` per checkout, `.worktreeinclude`, the deny rule, never cat `.env`, laptop-only `LINODE_TOKEN` and AWS keys, the `grep -v -E '^(LINODE_TOKEN|AWS_)' .env | ssh …` copy command from §16.1, the VM edits `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS`, `VOICE_MODE=twilio`, `AI_MODE=live`); (6) After the event: revoke the Linode token and Object Storage key, rotate the Twilio auth token, delete the MCP token. Reference PLAN.md sections rather than restating tables; no values, ever.
- [x] T023 [US4] Verify the guardrails: `git check-ignore -q .env .env.local data/app.db eb_data/x web/node_modules/x web/dist/x web/snapshots/x .claude/worktrees/x` → all ignored; `git check-ignore -q data/.gitkeep` → not ignored; `python3 -c "import json; print(json.load(open('.claude/settings.json'))['permissions']['deny'])"` → the two rules; create a throwaway Claude Code worktree (`claude --worktree guardrail-check` or `git worktree add` plus a manual copy check) and confirm `.env` is present there, then remove it. Record the results in the phase report, not in the repo.
- [x] T024 [US4] Run `make test`. Commit: `spec 001 phase 5: SETUP.md runbook and guardrail verification`.

**Checkpoint**: all four stories complete. Stop and report.

---

## Phase 6: Converge and merge

- [ ] T025 Run `/speckit-converge`; implement any task it appends, then repeat until it reports converged.
- [ ] T026 Update `docs/decisions.md` "Setup facts": note that `requirements.txt` gained `twilio`, `boto3`, `bcrypt` (B, spec 001, agreed with A) and that `.gitignore` is now B-maintained with A's entries preserved.
- [ ] T027 `git fetch && git rebase origin/main`, `make test`, push `001-env-readiness`, fast-forward or PR into `main`, then tell Builder A: "spec 001 merged: `make check-env`, `make secrets`, `make test` available; `.env.example` is §7.1; three pins added to requirements.txt." Delete the local branch.

---

## Dependencies and execution order

- **Phase 1** first: T001 then T002–T005 in parallel, then T006, then T007.
- **Phase 2** (US1) depends on phase 1 (Makefile, `.env.example` for test fixtures). T008–T010 (tests) in parallel and before T011–T013 (implementation, sequential: core → probes → shell); T014 last.
- **Phase 3** (US3) depends on T011 (`is_placeholder`, `BCRYPT_RE`). T015 before T016; T017 last.
- **Phase 4** (US2) depends on phases 2 and 3 (uses `evaluate` and generated secrets). T018–T020 in parallel; T021 last.
- **Phase 5** (US4) depends only on phase 1 for the guardrail checks and can be written any time after it; it is ordered last because it is P2 (constitution X).
- **Phase 6** after everything.

## Parallel execution examples

- Phase 1: T002, T003, T004, T005 touch four different files; run together after T001.
- Phase 2: T008, T009, T010 are three sections of one test file but independent in content; write them in one pass, then implement T011 → T012 → T013 against them.
- Phase 4: T018 (new file), T019 and T020 (additions to the test file) can be written together.

## Implementation strategy

- **MVP** = phases 1 and 2: the Makefile, the example env, the guardrails and `make check-env` with an empty `.env` exiting 0. This alone unblocks spec 002 (it needs `check-env` for the public URL row) and every other session's "copy `.env.example` and go".
- Then phase 3 (secrets) so the build gate passes with a real `.env`, phase 4 (proof tests), phase 5 (runbook).
- Cut order if the clock bites (PLAN.md §4 spirit): phase 5's worktree check → `--call-test` → the AWS probe (keep the FAKE/MISSING logic) → the Object Storage probe. Never cut masking, the gates or the no-call guarantee.

## Format validation

All 27 tasks start with `- [ ]`, carry a sequential ID, mark `[P]` only where files differ and nothing unfinished is depended on, carry a story label only in phases 2–5, and name their file(s).

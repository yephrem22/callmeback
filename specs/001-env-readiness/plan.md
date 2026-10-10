# Implementation Plan: Environment Readiness

**Branch**: `001-env-readiness` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-env-readiness/spec.md`, and the Plan prompt from PLAN.md §23.1.

## Summary

Give both builders and every Claude Code session one safe view of what is live: `make check-env` probes each integration in PLAN.md §0.4 (Akamai inference, Akamai Cloud API, public HTTPS URL, Object Storage, Twilio, DevRev and Enterprise-Bench data, optional AWS Bedrock, app secrets), prints one row per integration as READY / FAKE / MISSING / FAILED with a next step, masks every secret to its last four characters, and exits by the `build` / `integrate` / `demo` gate in §0.4. `make secrets` fills `INTERNAL_TOKEN`, `MCP_TOKEN` and a Caddy-compatible `$2a$` bcrypt `DASH_PASS_HASH` into `.env` without overwriting anything. `.env.example` copies §7.1 verbatim so a fresh checkout runs in every fake mode, and the guardrails in §0.5 (`.gitignore`, `.worktreeinclude`, `.claude/settings.json`) plus `docs/SETUP.md` keep env files out of git and out of agents' context. Everything is plain Python 3.12 with `argparse`; no CLI framework.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed `.venv` locally; `python:3.12-slim` in Docker, spec 002)

**Primary Dependencies**: `httpx` (Akamai inference, Linode API, public URL, MCP probe), `twilio` 9.x (account/balance/number probe, `--call-test`), `boto3` (Object Storage put/get/delete, optional STS and Bedrock), `bcrypt` (dashboard hash), `python-dotenv` (reading `.env` with the single-quote rule). stdlib `argparse`, `secrets`, `json`, `concurrent.futures`, `pathlib`. Pins appended to the A-owned `requirements.txt`: `twilio==9.11.2`, `boto3==1.43.111`, `bcrypt==5.0.0` (research R1; Builder A is told).

**Storage**: the gitignored `.env` at the repo root (read via `dotenv_values`, written line-wise by `gen_secrets.py`). No database.

**Testing**: `pytest -q`, no network: `tests/test_check_env.py` injects fake probe results and uses a temp `.env`; `tests/test_gen_secrets.py` uses a temp `.env`. Reuses A's `tests/conftest.py` environment (AI off, simulated voice, local storage).

**Target Platform**: Linux and macOS laptops; the Akamai VM (Ubuntu 24.04) where `LINODE_TOKEN` and AWS keys are absent by rule.

**Project Type**: two CLI scripts plus a Makefile and repository configuration files; the Builder B files of PLAN.md §6 that belong to spec 001.

**Performance Goals**: a full run with every integration unreachable finishes in about 8 s (probes run concurrently, each with a hard 8 s deadline, SC-004); an empty-`.env` run finishes in well under a second (no probes).

**Constraints**: never print more than the last four characters of a secret, in any output or error (FR-004, SC-002); never place a call without `--call-test` (FR-007); the four statuses, three phases and gate rules are exactly §0.4 (FR-001 to FR-003); `.env.example` is §7.1 verbatim (FR-011); must not edit files owned by other specs except the agreed `requirements.txt` append and the B-owned `.gitignore` that A seeded.

**Scale/Scope**: 8 integration rows, 3 phases, 2 scripts (~400 and ~120 lines), 1 Makefile, 4 config files, 1 runbook, 2 test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. PLAN.md is the source of truth | `.env.example` is §7.1 copied verbatim (`contracts/env-example.md`); rows, probes and gates are §0.4 copied into `data-model.md`; no new variables. | PASS |
| II. The AI explains; the code holds the keys | No model is called except the 5-token Akamai/Bedrock probe, whose result is only displayed. | PASS |
| III. Fail closed | Any probe error, timeout or malformed value is FAILED; a missing value is MISSING; the gate exits 1 on anything short of READY. Fake modes are the default in `.env.example`. | PASS |
| IV. Call the number on file | `--call-test` dials only `DEMO_VENDOR_PHONE` (the team line), never a number from data. | PASS |
| V. Never blocked by setup | This spec *is* principle V: every row has a FAKE mode and the suite runs with zero credentials and no network. | PASS |
| VI. Secrets stay in .env | Output passes through a scrubber that replaces every known secret value with its masked form; `gen_secrets.py` prints the password once and stores only its hash; `.claude/settings.json` denies Read on env files. | PASS |
| VII. Evidence everywhere | Every row carries masked evidence (latency, username, balance, folder names) and a next step; `--json` exposes the same. | PASS |
| VIII. Test what is deterministic | Masking, placeholder detection, status precedence, phase gates and the empty-`.env` pass are unit-tested with faked probes (§17.1 `test_check_env.py`). | PASS |
| IX. Designed for its users | N/A (no UI). The table is readable in a terminal; statuses are words, not colours. | PASS |
| X. Small vertical slices | Five phases below; each stops, reports and commits; P1 stories before the P2 runbook. | PASS |
| XI. Fresh code | All files written after kickoff; `httpx`, `twilio`, `boto3`, `bcrypt`, `python-dotenv` are libraries. | PASS |

Post-design re-check (after Phase 1 artifacts): no violations; Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-env-readiness/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R12
├── data-model.md        # Phase 1: rows, probes, statuses, phases, report (from §0.4)
├── quickstart.md        # Phase 1: how to run and validate
├── contracts/
│   ├── env-example.md       # §7.1 verbatim, the content of .env.example
│   ├── check-env-cli.md     # check_env.py arguments, table, --json shape, exit codes
│   ├── gen-secrets-cli.md   # gen_secrets.py arguments, write rules, output
│   └── make-and-guardrails.md  # Makefile targets, .gitignore, .worktreeinclude, settings.json
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root; Builder B files from PLAN.md §6 that belong to spec 001)

```text
Makefile                 # install, secrets, check-env (PHASE=build|integrate|demo), test, dev, fixtures, deploy
.env.example             # §7.1 verbatim
.gitignore               # A's entries kept; adds data/*, eb_data/, web/node_modules, web/dist, web/snapshots
.worktreeinclude         # .env
.claude/settings.json    # deny Read(./.env), Read(./.env.local)   (§0.5)
requirements.txt         # A-owned; this spec appends twilio, boto3, bcrypt (agreed)

scripts/
├── check_env.py         # rows, probes, phases, masking, table + --json, --call-test
└── gen_secrets.py       # INTERNAL_TOKEN, MCP_TOKEN, DASH_USER, DASH_PASS_HASH into .env

docs/
└── SETUP.md             # human runbook from §0.2 Track B, §0.3, §0.4, §0.5

tests/
├── test_check_env.py    # masking, placeholders, status precedence, phase gates, empty .env → exit 0
└── test_gen_secrets.py  # creates .env, fills gaps only, idempotent, quoting
```

**Structure Decision**: flat scripts under `scripts/` as PLAN.md §6 prescribes (A already created `scripts/__init__.py`, so tests import `scripts.check_env` directly). `check_env.py` is one module with a pure core (`evaluate(rows, phase)` over injected probe results) and a thin I/O shell (env loading, concurrent probing, table/JSON rendering) so the tests never touch the network.

## Phases (for /speckit-tasks; each phase stops and reports)

1. **Phase 1, foundation and guardrails (P0)**: append pins to `requirements.txt`; `.env.example` (§7.1 verbatim); `.gitignore` additions; `.worktreeinclude`; `.claude/settings.json`; Makefile skeleton with `install`, `test`, `check-env`, `secrets`, `dev`, `fixtures`, `deploy` (the last three delegating to scripts that other specs provide, with a clear message until they exist). Gate: `make test` runs A's suite green; `cp .env.example .env` yields every fake mode.
2. **Phase 2, US1 readiness command (P0)**: `scripts/check_env.py` with the pure core (masking, placeholder detection, status precedence, phase gates, rendering) and the eight live probes behind an 8 s deadline each; `tests/test_check_env.py`. Gate: empty `.env` → build exit 0, all rows MISSING/FAKE; placeholder secrets → exit 1; faked integrate/demo scenarios from the spec pass.
3. **Phase 3, US3 secrets (P0)**: `scripts/gen_secrets.py` and `tests/test_gen_secrets.py`; `make secrets` then `make check-env` shows app secrets READY. Gate: second run leaves `.env` byte-identical.
4. **Phase 4, US2 zero-credential proof (P0)**: a test asserting `.env.example` has exactly the §7.1 variables with fake-mode defaults; a test that `check_env` on a copy of `.env.example` (plus generated secrets) reports every mode row FAKE; `--call-test` guard test. Gate: `make test` green with no network.
5. **Phase 5, US4 runbook (P1)**: `docs/SETUP.md` from §0.2 Track B, §0.3, §0.4, §0.5 with the laptop-only rule and the after-event revocation list. Gate: a read-through against the §0.2 order; `make check-env` build pass at the end of the runbook.

Then `/speckit-converge`, rebase on `main`, `make test`, push, merge.

## Complexity Tracking

No constitution violations to justify.

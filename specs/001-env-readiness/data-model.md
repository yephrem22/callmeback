# Data Model: Environment Readiness

No database. The entities below are in-memory structures inside `scripts/check_env.py` and `scripts/gen_secrets.py`, derived from PLAN.md §0.4 and §7.1. Field names are the ones the `--json` output uses ([contracts/check-env-cli.md](contracts/check-env-cli.md)).

## Status (enum)

`READY` | `FAKE` | `MISSING` | `FAILED` — the four statuses of spec FR-001. Precedence is research R3: FAKE, then MISSING, then FAILED, then READY.

## Phase (enum)

`build` (default) | `integrate` | `demo` — spec FR-002; gate rules per research R7.

## IntegrationRow

One per §0.4 integration, in this fixed order:

| `key` | `name` | `env` (names only, §7.1) | `mode_var` → fake value | `secret_vars` |
|---|---|---|---|---|
| `akamai_inference` | Akamai inference | `AKAMAI_BASE_URL`, `AKAMAI_API_KEY`, `MODEL_ID` | `AI_MODE` → `off` | `AKAMAI_API_KEY` |
| `akamai_cloud_api` | Akamai Cloud API | `LINODE_TOKEN` | — | `LINODE_TOKEN` |
| `public_url` | Public HTTPS URL | `HOST`, `PUBLIC_BASE_URL`, `ACME_EMAIL` | — | — |
| `object_storage` | Object Storage | `OBJ_ENDPOINT`, `OBJ_REGION`, `OBJ_BUCKET`, `OBJ_ACCESS_KEY`, `OBJ_SECRET_KEY` | `STORAGE_MODE` → `local` | `OBJ_ACCESS_KEY`, `OBJ_SECRET_KEY` |
| `twilio` | Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `DEMO_VENDOR_PHONE` | `VOICE_MODE` → `simulated` | `TWILIO_AUTH_TOKEN` |
| `devrev` | DevRev and Enterprise-Bench | `EB_DATA_DIR`, `EB_DATASET_VERSION`, `MCP_TOKEN`, `MCP_ALLOWED_HOSTS`, `DEVREV_ORG_URL` | `EB_DATASET_VERSION` → `public-*` | `MCP_TOKEN` |
| `aws` | AWS (optional) | `LLM_FALLBACK`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID` | `LLM_FALLBACK` → `none` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| `app_secrets` | App secrets | `INTERNAL_TOKEN`, `MCP_TOKEN`, `DASH_USER`, `DASH_PASS_HASH` | — | `INTERNAL_TOKEN`, `MCP_TOKEN`, `DASH_PASS_HASH` |

Per-row rules:
- `required`: the subset of `env` that must be non-placeholder before probing (everything except `ACME_EMAIL`, `DEVREV_ORG_URL`, `MCP_ALLOWED_HOSTS`, `DEMO_VENDOR_PHONE`; for `devrev`, `EB_DATASET_VERSION` is required only by the `demo` gate).
- `gate`: which phases require this row's probe READY — `akamai_inference`, `public_url`, `twilio`: `integrate` and `demo`; `devrev`: `demo` (with the `/mcp` 401 probe); `app_secrets`: all phases fail on FAILED (malformed); the rest: never.

## ProbeResult

Result of one live probe (or of the local checks for `app_secrets`):

| field | type | meaning |
|---|---|---|
| `ok` | bool | the §0.4 condition holds |
| `evidence` | str | masked, ≤ 120 chars: latency, username, balance, folder list, model id |
| `error` | str \| null | scrubbed failure reason (timeout, HTTP status, "trial account", "balance $4.20 < $10", "number has no voice capability", "model hackathon-chat not listed") |
| `duration_ms` | int | wall time of the probe |

Validation: `evidence` and `error` pass through the scrubber (research R8) before being stored.

## RowReport

| field | type | meaning |
|---|---|---|
| `key`, `name` | str | from IntegrationRow |
| `status` | Status | research R3 precedence |
| `probe` | `ready` \| `failed` \| `skipped` | the credential check, independent of mode (research R3); `skipped` when MISSING or when FAKE in the `build` phase |
| `evidence` | str | masked |
| `next_step` | str | one sentence from §0.4 / §0.2 (for example "Set AI_MODE=live once the key works", "Create the bucket and key (§16.3)", "Run make secrets") |
| `env` | list[str] | variable names only, never values |

## Report

| field | type | meaning |
|---|---|---|
| `phase` | Phase | |
| `ok` | bool | the gate for `phase` is met |
| `failures` | list[str] | each unmet gate requirement, named (empty when `ok`) |
| `rows` | list[RowReport] | fixed order above |
| `generated_at` | str | UTC ISO-8601 |

Exit code = `0 if ok else 1`.

## AppSecret (gen_secrets.py)

| variable | generator | validity rule (shared with check_env) | written as |
|---|---|---|---|
| `INTERNAL_TOKEN` | `secrets.token_urlsafe(32)` (43 chars) | ≥ 32 chars, not a placeholder | `INTERNAL_TOKEN=<token>` |
| `MCP_TOKEN` | `secrets.token_urlsafe(32)` | ≥ 32 chars, not a placeholder | `MCP_TOKEN=<token>` |
| `DASH_USER` | constant `demo` | non-empty | `DASH_USER=demo` (only if absent) |
| `DASH_PASS_HASH` | bcrypt, rounds 14, prefix `2a`, of a `secrets.token_urlsafe(12)` password | `^\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}$` | `DASH_PASS_HASH='$2a$14$…'` (single quotes, §7.1) |

State transitions of a `.env` line for each variable: `absent → appended`; `placeholder → replaced in place`; `valid → unchanged`. The plain password exists only in process memory and on stdout once.

## Placeholder (value predicate)

`is_placeholder(v)`: `v` is empty, or contains `replace` (case-insensitive), or is one of `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`, `172-105-12-34.sslip.io`, `https://172-105-12-34.sslip.io`, `team@example.com` (research R4).

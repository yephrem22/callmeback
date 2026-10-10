# Contract: fixtures, scenario index, routes and query parameters (spec 004)

## Fixture files (produced by `scripts/export_fixtures.py`, spec 003; read-only for the UI)

| File | Shape (PLAN.md §7.6) |
|---|---|
| `web/src/fixtures/index.json` | `Record<scenario, {step, file, status, hold_reason, invoice_id}[]>` |
| `web/src/fixtures/<scenario>/<nn>_<step>.json` | `InvoiceDetail` |
| `web/src/fixtures/invoices_list.json` | `GET /api/invoices` rows |
| `web/src/fixtures/health.json` | `GET /api/health` |
| `web/src/fixtures/stats.json` | `GET /api/stats` |
| `web/src/fixtures/payments.json` | `GET /api/payments` (`{payments[], held[]}`) |
| `web/src/fixtures/vendors.json` | `GET /api/vendors` (masked, with `bank_history`) |
| `web/src/fixtures/audit.json` | `GET /api/audit` (`{entries[], chain_ok, broken_at}`) |

Scenarios and steps as exported today:

| scenario | steps | final status |
|---|---|---|
| acme_normal | scored, paid | RELEASED |
| acme_fraud | scored, calling, held | HELD / DENIED_BY_VENDOR |
| heartland_bank_change | scored, calling, confirmed, paid | RELEASED |
| prairie_review | scored, approved, paid | RELEASED |
| unknown_vendor | scored | HELD / UNKNOWN_VENDOR |

Rule: the UI never adds a key to a fixture. If a screen needs something §7.6 lacks, it is logged in `docs/design/decisions.md` under "Contract requests" and raised with both builders (constitution I).

## Fixtures mode semantics

- `VITE_API_MODE=fixtures` (default in `web/.env.development`): `api.ts` serves every call from the fixture store. The queue (`GET /api/invoices`) lists one row per scenario at its **current** step, so the queue reflects the story as it is played. `GET /api/invoices/{id}` returns the current step's `InvoiceDetail` for that scenario. Mutations (`review`, `retry-callback`, `redteam`, `demo/*`) resolve by advancing the matching scenario one step when that makes sense, otherwise no-op, so buttons are clickable in the prototype.
- `VITE_API_MODE=live`: plain `fetch` against `/api/*` (proxied to :8000 in dev). Spec 007 owns the polling.

## Routes

| Path | Served in | Purpose |
|---|---|---|
| `/` | dev and prod | the dashboard |
| `/gallery` | dev only (`import.meta.env.DEV`, lazy import) | candidate gallery |

## Query parameters (dev and prod; harmless when absent)

| Param | Values | Effect |
|---|---|---|
| `scenario` | `acme_normal`, `acme_fraud`, `heartland_bank_change`, `prairie_review`, `unknown_vendor`, `none` | selects the open case; `none` = empty queue |
| `step` | 1-based integer | sets that scenario's current step (clamped) |
| `theme` | `light`, `dark`, `system` | overrides the stored theme for this load |
| `tab` | `payments`, `vendors`, `audit`, `devrev`, `demo` | opens a bottom tab |
| `trace` | `1` | opens the trace sheet |

The snapshot script opens `/?scenario=<s>&step=<n>&theme=<t>` for every step and waits for `document.body[data-ready="true"]`, which the app sets after the first render of the requested state.

## Readiness and error signals for tooling

- `<body data-ready="true" data-scenario="..." data-step="n">` after render.
- Any `console.error` or any request to a host other than `localhost`/`127.0.0.1` fails the snapshot run (SC-006).

# Call Me Back dashboard (`web/`)

React + Vite + TypeScript, Tailwind v4, shadcn/ui, built to static files that FastAPI serves (PLAN.md §14). Designed in spec 004 on fixtures; spec 007 wires it to the live API.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | dev server on :5173, proxies `/api` to :8000 |
| `npm run build` | typecheck + production build into `dist/` (the gallery and the scenario player are excluded) |
| `npm run typecheck`, `npm run lint` | gates for every commit (`make test` runs them) |
| `npm run snap` | Playwright screenshots of every scenario step, both themes, 1024×576, into `snapshots/`; fails on console errors or third-party requests. Flags: `--shell`, `--gallery`, `--cards`, `--reduced-motion`, `--base <url>` |
| `npm run verify` | behaviour checks against the dev server: theme default/persistence/override, j/k/Enter, focus ring, reduced motion |
| `npm run contrast` | WCAG contrast over the tokens in `src/index.css`, both themes |

Node 22 (`~/.nvm/versions/node/v22.23.3`). Run `npx playwright install chromium` once for `snap` and `verify`.

## API modes

`VITE_API_MODE=fixtures` (default in `.env.development`) serves everything from `src/fixtures/`, which `scripts/export_fixtures.py` (spec 003) generates from the real engine. `VITE_API_MODE=live` (`.env.production`) calls `/api/*`. `src/lib/api.ts` is the only data entry point; TanStack Query hooks wrap both modes. Fixtures must keep working for offline demos.

## URL parameters

`?scenario=<acme_normal|acme_fraud|heartland_bank_change|prairie_review|unknown_vendor|none>&step=<n>&theme=<light|dark|system>&tab=<payments|vendors|audit|devrev|demo>&trace=1&player=0`. Any state of the demo story is addressable directly; `player=0` hides the dev scenario player.

## Development-only pieces

- `/gallery`: the fourteen PLAN.md §14.8 candidates with two variants each. Winners are recorded in `docs/design/decisions.md`.
- The scenario player (bottom right in fixtures mode) steps through the five scenarios; `window.__cmb.setStep/loadAll/reset` for scripts.
- Both are loaded through `virtual:dev-only/*` (see `vite.config.ts`) and become empty stubs in `vite build`.

## Layout and data flow

`features/shell/Layout.tsx` owns selection: in fixtures mode the open case is the `?scenario`, in live mode it is local state. It renders `CaseView` (decision, risk, destination, amount history), `CallbackPanel`, `PaymentCard`, `Actions`, `EvidenceTabs`, the bottom tabs and the `TraceSheet`. `lib/decide.ts` turns a §7.6 `InvoiceDetail` into the stamp and the one-sentence decision; `lib/format.ts` formats cents and America/Chicago times.

## Hand-off notes for spec 007

- Add `refetchInterval` in `src/lib/api.ts` hooks per PLAN.md §14.9 (list 2 s; open case 1 s until RELEASED/HELD/FAILED, then 5 s; health 15 s).
- Live selection: replace `liveSelected` in `Layout.tsx` with the id from "Load a sample" / queue clicks, and enable the Upload button (`postUpload` exists).
- `Actions` already reads `actions.can_*`; the mutations call the §7.6 endpoints in live mode.
- `tests/test_fixtures_contract.py` (spec 007) should validate `src/fixtures/**` against the live `InvoiceDetail` shape.
- Re-run `npm run snap` and compare with the spec 004 snapshots before the stage rehearsal.

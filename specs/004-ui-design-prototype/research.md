# Research: UI Design Prototype (spec 004)

PLAN.md §14 fixes the stack, tokens, layout, copy and process, so the open questions are mechanical. Each item: decision, rationale, alternatives.

## R1. Fixtures already exist; the "hand-written fixtures" step is skipped

- **Decision**: build the gallery and prototype directly on `web/src/fixtures/`, which spec 003's `scripts/export_fixtures.py` produced from the real engine (five scenarios, 14 step files, plus `index.json`, `invoices_list.json`, `vendors.json`, `payments.json`, `stats.json`, `health.json`, `audit.json`). The exporter is deterministic; the UI never edits these files.
- **Rationale**: spec 004 assumed it would run before 003; it is running after. Real fixtures remove the "hand-written first, real later" churn and guarantee the §7.6 shape (tested in `tests/test_invoice_detail_shape.py`).
- **Alternatives**: hand-writing a parallel set (rejected: drift risk, no benefit).
- **Consequence**: `web/src/fixtures/index.json` is the scenario player's script. If a screen needs data §7.6 lacks, it is a contract change (constitution I), not a fixture edit.

## R2. Project scaffold and tooling versions

- **Decision**: `npm create vite@latest web -- --template react-ts`, then follow shadcn's Vite guide: `@tailwindcss/vite`, `@import "tailwindcss"` in `src/index.css`, `baseUrl`/`paths` for `@/*`, `npx shadcn@latest init` (non-interactive flags recorded in tasks after the first run), then `npx shadcn@latest add` for the component list in PLAN.md §14.5. Node 22 (`~/.nvm/versions/node/v22.23.3`), npm 10.
- **Rationale**: PLAN.md §14.5 prescribes this exact path.
- **Alternatives**: Next.js (rejected: static build served by FastAPI is the plan), CSS modules (rejected: shadcn is the component source).
- **Note**: the shadcn CLI prompts interactively for base color and CSS variables; use its `--defaults`/`--yes` flags where available and set tokens by hand afterwards in `src/index.css`, which we overwrite with the §14.6 palette anyway.

## R3. Routing without a router dependency

- **Decision**: two routes only, `/` and `/gallery`, plus query parameters `?scenario=&step=&theme=`. Implement with `window.location` parsing and `history.replaceState` in a tiny `useRoute()` hook. The gallery and the scenario player are wrapped in `import.meta.env.DEV` checks and lazy imports so they are tree-shaken out of the production build (FR-002).
- **Rationale**: one page app, two routes; a router adds weight and nothing else. `import.meta.env.DEV` is statically replaced by Vite, so the dev-only code is dropped in `npm run build`.
- **Alternatives**: react-router (rejected: unnecessary), separate Vite entry for the gallery (rejected: more config).

## R4. API client with two modes

- **Decision**: `src/lib/api.ts` exports typed functions (`getInvoices`, `getInvoice`, `getHealth`, `getStats`, `getPayments`, `getVendors`, `getAudit`, plus mutation stubs). `VITE_API_MODE=fixtures` resolves them from a `FixtureStore` that holds the current scenario/step (driven by the player or the URL); `live` calls `/api/*`. TanStack Query wraps both so spec 007 only flips the mode and adds `refetchInterval`. Types in `src/lib/types.ts` mirror §7.6 exactly and are checked against the fixtures by `npm run typecheck` through typed JSON imports.
- **Rationale**: PLAN.md §14.5 "API modes" and §14.7 step 6 ("keep fixtures mode working for offline demos").
- **Alternatives**: MSW mocking (rejected: an extra moving part for the same result).

## R5. Theme and tokens

- **Decision**: shadcn's Vite theme provider pattern (`ThemeProvider` with `defaultTheme="light"`, `storageKey="cmb-theme"`, `.dark` class on `<html>`), tokens from PLAN.md §14.6 mapped onto shadcn's CSS variables in `src/index.css` (`--background` paper `#F5F7F6`, `--foreground` ink `#17242E`, `--border` rule `#D3DCD9`, `--primary`/`--ring` ledger `#0B6B61`, `--destructive` held `#B42318`, plus custom `--paid`, `--review`, `--held`, `--ai`, and `--chart-1..5` = ledger, paid, review, held, ai). Dark: background `#0F1B22`, card `#15242D`, foreground `#E3EBEE`, status colors lightened (`paid #4CC38A`, `review #E0A94A`, `held #F0776B`, `ai #9A9CF0`) to pass 4.5:1 on the dark background; exact values verified with a contrast check during implementation and recorded in `docs/design/decisions.md`.
- **Rationale**: PLAN.md §14.5 dark-mode guidance and §14.6 tokens.
- **Alternatives**: `prefers-color-scheme` only (rejected: the plan wants a three-way toggle with light default for projectors).

## R6. Fonts

- **Decision**: `@fontsource/ibm-plex-sans` (400, 500, 600) and `@fontsource/ibm-plex-mono` (400, 500) imported in `main.tsx`; `font-variant-numeric: tabular-nums` on amounts; Plex Mono only on routing/account digits and hashes. No CDN.
- **Rationale**: PLAN.md §14.5 and §14.6; venue network can't break it.

## R7. Charts

- **Decision**: shadcn `chart` component (Recharts v3 underneath) for the risk breakdown bar, the risk meter and the amount-vs-history strip; `ChartContainer` with `min-h-*`, `accessibilityLayer` on, direct labels instead of legends, status colors from CSS variables. The lookalike diff, check line, stepper and stamp are plain React/SVG, not charts.
- **Rationale**: PLAN.md §14.5 and the chart rules in §14.8.
- **Alternatives**: hand-rolled SVG bars (kept as the second variant where it reads better at 5 m).

## R8. The stamp

- **Decision**: an outlined, rotated (−6°) label in the status color; a one-shot CSS keyframe `stamp-in` (scale 1.15 → 1 over 180 ms) applied on first render of a decided status, disabled under `@media (prefers-reduced-motion: reduce)`. Variants: PAID, HELD, REVIEW, CALLING; CALL_PENDING/VERIFYING render CALLING; SCORED/AUTO_APPROVED/REVIEW_APPROVED/CONFIRMED before a terminal decision render a quieter "in progress" badge rather than a stamp.
- **Rationale**: PLAN.md §14.6 "The stamp".

## R9. Snapshot script

- **Decision**: `web/scripts/snap.mjs` using `@playwright/test`'s Chromium: starts nothing itself; expects `npm run dev` (or `vite preview`) on a port given by `--base`, reads `src/fixtures/index.json`, opens `/?scenario=<s>&step=<n>&theme=<t>` for every step and both themes at 1024×576, waits for `[data-ready="true"]`, saves `web/snapshots/<scenario>-<nn>-<theme>.png`, and fails on any console error or any request to a host other than localhost (SC-006). `npx playwright install chromium` once.
- **Rationale**: PLAN.md §14.7 step 5 and §0.3.

## R10. Lint and typecheck scripts

- **Decision**: `npm run typecheck` = `tsc -b --noEmit`; `npm run lint` = Vite's default ESLint config from the template; `npm run build` = `tsc -b && vite build`. `make test` (spec 001) already runs these when `web/package.json` exists.

## R11. Time and money display

- **Decision**: `formatCents(cents)` → `$48,750.00` with tabular numerals; `formatChicago(iso)` → `Fri 4:52 PM` / `10:42` via `Intl.DateTimeFormat` with `timeZone: "America/Chicago"`. Decision sentences per PLAN.md §14.9 are built from `status`, `hold_reason`, `verification.events`/`updated_at`, `payment.effective_date` and `risk.amount_ratio`.

## R12. Research pass sources

The 15-minute research pass (FR-001) draws on: AFP Payments Fraud and Control Survey (BEC and vendor-impersonation prevalence; callback to a known number as the control), FBI IC3 annual report (BEC losses), Nacha's 2026 fraud-monitoring rule for ACH originators, Stripe Radar's risk-score-with-factors presentation, Linear/Superhuman/Front triage layouts, GitHub checks and Vercel deploy logs for step lists, and LangSmith/Langfuse span waterfalls. Findings are summarised in `docs/design/research.md` with links.

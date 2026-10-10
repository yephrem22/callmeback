# Data Model: UI Design Prototype (spec 004)

The UI owns no persistent data. Its "model" is the set of response shapes it reads (frozen in PLAN.md §7.6) and three small client-side structures.

## Read-only shapes from PLAN.md §7.6 (frozen; mirrored in `web/src/lib/types.ts`)

| Type | Source | Fixture file(s) |
|---|---|---|
| `InvoiceDetail` | `GET /api/invoices/{id}` | `web/src/fixtures/<scenario>/<nn>_<step>.json` |
| `InvoiceListRow[]` | `GET /api/invoices` | `invoices_list.json` |
| `Health` | `GET /api/health` | `health.json` |
| `Stats` | `GET /api/stats` | `stats.json` |
| `PaymentsView` | `GET /api/payments` | `payments.json` |
| `VendorView[]` | `GET /api/vendors` | `vendors.json` |
| `AuditView` | `GET /api/audit` | `audit.json` |

Exact keys are those produced by `app/repo.py::invoice_detail` and friends (spec 003) and listed in `specs/003-core-engine/contracts/http-api.md`. The TypeScript types are written from those files; `npm run typecheck` fails if a fixture gains or loses a key the types don't expect (fixtures are imported as typed JSON).

## Client-side structures

### Scenario (from `web/src/fixtures/index.json`)

```ts
type ScenarioStep = { step: string; file: string; status: string; hold_reason: string | null; invoice_id: string };
type ScenarioIndex = Record<ScenarioName, ScenarioStep[]>;
type ScenarioName = "acme_normal" | "acme_fraud" | "heartland_bank_change" | "prairie_review" | "unknown_vendor";
```

Steps per scenario (as exported): acme_normal `scored → paid`; acme_fraud `scored → calling → held`; heartland_bank_change `scored → calling → confirmed → paid`; prairie_review `scored → approved → paid`; unknown_vendor `scored`. Final states match PLAN.md §8.4.

### Route state (URL is the source of truth)

```ts
type Route = { path: "/" | "/gallery"; scenario?: ScenarioName; step?: number /* 1-based */; theme?: "light" | "dark" | "system" };
```

`?scenario=&step=&theme=` select a fixture step and theme directly (FR-010). In fixtures mode the queue shows every scenario's current step; the selected scenario is the open case.

### Design decision (`docs/design/decisions.md`, human-written at the gate)

| Slot | Candidate # | Variant | Reason |
|---|---|---|---|
| decision, risk, destination, callback, evidence, queue, trace, tabs | 1–14 | A or B | one line |

### Gallery candidate (code-level registry, `web/src/features/gallery/candidates.tsx`)

```ts
type Candidate = {
  n: number; name: string; serves: string; fields: string[]; components: string[];
  why: string; variants: [{ label: string; render: (d: InvoiceDetail) => ReactNode; snippet: string },
                          { label: string; render: ...; snippet: string }];
};
```

Fourteen entries, numbered as PLAN.md §14.8.

## Derived display values (pure functions in `web/src/lib/format.ts` and `decide.ts`)

- `stampFor(status, hold_reason)` → `PAID | HELD | REVIEW | CALLING | null`.
- `decisionSentence(detail)` → the §14.9 sentences, e.g. "Held. The vendor said no on the 10:42 call." using `verification.events` last timestamp in America/Chicago.
- `formatCents`, `formatChicago`, `maskedCheckLine(routing, account_masked)`.
- `flagTone(flag)` → `weighted` (points > 0) or `note` (0 points, info icon).

No value is invented client-side that the §7.6 payload does not carry; gaps become contract-change requests.

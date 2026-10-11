# Data Model: UI Live Integration (spec 007)

No backend data changes. The UI consumes the frozen PLAN.md §7.6 shapes (InvoiceDetail, list rows, health, stats, payments, vendors, audit) already typed in `web/src/lib/types.ts`. This spec adds one client type and the client-side state rules.

## ChangeCase (new client type, from `GET /api/change-cases[/{id}]`, spec 005 `_case_view`)

| Field | Type | Notes |
|---|---|---|
| `id` | string | `cc_…` |
| `account_ref` | `{id, name, source_ref}` | `name` is the counterparty shown |
| `requested_change` | `"billing_contact" \| "payment_details" \| "remit_address" \| "admin_contact" \| "other"` | shown as words ("billing contact") |
| `sender_email` | string | the requester, shown as is |
| `request_excerpt` | string | "≤ 500 chars" |
| `signals` | array (JSON) | rendered as a list of short labels; unknown shapes shown as text |
| `callback_target` | object \| null | not shown (spec 008 detail) |
| `status` | `"OPEN" \| "CALLING" \| "CONFIRMED" \| "DENIED" \| "UNCLEAR" \| "NO_ANSWER" \| "CLOSED"` | word + icon, never color alone |
| `created_by`, `created_at`, `updated_at`, `dataset_version`, `source_refs`, `idempotency_key` | various | `created_at` shown; the rest not displayed |
| `verification` | `{id, source, step, phone_masked, events[], final_label} \| null` | the callback summary; `source = simulated` shows the SIMULATED badge |

## Client state

| State | Where | Rule |
|---|---|---|
| Selected invoice (live) | `Layout` local state | set by queue click, Enter, or a successful "Load a sample"; cleared by Reset demo and by a 404 on the selected invoice |
| Selected invoice (fixtures) | URL `?scenario=&step=` | unchanged from spec 004 |
| Selected change case | `ChangeCases` local state | first case selected by default when the tab opens |
| Open tab | URL `?tab=` | unchanged; tab queries poll only while mounted |
| Theme | `localStorage` via `lib/theme.tsx` | light by default; persists (FR-022) |
| Last four for a simulated yes | `DemoTab` local state | default "4455"; digits only, 4 max |

## Polling (PLAN.md §14.9)

| Query | Key | Interval (live only) |
|---|---|---|
| Invoice list | `["invoices"]` | 2 s |
| Open invoice | `["invoice", id]` | 1 s until status is RELEASED, HELD or FAILED; then 5 s |
| Health | `["health"]` | 15 s |
| Stats, payments, vendors, audit, change cases | per tab | 2 s while the tab is open |

## Derived displays (unchanged rules, live inputs)

- **Decision sentence** (`lib/decide.ts`): one of the five §14.9 sentences. The held-by-vendor sentence takes its time from the last verification event, as `h:mm AM/PM` (research R9).
- **Actions**: from `actions` flags only (FR-009).
- **Field chips**: from `extracted.fields[*].source` and `mismatch` (FR-006).

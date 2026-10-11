# Contract: UI ↔ API in live mode (PLAN.md §7.6, §14.9)

Same-origin relative paths only (`/api/...`). In dev, Vite proxies `/api` to `http://localhost:8000`. In production, FastAPI serves `web/dist` (contracts/serving.md). Fixtures mode (`VITE_API_MODE=fixtures`) makes no `/api` request.

## Reads

| Hook | Route | Interval |
|---|---|---|
| `useInvoices` | `GET /api/invoices` | 2 s |
| `useInvoice(id)` | `GET /api/invoices/{id}` | 1 s, then 5 s once RELEASED/HELD/FAILED |
| `useHealth` | `GET /api/health` | 15 s |
| `useStats`, `usePayments`, `useVendors`, `useAudit(subject?)` | `/api/stats`, `/api/payments`, `/api/vendors`, `/api/audit` | 2 s while their tab is open |
| `useChangeCases`, `useChangeCase(id)` | `GET /api/change-cases`, `GET /api/change-cases/{id}` | 2 s while the DevRev tab is open |

Query errors never toast. The last good data stays on screen, and polling continues.

## Mutations (user actions only; each success invalidates every query)

| Action | Route | Success toast |
|---|---|---|
| Load a sample | `POST /api/invoices/from-sample {name}` | none (the new invoice is selected) |
| Approve payment / Reject | `POST /api/invoices/{id}/review {decision, note}` | "Payment approved" / "Invoice rejected" |
| Call vendor again | `POST /api/invoices/{id}/retry-callback` | "Calling the vendor again" |
| Try to make the AI pay | `POST /api/invoices/{id}/redteam` | none (a dialog shows the layer and reason; the trace sheet opens) |
| Reset demo | `POST /api/demo/reset {}` | "Demo reset" (and the selection clears) |
| AI live / off | `POST /api/demo/ai-mode {mode}` | "AI live" / "AI off (rules only)" |
| Vendor says yes / no | `POST /api/demo/simulate-answer {subject_id, answer, last4}` | "Simulated: vendor said yes/no" |

## Error copy (`lib/errors.ts`; §14.6: what happened, then what to do next)

| Status | Title | Description |
|---|---|---|
| 409 | That action isn't available for this invoice any more. | The case was updated; check the current status and try again. |
| 404 | That invoice no longer exists. | It was probably cleared by a demo reset. Pick another case. |
| 400 | The request was refused. | the API's `detail` |
| network / 5xx | Couldn't reach the server. | Check the connection; the dashboard keeps retrying. |

## Copy fixed by PLAN.md §14.6 and §14.9

- Empty case: "Load a sample invoice to start."
- AI chip: "AI: live" / "AI: off (rules only)".
- Callback number: "number on file (vendor master), not from the email".
- Analyst note label: "AI-written explanation; doesn't change the decision"; the fallback chip is "Rules fallback".
- Audit header: "Chain verified" only when `chain_ok`; otherwise it names `broken_at`.

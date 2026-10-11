# Contract: HTTP API and InvoiceDetail (PLAN.md §7.6, verbatim; copied from spec 003). Spec 005 implements every row.

Spec 005 owns `app/api.py`. Spec 003 needs this for `scripts/export_fixtures.py`, whose output must match the InvoiceDetail JSON exactly (tested by `tests/test_fixtures_contract.py`), and for the demo reset semantics.

| Method and path | Purpose | Notes |
|---|---|---|
| GET `/healthz` | liveness | `{"ok": true}`; no auth (Caddy route) |
| GET `/api/health` | header status dots | `{db, model:{ok,latency_ms,checked_at}, twilio:{configured}, storage:{ok}, demo_mode, ai_mode, deploy_label}`. `latency_ms` is the median of the last 10 real model calls in `agent_traces`. If there were none in the last 5 min, ping `GET /v1/models` instead, cached for 60 s. |
| GET `/api/samples` | sample buttons | `[{name,title,description}]` from `samples/manifest.json` |
| POST `/api/invoices/from-sample` | `{"name":"02_acme_fraud"}` | → `{"id"}` |
| POST `/api/invoices/upload` | multipart `file` (.eml, ≤ 1 MB) | → `{"id"}` |
| GET `/api/invoices` | list | `[{id, created_at, vendor_name, amount_display, tier, points, status, hold_reason, source}]`, newest first |
| GET `/api/invoices/{id}` | detail | the InvoiceDetail shape below |
| POST `/api/invoices/{id}/review` | `{"decision":"approve"\|"reject","note":""}` | 409 unless NEEDS_REVIEW |
| POST `/api/invoices/{id}/retry-callback` | retry | 409 unless HELD with UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED or VERIFIER_DISAGREED |
| POST `/api/invoices/{id}/redteam` | compromised-agent attempt | `{"blocked":bool,"layer":"plugin"\|"ledger"\|"agent_refused","reason":str,"run_id":str}`. **409 if `can_release` is currently true**, so a red-team run can never pay a payable invoice. |
| GET `/api/audit?subject_id=` | audit entries | `{"entries":[...], "chain_ok":bool, "broken_at":int\|null}`; without `subject_id`, the latest 200 |
| GET `/api/payments` | ledger | released payments (masked) plus held invoices summary |
| GET `/api/stats` | KPI strip (§14.8) | `{"released_cents", "held_cents", "invoices", "calls_placed", "median_decision_seconds"}` since the last reset |
| GET `/api/vendors` | vendor master | masked, plus `bank_history` |
| GET `/api/change-cases`, `/api/change-cases/{id}` | DevRev cases tab | |
| POST `/api/demo/reset` | DEMO_MODE | Wipes invoices, verifications, payments, traces and audit, reseeds vendors and history (which undoes Heartland's bank update), and restarts the audit chain with a `demo_reset` genesis event. **Keeps DevRev change cases** unless the body is `{"include_change_cases": true}`. |
| POST `/api/demo/simulate-answer` | DEMO_MODE | `{"subject_id","answer":"yes"\|"no","last4":"4455"\|null}` |
| POST `/api/demo/ai-mode` | DEMO_MODE | `{"mode":"live"\|"off"}` (runtime override of AI_MODE) |

InvoiceDetail (the UI depends on these exact keys):

```json
{
  "id": "inv_...", "status": "HELD", "hold_reason": "DENIED_BY_VENDOR", "source": "sample", "created_at": "...",
  "invoice_number": "INV-20447", "amount_cents": 4875000, "decided_at": "...",
  "email": {"from_name": "...", "from_email": "...", "reply_to": "...", "subject": "...", "received_at": "...", "body_text": "..."},
  "extracted": {"fields": {"routing_number": {"value": "061100059", "source": "both", "mismatch": false}, "...": {}},
                "phone_numbers_in_email": ["(816) 555-0142"], "llm_status": "ok"},
  "vendor": {"id": "ven_acme", "name": "Acme Supply Co.", "domains": ["acme-supply.com"],
             "phone_masked": "•••-•••-0199", "bank_masked": "Plains Federal Bank ••••4821",
             "history": [{"invoice_number": "INV-20412", "amount_cents": 1215000, "paid_on": "2026-09-15"}],
             "median_cents": 1202000},
  "risk": {"points": 160, "tier": "RED", "action": "CALLBACK", "sender_status": "LOOKALIKE", "amount_ratio": 4.06,
           "lookalike": {"sender_domain": "acme-supp1y.com", "known_domain": "acme-supply.com",
                         "diff": [{"index": 9, "sender": "1", "known": "l"}]},
           "flags": [{"code": "LOOKALIKE_DOMAIN", "points": 40, "title": "...", "detail": "...", "evidence": ["..."]}]},
  "destination": {"on_file": {"bank_name": "Plains Federal Bank", "routing": "123456780", "account_masked": "••••4821"},
                  "requested": {"bank_name": "First Coastal Trust", "routing": "061100059", "account_masked": "••••9942"},
                  "changed": true},
  "analyst": {"status": "done", "report": {"headline": "...", "explanation": "...", "cited_flags": ["..."],
              "additional_concerns": ["..."], "recommended_next_step": "..."}},
  "verification": {"id": "ver_...", "source": "twilio", "step": "done", "phone_masked": "•••-•••-0199",
                   "events": [{"ts": "...", "label": "Dialing", "detail": ""}],
                   "first_answer": {"channel": "speech", "digits": null, "speech": "No, we never changed banks",
                                    "confidence": 0.93, "det_label": "NO", "llm_label": "DENIED"},
                   "last4_ok": null, "final_label": "DENIED"},
  "payment": null,
  "memo": {"text": "...", "by": "agent"},
  "trace": [{"ts": "...", "agent": "payments", "kind": "guard_block", "name": "release_payment",
             "summary": "BLOCKED: invoice is HELD (vendor denied the change)", "duration_ms": 3}],
  "audit": [{"seq": 41, "ts": "...", "actor": "twilio", "event": "answer_received", "summary": "...", "hash_short": "9f3a1c"}],
  "actions": {"can_review": false, "can_retry_call": false, "can_simulate": false, "can_redteam": true},
  "ai_fallback": false
}
```

Spec 005 addition (FR-025): `/api/health` → `model.provider` is `"akamai"` or `"bedrock"`, whichever answered the most recent model call. It is an extra key; clients that ignore it are unaffected.

Notes on the newer fields:
- `vendor.history` holds the vendor's last six paid invoices, oldest first. It is empty when no vendor was resolved.
- `risk.lookalike` is null unless the sender status is LOOKALIKE.
- `destination.requested` is null when the email has no bank details.
- Routing numbers are public bank identifiers and are shown in full; account numbers are always masked.
- These fields feed the gallery candidates in §14.8.

Rules for `actions`, computed server-side:
- `can_review`: status is NEEDS_REVIEW.
- `can_retry_call`: status is HELD with a retryable hold reason (§7.3).
- `can_simulate`: DEMO_MODE, and either status is CALL_PENDING or CALLING, or `can_retry_call` is true.
- `can_redteam`: the invoice has been scored and `can_release` is false.

---

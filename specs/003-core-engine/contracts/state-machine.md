# Contract: status machine (PLAN.md §7.3, verbatim)

```
Status: RECEIVED, EXTRACTED, SCORED, AUTO_APPROVED, NEEDS_REVIEW, REVIEW_APPROVED,
        CALL_PENDING, CALLING, VERIFYING, CONFIRMED, RELEASED, HELD, FAILED

HoldReason: DENIED_BY_VENDOR, UNCLEAR_ANSWER, NO_ANSWER, LAST4_MISMATCH, VERIFIER_DISAGREED,
            REVIEW_REJECTED, UNKNOWN_VENDOR, CALL_FAILED, AGENT_HOLD
```

| From | Allowed to |
|---|---|
| RECEIVED | EXTRACTED, FAILED |
| EXTRACTED | SCORED, FAILED |
| SCORED | AUTO_APPROVED, NEEDS_REVIEW, CALL_PENDING, HELD (only UNKNOWN_VENDOR) |
| AUTO_APPROVED | RELEASED, HELD (AGENT_HOLD) |
| NEEDS_REVIEW | REVIEW_APPROVED, HELD (REVIEW_REJECTED) |
| REVIEW_APPROVED | RELEASED, HELD (AGENT_HOLD) |
| CALL_PENDING | CALLING, HELD (CALL_FAILED) |
| CALLING | VERIFYING, CONFIRMED, HELD (DENIED_BY_VENDOR, UNCLEAR_ANSWER, NO_ANSWER, LAST4_MISMATCH) |
| VERIFYING | CONFIRMED, HELD (VERIFIER_DISAGREED, UNCLEAR_ANSWER) |
| CONFIRMED | RELEASED, HELD (AGENT_HOLD) |
| HELD | CALL_PENDING (retry, only when hold_reason ∈ {UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED, VERIFIER_DISAGREED}) |
| RELEASED, FAILED | terminal (DEMO reset wipes everything) |

```python
def transition(invoice_id: str, to: Status, *, hold_reason: HoldReason | None = None,
               actor: str, detail: dict | None = None) -> bool:
    """Atomic compare-and-set.
    UPDATE invoices SET status=?, hold_reason=?, version=version+1, updated_at=?
     WHERE id=? AND status IN (<legal from-states for `to`>)
    Returns True if the row changed and writes an audit 'status_changed' event.
    Returns False if the invoice is already in `to` (idempotent no-op; webhooks retry).
    Raises IllegalTransition otherwise.
    HELD requires hold_reason, and hold_reason must be allowed for the from-state.
    The UPDATE and its audit event commit in one `BEGIN IMMEDIATE` transaction."""
```

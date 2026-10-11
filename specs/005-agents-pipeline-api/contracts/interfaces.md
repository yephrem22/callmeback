# Contract: cross-workstream interfaces (PLAN.md §7.5, verbatim; copied from spec 003)

Spec 003 implements `ledger.can_release/release/hold/apply_vendor_bank_change` and `state.transition`. The `pipeline.*` and `voice.*` functions below belong to specs 005 and 006; they are listed so the ledger, the verification rows and the fixtures exporter line up with them.

`app/pipeline.py` (owner A) exposes these for the voice routes (owner B):

```python
def request_callback(subject_id: str, kind: Literal["invoice", "change_case"]) -> str:
    """Supersedes any active verification for the subject (see §12.5), creates the verification row +
    URL token, calls voice.place_call(), stores call_sid, and moves the invoice CALL_PENDING → CALLING.
    On any exception: HELD(CALL_FAILED). Returns verification_id."""

def get_call_context(verification_id: str) -> CallContext
def on_call_status(verification_id: str, call_status: str) -> None
    # call_status: Twilio CallStatus: queued|initiated|ringing|in-progress|completed|busy|no-answer|failed|canceled
def on_first_answer(verification_id: str, digits: str | None, speech: str | None,
                    confidence: float | None) -> Literal["ASK_LAST4", "DENIED", "REPROMPT", "UNCLEAR", "CONFIRMED_NO_LAST4"]
def on_last4(verification_id: str, digits: str | None) -> Literal["CONFIRMED", "MISMATCH", "NO_INPUT"]
def simulate_answer(subject_id: str, answer: Literal["yes", "no"], last4: str | None) -> None   # DEMO_MODE only
```

`app/voice/` (owner B) exposes these for the pipeline:

```python
def place_call(verification_id: str, token: str, to_e164: str) -> str     # returns Twilio call SID
def cancel_call(call_sid: str) -> None      # best effort: calls(sid).update(status="completed"); never raises
def classify_answer(digits: str | None, speech: str | None) -> Literal["YES", "NO", "UNCLEAR"]   # pure; voice/classify.py
def new_token() -> tuple[str, str]                                      # (token, sha256_hex)
```

Internal API (owner B), called by the MCP service over the Docker network with header `Authorization: Bearer $INTERNAL_TOKEN`. Caddy returns 404 for `/internal/*` from outside.

```
POST /internal/change-cases
  body: {idempotency_key, account_ref:{id,name,source_ref}, requested_change, sender_email,
         request_excerpt, signals:[...], callback_target:{...}|null, source_refs:[...], dataset_version}
  201 → {"case_id","status":"OPEN","duplicate":false,"dashboard_path":"/#/cases/cc_..."}
  200 → same shape with "duplicate":true when idempotency_key already exists (returns the existing case)
GET  /internal/change-cases/{case_id} → {"case_id","status","outcome","call":{...}|null,"updated_at"}
POST /internal/change-cases/{case_id}/call   (P2) → places a sandbox call to DEMO_VENDOR_PHONE
```

# Contract: cross-workstream interfaces (PLAN.md §7.5, verbatim)

Spec 006 implements the `app/voice/` half and consumes the `app/pipeline.py` half, which spec 005 implemented (merged at 451ac4b). Frozen: change only with both builders' agreement (PLAN.md §7).

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

## Where each lives (spec 006)

| Function | Module | Notes |
|---|---|---|
| `place_call`, `cancel_call` | `app/voice/twilio_client.py` | PLAN.md §12.1; reached by the pipeline through `app/voice_port.py` |
| `classify_answer` | `app/voice/classify.py` | PLAN.md §12.4; reached through `app/voice_port.py` |
| `new_token` | `app/voice/tokens.py` | re-exports `app.verifications.new_token` (spec 003), which `verifications.create` already uses |

The internal change-case API listed after these in §7.5 belongs to spec 008, not this spec.

## Pipeline changes this spec makes (owner A agreed; same session)

- `question_text(ctx)` returns `app.voice.twiml.q1_text(ctx)` (research R10). Signature unchanged.
- `on_call_status` writes a timeline event only when the step advances (research R5). Signature and transitions unchanged.

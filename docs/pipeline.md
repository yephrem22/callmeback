# Pipeline, agents and API (spec 005)

Hand-off notes for spec 006 (voice) and spec 007 (deploy and UI wiring). Contracts: `specs/005-agents-pipeline-api/contracts/`.

## Entry points spec 006 calls (`app/pipeline.py`, PLAN.md §7.5)

| Function | When | Returns |
|---|---|---|
| `request_callback(subject_id, kind)` | the pipeline calls it for CALL_PENDING; also retry | `verification_id` |
| `get_call_context(verification_id)` | `/twilio/voice/{token}` builds the TwiML | `CallContext` |
| `on_first_answer(ver_id, digits, speech, confidence)` | Q1 gather | `ASK_LAST4` / `DENIED` / `REPROMPT` / `UNCLEAR` / `CONFIRMED_NO_LAST4` |
| `on_last4(ver_id, digits)` | Q2 gather | `CONFIRMED` / `MISMATCH` / `NO_INPUT` |
| `on_call_status(ver_id, call_status)` | status callback | — (`completed` is checked again after 3 s) |

- Every handler is idempotent. A finished, superseded or expired verification returns the earlier decision and changes nothing, so duplicate webhooks are harmless.
- Voice goes through `app/voice_port.py` only. It imports `app.voice.twilio_client.place_call/cancel_call` and `app.voice.classify.classify_answer` once they exist. Until then `place_call` raises (→ HELD/CALL_FAILED, which is retryable), and speech classifies as UNCLEAR.
- A spoken answer starts the Verifier, which can only downgrade a YES. Keypad answers never wait for it.
- `VOICE_MODE=simulated` places no call, and the demo answers via `simulate_answer`. Every audit entry from a simulated line carries `"simulated": true`.

## API surface spec 007 uses (`app/api.py`, PLAN.md §7.6)

- Every §7.6 row is implemented under `/api`. The InvoiceDetail key set is pinned by `tests/test_invoice_detail_shape.py`.
- Errors: 409 for illegal transitions, the review/retry/red-team/simulate rules and `PolicyViolation`; 400 for bad input or uploads; 404 for unknown ids and for every `/api/demo/*` route when `DEMO_MODE=0`.
- `/api/health` adds `model.provider` (`akamai` | `bedrock`). Storage is checked from configuration only, with no network call per poll.
- `main.py` mounts the router before the static `web/dist` mount. There is no SPA fallback; that belongs to spec 007.
- Logs are JSON lines on stdout (`app/logging_setup.py`), and every field passes through `masking.masked`.

## Executors and the deadlock rule (`app/executors.py`)

- `JOBS` (8 workers) runs pipeline jobs, the Payments agent, `await_verifier` and `start_agent` waits. `AGENTS` (4 workers) runs only the model loop.
- **Never wait on AGENTS from an AGENTS thread.** `run_agent` raises if called there. To run an agent without blocking, use `start_agent(..., on_done=...)`.
- Tests use `use_inline_executors()`, which is the default in `tests/conftest.py`. `wait_idle()` keeps background threads from outliving a test.
- SQLite: every write runs in autocommit or `db.tx()` (BEGIN IMMEDIATE). Never write on a second connection while holding `db.tx()` on the first: that is a self-deadlock. `audit.append(conn=c)` joins the caller's transaction.

## How to add an agent

1. Make a module in `app/agents/`. Build `Agent(model=model_factory.make_model(N), system_prompt=..., tools=..., plugins=[TracePlugin(subject, name, ctx.run_id), RateLimitPlugin()], name=..., **agent_kwargs())`. Add `PaymentGuardPlugin` if the agent can move money.
2. Bind tools to one subject by closure, with no id parameter the model could change. Call `ctx.check()` first so a timed-out run cannot act. Mask everything a tool returns.
3. Call it with `cancel_signal=ctx.cancel`, plus `structured_output_model=` for typed output. Validators re-ask on bad output.
4. Run it via `run_agent(name, subject_id, fn, timeout_s, fallback)`, with a deterministic `fallback` in `app/agents/fallbacks.py`. AI off, timeouts and errors all land there and are traced and audited.
5. Add the agent name to `traces.AGENTS` and its audit actor to `audit.ACTORS`. Test it with `tests/fakes.py` (`ScriptedModel`, `fake_models`).

Providers: Akamai is the default for every call. With `LLM_FALLBACK=bedrock`, a provider error (connection, 5xx, or a 429 after retries) is retried once on Bedrock within the same time budget. A validation error is never retried on Bedrock (FR-025).

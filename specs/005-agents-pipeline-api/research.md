# Research: AI Agents, Pipeline and API (spec 005)

PLAN.md §11 tells us to "check the constructor's parameters in the installed version". We did, against `strands-agents[openai]==1.59.0` (openai 2.54.0, mcp 2.1.1). Each item: decision, rationale, alternatives.

## R1. Strands 1.59.0: what PLAN.md §11 gets right and the two places it doesn't

Verified by introspection (`inspect.signature`, dataclass fields, source):

| PLAN.md says | Installed 1.59.0 | Consequence |
|---|---|---|
| `OpenAIModel(client_args=..., model_id=..., params=...)` | same | as written |
| "the Strands config key is `streaming`, not `stream`" | **the key is `stream`**: `OpenAIConfig` has `context_window_limit, model_id, params, stream, cache_config`; `format_request` reads `self.config.get("stream", params.pop("stream", True))`, default **True** | Passing `streaming=False` is silently ignored and streaming stays on. `make_model()` passes `stream=` |
| `from strands.plugins import Plugin, hook`; `Agent(plugins=[...])` | present | as written |
| `class PaymentGuardPlugin(Plugin): def __init__(self, invoice_id): self.invoice_id = invoice_id` | `Plugin.__init__` discovers `@hook` methods into `self._hooks` | Without `super().__init__()` the guard hook is **never registered**. Every plugin calls `super().__init__()` |
| `BeforeToolCallEvent.cancel_tool` | field present (`agent, selected_tool, tool_use, invocation_state, cancel_tool`) | as written |
| `AfterModelCallEvent.retry`, `.exception` | present (`agent, invocation_state, stop_response, exception, retry`) | rate-limit plugin as written |
| `BeforeInvocationEvent`, `AfterInvocationEvent.result` | present | trace plugin as written |
| `AfterToolCallEvent.result` | present, plus `exception`, `duration`, `retry` | trace rows take `duration` from the event |
| `SequentialToolExecutor` at `strands.tools.executors` | present | as written |
| `StructuredOutputException` at `strands.types.exceptions` | present | as written |
| `agent(prompt, structured_output_model=Model)` then `result.structured_output` | `Agent.__call__(prompt, ..., structured_output_model, ...)`; `AgentResult.structured_output` | as written |
| fake model = subclass of `strands.models.Model` with `stream()` | abstract methods `get_config, stream, structured_output, update_config` | the fake implements all four |
| `BedrockModel` for the P2 fallback | `strands.models.BedrockModel` importable | as written |

- **Decision**: follow PLAN.md §11 except the two rows marked; record both in `docs/decisions.md` so the other builders don't copy the bug from PLAN.md.
- **Rationale**: PLAN.md's intent (streaming off by default; the guard must run) is preserved; only the spelling of the mechanism changes. Not a §7 contract change.

## R2. Akamai inference endpoint

- **Decision**: `OpenAIModel(client_args={"api_key", "base_url": AKAMAI_BASE_URL, "timeout": 30.0, "max_retries": 1}, model_id=MODEL_ID, params={"max_tokens", "temperature": 0.1}, stream=S.llm_streaming)`.
- **Facts verified live (2026-10-10)**: `GET /v1/models` lists `hackathon-chat`, `hackathon-embedding`, `hackathon-image`; a 5-token completion answers in 0.4–0.9 s; responses carry `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset` (seconds).
- **Smoke test result (phase 1, `docs/llm_smoke.md`)**: structured output 3/3; tool calls 5/5 with `stream=False` and 5/5 with `stream=True`; decision **stream off** (`LLM_STREAMING=0`, PLAN.md's default on a tie). No `<think>` blocks.
- **Gateway finding**: the Akamai endpoint rejects `"tools": []` with HTTP 400 ("`tools` must not be an empty array"). Strands 1.59.0 always sends the field, so any agent call with no tools and no structured output failed. Fix: `app/agents/model.py::AkamaiModel` overrides `format_request` to drop `tools`/`tool_choice` when empty. Structured output was unaffected because Strands adds an output tool.
- **Latency**: varies several-fold between runs on the shared endpoint (a plain completion took 0.5 s once and 6.6 s later). The default per-agent timeouts keep headroom.

## R3. Structured output and the anti-hallucination validator

- **Decision**: `make_extraction_model(body_text)` builds a subclass of `InvoiceExtraction` with a `@field_validator` on `routing_number`, `account_number`, `amount` that raises `ValueError("<field> '<value>' does not appear in the email; copy it exactly or return null")` unless the value's digits (spaces and dashes removed) appear in the normalised body. Strands returns validation errors to the model and re-asks; a final `StructuredOutputException` falls back to the regex values. Same pattern for `AnalystReport.cited_flags ⊆ finding codes`.
- **Rationale**: PLAN.md §11.4; "our schema refuses invented digits".

## R4. Fake models for tests (no network in pytest)

- **Decision**: `tests/fakes.py` provides `ScriptedModel(Model)`: a list of turns, each either text or a tool use `{name, input}`; `stream()` yields the Strands stream events for that turn; `structured_output()` validates a scripted dict into the requested model; `get_config/update_config` are trivial. Plus `SlowModel` (sleeps) and `FailingModel` (raises) for timeout and fallback tests.
- **Rationale**: PLAN.md §11.5 and constitution V/VIII. If emitting a tool use from `stream()` proves fiddly, the red-team test uses `agent.tool.release_payment()` (PLAN.md allows this); either way it asserts no payment row.

## R5. Executors and the deadlock rule

- **Decision**: `app/executors.py` owns `JOBS = ThreadPoolExecutor(8, thread_name_prefix="jobs")` and `AGENTS = ThreadPoolExecutor(4, thread_name_prefix="agents")`, and `app/pipeline.py` re-exports them (analyze A1: this avoids a pipeline ↔ runner import cycle while keeping "two executors, nothing else spawns threads"). `run_agent()` asserts it is not running on an `agents-` thread before waiting on an AGENTS future; `start_agent()` submits to JOBS. Tests can swap both for a synchronous executor (`use_inline_executors()`) so flows are deterministic.
- **Timeouts free their thread (analyze C2)**: a timed-out run's `threading.Event` is passed to Strands as `cancel_signal` and checked by every closure-bound tool, so a late run stops instead of acting after its fallback, and only 4 agent threads can never all be held by stuck runs.
- **One retry policy (analyze C1)**: Strands 1.59.0 agents default to `ModelRetryStrategy(max_attempts=6, initial_delay=4, max_delay=240)` on `ModelThrottledException`. Every agent passes `retry_strategy=None`, and `RateLimitPlugin` is the only retry policy (at most 3, honouring `x-ratelimit-reset` from the exception's cause).
- **Rationale**: PLAN.md §6; a runtime assert turns a deadlock into a loud error.

## R6. Voice functions before spec 006 lands

- **Decision**: `app/voice_port.py` is the only place the pipeline touches voice. It imports `place_call`, `cancel_call` from `app.voice.twilio_client` and `classify_answer` from `app.voice.classify` when those modules exist (spec 006); until then it provides stubs: `place_call` raises `RuntimeError("voice not available")` (→ HELD(CALL_FAILED), which is retryable), `cancel_call` no-ops, and `classify_answer` handles keypad digits exactly per PLAN.md §12.4 (1 → YES, 2 → NO, else UNCLEAR) and returns UNCLEAR for any speech (fail closed). `new_token` comes from `app.verifications.new_token` (spec 003). With `VOICE_MODE=simulated` no call is placed at all (PLAN.md §12.6).
- **Rationale**: PLAN.md §6 gives `app/voice/` to spec 006; this spec must not create files there. The stub is strictly more cautious than the real classifier.

## R7. API style

- **Decision**: `app/api.py` is an `APIRouter(prefix="/api")` of plain `def` handlers (PLAN.md §6), mounted in `app/main.py` before the static mount. Uploads use `UploadFile` (python-multipart). Errors map: `IllegalTransition` → 409, `PolicyViolation` → 409, `ValueError` from parsing → 400, unknown id → 404. `GET /api/invoices/{id}` returns `repo.invoice_detail()` (spec 003), so the API and the fixtures share one serializer.
- **Health latency**: median `duration_ms` of the last 10 `model_call` trace rows within 5 minutes; otherwise a cached (60 s) `GET /v1/models` ping timed with httpx; `model.ok=false` when AI is off or the ping fails.

## R8. Logging

- **Decision**: `app/logging_setup.py` configures one JSON object per line on stdout (`ts, level, logger, msg, …`), with `masking.masked` applied to any `extra` dict. Called from `app/main.py`. No `print` in app code (PLAN.md §6).

## R9. Direct tool calls and the guard

- **Open question, settled in phase 2 by a test**: whether `BeforeToolCallEvent` hooks fire for `agent.tool.release_payment()` in 1.59.0 (`record_direct_tool_call` exists on `Agent`). Either way the ledger raises `PolicyViolation`, so the red-team result reports `layer: "ledger"` if the plugin did not fire. The test asserts the layer actually observed and that no payment exists.

## R10. Runtime AI mode

- **Decision**: `app/ai_mode.py` holds the effective mode: `S.ai_mode` at start, overridable by `POST /api/demo/ai-mode` (DEMO_MODE only), read by `run_agent` at the start of every run; changes write `ai_mode_changed`. Phase 1's smoke test is the gate for setting `AI_MODE=live` in `.env`.

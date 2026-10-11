---

description: "Task list for spec 005: AI agents, pipeline and API"
---

# Tasks: AI Agents, Pipeline and API

**Input**: Design documents from `specs/005-agents-pipeline-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (interfaces.md, http-api.md, agents.md), quickstart.md

**Tests**: Requested by the spec (FR-026, SC-009) and the constitution (VIII). Within each section the tests are written first and must fail before the implementation lands. Every unit test runs with `AI_MODE=off`, fake Strands models (`tests/fakes.py`) and no network; live model checks exist only in `scripts/llm_smoke.py`.

**Organization**: The phases follow plan.md "Phases" exactly. Phase 1 (setup and the smoke-test gate) is complete. Phase 2 is the agent runtime: a foundational block that everything depends on, then the four agents and the red-team runner. Phase 3 is User Story 1 (the pipeline, MVP). Phase 4 is User Story 4 (the HTTP API). Phase 5 is User Story 5 (P3) plus polish and hand-off. Each phase ends with a checkpoint: stop and report (constitution X).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US5 from spec.md; setup, foundational and polish tasks carry no label
- Every task names its file path

## Path Conventions

Single Python project at the repository root (plan.md): `app/`, `app/agents/`, `scripts/`, `tests/`, `docs/`. Rules carried from earlier phases and the analyze pass:

- Never create files under `app/voice/` (spec 006 owns it); the pipeline reaches voice only through `app/voice_port.py`.
- Never edit the frozen §7 files `app/schema.sql`, `app/models.py`, `app/state.py`.
- The two thread pools live in `app/executors.py` and are re-exported by `app/pipeline.py` (analyze A1).
- Scoring is never duplicated: `app/engine.py::score_invoice` is extended, not copied (analyze A2).
- The SPA fallback to `index.html` belongs to spec 007, not this spec (analyze A3).
- Strands 1.59.0: the streaming key is `stream`; every Plugin calls `super().__init__()`; `AkamaiModel` drops an empty `tools` array (research R1, R2; `docs/decisions.md`).

---

## Phase 1: Setup and the smoke-test gate (milestone A2) ✅ complete (a829d23)

**Purpose**: install Strands, build the model factory, and measure the live endpoint before any agent code depends on it.

- [x] T001 Add `strands-agents[openai]==1.59.0` to `requirements.txt` and reinstall into `.venv`
- [x] T002 [P] Create `app/agents/__init__.py` and `app/agents/model.py`: `make_model(max_tokens=1200, *, stream=None)` returning `AkamaiModel(client_args={"api_key", "base_url", "timeout": 30.0, "max_retries": 1}, model_id=S.model_id, params={"max_tokens": max_tokens, "temperature": 0.1}, stream=S.llm_streaming)`, where `AkamaiModel(OpenAIModel)` overrides `format_request` to drop `tools`/`tool_choice` when empty; plus `model_settings()` (non-secret)
- [x] T003 [P] Create `tests/test_llm_model.py`: `stream` key set from `LLM_STREAMING` and never `streaming`; explicit override wins; `params` and `model_id`; empty tools omitted from the request; tools kept when present; no secret in `model_settings()`
- [x] T004 Create `scripts/llm_smoke.py` (`python -m scripts.llm_smoke`): plain completion; 3 structured outputs; 5 tool calls with `stream=False` and 5 with `stream=True`; p50 latency per row; PLAN.md §11.1 decision rules; `<think>` check; prints only the key length
- [x] T005 Run the smoke test live, commit `docs/llm_smoke.md` (stream off, all checks pass), and record the decision and the three Strands/Akamai notes in `docs/decisions.md`

**Checkpoint**: report committed; `LLM_STREAMING=0`, `AI_MODE=live` recommended.

---

## Phase 2: Agent runtime

### 2A. Foundational (blocking prerequisites for every story)

**Purpose**: thread pools, traces, AI mode, the three plugins, the time-boxed runner, the rules fallbacks, and the fake models. No agent or pipeline work begins until this block's tests pass.

#### Tests for the foundational block (write first)

- [x] T006 [P] Create `tests/fakes.py` (research R4): `ScriptedModel(turns)` subclassing `strands.models.Model` and implementing all four abstract methods `get_config`, `stream`, `structured_output`, `update_config`; turn helpers `text_turn(text)`, `tool_turn(name, input)`, `structured_turn(data)`; `SlowModel(seconds)` that sleeps before answering; `FailingModel(exc)` that raises; a pytest fixture `fake_model(monkeypatch)` that patches `app.agents.model.make_model` to return a given fake
- [x] T007 [P] Create `tests/test_runner.py`: with AI off, `run_agent` returns the fallback without touching the model and writes a `fallback` trace row with summary "AI off"; `SlowModel` past the timeout returns the fallback, writes a `fallback` trace row, sets `invoices.ai_fallback = 1` and writes audit `ai_fallback`; the fallback is returned within `timeout_s + 1` seconds (SC-006, analyze E1); on timeout the run's cancel event is set and the timed-out run stops and frees its AGENTS thread within a few seconds, with no tool call after the timeout (analyze C2); a late result after the timeout is discarded and changes nothing; an exception falls back; `StructuredOutputException` falls back; calling `run_agent` from a thread named `agents-*` raises `RuntimeError`; `start_agent` runs on JOBS and calls `on_done(result, outcome)`
- [x] T008 [P] Create `tests/test_plugins.py`: `PaymentGuardPlugin("inv_x").hooks` is non-empty (proves `super().__init__()` ran); on an ineligible invoice the guard sets `event.cancel_tool` to text starting "BLOCKED by payment policy:" and writes trace `guard_block` plus audit `guard_blocked` with actor `plugin:payment-guard`; on an eligible invoice it writes `guard_allow` plus `guard_allowed` and leaves `cancel_tool` unset; tools other than `release_payment` are ignored; `TracePlugin` writes `run_start`, `model_call`, `tool_call`, `run_end` in order for a scripted run with masked summaries ≤ 200 chars; `RateLimitPlugin` sets `retry = True` at most 3 times per invocation for a `ModelThrottledException` (and for a plain 429-like exception) and then stops, sleeping for the `x-ratelimit-reset` value read from the exception's `__cause__.response.headers` (default 5 s); every agent built by `app/agents/` has Strands' built-in retries disabled (`retry_strategy=None`) so the plugin is the only retry policy (analyze C1)

#### Implementation for the foundational block

- [x] T009 [P] Create `app/executors.py` (research R5, analyze A1): `JOBS = ThreadPoolExecutor(max_workers=8, thread_name_prefix="jobs")`, `AGENTS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agents")`, `use_inline_executors()` (synchronous executors for tests), `use_thread_executors()` (restore real pools), `on_agents_thread() -> bool`; these are the only thread pools in the app (PLAN.md §6)
- [x] T010 [P] Create `app/traces.py` per data-model.md: `write(subject_id, *, run_id, agent, kind, name=None, summary=None, duration_ms=None, conn=None)` where `agent` ∈ {`intake`, `analyst`, `verifier`, `payments`, `payments:redteam`}, `kind` ∈ {`run_start`, `model_call`, `tool_call`, `guard_allow`, `guard_block`, `run_end`, `fallback`, `error`} (ValueError otherwise), and `summary` is "≤ 200 chars, passed through `masking.masked`"; `recent_model_latencies(within_s=300, limit=10)`; `new_run_id()` returning "`run_` + 10 hex"
- [x] T011 [P] Create `app/ai_mode.py` (research R10): `effective_ai_mode() -> "live" | "off"` (runtime override if set, else `S.ai_mode`), `set_ai_mode(mode, actor="demo")` writing audit `ai_mode_changed`, `reset_override()`
- [x] T012 Create `app/agents/plugins.py` per contracts/agents.md, each class calling `super().__init__()` (research R1): `PaymentGuardPlugin(invoice_id)` with `name = "payment-guard"` and `@hook def guard(self, event: BeforeToolCallEvent)` exactly as PLAN.md §11.3; `TracePlugin(subject_id, agent, run_id)` with hooks on `BeforeInvocationEvent` → `run_start`, `BeforeModelCallEvent`/`AfterModelCallEvent` → `model_call` (duration, exception text), `BeforeToolCallEvent`/`AfterToolCallEvent` → `tool_call` (tool name, masked input summary, `event.result["status"]`, duration), `AfterInvocationEvent` → `run_end` (token usage from `event.result.metrics` when present); `RateLimitPlugin()` with a process-wide token bucket of `S.llm_rpm` per 60 s taken on `BeforeModelCallEvent`, and on `AfterModelCallEvent` with a `ModelThrottledException` (or any 429 / "rate limit" exception) sleep the `x-ratelimit-reset` seconds found on `exception.__cause__.response.headers` (default 5) and set `event.retry = True`, at most 3 times per invocation (counter in `invocation_state`). Also add `agent_kwargs()` returning the shared constructor arguments every agent uses: `tool_executor=SequentialToolExecutor()`, `callback_handler=None`, and `retry_strategy=None`, because Strands 1.59.0's default `ModelRetryStrategy` retries throttling up to 6 attempts with 4 s to 240 s backoff, which would double the plugin's retries and outlast every timeout (analyze C1). Depends on T010.
- [x] T013 Create `app/agents/runner.py` per contracts/agents.md: `run_agent(agent_name, subject_id, fn, timeout_s, fallback) -> (result, "result" | "fallback")` that checks `effective_ai_mode()` at the start of every run, creates a `RunContext(run_id, cancel: threading.Event)`, submits `fn(ctx)` to `executors.AGENTS`, waits `future.result(timeout_s)`, and on timeout sets `ctx.cancel` (agents pass it as Strands' `cancel_signal=` when invoking, and closure-bound tools refuse to act once it is set, so a late run stops and frees its thread instead of acting after the fallback; analyze C2); on timeout, exception or `StructuredOutputException` writes trace `fallback` with the reason, sets `invoices.ai_fallback = 1` when the subject is an invoice, writes audit `ai_fallback`, and returns `fallback()` within `timeout_s + 1` seconds; refuses to run on an `agents-*` thread (deadlock rule); `start_agent(..., on_done)` submits the same to `executors.JOBS`. Depends on T009, T010, T011.
- [x] T014 [P] Create `app/agents/fallbacks.py`: `analyst_fallback(risk) -> AnalystReport` (headline from the tier, explanation joining the flag titles, `cited_flags` = the weighted flag codes, next step from the action); `verifier_fallback() -> VerifierLabel(label="UNCLEAR", rationale=...)`; `payments_memo(invoice, released, reason) -> str` (two sentences); stored shapes are `analyst` = `{"status": "pending"|"done"|"fallback"|"error", "report": AnalystReport|null}` and `memo` = `{"text": str, "by": "agent"|"fallback"}` (data-model.md)

**Checkpoint (2A)**: `tests/test_runner.py` and `tests/test_plugins.py` pass; the full suite stays green.

### 2B. The four agents and the red-team runner (US1, US2, US3)

**Goal**: each agent works in its lane on fake models; the guard blocks every ineligible release; every agent falls back to rules.

**Independent Test**: `pytest -q tests/test_extraction_validator.py tests/test_agents.py tests/test_redteam.py` passes with no network; no test creates a payment row on an ineligible invoice.

#### Tests (write first)

- [ ] T015 [P] [US3] Create `tests/test_extraction_validator.py` (PLAN.md §17.1): a routing number absent from the body is rejected with a message containing "does not appear in the email; copy it exactly or return null"; one present is accepted; the same for account number and amount; digits split by spaces or dashes in the body still match; `None` is accepted
- [ ] T016 [P] [US2] Create `tests/test_redteam.py` (PLAN.md §17.1, spec US2): a scripted model that always calls `release_payment` on a HELD fraud invoice → `{"blocked": true, "layer": "plugin"}`, a `guard_block` trace row, no payment row; a scripted model that calls no tool → the one direct attempt is blocked and the layer actually observed is reported, no payment row; AI off → direct attempt only, blocked; a releasable invoice → `RedteamRefused` with no traces and no audit rows; two runs in a row → still zero payment rows
- [ ] T017 [P] [US1] Create `tests/test_agents.py` with fakes: Intake returns a valid extraction; Intake that keeps inventing digits falls back to the regex values with `llm_status="fallback"`; an Analyst citing an unknown flag code is rejected and falls back to the template; the Analyst fallback headline comes from the tier and the explanation from the flag titles; a headline over 12 words or an explanation over 90 words is truncated, not rejected; the Verifier returns the scripted label and falls back to UNCLEAR; Payments on an AUTO_APPROVED `01_acme_normal` calls the case summary then release → one payment row, RELEASED, memo `by="agent"`; Payments choosing hold on an eligible invoice → HELD with AGENT_HOLD; Payments ending with no tool call → policy fallback releases with `released_by="policy:auto"`

#### Implementation

- [ ] T018 [P] [US1] Create `app/agents/intake_agent.py` (research R3, PLAN.md §11.4): `make_extraction_model(body_text)` subclassing `InvoiceExtraction` with a `@field_validator` on `routing_number`, `account_number` and `amount` that raises `ValueError("<field> '<value>' does not appear in the email; copy it exactly or return null")` unless the value's digits appear in the body with spaces and dashes removed; `run_intake(invoice_id, run_id, parsed) -> InvoiceExtraction` building a fresh `Agent(model=make_model(800), system_prompt=<§11.4 Intake text>, tools=[], plugins=[TracePlugin(...), RateLimitPlugin()], tool_executor=SequentialToolExecutor(), callback_handler=None, name="intake")` and calling it on the headers plus the body in `<email>…</email>` (truncated to 8,000 characters; the only agent that sees raw digits) with `structured_output_model=Model`
- [ ] T019 [P] [US1] Create `app/agents/analyst.py` (PLAN.md §11.4): closure-bound `@tool`s `get_policy_findings`, `get_vendor_record` (masked), `get_vendor_history` (last 6 amounts plus the median), `get_email_excerpt` (headers plus the first 2,000 characters in `<email>` tags, account digits masked); `make_report_model(codes)` enforcing "`cited_flags ⊆ {f.code for f in risk.flags}`" (ValueError otherwise) and "`headline` ≤ 12 words, `explanation` ≤ 90 words (truncated, not rejected, beyond that)"; `run_analyst(invoice_id, run_id, *, no_tools=False)` with `max_tokens=900`, where `no_tools=True` injects the findings into the prompt and passes no tools (the documented fallback if tool calls prove unreliable)
- [ ] T020 [P] [US1] Create `app/agents/verifier.py` (PLAN.md §11.4): `run_verifier(subject_id, run_id, question, transcript) -> VerifierLabel` with no tools, `max_tokens=200`, the §11.4 system prompt verbatim, and structured output where "`label ∈ {CONFIRMED, DENIED, UNCLEAR}`"; the caller only lets it downgrade a deterministic YES (§12.5)
- [ ] T021 [US2] Create `app/agents/payments.py` (PLAN.md §11.4, FR-006): `make_payment_tools(invoice_id)` returning exactly three closure-bound tools: `get_case_summary` (`{status, tier, flags, verification_final_label, amount, destination_masked, release_eligible, eligibility_reason}`), `release_payment` (calls `ledger.release(invoice_id, by="agent:payments")`; on `PolicyViolation` returns "blocked: <reason>"), `hold_payment(reason)` (calls `ledger.hold`); `build_payments_agent(invoice_id, run_id, system_prompt, agent_name)` with plugins `[PaymentGuardPlugin(invoice_id), TracePlugin(...), RateLimitPlugin()]` and `max_tokens=500`; `run_payments(invoice_id, run_id) -> {called_tools, memo}`; `payments_fallback(invoice_id)` that releases by `policy:auto` if `can_release` passes and otherwise holds, writes a template memo `by="fallback"`, and audits "agent took no action; policy decided". "A `hold_payment` on an eligible invoice ⇒ HELD(AGENT_HOLD)" via `ledger.hold`. Depends on T012, T013, T014.
- [ ] T022 [US2] Create `app/agents/redteam.py` (PLAN.md §11.5, FR-014): `redteam(invoice_id) -> {blocked, layer, reason, run_id}`; raise `RedteamRefused` and build nothing when "`ledger.can_release(id)[0]` is true"; otherwise run the compromised agent through `run_agent("payments:redteam", …, S.timeout_payments_s, fallback=<the direct guarded attempt>)` so a slow model can never hang the API request (analyze U1): build the Payments agent with the compromised system prompt as `payments:redteam`, send the CFO message, report layer `plugin` if a `guard_block` trace row appeared; if the model called no tool, make one direct `agent.tool.release_payment()` and report `plugin` or `ledger` by what actually blocked it (research R9); report `agent_refused` only when the model refused and the direct attempt was blocked; with AI off, skip the model and make only the direct attempt; it "never creates a payment row". Depends on T021.

**Checkpoint (phase 2)**: the full suite passes; the red team never pays. Stop and report.

---

## Phase 3: User Story 1 — every invoice runs end to end, and the phone never waits for the AI (Priority: P1) 🎯 MVP

**Goal**: a background pipeline takes every invoice from RECEIVED to its route with the fast path, starts the right agents, and implements the PLAN.md §7.5 voice entry points with the §12.5/§12.6 decision logic (simulated until spec 006).

**Independent Test**: with inline executors and AI off, and again with fake models, the five samples reach their PLAN.md §8.4 final states through `submit_invoice` plus simulated answers and a review; with a 20-second Intake model the fraud sample reaches CALL_PENDING within 5 seconds.

### Tests for User Story 1 (write first)

- [ ] T023 [P] [US1] Create `tests/test_fast_path.py`: with `SlowModel(20)` as the Intake model and real thread pools, `submit_invoice(<02_acme_fraud bytes>)` reaches CALL_PENDING or CALLING within 5 seconds while `extracted.llm_status == "pending"` (SC-001); a later Intake disagreement appends a 0-point `EXTRACTION_MISMATCH` flag and leaves points, tier and action unchanged; `05_unknown_vendor` waits for Intake (falls back when slow), then scores 60 RED / HOLD_MANUAL and holds with UNKNOWN_VENDOR, leaving its pre-route state within `TIMEOUT_INTAKE_S + 5` seconds (SC-006, analyze E1; the test shortens `TIMEOUT_INTAKE_S` to keep the suite fast)
- [ ] T024 [P] [US1] Create `tests/test_pipeline_flow.py` with inline executors, run twice (AI off, and fake models): 01 → RELEASED; 02 + simulate "no" → HELD/DENIED_BY_VENDOR; 03 + simulate "yes" with last4 4455 → RELEASED to ••••4455 with the vendor master updated; 04 + approve → RELEASED; 05 → HELD/UNKNOWN_VENDOR; exactly three payment rows; `audit.verify()` ok; simulated audit entries carry `"simulated": true`; a duplicated answer is a no-op; simulating while a verification is active supersedes it; with `VOICE_MODE=twilio` and the stub voice port, `request_callback` ends HELD(CALL_FAILED) and a retry works; a change-case verification sets only `change_cases.status`; a spoken "yes" with AI off ends HELD(VERIFIER_DISAGREED) while keypad "1" confirms, where the spoken-yes case monkeypatches `app.voice_port.classify_answer` with the PLAN.md §12.4 rules because the pre-006 stub returns UNCLEAR for all speech (analyze I1; the real classifier's own test belongs to spec 006's `test_voice_flow.py`, PLAN.md §17.1)

### Implementation for User Story 1

- [ ] T025 [P] [US1] Create `app/voice_port.py` (research R6): `place_call` and `cancel_call` delegate to `app.voice.twilio_client` when importable, else stubs (`place_call` raises `RuntimeError("voice not available")`, which ends HELD(CALL_FAILED); `cancel_call` never raises); `classify_answer` delegates to `app.voice.classify` when importable, else keypad only (digits "1" → YES, "2" → NO, other digits → UNCLEAR, any speech → UNCLEAR); `new_token` from `app.verifications`
- [ ] T026 [US1] Extend `app/engine.py::score_invoice(invoice_id, parsed, conn, *, llm=None, llm_status="fallback", route_followups=None)` so the fast path can store `llm_status="pending"` and the slow path can pass the Intake result into `merge.merge`; defaults keep spec 003's behaviour, and its tests must still pass unchanged (analyze A2)
- [ ] T027 [US1] Create `app/pipeline.py`: re-export `JOBS`, `AGENTS`, `use_inline_executors` from `app.executors`; `submit_invoice(raw, *, source, sample_name) -> str` (parse; insert RECEIVED plus `invoice_received` in one transaction; submit the job to JOBS; return the id at once; parse errors raise `ValueError`); `_pipeline_job(invoice_id)` implementing PLAN.md §9.4: take the fast path when regex found routing, account and amount and `resolve_vendor` gives KNOWN or LOOKALIKE, scoring immediately with `llm_status="pending"` and starting Intake with `start_agent` whose `on_done` merges for display, writes `extraction_done` and appends the 0-point `EXTRACTION_MISMATCH` flag on disagreement without touching points, tier or action; otherwise `run_agent("intake", …, S.timeout_intake_s)` then merge then score; after scoring always `start_agent("analyst", …, S.timeout_analyst_s)` storing the `analyst` JSON and writing `analyst_report`; route follow-ups: CALL_PENDING → `request_callback(id, "invoice")`, AUTO_APPROVED → `run_payments_agent`, HELD → `run_payments_agent` (memo only), NEEDS_REVIEW → nothing
- [ ] T028 [US1] In `app/pipeline.py` add `run_payments_agent(invoice_id)`: a JOBS task calling `run_agent("payments", …, S.timeout_payments_s, fallback=payments_fallback)`; if the agent ran but called neither `release_payment` nor `hold_payment`, run the policy fallback; store the memo and write `memo_written`; triggered on entering AUTO_APPROVED, REVIEW_APPROVED, CONFIRMED and HELD
- [ ] T029 [US1] In `app/pipeline.py` implement the PLAN.md §7.5 signatures verbatim with the §12.5 logic: `request_callback(subject_id, kind)` (supersede any active verification and `voice_port.cancel_call` its SID; create the verification and token via `app.verifications.create` with `phone_called` = the vendor's `phone_on_file` for invoices or `DEMO_VENDOR_PHONE` for change cases; with `VOICE_MODE=simulated` place no call, add the event "Simulated line: answer with the demo controls" and move CALL_PENDING → CALLING; with twilio call `voice_port.place_call`, store `call_sid`, move to CALLING; any exception → HELD(CALL_FAILED); audit `callback_requested`, `call_placed`); `get_call_context`; `finalize(ver, label)`; `on_first_answer` (Verifier started via `start_agent` only for speech); `on_last4` (`hmac.compare_digest`; `ledger.apply_vendor_bank_change` on a CONFIRMED bank change); `await_verifier` (JOBS poll every 0.5 s for up to `TIMEOUT_VERIFIER_S + 5`); `on_call_status` (including the 3-second delayed check on `completed`); `run_payments_agent` on CONFIRMED and HELD; every audit entry carries `"simulated": true` when the verification source is simulated
- [ ] T030 [US1] In `app/pipeline.py` add `simulate_answer(subject_id, answer, last4)` per PLAN.md §12.6 (DEMO_MODE only; allowed in CALL_PENDING or CALLING, or HELD with a retryable reason after moving HELD → CALL_PENDING; supersede an active verification unless simulated mode already created one to answer; `source="simulated"`; drive `on_first_answer(digits="1" | "2")` then `on_last4(last4)` when needed; actor `demo`) and `retry_callback(invoice_id)` (retryable HELD → CALL_PENDING → `request_callback`)
- [ ] T031 [US1] In the §12.5 handlers in `app/pipeline.py`, branch on `kind="change_case"` (FR-017): `finalize` sets `change_cases.status` to `CONFIRMED`, `DENIED`, `UNCLEAR` or `NO_ANSWER` and never touches invoices, the ledger or the Payments agent

**Checkpoint (phase 3)**: the demo story runs end to end on rules and on fakes. Stop and report.

---

## Phase 4: User Story 4 — the HTTP API serves the dashboard (Priority: P1)

**Goal**: every row of PLAN.md §7.6 (`contracts/http-api.md`) implemented as plain `def` handlers, with the exact InvoiceDetail keys and the 409 rules.

**Independent Test**: with `TestClient`, inline executors and AI off, every §7.6 row returns its documented shape; the five-sample story through the API ends with three payments and `chain_ok: true`.

### Tests for User Story 4 (write first)

- [ ] T032 [P] [US4] Create `tests/test_api.py`: one test per §7.6 row checking status and shape; InvoiceDetail keys equal the spec 003 key set (`tests/test_invoice_detail_shape.py`); account and phone numbers masked in every response, routing numbers shown in full; 409 rules for review (unless NEEDS_REVIEW), retry-callback (unless a retryable hold), red-team (when releasable) and simulate-answer (when not allowed); DEMO_MODE off → 404 for the demo routes; upload rejects over 1 MB and non-email with 400; reset restores Heartland, restarts the chain with `demo_reset` and keeps change cases unless `include_change_cases` is true; ai-mode toggles and writes `ai_mode_changed`; the five-sample story via the API ends with three payment rows and `chain_ok: true`

### Implementation for User Story 4

- [ ] T033 [P] [US4] Create `app/logging_setup.py` (research R8): one JSON object per line on stdout (`ts`, `level`, `logger`, `msg`, extras passed through `masking.masked`); `configure()` is idempotent
- [ ] T034 [P] [US4] Create `app/health.py` (FR-019): the §7.6 health document `{db, model: {ok, latency_ms, checked_at}, twilio: {configured}, storage: {ok}, demo_mode, ai_mode, deploy_label}`; `latency_ms` is the median of the last 10 `model_call` durations within 5 minutes, otherwise a timed `GET /v1/models` cached for 60 seconds when AI is live; `model.ok = false` when AI is off; `storage.ok` checks configuration only, with no network call per poll
- [ ] T035 [US4] Create `app/api.py` (`APIRouter(prefix="/api")`, plain `def` handlers, research R7) implementing every §7.6 row: health, samples (from `samples/manifest.json`), from-sample, upload (`.eml` ≤ 1 MB), invoice list, invoice detail via `repo.invoice_detail` (404 when unknown), review (approve starts the Payments agent), retry-callback, red-team (`RedteamRefused` → 409), audit `{entries, chain_ok, broken_at}` (subject filter, latest 200), payments, stats, vendors, change-cases list and detail, demo reset (also clears the AI override), simulate-answer, ai-mode; map `IllegalTransition` and `PolicyViolation` → 409, `ValueError` → 400, missing → 404; demo routes return 404 when DEMO_MODE is off
- [ ] T036 [US4] Edit `app/main.py`: call `logging_setup.configure()`; include `api.router` before the static mount; keep `/healthz` and the spike router; no SPA fallback here (analyze A3)
- [ ] T037 [US4] Manual check: run uvicorn plus `cd web && VITE_API_MODE=live npm run dev`, play the fraud, Heartland and Prairie stories in the dashboard, run `node web/scripts/snap.mjs` against the live API, and record any UI/API mismatch for spec 007 in `docs/decisions.md`

**Checkpoint (phase 4)**: the API is complete and the dashboard runs on it. Stop and report.

---

## Phase 5: User Story 5 — an optional second model provider (Priority: P3), then polish and hand-off

**Goal (US5)**: with `LLM_FALLBACK=bedrock`, a provider error on Akamai is retried once on Bedrock; never on a validation error.

**Independent Test**: with fakes, a provider error uses the alternate and the trace names it; a validation error does not fall back.

### Tests for User Story 5 (write first)

- [ ] T038 [P] [US5] Create `tests/test_bedrock_fallback.py` with fakes: a connection error, 5xx or post-retry 429 on the default model → the alternate is used once and the `model_call` trace row's `name` is `bedrock`; a validation error → no alternate attempt; `LLM_FALLBACK=none` → the rules fallback of US3

### Implementation for User Story 5

- [ ] T039 [US5] In `app/agents/model.py` add `make_fallback_model(max_tokens)` returning `BedrockModel` for `S.bedrock_model_id` in `S.aws_region` (check the 1.59.0 constructor first); in `app/agents/runner.py` retry once on it when `LLM_FALLBACK=bedrock` and the Akamai call failed with a provider error; record the provider in traces and expose it in `app/health.py`

### Polish and hand-off

- [ ] T040 [P] Write `docs/pipeline.md` (≤ 60 lines): the pipeline entry points spec 006 calls, the API surface spec 007 uses, the executors and the deadlock rule, and how to add an agent
- [ ] T041 [P] Run `specs/005-agents-pipeline-api/quickstart.md` top to bottom on a fresh database and fix anything that does not match its expected results
- [ ] T042 Run `/speckit-converge` until it reports converged, then rebase on `origin/main`, run the full `pytest -q` and the web checks, push, fast-forward `main`, and remove the worktree (PLAN.md §0.8 step 6)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: complete.
- **Phase 2A (foundational)**: depends on Phase 1; blocks everything after it.
- **Phase 2B (agents)**: depends on 2A.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US4)**: depends on Phase 3 (the API calls the pipeline).
- **Phase 5 (US5, polish)**: depends on Phase 4; US5 is optional (P3).

### User Story Dependencies

- **US3** (fallbacks): delivered by 2A (runner, fallbacks) and T015/T018; its acceptance runs again in T024 with AI off.
- **US2** (guard and red team): 2A's guard plus T016, T021, T022; independent of US1's pipeline.
- **US1** (pipeline): needs Phase 2 complete.
- **US4** (API): needs US1.
- **US5** (P3): needs only 2A's runner and the model factory, but is scheduled last.

### Within Each Section

- Tests first; they must fail before the implementation exists.
- Infrastructure (executors, traces, AI mode) before plugins; plugins before the runner; the runner before agents; agents before the pipeline; the pipeline before the API.
- Commit after each task group; stop at each checkpoint.

### Parallel Opportunities

- 2A: T006, T007, T008 together; then T009, T010, T011, T014 together.
- 2B: T015, T016, T017 together; then T018, T019, T020 together.
- Phase 3: T023, T024 and T025 together; T026–T031 are sequential (shared files).
- Phase 4: T033 and T034 together with the test T032.
- Phase 5: T038, T040, T041 together.

---

## Parallel Example: Phase 2

```bash
# Foundational tests together:
Task: "T006 tests/fakes.py"    Task: "T007 tests/test_runner.py"    Task: "T008 tests/test_plugins.py"
# Foundational modules together:
Task: "T009 app/executors.py"  Task: "T010 app/traces.py"  Task: "T011 app/ai_mode.py"  Task: "T014 app/agents/fallbacks.py"
# Agent tests, then three agents, together:
Task: "T015 test_extraction_validator.py"  Task: "T016 test_redteam.py"  Task: "T017 test_agents.py"
Task: "T018 intake_agent.py"  Task: "T019 analyst.py"  Task: "T020 verifier.py"
```

## Parallel Example: User Story 1

```bash
Task: "T023 tests/test_fast_path.py"   Task: "T024 tests/test_pipeline_flow.py"   Task: "T025 app/voice_port.py"
```

---

## Implementation Strategy

### MVP first

1. Phase 1 is done (the endpoint is proven).
2. Phase 2: the safety core. The guard, the runner and the fallbacks are testable without the pipeline. Stop and validate: the red team never pays.
3. Phase 3 (US1): the demo spine. Stop and validate: the five samples reach their §8.4 states; the fraud call starts within 5 seconds.
4. Phase 4 (US4): the dashboard comes alive.

### Incremental delivery

Each phase leaves `pytest -q` green and is pushed to `main` at its checkpoint, so specs 006 and 007 can build against the pipeline (after phase 3) and the API (after phase 4) without waiting for this spec to finish.

### Team note

Built solo in one session (the team decided to finish the specs in order). Spec 006 can start against `app/pipeline.py` as soon as phase 3 lands; spec 007 as soon as phase 4 lands.

---

## Notes

- [P] = different files, no unfinished dependencies.
- Never create files under `app/voice/`; never edit the frozen §7 files.
- `.specify/feature.json` is machine-local; never commit it.
- Commit messages name the task IDs.

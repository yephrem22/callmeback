# Contract: agent runtime (spec 005, internal; from PLAN.md §11)

Module layout: `app/agents/` = `model.py`, `plugins.py`, `runner.py`, `fallbacks.py`, `intake_agent.py`, `analyst.py`, `verifier.py`, `payments.py`, `redteam.py`.

## Model factory (`model.py`)

```python
def make_model(max_tokens: int = 1200) -> OpenAIModel
    # OpenAIModel(client_args={"api_key", "base_url", "timeout": 30.0, "max_retries": 1},
    #             model_id=S.model_id, params={"max_tokens": max_tokens, "temperature": 0.1},
    #             stream=S.llm_streaming)            # NOTE: "stream", not "streaming" (research R1)
def make_fallback_model(max_tokens: int = 1200) -> BedrockModel   # only when LLM_FALLBACK=bedrock (P3)
```

## Runner (`runner.py`)

```python
def run_agent(agent_name: str, subject_id: str, fn: Callable[[str], T], timeout_s: float,
              fallback: Callable[[], T]) -> tuple[T, Literal["result", "fallback"]]
    # fn receives run_id. Submits to AGENTS, waits future.result(timeout_s) from a JOBS or request thread.
    # AI off → fallback() immediately (trace "fallback", summary "AI off").
    # Timeout / exception / StructuredOutputException → trace "fallback", invoices.ai_fallback = 1,
    #   audit ai_fallback, return fallback(). A late result is discarded.
    # Raises RuntimeError if called on an AGENTS thread (deadlock rule, PLAN.md §6).
def start_agent(agent_name, subject_id, fn, timeout_s, fallback, on_done: Callable[[T, str], None]) -> Future
    # submits run_agent(...) to JOBS and calls on_done(result, outcome) there.
```

## Plugins (`plugins.py`) — all call `super().__init__()` (research R1)

| Plugin | `name` | Hooks | Effect |
|---|---|---|---|
| `PaymentGuardPlugin(invoice_id)` | `payment-guard` | `BeforeToolCallEvent` | for `release_payment`: `ledger.can_release()`; allow → trace `guard_allow` + audit `guard_allowed`; deny → `event.cancel_tool = "BLOCKED by payment policy: <reason>"`, trace `guard_block`, audit `guard_blocked` |
| `TracePlugin(subject_id, agent, run_id)` | `trace` | Before/AfterInvocation, Before/AfterModelCall, Before/AfterToolCall | `run_start`, `model_call` (duration, exception), `tool_call` (name, masked input, ok/error, duration), `run_end` (tokens) |
| `RateLimitPlugin()` | `rate-limit` | BeforeModelCall, AfterModelCall | shared bucket of `LLM_RPM`/60 s; on 429-like exception sleep `x-ratelimit-reset` (default 5 s) and `event.retry = True`, at most 3 per invocation |

## Agents

| Agent | Tools (closure-bound to one subject) | Output | max_tokens | Fallback |
|---|---|---|---|---|
| Intake | none | `make_extraction_model(body)` (InvoiceExtraction + digit validators) | 800 | regex-only merge, `llm_status="fallback"` |
| Analyst | `get_policy_findings`, `get_vendor_record` (masked), `get_vendor_history`, `get_email_excerpt` | `AnalystReport` with `cited_flags ⊆ findings` | 900 | headline from tier, explanation from flag titles, `status="fallback"` |
| Verifier | none | `VerifierLabel` | 200 | `UNCLEAR` |
| Payments | `get_case_summary`, `release_payment`, `hold_payment(reason)` | text memo | 500 | policy decides: release (`policy:auto`) if eligible else hold; template memo; audit "agent took no action; policy decided" |
| Payments (red team) | same three | — | 500 | n/a; result `{blocked, layer, reason, run_id}` |

System prompts are PLAN.md §11.4 / §11.5 verbatim. Email text is wrapped in `<email>…</email>` and labelled untrusted. Only Intake sees raw digits.

## Pipeline entry points (`app/pipeline.py`) — PLAN.md §7.5 signatures, verbatim

`request_callback`, `get_call_context`, `on_call_status`, `on_first_answer`, `on_last4`, `simulate_answer`, plus:

```python
def submit_invoice(raw: bytes, *, source: Literal["sample","upload"], sample_name: str | None) -> str
    # parse (ValueError → 400), insert RECEIVED, queue the pipeline job on JOBS, return the id at once
def run_payments_agent(invoice_id: str) -> None     # on entering AUTO_APPROVED / REVIEW_APPROVED / CONFIRMED / HELD
def redteam(invoice_id: str) -> dict                # PLAN.md §11.5
def use_inline_executors() -> None                  # tests: run JOBS/AGENTS synchronously
```

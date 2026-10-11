# Implementation Plan: AI Agents, Pipeline and API

**Branch**: `worktree-agents-pipeline` (spec directory `specs/005-agents-pipeline-api`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification and the Plan prompt in PLAN.md §23.5.

## Summary

Wrap spec 003's deterministic engine in an asynchronous pipeline with four Strands agents that help but can never move money: Intake (structured extraction with digit validators), Analyst (plain-English explanation with read-only tools), Verifier (classifies spoken answers, can only downgrade), Payments (release/hold through a tool guarded by a Strands plugin and re-checked in the ledger). A fast path scores and routes from deterministic extraction so the phone call never waits for the model. Every run is traced, rate-limited, time-boxed and falls back to rules. The pipeline implements the §7.5 voice entry points and the §12.5 decision logic (simulated until spec 006), and `app/api.py` implements every §7.6 route. Phase 1 is the live LLM smoke test that settles the streaming setting.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `strands-agents[openai]==1.59.0` (OpenAIModel → Akamai `hackathon-chat`), FastAPI 0.143, pydantic 2.14, httpx, python-multipart, boto3 (P3 Bedrock only). Pinned in `requirements.txt`.

**Storage**: SQLite (spec 003 schema, unchanged); `agent_traces` for the live trace.

**Testing**: pytest with fake Strands models (`tests/fakes.py`), inline executors, FastAPI `TestClient`; no network. Live checks only in `scripts/llm_smoke.py`.

**Target Platform**: the Chicago VM (one uvicorn worker) and laptops.

**Project Type**: the existing single Python package; new modules under `app/agents/`, `app/pipeline.py`, `app/api.py`, `app/voice_port.py`, `app/ai_mode.py`, `app/logging_setup.py`, `app/health.py`.

**Performance Goals**: fraud sample to CALL_PENDING + callback requested ≤ 5 s regardless of model latency (SC-001); each agent's fallback ≤ its timeout + 1 s (SC-006); webhooks never wait on a model (PLAN.md §12.2).

**Constraints**: 60 req/min team cap (our bucket 45); one backing model; 512 default output tokens; JOBS=8 / AGENTS=4 executors and the deadlock rule; plain `def` routes; masking everywhere except Intake's raw email; no files created under `app/voice/` (spec 006 owns it).

**Scale/Scope**: ~12 new modules, ~10 test files, 22 HTTP routes.

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. PLAN.md source of truth | §7.5/§7.6 copied verbatim to contracts; §11 followed; two installed-API corrections recorded (research R1), no §7 change | PASS |
| II. AI explains, code holds keys | guard plugin + ledger re-check; Verifier only downgrades; Analyst cannot change score; red-team never pays | PASS |
| III. Fail closed | every agent has a rules fallback; timeouts/errors/validation failures fall back; place-call failure → HELD(CALL_FAILED); stub classifier returns UNCLEAR for speech | PASS |
| IV. Number on file | `request_callback` dials `vendor.phone_on_file` / `DEMO_VENDOR_PHONE` only; Intake's phone list is advisory | PASS |
| V. Never blocked by setup | AI off by default; fake models in tests; `VOICE_MODE=simulated`; voice stubs until 006 | PASS |
| VI. Secrets stay in .env | smoke script reads the key via settings and prints only lengths/status | PASS |
| VII. Evidence everywhere | trace rows for every step; audit events for every decision | PASS |
| VIII. Test the deterministic | red-team, validator, plugin, runner, flow and API tests on fakes | PASS |
| IX. Designed for users | API shapes are exactly what the UI consumes | PASS |
| X. Small slices | five phases, each stops and reports | PASS |
| XI. Fresh code | all new | PASS |

Post-design re-check: no violations.

## Project Structure

```text
specs/005-agents-pipeline-api/
├── plan.md, research.md, data-model.md, quickstart.md, tasks.md
└── contracts/ interfaces.md (§7.5), http-api.md (§7.6), agents.md

app/
├── agents/ model.py plugins.py runner.py fallbacks.py intake_agent.py analyst.py verifier.py payments.py redteam.py
├── pipeline.py        # executors, submit/ingest job, fast path, §7.5 handlers, §12.5/§12.6 logic
├── voice_port.py      # place_call/cancel_call/classify_answer adapters with stubs until spec 006 (R6)
├── ai_mode.py         # effective AI mode + runtime override (R10)
├── health.py          # /api/health document and latency cache (R7)
├── logging_setup.py   # JSON logs (R8)
├── traces.py          # agent_traces writes/reads (masked)
├── api.py             # §7.6 routes
└── main.py            # (edit) include the API router, configure logging
scripts/llm_smoke.py   # phase 1
docs/llm_smoke.md      # phase 1 output
tests/ fakes.py test_llm_model.py test_extraction_validator.py test_plugins.py test_runner.py test_agents.py
       test_redteam.py test_pipeline_flow.py test_fast_path.py test_api.py
```

**Structure Decision**: agents in their own package so each file is one agent; `pipeline.py` is the only orchestrator and the only owner of the executors; `voice_port.py` isolates the spec-006 dependency.

## Phases (each stops and reports)

1. **Phase 1, LLM smoke test (A2)**: `app/agents/model.py` (with `stream=`), `scripts/llm_smoke.py`, `docs/llm_smoke.md`, a unit test that `make_model` passes `stream` and never `streaming`. Gate: report written; streaming decided; `AI_MODE=live` recommended or not.
2. **Phase 2, agent runtime**: traces, ai_mode, plugins, runner, fallbacks, the four agents, the red-team runner, fakes; `test_extraction_validator`, `test_plugins`, `test_runner`, `test_agents`, `test_redteam`. Gate: red team never pays; validators reject invented digits; fallbacks fire on timeout.
3. **Phase 3, pipeline**: executors, ingest job with fast path, Payments triggers, §7.5 handlers with §12.5/§12.6 logic, voice port, change-case branching; `test_fast_path`, `test_pipeline_flow`. Gate: the five samples reach their §8.4 final states through simulated answers, AI off and with fake models; fraud CALL_PENDING ≤ 5 s with a 20 s Intake.
4. **Phase 4, HTTP API**: `api.py`, `health.py`, `logging_setup.py`, main.py wiring; `test_api` covering every §7.6 row and 409 rule; dashboard check in live mode. Gate: the quickstart's curl flow and the dashboard on the live API.
5. **Phase 5, P3 and hand-off**: optional Bedrock fallback; README notes; converge; merge.

## Complexity Tracking

None.

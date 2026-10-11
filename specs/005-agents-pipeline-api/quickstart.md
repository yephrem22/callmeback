# Quickstart: AI Agents, Pipeline and API (spec 005)

## Prerequisites

```bash
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
```

`.env` with `AKAMAI_API_KEY` for the live checks only. Unit tests need nothing.

## 1. Smoke test the model (phase 1, milestone A2)

```bash
.venv/bin/python -m scripts.llm_smoke            # writes docs/llm_smoke.md
```

Expected: a plain completion; 3/3 structured outputs; tool calls 5/5 in at least one of stream off / stream on, with p50 latency per row and the chosen setting written at the top. If neither reaches 4/5, the report says "Analyst: no-tools mode". Then set `LLM_STREAMING` accordingly and `AI_MODE=live`.

## 2. Unit tests (no network)

```bash
AI_MODE=off .venv/bin/python -m pytest -q
```

Includes `tests/test_extraction_validator.py`, `tests/test_redteam.py`, plugin, runner, fallback, pipeline-flow and API tests on fake models.

## 3. Run the app

```bash
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --port 8000
```

```bash
curl -s localhost:8000/api/health
curl -s -XPOST localhost:8000/api/invoices/from-sample -H 'content-type: application/json' -d '{"name":"02_acme_fraud"}'
curl -s localhost:8000/api/invoices                # 160 points, RED, CALLING within a few seconds
curl -s -XPOST localhost:8000/api/demo/simulate-answer -H 'content-type: application/json' \
     -d '{"subject_id":"<id>","answer":"no","last4":null}'
curl -s localhost:8000/api/invoices/<id>           # HELD / DENIED_BY_VENDOR, trace rows, memo
curl -s -XPOST localhost:8000/api/invoices/<id>/redteam   # {"blocked": true, "layer": "plugin", ...}
```

With the dashboard: `cd web && VITE_API_MODE=live npm run dev`, open :5173.

## 4. Expected end-to-end results (PLAN.md §8.4, simulated answers)

| Sample | Action | Final |
|---|---|---|
| 01_acme_normal | none | RELEASED (agent or policy:auto) |
| 02_acme_fraud | simulate "no" | HELD / DENIED_BY_VENDOR |
| 03_heartland_bank_change | simulate "yes" + 4455 | RELEASED to ••••4455, vendor master updated |
| 04_prairie_review | approve | RELEASED |
| 05_unknown_vendor | none | HELD / UNKNOWN_VENDOR |

Exactly three payment rows; `GET /api/audit` → `chain_ok: true`. Same results with `POST /api/demo/ai-mode {"mode":"off"}`.

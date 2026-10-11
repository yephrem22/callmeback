# LLM smoke test (PLAN.md §11.1, milestone A2)

Run 2026-10-11T01:15:37Z against `https://ws.akamai-workshops.com/v1`, model `hackathon-chat`, Strands 1.59.0 `OpenAIModel`.

**Decision: stream off.** Set `LLM_STREAMING=0` and `AI_MODE=live` in `.env`.

| Check | Result | p50 latency |
|---|---|---|
| Plain completion | pass | 6.55 s |
| Structured output (3-field model) | 3/3 | 3.13 s |
| Tool call, `stream=False` | 5/5 | 8.25 s |
| Tool call, `stream=True` | 5/5 | 4.63 s |

`<think>` blocks seen in output: no.

Notes:
- Streaming is set with the Strands 1.59.0 config key `stream` (default True); PLAN.md's `streaming` spelling is silently ignored (research R1).
- The Akamai gateway rejects `"tools": []` with HTTP 400; `AkamaiModel` omits the field when an agent has no tools (research R2). Without that fix the plain completion fails while structured output and tool calls pass.
- Each tool-call trial uses a fresh Agent and a fresh `@tool` counter; a pass needs the tool called and `42` in the answer.
- Latency on the shared endpoint varies several-fold between runs; the per-agent timeouts in `.env` (Intake 20 s, Analyst 45 s, Verifier 15 s, Payments 30 s) leave headroom for the slow end.
- First run (before the fix): plain completion 400 (empty tools array); structured 3/3 p50 8.75 s; tools off 5/5 p50 2.47 s; tools on 5/5 p50 1.57 s.

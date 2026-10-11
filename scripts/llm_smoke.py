"""LLM smoke test (PLAN.md §11.1, milestone A2). Run: python -m scripts.llm_smoke

1. a plain completion
2. structured output with a 3-field model, 3 times
3. a tool call with a dummy @tool, 5 times with stream off and 5 times with stream on

Decision rules (PLAN.md §11.1): keep the setting that gets 5/5 tool calls (prefer stream off on a tie);
if neither reaches 4/5, the Analyst switches to no-tools mode. Writes docs/llm_smoke.md.
Never prints the API key; only its length.
"""
from __future__ import annotations

import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from strands import Agent, tool

from app import config
from app.agents.model import make_model, model_settings

REPORT = config.REPO_ROOT / "docs" / "llm_smoke.md"


class Triple(BaseModel):
    city: str
    country: str
    population_millions: float


def _p50(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 2) if xs else None


def _fresh_agent(stream: bool, tools=None, max_tokens: int = 300) -> Agent:
    return Agent(model=make_model(max_tokens, stream=stream), tools=tools or [], callback_handler=None,
                 system_prompt="You are a terse assistant used in an automated test.")


def plain_completion() -> dict:
    t0 = time.perf_counter()
    try:
        result = _fresh_agent(stream=False, max_tokens=20)("Reply with exactly: OK")
        text = str(result).strip()
        return {"ok": "ok" in text.lower(), "seconds": round(time.perf_counter() - t0, 2), "text": text[:60],
                "think": "<think>" in text}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "seconds": round(time.perf_counter() - t0, 2), "error": f"{type(e).__name__}: {e}"[:200]}


def structured(n: int = 3) -> dict:
    passes, times, errors = 0, [], []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            result = _fresh_agent(stream=False, max_tokens=200)(
                "Give the city, country and approximate population in millions of the capital of France.",
                structured_output_model=Triple)
            out = result.structured_output
            if isinstance(out, Triple) and out.city and out.country:
                passes += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}"[:160])
        times.append(time.perf_counter() - t0)
    return {"passes": passes, "n": n, "p50": _p50(times), "errors": errors[:2]}


def tool_calls(stream: bool, n: int = 5) -> dict:
    passes, times, errors, think = 0, [], [], False
    for _ in range(n):
        calls = {"n": 0}

        @tool
        def get_magic_number() -> int:
            """Return today's magic number."""
            calls["n"] += 1
            return 42

        t0 = time.perf_counter()
        try:
            result = _fresh_agent(stream=stream, tools=[get_magic_number], max_tokens=200)(
                "Call the get_magic_number tool, then reply with the number it returned.")
            text = str(result)
            think = think or "<think>" in text
            if calls["n"] >= 1 and "42" in text:
                passes += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {e}"[:160])
        times.append(time.perf_counter() - t0)
    return {"stream": stream, "passes": passes, "n": n, "p50": _p50(times), "errors": errors[:2], "think": think}


def decide(off: dict, on: dict) -> tuple[str, str]:
    if off["passes"] == off["n"]:
        return "stream off", "LLM_STREAMING=0"
    if on["passes"] == on["n"]:
        return "stream on", "LLM_STREAMING=1"
    best = off if off["passes"] >= on["passes"] else on
    if best["passes"] >= 4:
        return f"stream {'on' if best['stream'] else 'off'} (4/5, best available)", f"LLM_STREAMING={1 if best['stream'] else 0}"
    return "Analyst: no-tools mode (neither setting reached 4/5)", "LLM_STREAMING=0"


def main() -> int:
    S = config.S
    print(f"key length {len(S.akamai_api_key)}; base {S.akamai_base_url}; model {S.model_id}")
    if not S.akamai_api_key or S.akamai_api_key == "replace-me":
        print("AKAMAI_API_KEY is not set; nothing to test.")
        return 1

    started = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    plain = plain_completion()
    print("plain completion:", "ok" if plain["ok"] else "FAIL", plain.get("seconds"), "s")
    struct = structured()
    print(f"structured output: {struct['passes']}/{struct['n']}, p50 {struct['p50']} s")
    off = tool_calls(stream=False)
    print(f"tool calls, stream off: {off['passes']}/{off['n']}, p50 {off['p50']} s")
    on = tool_calls(stream=True)
    print(f"tool calls, stream on:  {on['passes']}/{on['n']}, p50 {on['p50']} s")
    choice, env_line = decide(off, on)
    think = plain.get("think") or off["think"] or on["think"]
    print("decision:", choice)

    settings = model_settings()
    lines = [
        "# LLM smoke test (PLAN.md §11.1, milestone A2)",
        "",
        f"Run {started} against `{settings['base_url']}`, model `{settings['model_id']}`, Strands 1.59.0 `OpenAIModel`.",
        "",
        f"**Decision: {choice}.** Set `{env_line}` and `AI_MODE=live` in `.env`." if plain["ok"] else
        "**Decision: keep `AI_MODE=off`; the plain completion failed.**",
        "",
        "| Check | Result | p50 latency |",
        "|---|---|---|",
        f"| Plain completion | {'pass' if plain['ok'] else 'FAIL'} | {plain.get('seconds')} s |",
        f"| Structured output (3-field model) | {struct['passes']}/{struct['n']} | {struct['p50']} s |",
        f"| Tool call, `stream=False` | {off['passes']}/{off['n']} | {off['p50']} s |",
        f"| Tool call, `stream=True` | {on['passes']}/{on['n']} | {on['p50']} s |",
        "",
        f"`<think>` blocks seen in output: {'yes, add chat_template_kwargs.enable_thinking=False' if think else 'no'}.",
        "",
        "Notes:",
        "- Streaming is set with the Strands 1.59.0 config key `stream` (default True); PLAN.md's `streaming` spelling is silently ignored (research R1).",
        "- The Akamai gateway rejects `\"tools\": []` with HTTP 400; `AkamaiModel` omits the field when an agent has no tools (research R2). Without that fix the plain completion fails while structured output and tool calls pass.",
        "- Each tool-call trial uses a fresh Agent and a fresh `@tool` counter; a pass needs the tool called and `42` in the answer.",
        "- Latency on the shared endpoint varies several-fold between runs; the per-agent timeouts in `.env` (Intake 20 s, Analyst 45 s, Verifier 15 s, Payments 30 s) leave headroom for the slow end.",
    ]
    errs = (plain.get("error") and [plain["error"]] or []) + struct["errors"] + off["errors"] + on["errors"]
    if errs:
        lines += ["", "Errors seen (truncated):", *[f"- `{e}`" for e in errs[:5]]]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT.relative_to(config.REPO_ROOT)}")
    return 0 if plain["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

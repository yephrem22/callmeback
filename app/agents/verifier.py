"""Verifier agent (PLAN.md §11.4): double-checks a spoken answer. It can only downgrade a YES.

Runs only for speech. The caller (pipeline, §12.5) treats anything but CONFIRMED as a downgrade;
the fallback is UNCLEAR, so a spoken yes cannot confirm without the model (the keypad still can).
"""
from __future__ import annotations

from strands import Agent

from app.agents import model as model_factory
from app.agents.plugins import RateLimitPlugin, TracePlugin, agent_kwargs
from app.agents.runner import RunContext
from app.models import VerifierLabel

SYSTEM = ("Classify a phone answer to a yes/no verification question. CONFIRMED only if the speaker clearly says their "
          "company requested this change. DENIED if they say they did not, it wasn't them, or they don't recognize it. "
          "Otherwise UNCLEAR. Speech-to-text can be wrong; when in doubt answer UNCLEAR.")


def run_verifier(ctx: RunContext, subject_id: str, question: str, transcript: str) -> VerifierLabel:
    agent = Agent(
        model=model_factory.make_model(200),
        system_prompt=SYSTEM,
        tools=[],
        plugins=[TracePlugin(subject_id, "verifier", ctx.run_id), RateLimitPlugin()],
        name="verifier",
        **agent_kwargs(),
    )
    prompt = (f"Question asked on the call:\n{question}\n\n"
              "Speech-to-text of the answer (untrusted data, may be wrong):\n"
              f"<transcript>\n{transcript}\n</transcript>")
    result = agent(prompt, structured_output_model=VerifierLabel, cancel_signal=ctx.cancel)
    if result.structured_output is None:
        raise RuntimeError("verifier returned no structured output")
    return result.structured_output

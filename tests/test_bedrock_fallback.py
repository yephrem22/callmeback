"""P3 alternate model (spec 005 US5, FR-025): Akamai first; Bedrock once on a provider error."""
from __future__ import annotations

import httpx
import openai
import pytest
from strands.types.exceptions import ModelThrottledException, StructuredOutputException

from app import ai_mode, config, health
from app import db as dbm
from app.agents import model as model_factory
from app.agents import plugins, verifier
from app.agents.runner import run_agent
from app.agents.fallbacks import verifier_fallback
from tests.fakes import ScriptedModel, raise_turn, structured_turn

REQ = httpx.Request("POST", "http://akamai.test/v1/chat/completions")
SUBJECT = "cc_bedrock_test"


def _conn_error():
    return openai.APIConnectionError(request=REQ)


def _server_error():
    return openai.InternalServerError("bad gateway", response=httpx.Response(502, request=REQ), body=None)


def _bad_request():
    return openai.BadRequestError("bad request", response=httpx.Response(400, request=REQ), body=None)


@pytest.fixture
def providers(db, monkeypatch):
    """Install Akamai/Bedrock fakes; returns a dict counting Bedrock builds."""
    monkeypatch.setenv("LLM_FALLBACK", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.test-model")
    config.reload()
    ai_mode.set_ai_mode("live", record=False)
    monkeypatch.setattr(plugins, "_sleep", lambda s: None)
    calls = {"bedrock": 0}

    def install(akamai_exc_factory):
        monkeypatch.setattr(model_factory, "make_akamai_model",
                            lambda *a, **k: ScriptedModel([raise_turn(akamai_exc_factory()) for _ in range(6)]))

        def bedrock(max_tokens):
            calls["bedrock"] += 1
            return ScriptedModel([structured_turn({"label": "DENIED", "rationale": "they said no"})])
        monkeypatch.setattr(model_factory, "make_fallback_model", bedrock)
        return calls

    return install


def _run():
    return run_agent("verifier", SUBJECT, lambda ctx: verifier.run_verifier(ctx, SUBJECT, "Did you?", "no we did not"),
                     10, verifier_fallback)


def _model_call_names() -> list[str]:
    c = dbm.connect()
    try:
        return [r[0] for r in c.execute(
            "SELECT name FROM agent_traces WHERE subject_id=? AND kind='model_call' ORDER BY id", (SUBJECT,))]
    finally:
        c.close()


@pytest.mark.parametrize("exc", [_conn_error, _server_error, lambda: ModelThrottledException("429 after retries")],
                         ids=["connection", "5xx", "429-after-retries"])
def test_provider_error_uses_bedrock_once(providers, exc):
    calls = providers(exc)
    label, outcome = _run()
    assert outcome == "result" and label.label == "DENIED"
    assert calls["bedrock"] == 1
    assert _model_call_names()[-1] == "bedrock"
    assert health.health()["model"]["provider"] == "bedrock"


@pytest.mark.parametrize("exc", [_bad_request, lambda: StructuredOutputException("invalid output")],
                         ids=["400", "validation"])
def test_validation_errors_do_not_try_the_alternate(providers, exc):
    calls = providers(exc)
    label, outcome = _run()
    assert outcome == "fallback" and label.label == "UNCLEAR"
    assert calls["bedrock"] == 0


def test_llm_fallback_none_uses_the_rules(providers, monkeypatch):
    calls = providers(_conn_error)
    monkeypatch.setenv("LLM_FALLBACK", "none")
    config.reload()
    label, outcome = _run()
    assert outcome == "fallback" and label.label == "UNCLEAR"
    assert calls["bedrock"] == 0


def test_make_fallback_model_builds_bedrock(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.test-model")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    config.reload()
    m = model_factory.make_fallback_model(300)
    assert type(m).__name__ == "BedrockModel"
    cfg = m.get_config()
    assert cfg["model_id"] == "anthropic.test-model" and cfg["max_tokens"] == 300
    assert model_factory.current_provider() == "akamai"
    with model_factory.use_provider("bedrock"):
        assert model_factory.current_provider() == "bedrock"
    assert model_factory.current_provider() == "akamai"

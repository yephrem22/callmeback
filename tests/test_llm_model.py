"""The model factory sets the Strands 1.59.0 `stream` key (research R1) and makes no network call."""
from __future__ import annotations

import os

import pytest

from app import config
from app.agents.model import make_model, model_settings


@pytest.fixture
def env_stream(monkeypatch):
    def _set(value: str):
        monkeypatch.setenv("LLM_STREAMING", value)
        monkeypatch.setenv("AKAMAI_API_KEY", "test-key-not-real")
        config.reload()
    yield _set
    config.reload()


def test_stream_off_by_default(env_stream):
    env_stream("0")
    cfg = make_model().get_config()
    assert cfg["stream"] is False
    assert "streaming" not in cfg


def test_stream_on_when_configured(env_stream):
    env_stream("1")
    assert make_model().get_config()["stream"] is True


def test_explicit_override_wins(env_stream):
    env_stream("1")
    assert make_model(stream=False).get_config()["stream"] is False


def test_params_and_model_id(env_stream):
    env_stream("0")
    cfg = make_model(max_tokens=800).get_config()
    assert cfg["params"] == {"max_tokens": 800, "temperature": 0.1}
    assert cfg["model_id"] == config.S.model_id


def test_empty_tools_are_omitted_from_the_request(env_stream):
    """The Akamai gateway rejects "tools": [] (smoke test, research R2)."""
    env_stream("0")
    m = make_model()
    msgs = [{"role": "user", "content": [{"text": "hi"}]}]
    req = m.format_request(msgs, None, "system")
    assert "tools" not in req and "tool_choice" not in req
    req2 = m.format_request(msgs, [], "system")
    assert "tools" not in req2


def test_tools_are_kept_when_present(env_stream):
    env_stream("0")
    m = make_model()
    spec = {"name": "get_x", "description": "d", "inputSchema": {"json": {"type": "object", "properties": {}}}}
    req = m.format_request([{"role": "user", "content": [{"text": "hi"}]}], [spec], "system")
    assert [t["function"]["name"] for t in req["tools"]] == ["get_x"]


def test_settings_have_no_secret(env_stream):
    env_stream("0")
    s = model_settings()
    assert "test-key-not-real" not in repr(s)
    assert set(s) == {"provider", "base_url", "model_id", "stream", "rpm"}
    assert os.environ["AKAMAI_API_KEY"] == "test-key-not-real"

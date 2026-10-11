"""Helpers for the /twilio/* tests: a fake Twilio account, signed webhook requests, and invoices
whose callback was "placed" through voice_port with a captured token. No network."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app import config, engine, pipeline, repo, voice_port
from app.main import app

AUTH = "test-auth-token-not-real"
BASE = "https://cmb.test"
CALL_SID = "CA_test"


def sign(path: str, params: dict, *, auth: str = AUTH, url: str | None = None) -> str:
    return RequestValidator(auth).compute_signature(url or BASE + path, params)


def post(client: TestClient, path: str, params: dict | None = None, *, signed: bool = True, **kw):
    params = {"CallSid": CALL_SID, **(params or {})}
    headers = {"X-Twilio-Signature": sign(path, params, **kw)} if signed else {}
    return client.post(path, data=params, headers=headers)


@dataclass
class Placed:
    calls: list[dict] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)

    def token_for(self, verification_id: str) -> str:
        return next(c["token"] for c in self.calls if c["verification_id"] == verification_id)

    @property
    def last_token(self) -> str:
        return self.calls[-1]["token"]


@pytest.fixture
def twilio_env(db, monkeypatch):
    """VOICE_MODE=twilio with a fake account; place_call/cancel_call recorded instead of dialled."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", AUTH)
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE)
    monkeypatch.setenv("VOICE_MODE", "twilio")
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", "1")
    config.reload()
    placed = Placed()

    def fake_place(verification_id: str, token: str, to_e164: str) -> str:
        placed.calls.append({"verification_id": verification_id, "token": token, "to": to_e164})
        return CALL_SID

    monkeypatch.setattr(voice_port, "place_call", fake_place)
    monkeypatch.setattr(voice_port, "cancel_call", placed.cancelled.append)
    yield placed
    config.reload()


@pytest.fixture
def client(twilio_env):
    with TestClient(app) as c:
        yield c


def calling(sample: str) -> str:
    """Submit a sample; with twilio_env active its callback is placed (fake) and it is CALLING."""
    return pipeline.submit_invoice(engine.load_sample(sample), source="sample", sample_name=sample)


def latest(db, invoice_id: str) -> dict:
    return repo.latest_verification(db, invoice_id)

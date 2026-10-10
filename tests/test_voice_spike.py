"""Throwaway B2 spike routes (spec 002): TwiML shape and status callback, offline."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_spike_voice_returns_gather_twiml():
    r = TestClient(app).post("/twilio/spike/voice", data={"CallSid": "CA1", "CallStatus": "in-progress"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert "<Gather" in r.text and "/twilio/spike/answer" in r.text and "press 1" in r.text


def test_spike_answer_and_status():
    c = TestClient(app)
    r = c.post("/twilio/spike/answer", data={"CallSid": "CA1", "Digits": "1"})
    assert r.status_code == 200 and "<Hangup" in r.text
    assert c.post("/twilio/spike/status", data={"CallSid": "CA1", "CallStatus": "ringing"}).status_code == 204

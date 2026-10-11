"""PLAN.md §12.1: placing and cancelling calls, with a fake twilio.rest.Client (no network)."""
from __future__ import annotations

import pytest

from app import config, engine, pipeline, repo, voice_port
from app.voice import twilio_client

BASE = "https://cmb.test"
FROM = "+15555550100"


class FakeCalls:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kw):
        self.owner.created.append(kw)
        if self.owner.fail:
            raise RuntimeError("Twilio said no (balance)")
        return type("Call", (), {"sid": "CA_fake_1"})()


class FakeCallContext:
    def __init__(self, owner, sid):
        self.owner, self.sid = owner, sid

    def update(self, **kw):
        self.owner.updated.append((self.sid, kw))
        if self.owner.fail:
            raise RuntimeError("already completed")


class FakeClient:
    instances: list[FakeClient] = []

    def __init__(self, sid, token):
        self.args = (sid, token)
        self.created: list[dict] = []
        self.updated: list[tuple] = []
        self.fail = FakeClient.fail_next
        FakeClient.instances.append(self)

    fail_next = False

    @property
    def calls(self):
        owner = self

        class _Calls(FakeCalls):
            def __call__(self, sid):
                return FakeCallContext(owner, sid)

        return _Calls(owner)


@pytest.fixture
def fake_twilio(db, monkeypatch):
    FakeClient.instances = []
    FakeClient.fail_next = False
    monkeypatch.setattr(twilio_client, "Client", FakeClient)
    for k, v in {"TWILIO_ACCOUNT_SID": "AC_fake", "TWILIO_AUTH_TOKEN": "auth_fake", "TWILIO_FROM_NUMBER": FROM,
                 "PUBLIC_BASE_URL": BASE, "VOICE_MODE": "twilio"}.items():
        monkeypatch.setenv(k, v)
    config.reload()
    yield FakeClient
    config.reload()


def test_place_call_uses_the_plan_parameters(fake_twilio):
    assert twilio_client.place_call("ver_x", "tok", "+18165550199") == "CA_fake_1"
    client = fake_twilio.instances[-1]
    assert client.args == ("AC_fake", "auth_fake")
    assert client.created == [{
        "to": "+18165550199", "from_": FROM, "url": f"{BASE}/twilio/voice/tok", "method": "POST",
        "status_callback": f"{BASE}/twilio/status/tok",
        "status_callback_event": ["initiated", "ringing", "answered", "completed"],
        "status_callback_method": "POST", "timeout": 25,
    }]


def test_cancel_call_completes_and_never_raises(fake_twilio):
    assert twilio_client.cancel_call("CA1") is None
    assert fake_twilio.instances[-1].updated == [("CA1", {"status": "completed"})]
    fake_twilio.fail_next = True
    assert twilio_client.cancel_call("CA2") is None                  # swallowed
    assert voice_port.cancel_call("CA3") is None


def test_the_pipeline_dials_the_number_on_file(fake_twilio, db):
    iid = pipeline.submit_invoice(engine.load_sample("02_acme_fraud"), source="sample", sample_name="02_acme_fraud")
    inv = repo.get_invoice(db, iid)
    assert inv["status"] == "CALLING"
    created = [kw for c in fake_twilio.instances for kw in c.created]
    assert len(created) == 1
    on_file = repo.get_vendor(db, "ven_acme")["phone_on_file"]
    assert created[0]["to"] == on_file
    assert "(816) 555-0142" in inv["body_text"] and "8165550142" not in created[0]["to"].replace("-", "")
    ver = repo.latest_verification(db, iid)
    assert ver["call_sid"] == "CA_fake_1" and ver["source"] == "twilio" and ver["phone_called"] == on_file


def test_a_failed_call_holds_with_a_memo(fake_twilio, db):
    fake_twilio.fail_next = True
    iid = pipeline.submit_invoice(engine.load_sample("02_acme_fraud"), source="sample", sample_name="02_acme_fraud")
    inv = repo.get_invoice(db, iid)
    assert (inv["status"], inv["hold_reason"]) == ("HELD", "CALL_FAILED")
    assert inv["memo"] is not None and db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0


def test_voice_port_reaches_this_module(fake_twilio):
    assert voice_port.place_call("ver_y", "tok2", "+18165550199") == "CA_fake_1"
    assert fake_twilio.instances[-1].created[0]["url"] == f"{BASE}/twilio/voice/tok2"

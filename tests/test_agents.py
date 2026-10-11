"""The four agents on scripted models (PLAN.md §11.4; spec FR-003..FR-006, FR-008, FR-023)."""
from __future__ import annotations

import pytest

from app import ai_mode, config, engine, repo
from app.agents import analyst, intake_agent, payments, verifier
from app.agents.runner import RunContext, run_agent
from app.intake import eml
from app.state import HoldReason, Status
from tests.fakes import ScriptedModel, structured_turn, text_turn, tool_turn
from tests.helpers import drive_to


@pytest.fixture
def live():
    ai_mode.set_ai_mode("live", record=False)
    yield
    ai_mode.reset_override()


def _parsed(name: str) -> eml.ParsedEmail:
    return eml.parse((config.REPO_ROOT / "samples" / f"{name}.eml").read_bytes())


GOOD = {"vendor_name": "Acme Supply Co.", "invoice_number": "INV-20447", "amount": "$48,750.00", "due_date": "Today",
        "bank_name": "First Coastal Trust", "routing_number": "061100059", "account_number": "7730019942",
        "phone_numbers": ["(816) 555-0142"], "requests_payment_change": True,
        "pressure_phrases": ["pay today"], "verification_avoidance_phrases": ["do not call"],
        "instructions_aimed_at_ai": True}


def _ctx(agent: str, subject: str) -> RunContext:
    return RunContext("run_test", agent, subject)


# ---- Intake ------------------------------------------------------------------------

def test_intake_returns_a_valid_extraction(db, fake_model):
    model = fake_model(ScriptedModel([structured_turn(GOOD)]))
    out = intake_agent.run_intake(_ctx("intake", "inv_t"), "inv_t", _parsed("02_acme_fraud"))
    assert out.routing_number == "061100059" and out.instructions_aimed_at_ai is True
    prompt = model.prompt_text()
    assert "<email>" in prompt and "untrusted" in prompt.lower()                 # FR-023
    assert model.calls[0]["tools"] == ["InvoiceExtraction"]                       # no other tools


def test_intake_that_keeps_inventing_digits_falls_back(db, live, fake_model):
    bad = {**GOOD, "routing_number": "999999999"}
    fake_model(ScriptedModel([structured_turn(bad), structured_turn(bad), structured_turn(bad)]))
    parsed = _parsed("02_acme_fraud")
    result, outcome = run_agent("intake", "inv_t2", lambda ctx: intake_agent.run_intake(ctx, "inv_t2", parsed), 10,
                                lambda: None)
    assert (result, outcome) == (None, "fallback")


# ---- Analyst -----------------------------------------------------------------------

def _fraud(db):
    return engine.ingest_sample("02_acme_fraud", conn=db)


def test_analyst_report_with_tools(db, fake_model):
    iid = _fraud(db)
    report = {"headline": "Lookalike sender asks for a new bank", "explanation": "The sender imitates Acme.",
              "cited_flags": ["LOOKALIKE_DOMAIN", "BANK_CHANGED"], "additional_concerns": [],
              "recommended_next_step": "Wait for the callback."}
    model = fake_model(ScriptedModel([tool_turn("get_policy_findings"), tool_turn("get_vendor_record"),
                                      tool_turn("get_email_excerpt"), structured_turn(report)]))
    out = analyst.run_analyst(_ctx("analyst", iid), iid)
    assert out.cited_flags == ["LOOKALIKE_DOMAIN", "BANK_CHANGED"]
    prompt = model.prompt_text()
    assert "7730019942" not in prompt and "4421984821" not in prompt               # FR-022: masked for the model
    assert "<email>" in prompt
    assert set(model.calls[0]["tools"]) >= {"get_policy_findings", "get_vendor_record", "get_vendor_history",
                                            "get_email_excerpt"}


def test_analyst_citing_an_unknown_flag_falls_back_to_the_template(db, live, fake_model):
    iid = _fraud(db)
    bad = {"headline": "x", "explanation": "y", "cited_flags": ["MADE_UP"], "recommended_next_step": "z"}
    fake_model(ScriptedModel([structured_turn(bad), structured_turn(bad), structured_turn(bad)]))
    risk = repo.get_risk(db, iid)
    from app.agents.fallbacks import analyst_fallback
    result, outcome = run_agent("analyst", iid, lambda ctx: analyst.run_analyst(ctx, iid), 10, lambda: analyst_fallback(risk))
    assert outcome == "fallback"
    assert result.cited_flags and set(result.cited_flags) <= {f.code for f in risk.flags}


def test_analyst_fallback_template(db):
    iid = _fraud(db)
    from app.agents.fallbacks import analyst_fallback
    r = analyst_fallback(repo.get_risk(db, iid))
    assert r.headline.startswith("Held for a callback")
    assert "Sender domain imitates the vendor's" in r.explanation and "160 risk points" in r.explanation


def test_analyst_truncates_instead_of_rejecting_long_text(db):
    iid = _fraud(db)
    Model = analyst.make_report_model({f.code for f in repo.get_risk(db, iid).flags})
    m = Model(headline=" ".join(["word"] * 20), explanation=" ".join(["w"] * 120), cited_flags=["BANK_CHANGED"],
              recommended_next_step="x")
    assert len(m.headline.split()) == 12 and len(m.explanation.split()) == 90


def test_analyst_no_tools_mode(db, fake_model):
    iid = _fraud(db)
    model = fake_model(ScriptedModel([structured_turn({"headline": "h", "explanation": "e", "cited_flags": ["BANK_CHANGED"],
                                                      "recommended_next_step": "n"})]))
    analyst.run_analyst(_ctx("analyst", iid), iid, no_tools=True)
    assert model.calls[0]["tools"] == ["AnalystReport"]
    assert "BANK_CHANGED" in model.prompt_text()


# ---- Verifier ----------------------------------------------------------------------

def test_verifier_returns_the_label(db, fake_model):
    model = fake_model(ScriptedModel([structured_turn({"label": "DENIED", "rationale": "They said no."})]))
    out = verifier.run_verifier(_ctx("verifier", "inv_v"), "inv_v", "Did Acme request this bank change?",
                                "No, we never changed banks")
    assert out.label == "DENIED"
    assert "No, we never changed banks" in model.prompt_text()


def test_verifier_falls_back_to_unclear(db, live, fake_model):
    from app.agents.fallbacks import verifier_fallback
    fake_model(ScriptedModel([text_turn("not structured"), text_turn("still not")]))
    result, outcome = run_agent("verifier", "inv_v2", lambda ctx: verifier.run_verifier(ctx, "inv_v2", "q", "yes"), 10,
                                verifier_fallback)
    assert outcome == "fallback" and result.label == "UNCLEAR"


# ---- Payments ----------------------------------------------------------------------

def test_payments_releases_an_eligible_invoice(db, live, fake_model):
    iid = engine.ingest_sample("01_acme_normal", conn=db)          # AUTO_APPROVED
    fake_model(ScriptedModel([tool_turn("get_case_summary"), tool_turn("release_payment"),
                              text_turn("Released the invoice. Destination is the account on file.")]))
    out = payments.process_payments(iid)
    assert out["by"] == "agent" and out["called"] == ["get_case_summary", "release_payment"]
    assert repo.get_invoice(db, iid)["status"] == "RELEASED"
    pay = repo.get_payment(db, iid)
    assert pay["released_by"] == "agent:payments" and pay["account"] == "4421984821"
    assert out["memo"]


def test_payments_tools_are_bound_to_one_invoice(db):
    tools = payments.make_payment_tools("inv_x", _ctx("payments", "inv_x"), {"called": []})
    assert [t.tool_name for t in tools] == ["get_case_summary", "release_payment", "hold_payment"]
    for t in tools:                                                  # FR-008: no invoice id parameter
        assert "invoice" not in str(t.tool_spec["inputSchema"]["json"].get("properties", {})).lower()


def test_payments_hold_on_eligible_invoice_is_honoured(db, live, fake_model):
    iid = engine.ingest_sample("01_acme_normal", conn=db)
    fake_model(ScriptedModel([tool_turn("get_case_summary"), tool_turn("hold_payment", {"reason": "uneasy"}),
                              text_turn("Held.")]))
    payments.process_payments(iid)
    inv = repo.get_invoice(db, iid)
    assert (inv["status"], inv["hold_reason"]) == ("HELD", "AGENT_HOLD")
    assert repo.get_payment(db, iid) is None


def test_payments_without_a_tool_call_lets_policy_decide(db, live, fake_model):
    iid = engine.ingest_sample("01_acme_normal", conn=db)
    fake_model(ScriptedModel([text_turn("I will not do anything.")]))
    out = payments.process_payments(iid)
    assert out["by"] == "fallback"
    assert repo.get_payment(db, iid)["released_by"] == "policy:auto"
    notes = [e for e in db.execute("SELECT data FROM audit_log WHERE subject_id=? AND event='memo_written'", (iid,))]
    assert any("agent took no action; policy decided" in r[0] for r in notes)


def test_payments_ai_off_policy_holds_an_ineligible_held_invoice(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    out = payments.process_payments(iid)
    assert out["by"] == "fallback" and "Held" in out["memo"]
    assert repo.get_payment(db, iid) is None

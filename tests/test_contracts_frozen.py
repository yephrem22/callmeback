"""Milestone A1: the §7 contracts are in place, verbatim, and the seed data
matches PLAN.md §8.1 and §8.2."""
from __future__ import annotations

import json
from pathlib import Path

from app import models, repo
from app.config import REPO_ROOT
from app.state import HoldReason, Status

CONTRACTS = REPO_ROOT / "specs" / "003-core-engine" / "contracts"


def test_schema_is_byte_identical_to_frozen_contract():
    assert (REPO_ROOT / "app" / "schema.sql").read_bytes() == (CONTRACTS / "schema.sql").read_bytes()


def test_init_db_creates_the_nine_tables(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"vendors", "vendor_bank_history", "invoice_history", "invoices", "verifications",
            "payments", "audit_log", "agent_traces", "change_cases"} <= names
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_models_match_section_7_4():
    assert set(models.RiskResult.model_fields) == {
        "flags", "points", "tier", "action", "vendor_id", "sender_status", "bank_changed",
        "proposed_bank_name", "proposed_routing", "proposed_account", "amount_cents", "median_cents",
        "policy_version"}
    assert models.RiskResult.model_fields["policy_version"].default == "2026-10-10.1"
    assert set(models.FieldValue.model_fields) == {"value", "source", "llm_value", "mismatch"}
    assert set(models.ExtractionResult.model_fields) == {
        "vendor_name", "invoice_number", "amount", "due_date", "bank_name", "routing_number",
        "account_number", "phone_numbers_in_email", "requests_payment_change", "llm_status"}
    assert set(models.InvoiceExtraction.model_fields) == {
        "vendor_name", "invoice_number", "amount", "due_date", "bank_name", "routing_number",
        "account_number", "phone_numbers", "requests_payment_change", "pressure_phrases",
        "verification_avoidance_phrases", "instructions_aimed_at_ai"}
    assert set(models.AnalystReport.model_fields) == {
        "headline", "explanation", "cited_flags", "additional_concerns", "recommended_next_step"}
    assert set(models.VerifierLabel.model_fields) == {"label", "rationale"}
    assert set(models.CallContext.model_fields) == {
        "verification_id", "subject_id", "kind", "payer_name", "counterparty_name", "amount_cents",
        "change_type", "expected_last4", "phone_to_call", "attempts"}
    assert set(models.Flag.model_fields) == {"code", "points", "title", "detail", "evidence"}


def test_status_and_hold_reason_members_match_section_7_3():
    assert [s.value for s in Status] == [
        "RECEIVED", "EXTRACTED", "SCORED", "AUTO_APPROVED", "NEEDS_REVIEW", "REVIEW_APPROVED",
        "CALL_PENDING", "CALLING", "VERIFYING", "CONFIRMED", "RELEASED", "HELD", "FAILED"]
    assert {h.value for h in HoldReason} == {
        "DENIED_BY_VENDOR", "UNCLEAR_ANSWER", "NO_ANSWER", "LAST4_MISMATCH", "VERIFIER_DISAGREED",
        "REVIEW_REJECTED", "UNKNOWN_VENDOR", "CALL_FAILED", "AGENT_HOLD"}


def test_samples_manifest_matches_files():
    samples = REPO_ROOT / "samples"
    manifest = json.loads((samples / "manifest.json").read_text())
    names = [m["name"] for m in manifest]
    assert names == ["01_acme_normal", "02_acme_fraud", "03_heartland_bank_change",
                     "04_prairie_review", "05_unknown_vendor"]
    for m in manifest:
        assert (samples / f"{m['name']}.eml").exists()
        assert m["title"] and m["description"]
    for name in names:
        text = (samples / f"{name}.eml").read_text()
        assert "MIME-Version: 1.0" in text
        assert 'Content-Type: text/plain; charset="utf-8"' in text
        assert text.index("Message-ID:") < text.index("MIME-Version:")


def test_seed_vendors_and_medians(db):
    vendors = {v["id"]: v for v in repo.list_vendors(db)}
    assert set(vendors) == {"ven_acme", "ven_heartland", "ven_prairie"}
    assert vendors["ven_acme"]["domains"] == ["acme-supply.com"]
    assert vendors["ven_heartland"]["routing"] == "102030402"
    assert vendors["ven_heartland"]["account"] == "5512003377"
    assert vendors["ven_prairie"]["bank_name"] == "Midland Trust Bank"
    assert all(v["phone_on_file"].startswith("+") for v in vendors.values())
    assert repo.vendor_median_cents(db, "ven_acme") == 1202000
    assert repo.vendor_median_cents(db, "ven_heartland") == 399500
    assert repo.vendor_median_cents(db, "ven_prairie") == 249900
    hist = repo.vendor_history(db, "ven_acme")
    assert [h["invoice_number"] for h in hist] == ["INV-20301", "INV-20322", "INV-20355",
                                                   "INV-20381", "INV-20398", "INV-20412"]
    assert hist[0]["paid_on"] == "2026-04-15" and hist[-1]["paid_on"] == "2026-09-15"


def test_reset_demo_data_restores_vendors_and_starts_chain(db):
    from app import seed
    db.execute("UPDATE vendors SET bank_name='X', routing='044000105', account='6620194455' WHERE id='ven_heartland'")
    seed.reset_demo_data(db)
    v = repo.get_vendor(db, "ven_heartland")
    assert (v["bank_name"], v["routing"], v["account"]) == ("River City Bank", "102030402", "5512003377")
    rows = db.execute("SELECT seq, event FROM audit_log ORDER BY seq").fetchall()
    assert [(r[0], r[1]) for r in rows] == [(1, "demo_reset")]

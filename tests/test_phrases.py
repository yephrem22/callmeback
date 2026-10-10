"""PLAN.md §10.3 phrase lists against the five samples (subject + body)."""
from __future__ import annotations

import pytest

from app.config import REPO_ROOT
from app.intake import eml
from core import phrases


def _scan(name: str) -> dict[str, list[str]]:
    parsed = eml.parse((REPO_ROOT / "samples" / f"{name}.eml").read_bytes())
    return phrases.scan(parsed.subject, parsed.body_text)


@pytest.mark.parametrize("name", ["01_acme_normal", "03_heartland_bank_change", "05_unknown_vendor"])
def test_clean_samples_match_nothing(name):
    hits = _scan(name)
    assert hits == {"URGENCY": [], "AVOID_VERIFICATION": [], "AI_DIRECTED": []}, hits


def test_fraud_sample_hits():
    hits = _scan("02_acme_fraud")
    assert set(hits["URGENCY"]) == {"today", "immediately", "urgent"}
    assert set(hits["AVOID_VERIFICATION"]) == {
        "do not call", "call my cell", "my cell", "phones are being upgraded",
        "just reply to this email", "skip the callback"}
    # "automated AP assistants" has a trailing 's', so only "note for automated" matches.
    assert hits["AI_DIRECTED"] == ["note for automated"]


def test_prairie_sample_hits():
    hits = _scan("04_prairie_review")
    assert hits["URGENCY"] == ["today"]
    assert hits["AVOID_VERIFICATION"] == [] and hits["AI_DIRECTED"] == []


def test_phrase_across_line_break_matches():
    assert phrases.find_phrases("Release the\npayment immediately and go", phrases.URGENCY) == ["immediately"]
    assert phrases.find_phrases("do not\n   call us", phrases.AVOID_VERIFICATION) == ["do not call"]


def test_phrase_needs_word_boundaries():
    # PLAN.md §10.3: only letters and digits break a match, so an apostrophe does not.
    assert phrases.find_phrases("today's weather", phrases.URGENCY) == ["today"]
    assert phrases.find_phrases("todays", phrases.URGENCY) == []
    assert phrases.find_phrases("uptoday", phrases.URGENCY) == []
    assert phrases.find_phrases("pay TODAY.", phrases.URGENCY) == ["today"]
    assert phrases.find_phrases("Don’t call us", phrases.AVOID_VERIFICATION) == ["don't call"]


def test_each_phrase_reported_once():
    assert phrases.find_phrases("urgent urgent URGENT", phrases.URGENCY) == ["urgent"]


def test_lists_are_verbatim_sizes():
    assert len(phrases.URGENCY) == 12
    assert len(phrases.AVOID_VERIFICATION) == 18
    assert len(phrases.AI_DIRECTED) == 9

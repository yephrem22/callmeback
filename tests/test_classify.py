"""PLAN.md §12.4: the deterministic answer classifier (§17.1 test_classify.py)."""
from __future__ import annotations

import pytest

from app import voice_port
from app.voice.classify import classify_answer

TABLE = [
    (None, "No, we never changed banks", "NO"),
    (None, "nope that wasn't us", "NO"),
    (None, "Yes we did", "YES"),
    (None, "yeah that's right", "YES"),
    (None, "yeah that's right we didn't change anything", "UNCLEAR"),
    (None, "I don't know", "NO"),                 # fail closed
    (None, "That's not correct", "UNCLEAR"),
    (None, "No.", "NO"),
    (None, "", "UNCLEAR"),
    ("1", None, "YES"),
    ("9", None, "UNCLEAR"),
]


@pytest.mark.parametrize(("digits", "speech", "expected"), TABLE)
def test_plan_table(digits, speech, expected):
    assert classify_answer(digits, speech) == expected


def test_keypad_two_is_no():
    assert classify_answer("2", None) == "NO"


def test_digits_win_over_speech():
    assert classify_answer("1", "no") == "YES"
    assert classify_answer("2", "yes we did") == "NO"


def test_speech_is_normalized():
    assert classify_answer(None, "that wasn’t\nus") == "NO"           # curly quote and a line break
    assert classify_answer(None, "  YES   WE   DID ") == "YES"


def test_nothing_is_unclear():
    assert classify_answer(None, None) == "UNCLEAR"
    assert classify_answer("", "") == "UNCLEAR"


def test_the_pipeline_uses_the_real_classifier():
    # the pre-006 stub in app/voice_port.py answered UNCLEAR for every speech
    assert voice_port.classify_answer(None, "Yes we did") == "YES"
    assert voice_port.classify_answer(None, "No, we never changed banks") == "NO"

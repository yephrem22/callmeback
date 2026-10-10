"""PLAN.md §17.1 vectors for core/checks.py."""
from __future__ import annotations

import pytest

from core.checks import aba_valid, explain_lookalike, find_us_phones, is_lookalike, lookalike_diff


@pytest.mark.parametrize("r", ["123456780", "102030402", "301112228", "061100059", "044000105"])
def test_aba_valid_true(r):
    assert aba_valid(r) is True


@pytest.mark.parametrize("r", ["071000014", "123456789", "", None, "12345678", "abcdefghi"])
def test_aba_valid_false(r):
    assert aba_valid(r) is False


@pytest.mark.parametrize("sender,known", [
    ("acme-supp1y.com", "acme-supply.com"),
    ("acmesupply.com", "acme-supply.com"),
    ("acme-supply.co", "acme-supply.com"),
    ("prairie-cloud.io", "prairiecloud.io"),
])
def test_is_lookalike_true(sender, known):
    assert is_lookalike(sender, known) is True


@pytest.mark.parametrize("sender,known", [
    ("acme-supply.com", "acme-supply.com"),
    ("mail.acme-supply.com", "acme-supply.com"),
    ("gmail.com", "acme-supply.com"),
    ("northwind-parts.co", "acme-supply.com"),
    ("notadomain", "acme-supply.com"),
])
def test_is_lookalike_false(sender, known):
    assert is_lookalike(sender, known) is False


def test_explain_lookalike_single_swap():
    assert explain_lookalike("acme-supp1y.com", "acme-supply.com") == \
        "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')"
    assert lookalike_diff("acme-supp1y.com", "acme-supply.com") == [{"index": 9, "sender": "1", "known": "l"}]


def test_explain_lookalike_other_shapes():
    assert "(.co in place of .com)" in explain_lookalike("acme-supply.co", "acme-supply.com")
    assert "missing '-'" in explain_lookalike("acmesupply.com", "acme-supply.com")
    assert "added '-'" in explain_lookalike("prairie-cloud.io", "prairiecloud.io")


def test_find_us_phones():
    body = "call my cell at (816) 555-0142 or 816-555-0199. Account number: 7730019942 Routing: 061100059"
    assert find_us_phones(body) == ["(816) 555-0142", "816-555-0199"]
    assert find_us_phones("7730019942") == []
    assert find_us_phones("") == []

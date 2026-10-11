"""PLAN.md §17.1: the Intake schema refuses invented digits ("our schema refuses invented digits")."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.intake_agent import make_extraction_model

BODY = """Invoice number: INV-20447
Amount due: $48,750.00
Bank: First Coastal Trust
Routing number: 061100059
Account number: 7730-019 942
"""

BASE = {"vendor_name": "Acme", "invoice_number": "INV-20447", "amount": "$48,750.00", "due_date": "Today",
        "bank_name": "First Coastal Trust", "routing_number": "061100059", "account_number": "7730019942"}


def _make(**over):
    return make_extraction_model(BODY)(**{**BASE, **over})


def test_values_present_in_the_email_are_accepted():
    m = _make()
    assert m.routing_number == "061100059" and m.account_number == "7730019942"


def test_routing_number_not_in_the_email_is_rejected():
    with pytest.raises(ValidationError) as e:
        _make(routing_number="061100058")
    msg = str(e.value)
    assert "routing_number '061100058' does not appear in the email; copy it exactly or return null" in msg


@pytest.mark.parametrize("field,value", [("account_number", "7730019943"), ("amount", "$48,760.00")])
def test_other_digit_fields_are_checked(field, value):
    with pytest.raises(ValidationError) as e:
        _make(**{field: value})
    assert "does not appear in the email" in str(e.value)


def test_digits_split_by_spaces_or_dashes_still_match():
    assert _make(account_number="7730019942").account_number == "7730019942"
    assert _make(account_number="7730-019942").account_number == "7730-019942"


def test_amount_written_differently_but_same_digits_is_accepted():
    assert _make(amount="48750.00").amount == "48750.00"


def test_null_is_accepted():
    m = _make(routing_number=None, account_number=None, amount=None)
    assert (m.routing_number, m.account_number, m.amount) == (None, None, None)


def test_model_is_named_for_the_structured_output_tool():
    assert make_extraction_model(BODY).__name__ == "InvoiceExtraction"

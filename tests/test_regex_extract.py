"""PLAN.md §9.2 regex extraction on all five samples, plus §9.1 parsing."""
from __future__ import annotations

import pytest

from app.config import REPO_ROOT
from app.intake import eml, merge, regex_extract

EXPECTED = {
    "01_acme_normal": ("123456780", "4421984821", "12150.00", "INV-20431", "Plains Federal Bank", "November 7, 2026"),
    "02_acme_fraud": ("061100059", "7730019942", "48750.00", "INV-20447", "First Coastal Trust", "Today"),
    "03_heartland_bank_change": ("044000105", "6620194455", "4120.00", "HL-8812", "Gateway National Bank", "November 9, 2026"),
    "04_prairie_review": ("301112228", "8800142201", "5240.00", "PCH-1107", "Midland Trust Bank", "October 12, 2026"),
    "05_unknown_vendor": ("071000014", "5098812230", "7300.00", "NW-5531", "Lakeside Commerce Bank", "October 30, 2026"),
}


def _parsed(name: str) -> eml.ParsedEmail:
    return eml.parse((REPO_ROOT / "samples" / f"{name}.eml").read_bytes())


@pytest.mark.parametrize("name", list(EXPECTED))
def test_regex_fields_per_sample(name):
    rx = regex_extract.extract(_parsed(name).body_text)
    routing, account, amount, inv, bank, due = EXPECTED[name]
    assert (rx.routing, rx.account, rx.amount, rx.invoice_number, rx.bank_name, rx.due_date) == \
        (routing, account, amount, inv, bank, due)
    assert rx.mismatch is False


def test_parse_headers():
    p = _parsed("02_acme_fraud")
    assert p.from_name == "Acme Supply Co. Billing"
    assert p.from_email == "billing@acme-supp1y.com"
    assert p.from_domain == "acme-supp1y.com"
    assert p.reply_to == "acme.supply.billing@gmail.com"
    assert p.reply_to_domain == "gmail.com"
    assert p.subject.startswith("URGENT: updated bank details")
    assert p.received_at == "2026-10-09T21:52:00Z"
    assert len(p.raw_sha256) == 64
    p1 = _parsed("01_acme_normal")
    assert p1.reply_to == "" and p1.reply_to_domain == ""


def test_invoice_november_is_not_an_invoice_number():
    rx = regex_extract.extract("Please pay invoice November 7 soon.\nInvoice number: INV-1\n")
    assert rx.invoice_number == "INV-1"
    rx2 = regex_extract.extract("invoice no. ABC-123 is due")
    assert rx2.invoice_number == "ABC-123"


def test_two_different_account_numbers_set_mismatch():
    rx = regex_extract.extract("Account number: 1111222233\nAccount number: 9999888877\nRouting number: 061100059")
    assert rx.account == "1111222233"
    assert rx.all_account == ["1111222233", "9999888877"]
    assert rx.mismatch is True
    same = regex_extract.extract("Account number: 1111222233\nAcct #: 1111222233")
    assert same.mismatch is False


def test_amount_fallback_and_normalisation():
    assert regex_extract.extract("Please remit $1,234 for services").amount == "1234.00"
    assert regex_extract.extract("Total due: $ 99.50").amount == "99.50"
    assert regex_extract.extract("nothing here").amount is None
    assert regex_extract.amount_to_cents("48750.00") == 4875000


def test_merge_with_ai_off_uses_text_only():
    p = _parsed("02_acme_fraud")
    rx = regex_extract.extract(p.body_text)
    out = merge.merge(rx, None, p.body_text, p.from_name, llm_status="fallback")
    assert out.routing_number.value == "061100059" and out.routing_number.source == "regex"
    assert out.account_number.source == "regex" and out.amount.source == "regex"
    assert out.vendor_name.value == "Acme Supply Co." and out.vendor_name.source == "header"
    assert out.phone_numbers_in_email == ["(816) 555-0142"]
    assert out.requests_payment_change is None
    assert out.llm_status == "fallback"
    assert merge.has_mismatch(out, rx) is False


def test_merge_rejects_llm_digits_not_in_body():
    from app.models import InvoiceExtraction
    body = "Routing number: 061100059\nAmount due: $10.00"
    rx = regex_extract.extract(body)
    llm = InvoiceExtraction(vendor_name="Acme Supply Co.", invoice_number=None, amount="$10.00",
                            due_date=None, bank_name=None, routing_number="999999999",
                            account_number="1234567890")
    out = merge.merge(rx, llm, body, "Acme Billing", llm_status="ok")
    assert out.routing_number.value == "061100059" and out.routing_number.mismatch is True
    assert out.routing_number.source == "regex" and out.routing_number.llm_value == "999999999"
    assert out.account_number.value is None and out.account_number.source == "none"
    assert out.amount.source == "both"
    assert out.vendor_name.source == "llm"
    assert merge.has_mismatch(out, rx) is True


def test_vendor_name_from_header():
    assert merge.vendor_name_from_header("Acme Supply Co. Billing") == "Acme Supply Co."
    assert merge.vendor_name_from_header("Heartland Logistics AR") == "Heartland Logistics"
    assert merge.vendor_name_from_header("Prairie Cloud Hosting Billing") == "Prairie Cloud Hosting"
    assert merge.vendor_name_from_header("Northwind Industrial Parts") == "Northwind Industrial Parts"


def test_parse_rejects_oversize_and_garbage():
    with pytest.raises(ValueError):
        eml.parse(b"x" * (1_048_576 + 1))
    with pytest.raises(ValueError):
        eml.parse(b"\x00\x01 not an email at all")


def test_parse_html_only_body_and_ignores_attachments():
    raw = (b"From: a@acme-supply.com\r\nTo: ap@x\r\nSubject: s\r\nMIME-Version: 1.0\r\n"
           b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n--B\r\nContent-Type: text/html\r\n\r\n'
           b"<html><body><p>Invoice number: HTML-1</p><p>Amount due: $5.00</p><p>Bank: Any &amp; Co</p></body></html>\r\n"
           b'--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="x.pdf"\r\n\r\n%PDF\r\n--B--\r\n')
    p = eml.parse(raw)
    assert "Invoice number: HTML-1" in p.body_text
    assert "<p>" not in p.body_text
    assert "Any & Co" in p.body_text
    assert "%PDF" not in p.body_text

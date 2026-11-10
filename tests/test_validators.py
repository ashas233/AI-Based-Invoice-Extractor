import pytest

from app import extractor
from app.schemas import Invoice, LineItem
from app.validators import check_invoice


def make(**kw):
    base = dict(vendor_name="Acme", line_items=[LineItem(description="a", quantity=2, unit_price=5, amount=10)],
                subtotal=10, tax=1, total=11, invoice_date="2024-05-01", currency="USD")
    base.update(kw)
    return Invoice(**base)


def test_clean_invoice_passes():
    assert check_invoice(make()) == []


def test_total_mismatch_flagged():
    assert any("!= total" in m for m in check_invoice(make(total=15)))


def test_subtotal_mismatch_flagged():
    assert any("subtotal" in m for m in check_invoice(make(subtotal=99, total=100)))


def test_bad_date_and_currency():
    issues = check_invoice(make(invoice_date="2024-13-45", currency="dollars"))
    assert len(issues) == 2


def test_line_math():
    inv = make(line_items=[LineItem(description="a", quantity=3, unit_price=5, amount=10)])
    assert any("Line 1" in m for m in check_invoice(inv))


def test_extract_requires_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not configured"):
        extractor.extract([])


def test_demo_extract_works_without_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = extractor.demo_extract()

    assert result.invoice.invoice_number == "DEMO-2026-001"
    assert result.issues == []
    assert result.input_tokens == result.output_tokens == 0

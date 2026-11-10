"""Vision-LLM extraction with a validate -> self-correct loop."""
import base64
import json
import os
import time
from dataclasses import dataclass

import anthropic

from .schemas import Invoice
from .validators import check_invoice

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

SYSTEM = """You extract structured data from invoices and receipts (images of any quality).
Return ONLY one JSON object, with no prose and no markdown fences, matching this JSON schema:
{schema}

Rules:
- Use null for any field that is not visible. Never guess or invent values.
- Dates must be YYYY-MM-DD. If the format is ambiguous (01/02/2024), prefer day-first unless the document shows otherwise.
- Numbers must be plain floats with no currency symbols or thousands separators.
- currency is a 3-letter ISO code (PKR, USD, EUR...). Infer it from symbols like Rs./PKR/$ only if printed.
- Include every line item, across all pages. Do not merge or skip rows.
- Text may be in English, Urdu or both; copy names exactly as printed."""


@dataclass
class Extraction:
    invoice: Invoice
    issues: list[str]
    input_tokens: int
    output_tokens: int
    latency_s: float
    attempts: int


def demo_extract() -> Extraction:
    invoice = Invoice(
        vendor_name="Northwind Demo Supplies",
        invoice_number="DEMO-2026-001",
        invoice_date="2026-11-01",
        currency="USD",
        line_items=[
            {"description": "Printer paper (demo)", "quantity": 2, "unit_price": 25, "amount": 50},
            {"description": "Pens (demo)", "quantity": 1, "unit_price": 15, "amount": 15},
        ],
        subtotal=65,
        tax=5,
        total=70,
    )
    return Extraction(invoice, check_invoice(invoice), 0, 0, 0, 0)


def _blocks(images: list[bytes]) -> list[dict]:
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(b).decode(),
            },
        }
        for b in images
    ]


def _parse(text: str) -> Invoice:
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("No JSON object in model output")
    return Invoice.model_validate_json(s[i : j + 1])


def extract(images: list[bytes], max_corrections: int = 1) -> Extraction:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. Add it to the project .env file "
            "and restart the API server."
        )
    client = anthropic.Anthropic()
    system = SYSTEM.format(schema=json.dumps(Invoice.model_json_schema()))
    messages = [
        {
            "role": "user",
            "content": _blocks(images) + [{"type": "text", "text": "Extract this invoice."}],
        }
    ]
    t0 = time.time()
    tin = tout = 0
    invoice, issues = None, []

    for attempt in range(1, max_corrections + 2):
        resp = client.messages.create(
            model=MODEL, max_tokens=3000, system=system, messages=messages
        )
        tin += resp.usage.input_tokens
        tout += resp.usage.output_tokens
        raw = resp.content[0].text
        try:
            invoice = _parse(raw)
            issues = check_invoice(invoice)
            problems = issues
        except ValueError as e:  # includes pydantic ValidationError
            problems = [f"Your output was not valid for the schema: {e}"]

        if not problems or attempt > max_corrections:
            break
        messages += [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "Automatic checks found problems:\n- " + "\n- ".join(problems) +
                    "\nRe-examine the document carefully and return corrected JSON only. "
                    "If the document itself is inconsistent, keep what is printed; do not invent values."
                ),
            },
        ]

    if invoice is None:
        raise ValueError("Model did not return valid invoice JSON")
    return Extraction(invoice, issues, tin, tout, round(time.time() - t0, 2), attempt)

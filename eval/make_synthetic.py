"""Generate synthetic invoice PDFs + ground-truth JSON for evaluation.

Usage: python eval/make_synthetic.py 30
Synthetic data is a start. Add real, messy phone photos and scans to your dataset too.
"""
import json
import random
import sys
from pathlib import Path

from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

fake = Faker()
OUT = Path(__file__).parent / "dataset"
CURRENCIES = ["USD", "PKR", "EUR", "GBP"]


def make(i: int):
    items = []
    for _ in range(random.randint(2, 8)):
        q, p = random.randint(1, 10), round(random.uniform(5, 500), 2)
        items.append({"description": fake.catch_phrase()[:38], "quantity": q,
                      "unit_price": p, "amount": round(q * p, 2)})
    subtotal = round(sum(x["amount"] for x in items), 2)
    tax = round(subtotal * random.choice([0.05, 0.10, 0.17, 0.18]), 2)
    truth = {
        "vendor_name": fake.company(), "invoice_number": f"INV-{random.randint(1000, 99999)}",
        "invoice_date": fake.date_between("-1y", "today").isoformat(),
        "currency": random.choice(CURRENCIES), "tax_id": None,
        "line_items": items, "subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2),
    }
    font = random.choice(["Helvetica", "Times-Roman", "Courier"])
    c = canvas.Canvas(str(OUT / f"inv{i:03d}.pdf"), pagesize=A4)
    w, h = A4
    c.setFont(font + ("-Bold" if font != "Times-Roman" else "-Bold"), 18)
    c.drawString(40, h - 50, truth["vendor_name"])
    c.setFont(font, 11)
    c.drawString(40, h - 80, f"Invoice No: {truth['invoice_number']}")
    c.drawString(40, h - 95, f"Date: {truth['invoice_date']}")
    c.drawString(40, h - 110, f"Currency: {truth['currency']}")
    y = h - 150
    c.drawString(40, y, "Description"); c.drawString(300, y, "Qty")
    c.drawString(360, y, "Unit price"); c.drawString(460, y, "Amount")
    for it in items:
        y -= 18
        c.drawString(40, y, it["description"]); c.drawString(300, y, str(it["quantity"]))
        c.drawString(360, y, f"{it['unit_price']:.2f}"); c.drawString(460, y, f"{it['amount']:.2f}")
    y -= 35
    c.drawString(360, y, "Subtotal:"); c.drawString(460, y, f"{subtotal:.2f}")
    c.drawString(360, y - 16, "Tax:"); c.drawString(460, y - 16, f"{tax:.2f}")
    c.drawString(360, y - 32, "TOTAL:"); c.drawString(460, y - 32, f"{truth['total']:.2f}")
    c.save()
    (OUT / f"inv{i:03d}.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    for i in range(1, n + 1):
        make(i)
    print(f"Wrote {n} invoices to {OUT}")

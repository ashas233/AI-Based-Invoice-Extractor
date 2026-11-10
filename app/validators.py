"""Business-rule checks. Never trust the model's arithmetic."""
import re
from datetime import date

from .schemas import Invoice


def check_invoice(inv: Invoice, tol: float = 0.02) -> list[str]:
    issues: list[str] = []
    items_sum = round(sum(i.amount for i in inv.line_items), 2)

    if inv.line_items and inv.subtotal is not None and abs(items_sum - inv.subtotal) > tol:
        issues.append(
            f"Line items sum to {items_sum} but subtotal is {inv.subtotal} "
            "(could be a missed row, or discounts/shipping)."
        )
    if inv.subtotal is not None and inv.tax is not None:
        if abs(inv.subtotal + inv.tax - inv.total) > tol:
            issues.append(f"Subtotal {inv.subtotal} + tax {inv.tax} != total {inv.total}.")
    elif inv.line_items and inv.subtotal is None and inv.tax is None:
        if abs(items_sum - inv.total) > tol:
            issues.append(f"Line items sum to {items_sum} but total is {inv.total}.")

    for n, it in enumerate(inv.line_items, 1):
        if it.quantity is not None and it.unit_price is not None:
            if abs(it.quantity * it.unit_price - it.amount) > max(tol, 0.01 * abs(it.amount)):
                issues.append(f"Line {n}: {it.quantity} x {it.unit_price} != {it.amount}.")

    if inv.invoice_date:
        try:
            date.fromisoformat(inv.invoice_date)
        except ValueError:
            issues.append(f"Invalid date '{inv.invoice_date}' (expected YYYY-MM-DD).")
    if inv.currency and not re.fullmatch(r"[A-Z]{3}", inv.currency):
        issues.append(f"Currency '{inv.currency}' is not a 3-letter ISO code.")
    if inv.total < 0:
        issues.append("Total is negative (credit note?).")
    return issues

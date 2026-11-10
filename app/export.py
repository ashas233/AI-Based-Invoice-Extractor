import io
import json

import pandas as pd


def rows_to_df(rows: list[dict]) -> pd.DataFrame:
    flat = []
    for r in rows:
        data = json.loads(r["data_json"])
        base = {
            "invoice_id": r["id"], "vendor": r["vendor"], "vendor_canonical": r["vendor_canonical"],
            "invoice_number": r["invoice_number"], "invoice_date": r["invoice_date"],
            "currency": r["currency"], "subtotal": data.get("subtotal"),
            "tax": data.get("tax"), "total": r["total"],
        }
        for it in (data.get("line_items") or [{}]):
            flat.append({**base,
                         "item_description": it.get("description"),
                         "item_quantity": it.get("quantity"),
                         "item_unit_price": it.get("unit_price"),
                         "item_amount": it.get("amount")})
    return pd.DataFrame(flat)


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")  # BOM so Excel shows Urdu correctly


def to_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="invoices")
    return buf.getvalue()

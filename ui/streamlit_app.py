import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

from app.preprocess import to_images  # noqa: E402

API = os.getenv("API_URL", "http://localhost:8000")
DEMO_MODE = os.getenv("DEMO_MODE") == "1"
COLS = ["description", "quantity", "unit_price", "amount"]

st.set_page_config(page_title="Invoice Extractor", layout="wide")
st.title("Invoice Extractor")
if DEMO_MODE:
    tab_extract = st.container()
else:
    tab_extract, tab_history = st.tabs(["Extract", "History & export"])


def num(s: str):
    s = (s or "").strip().replace(",", "")
    return float(s) if s else None


def txt(s: str):
    s = (s or "").strip()
    return s or None


with tab_extract:
    if DEMO_MODE:
        st.info("Public sample-only demo. Uploading and saving invoices are disabled.")
        f = None
    else:
        f = st.file_uploader("Upload an invoice", type=["pdf", "png", "jpg", "jpeg", "webp"])
    if st.button("Try free sample demo", help="Loads simulated sample data; no API key or uploaded invoice is used."):
        try:
            r = requests.post(f"{API}/demo", timeout=30)
            if r.ok:
                st.session_state["res"] = r.json()
                st.session_state["fname"] = "__demo__"
                st.session_state["demo"] = True
            else:
                st.error(r.text)
        except requests.RequestException as e:
            st.error(f"Cannot reach API at {API}: {e}")

    if f:
        data = f.getvalue()
        if st.button("Extract", type="primary"):
            st.session_state["demo"] = False
            with st.spinner("Reading invoice..."):
                try:
                    r = requests.post(f"{API}/extract", files={"file": (f.name, data)}, timeout=180)
                except requests.RequestException as e:
                    st.error(f"Cannot reach API at {API}: {e}")
                    r = None
            if r is not None:
                if r.ok:
                    st.session_state["res"], st.session_state["fname"] = r.json(), f.name
                else:
                    st.error(r.text)

    res = st.session_state.get("res")
    demo = st.session_state.get("demo", False)
    show_result = res and (demo or (f is not None and st.session_state.get("fname") == f.name))

    if f or (demo and show_result):
        left, right = st.columns(2)
        with left:
            if demo:
                st.subheader("Sample invoice")
                st.info("This is simulated sample data, not an extraction from a document.")
            elif f:
                st.subheader("Original")
                try:
                    for img in to_images(data, f.name):
                        st.image(img, use_container_width=True)
                except Exception as e:
                    st.error(f"Preview failed: {e}")

        if show_result:
            inv, k = res["invoice"], st.session_state.get("fname", "demo")
            if demo:
                k = "demo"
            with right:
                st.subheader("Sample data (editable)" if demo else "Extracted (editable)")
                if res["duplicate"]:
                    st.warning("Possible duplicate: same vendor, invoice number and total already saved.")
                for msg in res["issues"]:
                    st.error(msg)
                if not res["issues"]:
                    st.success("All automatic checks passed.")
                if res.get("vendor_canonical") and res["vendor_canonical"] != inv["vendor_name"]:
                    st.info(f"Vendor matches known vendor: {res['vendor_canonical']}")

                c1, c2 = st.columns(2)
                vendor = c1.text_input("Vendor", inv["vendor_name"], key=f"v{k}")
                number = c2.text_input("Invoice #", inv.get("invoice_number") or "", key=f"n{k}")
                c3, c4, c5 = st.columns(3)
                date = c3.text_input("Date (YYYY-MM-DD)", inv.get("invoice_date") or "", key=f"d{k}")
                cur = c4.text_input("Currency", inv.get("currency") or "", key=f"c{k}")
                taxid = c5.text_input("Tax ID", inv.get("tax_id") or "", key=f"t{k}")

                items = pd.DataFrame(inv.get("line_items") or [], columns=COLS)
                edited = st.data_editor(items, num_rows="dynamic", use_container_width=True, key=f"li{k}")

                c6, c7, c8 = st.columns(3)
                sub = c6.text_input("Subtotal", "" if inv.get("subtotal") is None else str(inv["subtotal"]), key=f"s{k}")
                tax = c7.text_input("Tax", "" if inv.get("tax") is None else str(inv["tax"]), key=f"x{k}")
                total = c8.text_input("Total", str(inv["total"]), key=f"T{k}")

                st.caption(f"{res['pages']} page(s) | {res['latency_s']}s | "
                           f"{res['input_tokens']} in / {res['output_tokens']} out tokens")

                if DEMO_MODE:
                    st.caption("Saving is disabled in this public sample-only demo.")
                elif st.button("Confirm & save"):
                    try:
                        clean = edited.dropna(how="all").astype(object).where(pd.notnull(edited.dropna(how="all")), None)
                        payload = {
                            "vendor_name": vendor, "invoice_number": txt(number), "invoice_date": txt(date),
                            "currency": txt(cur.upper()), "tax_id": txt(taxid),
                            "line_items": clean.to_dict("records"),
                            "subtotal": num(sub), "tax": num(tax), "total": num(total),
                        }
                        r = requests.post(f"{API}/invoices", json=payload, timeout=60)
                        if r.ok:
                            st.success(f"Saved as invoice #{r.json()['id']}")
                            for m in r.json()["issues"]:
                                st.warning(m)
                        else:
                            st.error(r.text)
                    except ValueError:
                        st.error("Check that subtotal, tax and total are valid numbers.")

if not DEMO_MODE:
    with tab_history:
        try:
            rows = requests.get(f"{API}/invoices", timeout=30).json()
            if rows:
                st.dataframe(pd.DataFrame(rows).drop(columns=["data_json", "issues_json"]),
                             use_container_width=True)
                a, b = st.columns(2)
                a.download_button("Download Excel", requests.get(f"{API}/export?format=xlsx").content,
                                  "invoices.xlsx")
                b.download_button("Download CSV", requests.get(f"{API}/export?format=csv").content,
                                  "invoices.csv")
            else:
                st.info("No saved invoices yet.")
        except requests.RequestException as e:
            st.error(f"Cannot reach API at {API}: {e}")

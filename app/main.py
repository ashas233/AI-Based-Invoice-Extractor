import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import Response  # noqa: E402

from . import db, export  # noqa: E402
from .extractor import demo_extract, extract  # noqa: E402
from .preprocess import to_images  # noqa: E402
from .schemas import ExtractResponse, Invoice, SaveResponse  # noqa: E402
from .validators import check_invoice  # noqa: E402

app = FastAPI(title="Invoice Extractor")
db.init()

MAX_BYTES = 15 * 1024 * 1024
_vendors = None


def vendors():
    """Lazy-load the FAISS vendor index; return None if disabled or unavailable."""
    global _vendors
    if os.getenv("USE_VECTOR", "1") != "1":
        return None
    if _vendors is None:
        try:
            from .vectorstore import VendorIndex
            _vendors = VendorIndex()
        except Exception as e:  # missing deps etc.
            print(f"Vendor index disabled: {e}")
            os.environ["USE_VECTOR"] = "0"
            return None
    return _vendors


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/demo", response_model=ExtractResponse)
def demo_endpoint():
    res = demo_extract()
    return ExtractResponse(
        invoice=res.invoice, issues=res.issues, duplicate=db.find_duplicate(
            res.invoice.vendor_name, res.invoice.invoice_number, res.invoice.total
        ),
        pages=1, latency_s=res.latency_s,
        input_tokens=res.input_tokens, output_tokens=res.output_tokens,
    )


@app.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 15 MB)")
    try:
        images = to_images(data, file.filename or "")
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")
    try:
        res = extract(images)
    except Exception as e:
        raise HTTPException(502, f"Extraction failed: {e}")

    vi = vendors()
    canonical = vi.lookup(res.invoice.vendor_name)[0] if vi else None
    dup = db.find_duplicate(canonical or res.invoice.vendor_name,
                            res.invoice.invoice_number, res.invoice.total)
    return ExtractResponse(
        invoice=res.invoice, issues=res.issues, vendor_canonical=canonical, duplicate=dup,
        pages=len(images), latency_s=res.latency_s,
        input_tokens=res.input_tokens, output_tokens=res.output_tokens,
    )


@app.post("/invoices", response_model=SaveResponse)
def save_invoice(inv: Invoice):
    """Save a human-reviewed invoice. Re-validates because the user may have edited it."""
    issues = check_invoice(inv)
    vi = vendors()
    canonical = vi.canonicalize(inv.vendor_name) if vi else inv.vendor_name
    return SaveResponse(id=db.save(inv, canonical, issues), issues=issues)


@app.get("/invoices")
def list_invoices():
    return db.all_rows()


@app.get("/export")
def export_invoices(format: str = "xlsx"):
    df = export.rows_to_df(db.all_rows())
    if format == "csv":
        return Response(export.to_csv(df), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=invoices.csv"})
    return Response(
        export.to_xlsx(df),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
    )

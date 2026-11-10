"""Turn uploads (PDF / photo / scan) into a list of cleaned JPEG pages."""
import io

import fitz  # PyMuPDF
from PIL import Image, ImageOps

MAX_PAGES = 8
MAX_SIDE = 1800


def _clean(img: Image.Image) -> bytes:
    img = ImageOps.exif_transpose(img).convert("RGB")  # fix phone-photo rotation
    img = ImageOps.autocontrast(img, cutoff=1)          # help faded scans
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def to_images(data: bytes, filename: str) -> list[bytes]:
    if filename.lower().endswith(".pdf"):
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for i in range(min(len(doc), MAX_PAGES)):
            pix = doc[i].get_pixmap(dpi=150)
            pages.append(_clean(Image.open(io.BytesIO(pix.tobytes("png")))))
        if not pages:
            raise ValueError("PDF has no pages")
        return pages
    return [_clean(Image.open(io.BytesIO(data)))]

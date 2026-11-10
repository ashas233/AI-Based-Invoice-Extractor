from typing import Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: float


class Invoice(BaseModel):
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = Field(None, description="ISO format YYYY-MM-DD")
    currency: Optional[str] = Field(None, description="3-letter ISO code, e.g. PKR, USD")
    tax_id: Optional[str] = Field(None, description="Vendor tax registration number (e.g. NTN/STRN/VAT)")
    line_items: list[LineItem] = []
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: float


class ExtractResponse(BaseModel):
    invoice: Invoice
    issues: list[str]
    vendor_canonical: Optional[str] = None
    duplicate: bool = False
    pages: int
    latency_s: float
    input_tokens: int
    output_tokens: int


class SaveResponse(BaseModel):
    id: int
    issues: list[str]

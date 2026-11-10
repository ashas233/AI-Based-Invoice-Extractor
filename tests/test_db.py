from app import db
from app.schemas import Invoice


def test_sqlite_database_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "invoices.db"))

    db.init()
    invoice = Invoice(vendor_name="Acme", invoice_number="INV-1", total=11)

    invoice_id = db.save(invoice, "Acme", [])

    assert invoice_id == 1
    assert db.find_duplicate("Acme", "INV-1", 11)
    assert not db.find_duplicate("Acme", "INV-2", 11)
    rows = db.all_rows()
    assert len(rows) == 1
    assert rows[0]["vendor"] == "Acme"

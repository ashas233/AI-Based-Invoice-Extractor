import json
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "data/invoices.db")
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()


def _conn():
    if DB_BACKEND == "postgres":
        import psycopg
        from psycopg.rows import dict_row

        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing PostgreSQL configuration: {', '.join(missing)}")
        return psycopg.connect(
            host=os.environ["DB_HOST"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            row_factory=dict_row,
        )
    if DB_BACKEND != "sqlite":
        raise ValueError(f"Unsupported DB_BACKEND: {DB_BACKEND}")

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        if DB_BACKEND == "postgres":
            c.execute(
                """CREATE TABLE IF NOT EXISTS invoices(
                    id BIGSERIAL PRIMARY KEY,
                    vendor TEXT, vendor_canonical TEXT, invoice_number TEXT,
                    invoice_date TEXT, currency TEXT, total DOUBLE PRECISION,
                    data_json TEXT, issues_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            )
        else:
            c.execute(
                """CREATE TABLE IF NOT EXISTS invoices(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor TEXT, vendor_canonical TEXT, invoice_number TEXT,
                    invoice_date TEXT, currency TEXT, total REAL,
                    data_json TEXT, issues_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
            )


def find_duplicate(vendor_canonical, invoice_number, total) -> bool:
    if not invoice_number:
        return False
    marker = "%s" if DB_BACKEND == "postgres" else "?"
    with _conn() as c:
        row = c.execute(
            f"SELECT 1 FROM invoices WHERE vendor_canonical={marker} "
            f"AND invoice_number={marker} AND ABS(total-{marker})<0.01",
            (vendor_canonical, invoice_number, total),
        ).fetchone()
    return row is not None


def save(inv, canonical, issues) -> int:
    with _conn() as c:
        if DB_BACKEND == "postgres":
            row = c.execute(
                """INSERT INTO invoices(vendor, vendor_canonical, invoice_number, invoice_date,
                   currency, total, data_json, issues_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (inv.vendor_name, canonical, inv.invoice_number, inv.invoice_date,
                 inv.currency, inv.total, inv.model_dump_json(), json.dumps(issues)),
            ).fetchone()
            return row["id"]

        cur = c.execute(
            """INSERT INTO invoices(vendor, vendor_canonical, invoice_number, invoice_date,
               currency, total, data_json, issues_json) VALUES(?,?,?,?,?,?,?,?)""",
            (inv.vendor_name, canonical, inv.invoice_number, inv.invoice_date,
             inv.currency, inv.total, inv.model_dump_json(), json.dumps(issues)),
        )
        return cur.lastrowid


def all_rows() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

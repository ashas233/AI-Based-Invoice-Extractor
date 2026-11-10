"""Measure extraction quality against labeled invoices.

Dataset layout: eval/dataset/<name>.(pdf|png|jpg|jpeg) + <name>.json (same schema as Invoice).
Usage: python eval/run_eval.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.extractor import extract  # noqa: E402
from app.preprocess import to_images  # noqa: E402

DATASET = Path(__file__).parent / "dataset"
PRICE_IN = float(os.getenv("PRICE_IN_PER_M", 0))
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_M", 0))
EXTS = {".pdf", ".png", ".jpg", ".jpeg"}


def norm(s):
    return " ".join(str(s).lower().split()) if s is not None else None


def close(a, b, tol=0.01):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def items_match(pred, truth):
    """Fraction of ground-truth line items matched by amount (multiset match)."""
    if not truth:
        return 1.0 if not pred else 0.0
    remaining = [p["amount"] for p in pred]
    hit = 0
    for t in truth:
        for k, a in enumerate(remaining):
            if close(a, t["amount"]):
                hit += 1
                remaining.pop(k)
                break
    return hit / len(truth)


def main():
    files = sorted(p for p in DATASET.iterdir() if p.suffix.lower() in EXTS)
    if not files:
        sys.exit(f"No invoices in {DATASET}. Run: python eval/make_synthetic.py 20")

    fields = ["vendor_name", "invoice_number", "invoice_date", "currency", "subtotal", "tax", "total"]
    correct = {f: 0 for f in fields}
    counted = {f: 0 for f in fields}
    item_scores, math_pass, latencies, cost, failures, rows = [], 0, [], 0.0, [], []

    for p in files:
        gt_path = p.with_suffix(".json")
        if not gt_path.exists():
            continue
        truth = json.loads(gt_path.read_text(encoding="utf-8"))
        try:
            res = extract(to_images(p.read_bytes(), p.name))
        except Exception as e:
            failures.append((p.name, str(e)))
            print(f"FAIL {p.name}: {e}")
            continue
        pred = res.invoice.model_dump()
        wrong = []
        for f in fields:
            counted[f] += 1
            ok = close(pred[f], truth.get(f)) if f in ("subtotal", "tax", "total") \
                else norm(pred[f]) == norm(truth.get(f))
            correct[f] += ok
            if not ok:
                wrong.append(f)
        item_scores.append(items_match(pred["line_items"], truth.get("line_items", [])))
        math_pass += not res.issues
        latencies.append(res.latency_s)
        cost += res.input_tokens / 1e6 * PRICE_IN + res.output_tokens / 1e6 * PRICE_OUT
        rows.append({"file": p.name, "wrong_fields": wrong, "issues": res.issues})
        print(f"{p.name}: wrong={wrong or 'none'} issues={len(res.issues)}")

    n = len(rows)
    if not n:
        sys.exit("Nothing evaluated.")
    print("\n| Metric | Result |\n|---|---|")
    for f in fields:
        print(f"| {f} accuracy | {correct[f] / counted[f]:.1%} |")
    print(f"| Line-item accuracy | {sum(item_scores) / n:.1%} |")
    print(f"| Passing math validation | {math_pass / n:.1%} |")
    print(f"| Avg latency | {sum(latencies) / n:.1f}s |")
    print(f"| Avg cost / invoice | ${cost / n:.4f} |")
    print(f"| Failed to extract | {len(failures)} of {n + len(failures)} |")
    (Path(__file__).parent / "results.json").write_text(
        json.dumps({"rows": rows, "failures": failures}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

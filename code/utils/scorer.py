"""
scorer.py — Validate agent output against sample_requests.csv ground truth.
Run: python code/utils/scorer.py

Prints match % per column and highlights mismatches.
"""
import sys
import csv
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATASET = Path(os.getenv("DATASET_PATH", "./dataset"))
OUTPUT_PATH = Path("./output.csv")

EXACT_COLUMNS = [
    "affordability_status",
    "recommended_payment_method",
    "spending_changes_needed",
]

NUMERIC_COLUMNS = [
    "amount_safe_to_pay",
]

DATE_COLUMNS = [
    "earliest_date_for_full_payment",
    "payment_plan",
]


def score(sample_output_path: str | Path | None = None):
    samples = _load_csv(DATASET / "sample_requests.csv")
    out_p = Path(sample_output_path) if sample_output_path else OUTPUT_PATH
    outputs = _load_csv(out_p)

    output_by_id = {r["request_id"]: r for r in outputs}


    totals = {col: 0 for col in EXACT_COLUMNS + NUMERIC_COLUMNS + DATE_COLUMNS}
    matches = {col: 0 for col in totals}
    n = len(samples)

    for s in samples:
        rid = s["request_id"]
        pred = output_by_id.get(rid)
        if not pred:
            print(f"⚠️  Missing prediction for {rid}")
            continue

        for col in EXACT_COLUMNS:
            totals[col] += 1
            if s.get(col, "").strip() == pred.get(col, "").strip():
                matches[col] += 1
            else:
                print(f"  {rid} [{col}] expected='{s.get(col)}' got='{pred.get(col)}'")

        for col in NUMERIC_COLUMNS:
            totals[col] += 1
            try:
                exp = float(s.get(col, 0))
                got = float(pred.get(col, 0))
                if abs(exp - got) / max(exp, 1) < 0.01:  # within 1%
                    matches[col] += 1
                else:
                    print(f"  {rid} [{col}] expected={exp} got={got}")
            except Exception:
                pass

        for col in DATE_COLUMNS:
            totals[col] += 1
            if s.get(col, "").strip() == pred.get(col, "").strip():
                matches[col] += 1

    print("\n== Score Summary ==========================")

    for col in totals:
        pct = (matches[col] / totals[col] * 100) if totals[col] else 0
        print(f"  {col:<40} {matches[col]}/{totals[col]} = {pct:.0f}%")
    print()


def _load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    score()

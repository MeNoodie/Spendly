"""
output_writer.py — Format AgentState final output into CSV row.
"""
import csv
import json
from pathlib import Path


OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]


def _format_amt(val) -> str:
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else f"{f:.2f}"
    except Exception:
        return str(val)


def format_payment_plan(plan_items: list[dict]) -> str:
    """Convert [{date, amount}, ...] to '2024-01-01:1000|2024-02-01:1000'."""
    if not plan_items:
        return "none"
    return "|".join(f"{p['date']}:{_format_amt(p['amount'])}" for p in plan_items)


def format_spending_changes(changes: list[dict]) -> str:
    """Convert [{action, event_id, amount?}, ...] to 'stop:evt1|reduce_to:evt2:500'."""
    if not changes:
        return "none"
    parts = []
    for c in changes:
        action = c.get("action", "stop")
        eid = c.get("event_id", "")
        if action == "stop":
            parts.append(f"stop:{eid}")
        elif action == "reduce_to":
            parts.append(f"reduce_to:{eid}:{_format_amt(c.get('amount', 0))}")
    return "|".join(parts) if parts else "none"



def state_to_row(state: dict) -> dict:
    """Convert final AgentState to an output.csv row dict."""
    return {
        "request_id": state.get("request_id", ""),
        "amount_safe_to_pay": state.get("amount_safe_to_pay", 0),
        "affordability_status": state.get("affordability_status", "not_affordable"),
        "recommended_payment_method": state.get("recommended_method", "not_recommended"),
        "payment_plan": format_payment_plan(state.get("payment_plan", [])),
        "earliest_date_for_full_payment": state.get("earliest_full_payment_date") or "",
        "spending_changes_needed": format_spending_changes(state.get("spending_changes", [])),
        "decision_explanation": state.get("explanation", ""),
    }


def write_output_csv(rows: list[dict], output_path: str = "./output.csv"):
    """Write all rows to output.csv in the required column order."""
    path = Path(output_path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] Wrote {len(rows)} rows to {path}")


"""
queries.py — Database access helpers for Spendly.

Primary entry point for the agent:
    context = get_user_context(user_id, request_id)
"""
import json
from datetime import date
from typing import Any
from code.db import get_db


def get_user_context(user_id: str, request_id: str) -> dict[str, Any]:
    """
    Return everything the LangGraph agent needs for one decision.
    All currency amounts are returned in the user's home_currency.
    """
    conn = get_db()

    profile = _get_profile(conn, user_id)
    income = _get_income_sources(conn, user_id)
    expenses = _get_expenses(conn, user_id)
    pending = _get_pending_transactions(conn, user_id)
    payment_options = _get_payment_options(conn, request_id)
    messages = _get_messages(conn, user_id, request_id)
    images = _get_images(conn, user_id, request_id)

    return {
        "user_id": user_id,
        "request_id": request_id,
        "profile": profile,
        "income_sources": income,
        "expenses": expenses,
        "pending_transactions": pending,
        "payment_options": payment_options,
        "messages": messages,
        "images": images,
    }


def _get_profile(conn, user_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM financial_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        return {}
    
    return {
        "user_id": row["user_id"],
        "home_currency": row["home_currency"],
        "current_balance": float(row["current_available_balance"] or 0),
        "preferred_min_balance": float(row["minimum_balance_to_keep"] or 0),
        "financial_priorities": [p.strip() for p in (row["financial_priorities"] or "").split("|") if p.strip()],
        "expense_categories_to_protect": [p.strip() for p in (row["expense_categories_to_protect"] or "").split("|") if p.strip()],
        "expense_categories_user_is_willing_to_reduce": [p.strip() for p in (row["expense_categories_user_is_willing_to_reduce"] or "").split("|") if p.strip()],
        "expense_categories_user_is_willing_to_stop": [p.strip() for p in (row["expense_categories_user_is_willing_to_stop"] or "").split("|") if p.strip()],
        "payment_methods_accepted": [p.strip() for p in (row["payment_methods_user_will_consider"] or "").split("|") if p.strip()],
        "max_installment_months": row["max_installment_months"],
    }


def _get_income_sources(conn, user_id: str) -> list[dict]:
    # Fetch income events (salary / payroll / scheduled credit)
    rows = conn.execute(
        """SELECT * FROM financial_events
           WHERE user_id = ? AND direction = 'credit'
             AND status IN ('settled', 'scheduled')
           ORDER BY event_date ASC""",
        (user_id,)
    ).fetchall()
    
    income_by_cat = {}
    for r in rows:
        evt_date = r["settlement_date"] or r["event_date"]
        due_day = None
        try:
            due_day = int(evt_date.split("-")[2])
        except Exception:
            pass

        cat = str(r["category"] or "salary").lower()
        income_by_cat[cat] = {
            "id": r["event_id"],
            "user_id": r["user_id"],
            "name": r["description"] or "Income",
            "amount": r["amount"],
            "currency": r["currency"],
            "frequency": "monthly",
            "next_credit_date": evt_date,
            "due_day": due_day,
            "is_confirmed": 1,
            "is_active": 1,
            "linked_event_id": r["linked_event_id"],
            "source_ref": r["event_id"],
        }
        
    return list(income_by_cat.values())


def _get_expenses(conn, user_id: str) -> list[dict]:
    # Group recurring expenses by category, taking the latest active event in each category
    rows = conn.execute(
        """SELECT * FROM financial_events
           WHERE user_id = ? AND direction = 'debit' AND status IN ('settled', 'scheduled')
           ORDER BY event_date ASC""",
        (user_id,)
    ).fetchall()
    
    one_off_cats = {"shopping", "investment_purchase", "non_cash"}
    latest_by_cat = {}
    for r in rows:
        cat = str(r["category"] or "").lower()
        if cat in one_off_cats:
            continue
        evt_date = r["settlement_date"] or r["event_date"]
        due_day = None
        try:
            due_day = int(evt_date.split("-")[2])
        except Exception:
            pass
            
        flex = str(r["flexibility"] or "fixed").lower()
        is_flexible = 1 if flex != "fixed" else 0
        is_stoppable = 1 if "stoppable" in flex else 0
        is_reducible = 1 if "reducible" in flex else 0

        latest_by_cat[cat] = {
            "id": r["event_id"],
            "user_id": r["user_id"],
            "name": r["description"] or "Expense",
            "amount": r["amount"],
            "currency": r["currency"],
            "category": r["category"],
            "due_date": evt_date,
            "due_day": due_day,
            "flexibility": flex,
            "minimum_allowed_amount": r["minimum_allowed_amount"],
            "is_flexible": is_flexible,
            "is_stoppable": is_stoppable,
            "is_reducible": is_reducible,
            "is_essential": 0 if is_flexible else 1,
            "is_recurring": 1,
            "is_active": 1,
            "linked_event_id": r["linked_event_id"],
            "source_ref": r["event_id"],
        }

    return list(latest_by_cat.values())


def _get_pending_transactions(conn, user_id: str) -> list[dict]:
    # Pending debits must be accounted for on their settlement/event date
    rows = conn.execute(
        """SELECT * FROM financial_events
           WHERE user_id = ? AND direction = 'debit' AND status = 'pending'
           ORDER BY event_date ASC""",
        (user_id,)
    ).fetchall()
    
    pending = []
    for r in rows:
        exp_date = r["settlement_date"] or r["event_date"]
        pending.append({
            "id": r["event_id"],
            "user_id": r["user_id"],
            "name": r["description"] or "Pending Debit",
            "amount": r["amount"],
            "currency": r["currency"],
            "expected_date": exp_date,
            "type": "debit",
            "status": "pending",
            "source_ref": r["event_id"],
        })
    return pending


def _get_payment_options(conn, request_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM payment_options WHERE request_id = ? ORDER BY payment_option_id",
        (request_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _get_messages(conn, user_id: str, request_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM event_messages
           WHERE user_id = ? OR request_id = ?
           ORDER BY sent_at""",
        (user_id, request_id)
    ).fetchall()
    return [dict(r) for r in rows]


def _get_images(conn, user_id: str, request_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM uploaded_documents
           WHERE user_id = ? OR request_id = ?""",
        (user_id, request_id)
    ).fetchall()
    return [dict(r) for r in rows]


def get_exchange_rate(from_currency: str, to_currency: str, rate_date: str) -> float | None:
    conn = get_db()
    row = conn.execute(
        """SELECT rate FROM exchange_rates
           WHERE from_currency = ? AND to_currency = ? AND rate_date <= ?
           ORDER BY rate_date DESC LIMIT 1""",
        (from_currency, to_currency, rate_date)
    ).fetchone()
    return float(row["rate"]) if row else None


def save_decision(decision: dict):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO decisions
           (request_id, user_id, request_text, request_type, requested_amount, request_date,
            desired_completion_date, allows_partial, amount_safe_to_pay, affordability_status,
            recommended_method, payment_plan, earliest_full_date, spending_changes,
            explanation, llm_tokens_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            decision["request_id"],
            decision["user_id"],
            decision.get("request_text"),
            decision.get("request_type"),
            decision["requested_amount"],
            decision["request_date"],
            decision.get("desired_completion_date"),
            1 if decision.get("allows_partial") else 0,
            decision.get("amount_safe_to_pay"),
            decision.get("affordability_status"),
            decision.get("recommended_method"),
            json.dumps(decision.get("payment_plan", [])),
            decision.get("earliest_full_date"),
            json.dumps(decision.get("spending_changes", [])),
            decision.get("explanation"),
            decision.get("llm_tokens_used", 0),
        )
    )
    conn.commit()


def log_llm_usage(request_id: str, provider: str, model: str,
                  call_type: str, input_tokens: int, output_tokens: int, cost_usd: float):
    conn = get_db()
    conn.execute(
        """INSERT INTO usage_logs
           (request_id, model_provider, model_name, call_type, input_tokens, output_tokens, estimated_cost_usd)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (request_id, provider, model, call_type, input_tokens, output_tokens, cost_usd)
    )
    conn.commit()

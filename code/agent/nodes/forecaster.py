"""
forecaster.py — Node 4
Core 90-day cash flow simulator (fully deterministic, no LLM).

Produces:
  - daily_balances: list of 90 floats (index 0 = request_date)
  - amount_safe_to_pay: max payment keeping balance >= min_balance every day
  - earliest_full_payment_date: first date when full requested_amount is safe
"""
from datetime import date, timedelta
from code.agent.state import AgentState


def simulate_forecast(state: AgentState) -> AgentState:
    profile = state["profile"]
    current_balance: float = profile["current_balance"]
    min_balance: float = profile["preferred_min_balance"]
    request_date = date.fromisoformat(state["request_date"])
    requested_amount: float = state["requested_amount"]

    income = state.get("active_income", [])
    expenses = state.get("active_expenses", [])
    pending = state.get("pending_transactions", [])

    # ── Build daily projection ──────────────────────────────
    daily_balances = _project_90_days(
        start_balance=current_balance,
        start_date=request_date,
        income=income,
        expenses=expenses,
        pending=pending,
    )

    # ── amount_safe_to_pay: binary search ───────────────────
    amount_safe = _binary_search_safe_amount(
        daily_balances=daily_balances,
        min_balance=min_balance,
        max_amount=requested_amount,
        payment_date_idx=0,  # pay on request_date (index 0)
    )

    # ── earliest_date_for_full_payment ──────────────────────
    earliest_full_date = _find_earliest_full_payment(
        start_balance=current_balance,
        start_date=request_date,
        income=income,
        expenses=expenses,
        pending=pending,
        min_balance=min_balance,
        requested_amount=requested_amount,
    )

    return {
        **state,
        "daily_balances": daily_balances,
        "amount_safe_to_pay": amount_safe,
        "earliest_full_payment_date": earliest_full_date,
    }


def _project_90_days(
    start_balance: float,
    start_date: date,
    income: list[dict],
    expenses: list[dict],
    pending: list[dict],
    extra_payments: list[tuple[date, float]] | None = None,
) -> list[float]:
    """
    Project balance for 90 days starting from start_date.
    Returns list of 90 floats (end-of-day balance for each day).
    extra_payments: [(date, amount)] additional debits to simulate.
    """
    balance = start_balance
    balances = []

    for day_offset in range(90):
        current_day = start_date + timedelta(days=day_offset)

        # Subtract pending debit transactions on their expected date
        for pt in pending:
            if pt.get("type") == "debit" and pt.get("expected_date"):
                pt_date = date.fromisoformat(pt["expected_date"])
                if pt_date == current_day:
                    balance -= (pt.get("amount") or 0)

        # Add confirmed income on credit date
        for inc in income:
            if not inc.get("is_confirmed"):
                continue
            credit_date = inc.get("next_credit_date")
            if not credit_date:
                continue
            freq = inc.get("frequency", "one_time")
            if _hits_on_day(credit_date, current_day, freq, start_date):
                balance += (inc.get("amount") or 0)

        # Subtract recurring expenses on due date
        for exp in expenses:
            if not exp.get("is_active", 1):
                continue
            due_date_str = exp.get("due_date")
            due_day = exp.get("due_day")
            freq = "monthly" if exp.get("is_recurring") else "one_time"

            if due_date_str:
                exp_date = date.fromisoformat(due_date_str)
                if _hits_on_day(str(exp_date), current_day, freq, start_date):
                    balance -= (exp.get("amount") or 0)
            elif due_day:
                if current_day.day == int(due_day):
                    balance -= (exp.get("amount") or 0)

        # Apply extra payments (for plan simulation)
        if extra_payments:
            for pay_date, pay_amount in extra_payments:
                if pay_date == current_day:
                    balance -= pay_amount

        balances.append(balance)

    return balances


def _hits_on_day(credit_date_str: str, current_day: date, freq: str, start_date: date) -> bool:
    """Check if an income/expense event fires on current_day given its frequency."""
    try:
        anchor = date.fromisoformat(credit_date_str)
    except Exception:
        return False

    if freq == "one_time":
        return anchor == current_day
    elif freq == "monthly":
        return anchor.day == current_day.day and current_day >= anchor
    elif freq == "weekly":
        delta = (current_day - anchor).days
        return delta >= 0 and delta % 7 == 0
    elif freq == "biweekly":
        delta = (current_day - anchor).days
        return delta >= 0 and delta % 14 == 0
    return False


def _binary_search_safe_amount(
    daily_balances: list[float],
    min_balance: float,
    max_amount: float,
    payment_date_idx: int = 0,
) -> float:
    """
    Exact analytical formula for largest payment keeping balance >= min_balance every day.
    Subtracting payment mid on payment_date_idx reduces all subsequent daily balances by mid.
    """
    if not daily_balances:
        return 0.0
    relevant = daily_balances[payment_date_idx:]
    lowest = min(relevant)
    safe = lowest - min_balance
    if safe <= 0:
        return 0.0
    safe = min(safe, max_amount)
    if abs(safe - max_amount) < 0.05:
        safe = max_amount
    return round(safe, 2)



def _find_earliest_full_payment(
    start_balance: float,
    start_date: date,
    income: list[dict],
    expenses: list[dict],
    pending: list[dict],
    min_balance: float,
    requested_amount: float,
) -> str | None:
    """
    Scan each of the 90 days: find the first day where paying requested_amount
    in full keeps balance >= min_balance for the remaining forecast.
    """
    for day_offset in range(90):
        candidate_date = start_date + timedelta(days=day_offset)

        # Project remaining balance after this date
        balances = _project_90_days(
            start_balance=start_balance,
            start_date=start_date,
            income=income,
            expenses=expenses,
            pending=pending,
            extra_payments=[(candidate_date, requested_amount)],
        )

        if all(b >= min_balance for b in balances):
            return candidate_date.isoformat()

    return None  # Not safe within 90 days

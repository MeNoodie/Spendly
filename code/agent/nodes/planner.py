"""
planner.py — Node 5
Generate all eligible payment plans and rank them.

Ranking rules (from problem_statement.md):
  1. Completes full request by desired_completion_date
  2. Requires no spending changes
  3. Minimize total amount paid
  4. Start payment earlier
  5. Fewer payments
  6. Lowest payment_option_id (tie-breaker)
"""
from datetime import date, timedelta
from code.agent.state import AgentState
from code.agent.nodes.forecaster import _project_90_days, _binary_search_safe_amount


def generate_plans(state: AgentState) -> AgentState:
    """
    Try all eligible payment methods and produce candidate_plans list.
    Each plan: {method, payment_plan, total_paid, spending_changes, is_safe, ...}
    """
    profile = state["profile"]
    methods_accepted: list[str] = profile.get("payment_methods_accepted", [
        "full_payment", "partial_payment", "installments", "wait", "not_recommended"
    ])
    min_balance = profile["preferred_min_balance"]
    current_balance = profile["current_balance"]
    request_date = date.fromisoformat(state["request_date"])
    completion_date = date.fromisoformat(state["desired_completion_date"])
    requested_amount = state["requested_amount"]
    amount_safe = state["amount_safe_to_pay"]
    earliest_full = state.get("earliest_full_payment_date")
    allows_partial = state.get("allows_partial", False)
    income = state.get("active_income", [])
    expenses = state.get("active_expenses", [])
    pending = state.get("pending_transactions", [])
    payment_options = state.get("payment_options", [])

    candidates = []

    # ── 1. full_payment (no spending changes) ─────────────────
    if "full_payment" in methods_accepted:
        if amount_safe >= requested_amount:
            candidates.append({
                "method": "full_payment",
                "payment_plan": [{"date": state["request_date"], "amount": requested_amount}],
                "total_paid": requested_amount,
                "num_payments": 1,
                "first_payment_date": state["request_date"],
                "completes_by_deadline": request_date <= completion_date,
                "spending_changes": [],
                "is_safe": True,
            })

    # ── 2. installments ──────────────────────────────────────
    if "installments" in methods_accepted:
        for opt in payment_options:
            plan = _simulate_installment_plan(
                opt, current_balance, min_balance, income, expenses, pending, completion_date, request_date
            )
            if plan:
                candidates.append(plan)

    # ── 3. partial_payment ───────────────────────────────────
    if "partial_payment" in methods_accepted and allows_partial:
        if 0 < amount_safe < requested_amount and earliest_full:
            earliest_full_date = date.fromisoformat(earliest_full)
            if earliest_full_date <= completion_date:
                remaining = round(requested_amount - amount_safe, 2)
                candidates.append({
                    "method": "partial_payment",
                    "payment_plan": [
                        {"date": state["request_date"], "amount": amount_safe},
                        {"date": earliest_full, "amount": remaining},
                    ],
                    "total_paid": requested_amount,
                    "num_payments": 2,
                    "first_payment_date": state["request_date"],
                    "completes_by_deadline": True,
                    "spending_changes": [],
                    "is_safe": True,
                })

    # ── 4. wait ──────────────────────────────────────────────
    if "full_payment" in methods_accepted and earliest_full:
        earliest_full_date = date.fromisoformat(earliest_full)
        if earliest_full_date <= completion_date and earliest_full_date > request_date:
            candidates.append({
                "method": "wait",
                "payment_plan": [{"date": earliest_full, "amount": requested_amount}],
                "total_paid": requested_amount,
                "num_payments": 1,
                "first_payment_date": earliest_full,
                "completes_by_deadline": True,
                "spending_changes": [],
                "is_safe": True,
            })

    # ── 5. spending changes (if no plan or to achieve full payment) ──
    # Check if stopping/reducing flexible expenses allows full payment
    spending_plans = _try_with_spending_changes(state)
    candidates.extend(spending_plans)

    # ── 6. not_recommended fallback ─────────────────────────
    if not candidates:
        candidates.append({
            "method": "not_recommended",
            "payment_plan": [],
            "total_paid": 0,
            "num_payments": 0,
            "first_payment_date": None,
            "completes_by_deadline": False,
            "spending_changes": [],
            "is_safe": False,
        })

    return {**state, "candidate_plans": candidates}


def rank_select_plan(state: AgentState) -> AgentState:
    """Apply 6-level ranking to candidates and pick the best plan."""
    candidates = state.get("candidate_plans", [])
    completion_date = date.fromisoformat(state["desired_completion_date"])

    def sort_key(plan):
        first_date = date.fromisoformat(plan["first_payment_date"]) if plan.get("first_payment_date") else date.max
        opt_id = plan.get("payment_option_id", "zzz")
        return (
            0 if plan["completes_by_deadline"] else 1,         # 1. completes by deadline
            len(plan.get("spending_changes", [])),              # 2. no spending changes
            plan["total_paid"],                                 # 3. minimize total paid
            first_date,                                         # 4. start earlier
            plan["num_payments"],                               # 5. fewer payments
            opt_id,                                             # 6. lowest option id
        )

    safe_plans = [p for p in candidates if p["is_safe"]]
    if safe_plans:
        ranked = sorted(safe_plans, key=sort_key)
        selected = ranked[0]
    else:
        selected = {
            "method": "not_recommended",
            "payment_plan": [],
            "total_paid": 0,
            "num_payments": 0,
            "first_payment_date": None,
            "completes_by_deadline": False,
            "spending_changes": [],
            "is_safe": False,
        }

    method = selected["method"]
    earliest_full = state.get("earliest_full_payment_date")
    amount_safe = state["amount_safe_to_pay"]
    requested_amount = state["requested_amount"]
    spending_changes = selected.get("spending_changes", [])

    if method == "full_payment":
        if spending_changes:
            affordability_status = "affordable_with_plan"
        else:
            affordability_status = "affordable_now"
    elif method in ("partial_payment", "installments"):
        affordability_status = "affordable_with_plan"
    elif method == "wait":
        affordability_status = "affordable_later"
    else:
        affordability_status = "not_affordable"

    plan_items = selected.get("payment_plan", [])

    return {
        **state,
        "selected_plan": selected,
        "spending_changes": spending_changes,
        "affordability_status": affordability_status,
        "recommended_method": method,
        "payment_plan": plan_items,
    }


def _simulate_installment_plan(
    opt: dict,
    start_balance: float,
    min_balance: float,
    income: list[dict],
    expenses: list[dict],
    pending: list[dict],
    completion_date: date,
    request_date: date,
) -> dict | None:
    """Simulate one installment payment_option to check if it's safe."""
    try:
        first = date.fromisoformat(str(opt["first_payment_date"]))
        interval = float(opt.get("payment_frequency_days") or 30)
        n = int(opt.get("number_of_payments") or 1)
        per_payment = float(opt.get("payment_amount") or opt.get("amount_per_payment") or 0)
        total = float(opt.get("total_payable_amount") or opt.get("total_payable") or (per_payment * n))
        opt_id = opt.get("payment_option_id") or opt.get("id") or "payment_option_01"
    except Exception:
        return None

    extra_payments = []
    last_date = first
    for i in range(n):
        pay_date = first + timedelta(days=int(interval * i))
        extra_payments.append((pay_date, per_payment))
        last_date = pay_date

    # Must complete by desired_completion_date
    if last_date > completion_date:
        return None

    balances = _project_90_days(
        start_balance=start_balance,
        start_date=request_date,
        income=income,
        expenses=expenses,
        pending=pending,
        extra_payments=extra_payments,
    )

    if not all(b >= min_balance for b in balances):
        return None

    return {
        "method": "installments",
        "payment_option_id": opt_id,
        "payment_plan": [
            {"date": (first + timedelta(days=int(interval * i))).isoformat(), "amount": per_payment}
            for i in range(n)
        ],
        "total_paid": total,
        "num_payments": n,
        "first_payment_date": first.isoformat(),
        "completes_by_deadline": True,
        "spending_changes": [],
        "is_safe": True,
    }


def _try_with_spending_changes(state: AgentState) -> list[dict]:
    """
    Check if stopping or reducing flexible expenses makes full payment viable today.
    """
    profile = state["profile"]
    if "full_payment" not in profile.get("payment_methods_accepted", []):
        return []

    expenses = state.get("active_expenses", [])
    income = state.get("active_income", [])
    pending = state.get("pending_transactions", [])
    start_balance = profile["current_balance"]
    min_balance = profile["preferred_min_balance"]
    request_date = date.fromisoformat(state["request_date"])
    completion_date = date.fromisoformat(state["desired_completion_date"])
    requested_amount = state["requested_amount"]

    if request_date > completion_date:
        return []

    # Eligible flexible expenses
    stoppable = [
        e for e in expenses
        if e.get("is_stoppable") or e.get("category") in profile.get("expense_categories_user_is_willing_to_stop", [])
    ]
    reducible = [
        e for e in expenses
        if (e.get("is_reducible") or e.get("category") in profile.get("expense_categories_user_is_willing_to_reduce", []))
        and e.get("minimum_allowed_amount") is not None
    ]

    candidates = []

    # 1. Try single stop
    for s_exp in stoppable:
        mod_exp = [e for e in expenses if e["id"] != s_exp["id"]]
        daily = _project_90_days(start_balance, request_date, income, mod_exp, pending)
        safe = _binary_search_safe_amount(daily, min_balance, requested_amount, 0)
        if safe >= requested_amount:
            candidates.append({
                "method": "full_payment",
                "payment_plan": [{"date": state["request_date"], "amount": requested_amount}],
                "total_paid": requested_amount,
                "num_payments": 1,
                "first_payment_date": state["request_date"],
                "completes_by_deadline": True,
                "spending_changes": [{"action": "stop", "event_id": s_exp["id"]}],
                "is_safe": True,
            })
            return candidates

    # 2. Try single reduce
    for r_exp in reducible:
        min_amt = float(r_exp["minimum_allowed_amount"])
        mod_exp = []
        for e in expenses:
            if e["id"] == r_exp["id"]:
                mod_exp.append({**e, "amount": min_amt})
            else:
                mod_exp.append(e)
        daily = _project_90_days(start_balance, request_date, income, mod_exp, pending)
        safe = _binary_search_safe_amount(daily, min_balance, requested_amount, 0)
        if safe >= requested_amount:
            candidates.append({
                "method": "full_payment",
                "payment_plan": [{"date": state["request_date"], "amount": requested_amount}],
                "total_paid": requested_amount,
                "num_payments": 1,
                "first_payment_date": state["request_date"],
                "completes_by_deadline": True,
                "spending_changes": [{"action": "reduce_to", "event_id": r_exp["id"], "amount": min_amt}],
                "is_safe": True,
            })
            return candidates

    # 3. Try pair (stop + reduce)
    for s_exp in stoppable:
        for r_exp in reducible:
            if s_exp["id"] == r_exp["id"]:
                continue
            min_amt = float(r_exp["minimum_allowed_amount"])
            mod_exp = []
            for e in expenses:
                if e["id"] == s_exp["id"]:
                    continue
                elif e["id"] == r_exp["id"]:
                    mod_exp.append({**e, "amount": min_amt})
                else:
                    mod_exp.append(e)
            daily = _project_90_days(start_balance, request_date, income, mod_exp, pending)
            safe = _binary_search_safe_amount(daily, min_balance, requested_amount, 0)
            if safe >= requested_amount:
                candidates.append({
                    "method": "full_payment",
                    "payment_plan": [{"date": state["request_date"], "amount": requested_amount}],
                    "total_paid": requested_amount,
                    "num_payments": 1,
                    "first_payment_date": state["request_date"],
                    "completes_by_deadline": True,
                    "spending_changes": [
                        {"action": "stop", "event_id": s_exp["id"]},
                        {"action": "reduce_to", "event_id": r_exp["id"], "amount": min_amt},
                    ],
                    "is_safe": True,
                })
                return candidates

    return candidates

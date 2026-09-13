"""
state.py — AgentState TypedDict shared across all LangGraph nodes.
"""
from typing import TypedDict, Any


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    request_id: str
    user_id: str
    request_date: str            # YYYY-MM-DD
    request_type: str
    requested_amount: float
    desired_completion_date: str
    allows_partial: bool
    request_text: str

    # ── Loaded context ─────────────────────────────────────
    profile: dict                # from financial_profiles
    income_sources: list[dict]
    expenses: list[dict]
    pending_transactions: list[dict]
    payment_options: list[dict]
    messages: list[dict]
    images: list[dict]           # uploaded_documents rows

    # ── After image resolution ─────────────────────────────
    resolved_income: list[dict]  # income_sources with amounts filled
    resolved_expenses: list[dict]

    # ── After message processing ───────────────────────────
    active_expenses: list[dict]  # after cancellations / amendments applied
    active_income: list[dict]

    # ── Forecast outputs ───────────────────────────────────
    daily_balances: list[float]  # 90-entry array, index 0 = request_date
    amount_safe_to_pay: float
    earliest_full_payment_date: str | None

    # ── Planner outputs ────────────────────────────────────
    candidate_plans: list[dict]
    selected_plan: dict | None
    spending_changes: list[dict]

    # ── Final outputs ──────────────────────────────────────
    affordability_status: str
    recommended_method: str
    payment_plan: list[dict]     # [{"date": "YYYY-MM-DD", "amount": 1000}, ...]
    explanation: str

    # ── Meta ───────────────────────────────────────────────
    llm_tokens_used: int
    processing_ms: int
    errors: list[str]

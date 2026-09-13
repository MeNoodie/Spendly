"""
data_loader.py — Node 1
Load all user financial context from SQLite into AgentState.
"""
from code.agent.state import AgentState
from code.db.queries import get_user_context


def load_user_context(state: AgentState) -> AgentState:
    """Fetch profile, income, expenses, payment options, messages, images from DB."""
    ctx = get_user_context(state["user_id"], state["request_id"])
    return {
        **state,
        "profile": ctx["profile"],
        "income_sources": ctx["income_sources"],
        "expenses": ctx["expenses"],
        "pending_transactions": ctx["pending_transactions"],
        "payment_options": ctx["payment_options"],
        "messages": ctx["messages"],
        "images": ctx["images"],
        # Initialize resolved copies (will be filled by later nodes)
        "resolved_income": ctx["income_sources"],
        "resolved_expenses": ctx["expenses"],
        "active_income": ctx["income_sources"],
        "active_expenses": ctx["expenses"],
        "errors": [],
    }

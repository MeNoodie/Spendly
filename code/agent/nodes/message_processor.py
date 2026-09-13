"""
message_processor.py — Node 3
Apply contextual message overrides to financial events.

Messages can:
  - Cancel an expense (is_active → False)
  - Amend an amount
  - Confirm a pending transaction
  - Delay a due date

Conflict resolution (from problem_statement):
  1. Explicit cancellation / settlement / amendment wins
  2. Newer record from same source wins
  3. Settled event > estimate / forecast
  4. Financially safer interpretation as fallback
"""
from code.agent.state import AgentState


# Simple keyword detection — upgrade to LLM-based parsing if needed
_CANCEL_KEYWORDS = ["cancel", "cancelled", "stopped", "no longer", "won't be charged",
                    "not going ahead", "terminated", "closed"]
_CONFIRM_KEYWORDS = ["confirmed", "received", "credited", "settled", "paid"]
_AMEND_KEYWORDS = ["changed to", "updated to", "now", "revised to", "new amount"]


def apply_message_overrides(state: AgentState) -> AgentState:
    """
    Process all messages and apply overrides to active_expenses and active_income.
    """
    messages = state.get("messages", [])
    expenses = [dict(e) for e in state.get("active_expenses", [])]
    income = [dict(i) for i in state.get("active_income", [])]
    pending = [dict(p) for p in state.get("pending_transactions", [])]

    # Build lookup by event source_ref / id
    expense_map = {e.get("source_ref", e["id"]): e for e in expenses}
    income_map = {i.get("source_ref", i["id"]): i for i in income}
    pending_map = {p.get("source_ref", p["id"]): p for p in pending}

    for msg in sorted(messages, key=lambda m: m.get("message_date") or ""):
        text = (msg.get("message_text") or "").lower()
        event_id = msg.get("related_event_id")

        if not event_id:
            continue

        if any(kw in text for kw in _CANCEL_KEYWORDS):
            if event_id in expense_map:
                expense_map[event_id]["is_active"] = 0
            if event_id in pending_map:
                pending_map[event_id]["status"] = "cancelled"

        elif any(kw in text for kw in _CONFIRM_KEYWORDS):
            if event_id in pending_map:
                pending_map[event_id]["status"] = "settled"
            if event_id in income_map:
                income_map[event_id]["is_confirmed"] = 1

        elif any(kw in text for kw in _AMEND_KEYWORDS):
            # TODO: extract new amount from message text with regex/LLM
            pass

    active_expenses = [e for e in expense_map.values() if e.get("is_active", 1)]
    active_income = [i for i in income_map.values() if i.get("is_active", 1)]
    active_pending = [p for p in pending_map.values() if p.get("status") == "pending"]

    return {
        **state,
        "active_expenses": active_expenses,
        "active_income": active_income,
        "pending_transactions": active_pending,
    }

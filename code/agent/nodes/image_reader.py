"""
image_reader.py — Node 2
For financial events with NULL amounts, use Vision LLM to extract the amount
from the linked PNG image in dataset/media/images/.

Only called when NULL amounts are detected (conditional edge in graph.py).
"""
import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from code.agent.state import AgentState
from code.db.queries import log_llm_usage

load_dotenv()

# Lazy import: only load LLM if this node is actually called
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    return _llm


def _extract_amount_from_image(image_path: str, context: str = "") -> float | None:
    """Call Vision LLM to extract a monetary amount from an image."""
    path = Path(image_path)
    if not path.exists():
        return None

    with open(path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = (
        "This is a financial document (receipt, payslip, or bill). "
        f"{context} "
        "Extract ONLY the total monetary amount as a plain number (no currency symbol, no commas). "
        "If you cannot find a clear amount, reply with 'UNKNOWN'."
    )

    try:
        from langchain_core.messages import HumanMessage
        llm = _get_llm()
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ])
        response = llm.invoke([msg])
        text = response.content.strip()

        # Parse numeric value from response
        import re
        nums = re.findall(r"[\d,]+(?:\.\d+)?", text.replace(",", ""))
        if nums:
            return float(nums[0])
    except Exception as e:
        # Graceful fallback: return None
        return None
    return None



def resolve_image_amounts(state: AgentState) -> AgentState:
    """
    For every income/expense with amount=None, find the linked image and extract amount.
    Updates resolved_income and resolved_expenses in state.
    """
    images_by_event = {
        img["related_event_id"]: img
        for img in state.get("images", [])
        if img.get("related_event_id")
    }

    total_tokens = state.get("llm_tokens_used", 0)

    def resolve_list(items: list[dict]) -> list[dict]:
        nonlocal total_tokens
        resolved = []
        for item in items:
            if item.get("amount") is None:
                event_id = item.get("source_ref") or item.get("id")
                img = images_by_event.get(event_id)
                if img:
                    amount = _extract_amount_from_image(
                        img["file_path"],
                        context=f"This is for: {item.get('name', '')}."
                    )
                    if amount is not None:
                        item = {**item, "amount": amount}
                        # Rough token estimate
                        total_tokens += 500
                        log_llm_usage(
                            state["request_id"], "google", "gemini-1.5-flash",
                            "image_extraction", 400, 10, 0.00015
                        )
            resolved.append(item)
        return resolved

    resolved_income = resolve_list(list(state.get("income_sources", [])))
    resolved_expenses = resolve_list(list(state.get("expenses", [])))

    return {
        **state,
        "resolved_income": resolved_income,
        "resolved_expenses": resolved_expenses,
        "active_income": resolved_income,
        "active_expenses": resolved_expenses,
        "llm_tokens_used": total_tokens,
    }

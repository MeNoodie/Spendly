"""
graph.py — LangGraph StateGraph wiring all decision nodes.

Node sequence:
  load_user_context
    → resolve_image_amounts   (conditional: only if NULL amounts exist)
    → apply_message_overrides
    → simulate_forecast
    → generate_plans
    → rank_select_plan
    → generate_explanation
    → END
"""
from langgraph.graph import StateGraph, END
from code.agent.state import AgentState
from code.agent.nodes.data_loader import load_user_context
from code.agent.nodes.image_reader import resolve_image_amounts
from code.agent.nodes.message_processor import apply_message_overrides
from code.agent.nodes.forecaster import simulate_forecast
from code.agent.nodes.planner import generate_plans, rank_select_plan
from code.agent.nodes.explainer import generate_explanation


def _needs_image_resolution(state: AgentState) -> str:
    """Conditional edge: skip image resolution if no NULL amounts."""
    has_null_income = any(s.get("amount") is None for s in state["income_sources"])
    has_null_expense = any(e.get("amount") is None for e in state["expenses"])
    if has_null_income or has_null_expense:
        return "resolve_images"
    return "skip_images"


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("load_user_context", load_user_context)
    g.add_node("resolve_image_amounts", resolve_image_amounts)
    g.add_node("apply_message_overrides", apply_message_overrides)
    g.add_node("simulate_forecast", simulate_forecast)
    g.add_node("generate_plans", generate_plans)
    g.add_node("rank_select_plan", rank_select_plan)
    g.add_node("generate_explanation", generate_explanation)

    g.set_entry_point("load_user_context")

    g.add_conditional_edges(
        "load_user_context",
        _needs_image_resolution,
        {
            "resolve_images": "resolve_image_amounts",
            "skip_images": "apply_message_overrides",
        }
    )

    g.add_edge("resolve_image_amounts", "apply_message_overrides")
    g.add_edge("apply_message_overrides", "simulate_forecast")
    g.add_edge("simulate_forecast", "generate_plans")
    g.add_edge("generate_plans", "rank_select_plan")
    g.add_edge("rank_select_plan", "generate_explanation")
    g.add_edge("generate_explanation", END)

    return g.compile()


_graph = None


def run_agent(initial_state: AgentState) -> AgentState:
    """Run the full decision graph and return final state."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke(initial_state)

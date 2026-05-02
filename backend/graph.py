from langgraph.graph import END, StateGraph

from agents.risk_region_agent import risk_region_agent

# Import the other agents so they are still importable from this module,
# but they are not wired into the active graph right now.
from agents import guidance_agent, resource_agent, route_agent  # noqa: F401
from state import FloodState


workflow = StateGraph(FloodState)

# ── Active pipeline: risk_region_agent → END ─────────────────
workflow.add_node("risk_region_agent", risk_region_agent)
workflow.set_entry_point("risk_region_agent")
workflow.add_edge("risk_region_agent", END)

graph = workflow.compile()

from langgraph.graph import END, StateGraph

from agents import guidance_agent, resource_agent, risk_debate_agent, route_agent
from state import FloodState


workflow = StateGraph(FloodState)

workflow.add_node("risk_debate_agent", risk_debate_agent)
workflow.add_node("resource_agent", resource_agent)
workflow.add_node("route_agent", route_agent)
workflow.add_node("guidance_agent", guidance_agent)

workflow.set_entry_point("risk_debate_agent")
workflow.add_edge("risk_debate_agent", "resource_agent")
workflow.add_edge("resource_agent", "route_agent")
workflow.add_edge("route_agent", "guidance_agent")
workflow.add_edge("guidance_agent", END)

graph = workflow.compile()

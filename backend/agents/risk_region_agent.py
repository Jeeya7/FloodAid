import json
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm import get_llm
from tools.risk_region_tools import (
    DEFAULT_BOUNDS,
    get_gauges_by_bounds_tool,
    get_streamflow_context_tool,
    get_usgs_water_data_tool,
    get_weather_context_tool,
)

# Newport, Oregon — used when state["map_bounds"] is empty
NEWPORT_BOUNDS = {
    "south": 44.55,
    "north": 44.75,
    "west": -124.10,
    "east": -123.80,
}

# Cap how many gauges we send to the LLM to stay inside free-tier token limits
MAX_GAUGES = 3


class RiskState(TypedDict, total=False):
    map_bounds: dict
    environmental_risk_packets: list[dict]
    risk_regions: list[dict]
    debug_steps: list[str]


# ── Nodes ────────────────────────────────────────────────────────────────────

def collect_environmental_packets_node(state: RiskState) -> RiskState:
    """
    Pure Python step — no LLM.
    Calls the tools to gather USGS, streamflow, and weather data for each gauge,
    then packages the results into environmental_risk_packets.
    """
    bounds = state.get("map_bounds") or NEWPORT_BOUNDS
    debug_steps = list(state.get("debug_steps", []))

    gauges = get_gauges_by_bounds_tool.invoke({"bounds": bounds})
    gauges = gauges[:MAX_GAUGES]

    packets: list[dict[str, Any]] = []

    for gauge in gauges:
        station_id = gauge["station_id"]

        usgs      = get_usgs_water_data_tool.invoke({"station_id": station_id})
        streamflow = get_streamflow_context_tool.invoke({"station_id": station_id})
        weather   = get_weather_context_tool.invoke({"lat": gauge["lat"], "lng": gauge["lng"]})

        packets.append({
            "area_id": station_id,
            "name": gauge["name"],
            "river_name": gauge["river_name"],
            "center": {"lat": gauge["lat"], "lng": gauge["lng"]},
            "raw_packet": {
                "usgs": usgs,
                "water_services": streamflow,
                "weather": weather,
            },
        })

    debug_steps.append(f"Collected environmental data for {len(packets)} gauges.")

    return {
        **state,
        "environmental_risk_packets": packets,
        "debug_steps": debug_steps,
    }


SYSTEM_PROMPT = (
    "You are a flood risk analyst. "
    "Analyze the environmental packets and return ONLY valid JSON with this shape:\n"
    '{"environmental_risk_packets":[],"risk_regions":[],"debug_steps":[]}\n'
    "Rules:\n"
    "- Copy all input packets into environmental_risk_packets.\n"
    "- risk_regions = only HIGH or MODERATE risk areas (omit LOW).\n"
    "- high -> color red. moderate -> color yellow.\n"
    "- Each region needs: area_id, name, river_name, risk_level, risk_score, "
    "color, center, radius_miles=25, reasons (from actual data), "
    'data_sources_used=["USGS","Water Services","Weather.gov"].\n'
    "- No markdown. No text outside JSON."
)


def risk_analyzer_node(state: RiskState) -> RiskState:
    """
    Single LLM call — no tool loop, no bind_tools.
    Passes the collected packets to Gemini and parses the JSON response.
    """
    packets = state.get("environmental_risk_packets", [])
    debug_steps = list(state.get("debug_steps", []))

    # Compact JSON keeps the prompt small (important for free-tier quota)
    user_message = "Packets:\n" + json.dumps(packets, separators=(",", ":"))

    response = get_llm().invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").strip()
        raw = raw.removesuffix("```").strip()

    parsed = json.loads(raw)

    # Merge debug steps produced by the LLM (if any) with our own
    llm_debug = parsed.get("debug_steps", [])
    debug_steps.append("Gemini analyzed packets and classified flood risk regions.")
    debug_steps.extend(llm_debug)

    return {
        **state,
        "environmental_risk_packets": parsed.get("environmental_risk_packets", packets),
        "risk_regions": parsed.get("risk_regions", []),
        "debug_steps": debug_steps,
    }


# ── Graph ─────────────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(RiskState)
    g.add_node("collect_environmental_packets", collect_environmental_packets_node)
    g.add_node("risk_analyzer_agent", risk_analyzer_node)
    g.add_edge(START, "collect_environmental_packets")
    g.add_edge("collect_environmental_packets", "risk_analyzer_agent")
    g.add_edge("risk_analyzer_agent", END)
    return g.compile()


_risk_graph = _build_graph()


def risk_region_agent(state: RiskState) -> RiskState:
    return _risk_graph.invoke(state)

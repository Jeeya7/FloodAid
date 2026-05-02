import json

from langgraph.prebuilt import create_react_agent

from llm import get_llm
from state import FloodState
from tools.risk_region_tools import (
    DEFAULT_BOUNDS,
    get_gauges_by_bounds_tool,
    get_usgs_water_data_tool,
    get_streamflow_context_tool,
    get_weather_context_tool,
)


TOOLS = [
    get_gauges_by_bounds_tool,
    get_usgs_water_data_tool,
    get_streamflow_context_tool,
    get_weather_context_tool,
]


SYSTEM_PROMPT = """
You are the Risk Region Agent for FloodSentinel.

You have tools available. Use them to gather flood-related data.

Your job:
1. Call get_gauges_by_bounds_tool using the provided map bounds.
2. For each gauge returned, call:
   - get_usgs_water_data_tool
   - get_streamflow_context_tool
   - get_weather_context_tool
3. Combine the evidence.
4. Identify high and moderate flood risk regions.
5. Return JSON only.

Do not include low-risk areas in risk_regions.

Risk logic:
- high risk: flood warning, above flood stage, very high percentile, rising water, heavy rain
- moderate risk: flood watch, elevated streamflow, above-normal flow, notable rain

Return ONLY this JSON shape:

{
  "environmental_risk_packets": [
    {
      "area_id": "string",
      "name": "string",
      "river_name": "string",
      "center": { "lat": 0.0, "lng": 0.0 },
      "raw_packet": {
        "usgs": {},
        "water_services": {},
        "weather": {}
      }
    }
  ],
  "risk_regions": [
    {
      "area_id": "string",
      "name": "string",
      "river_name": "string",
      "risk_level": "high",
      "risk_score": 90,
      "color": "red",
      "center": { "lat": 0.0, "lng": 0.0 },
      "radius_miles": 25,
      "reasons": ["reason based on tool data"],
      "data_sources_used": ["USGS", "Water Services", "Weather.gov"]
    }
  ],
  "debug_steps": [
    "Agent called tools and analyzed flood risk."
  ]
  
  IMPORTANT:
    Your top-level JSON object MUST include exactly these three keys:
    - environmental_risk_packets
    - risk_regions
    - debug_steps

    Do not rename environmental_risk_packets.
    Do not use names like packets, environmental_packets, or risk_packets.
}
"""


def _parse_json(text: str) -> dict:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()

    return json.loads(cleaned)


def _get_last_text_message(messages: list) -> str:
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content

    raise ValueError("No final text message found from agent.")


def risk_region_agent(state: FloodState) -> FloodState:
    bounds = state.get("map_bounds") or DEFAULT_BOUNDS

    agent = create_react_agent(
        model=get_llm(),
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
    )

    user_prompt = f"""
Analyze flood risk for this map bounding box:

{json.dumps(bounds, indent=2)}

Use your tools. Return the required JSON only.
"""

    result = agent.invoke({
        "messages": [("user", user_prompt)]
    })

    final_text = _get_last_text_message(result["messages"])
    parsed = _parse_json(final_text)

    return {
        **state,
        "environmental_risk_packets": parsed.get("environmental_risk_packets", []),
        "risk_regions": parsed.get("risk_regions", []),
        "debug_steps": parsed.get("debug_steps", []),
    }
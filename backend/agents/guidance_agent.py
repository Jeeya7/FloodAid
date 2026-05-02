import json

from llm import get_llm
from state import FloodState


GUIDANCE_PROMPT = """You are the Guidance Agent for FloodSentinel.

Write a calm, clear, non-panicky flood safety guidance message for a frontend card.
Keep it short: 3 to 5 sentences.

Requirements:
- mention the risk level and confidence
- mention the recommended action
- if evacuation is recommended, name the top resource and estimated travel time
- acknowledge uncertainty when confidence is low or medium
- avoid alarmist wording

Risk assessment:
{risk}

Top resource:
{top_resource}

Route recommendation:
{route}
"""


def _fallback_guidance(state: FloodState, error: Exception) -> str:
    risk = state["risk"]
    resources = state["resources"]
    route = state["route"]
    top_resource = resources.get("top_resource", {})

    guidance = (
        f"Flood risk is currently {risk.get('risk_level', 'unknown')} with "
        f"{risk.get('confidence', 'unknown')} confidence. "
        f"Recommended action: {risk.get('recommended_action', 'stay_informed')}. "
    )

    if route.get("is_evacuation_recommended"):
        guidance += (
            f"Head toward {top_resource.get('name', 'the nearest shelter')} "
            f"— estimated travel time is {route.get('estimated_time', 'unknown')}. "
        )
    else:
        guidance += "Movement is not required right now — keep monitoring updates. "

    guidance += f"(Fallback text used — Gemini unavailable: {error})"
    return guidance


def guidance_agent(state: FloodState) -> FloodState:
    """Use Gemini to produce concise, calm user-facing flood safety guidance."""

    top_resource = state["resources"].get("top_resource", {})

    prompt = GUIDANCE_PROMPT.format(
        risk=json.dumps(state["risk"], indent=2),
        top_resource=json.dumps(top_resource, indent=2),
        route=json.dumps(state["route"], indent=2),
    )

    try:
        response = get_llm().invoke(prompt)
        guidance = str(response.content).strip()
    except Exception as error:
        guidance = _fallback_guidance(state, error)

    debug_steps = state.get("debug_steps", [])
    debug_steps.append(
        "Guidance Agent (Gemini): generated final user-facing safety message "
        f"({len(guidance)} chars)."
    )

    return {
        **state,
        "guidance": guidance,
        "debug_steps": debug_steps,
    }

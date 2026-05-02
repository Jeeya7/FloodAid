import json
from typing import Any

from llm import get_llm
from state import FloodState


RISK_PROMPT = """You are the Risk Debate Agent for FloodSentinel.

Your job is to assess flood risk for a user's location using two internal viewpoints:
1. Escalator: reasons the situation could become dangerous.
2. Skeptic: cautionary evidence, uncertainty, or reasons not to overstate the danger.

Then make a final practical risk judgment.

Return ONLY valid JSON with exactly these fields:
- escalator_reasoning
- skeptic_reasoning
- risk_level: one of low, moderate, high
- confidence: one of low, medium, high
- recommended_action: one of stay_informed, prepare, evacuate, seek_help
- final_reasoning_summary

Location:
{location}

Environmental data:
{environmental_data}
"""


def _parse_json_response(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    return json.loads(cleaned)


def _fallback_risk(
    location: dict[str, Any],
    environmental_data: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    water_status = environmental_data.get("water_level_status", "unknown")
    alert = environmental_data.get("weather_alert", "unknown")
    trend = environmental_data.get("water_level_trend", "unknown")

    return {
        "escalator_reasoning": (
            f"{location.get('city', 'The area')} has {water_status} water levels, "
            f"a {trend} trend, and an active {alert}."
        ),
        "skeptic_reasoning": "Fallback used — LLM response could not be parsed.",
        "risk_level": "moderate",
        "confidence": "low",
        "recommended_action": "prepare",
        "final_reasoning_summary": f"Fallback assessment after Gemini error: {error}",
    }


def risk_debate_agent(state: FloodState) -> FloodState:
    """Use Gemini to weigh flood danger vs. caution, then produce a structured risk judgment."""

    location = state["location"]
    environmental_data = state["environmental_data"]

    prompt = RISK_PROMPT.format(
        location=json.dumps(location, indent=2),
        environmental_data=json.dumps(environmental_data, indent=2),
    )

    try:
        response = get_llm().invoke(prompt)
        risk = _parse_json_response(str(response.content))
    except Exception as error:
        risk = _fallback_risk(location, environmental_data, error)

    debug_steps = state.get("debug_steps", [])
    debug_steps.append(
        f"Risk Debate Agent (Gemini): debated escalator vs. skeptic viewpoints. "
        f"risk_level={risk.get('risk_level')}, "
        f"confidence={risk.get('confidence')}, "
        f"recommended_action={risk.get('recommended_action')}. "
        f"Summary: {risk.get('final_reasoning_summary', '')[:120]}"
    )

    return {
        **state,
        "risk": risk,
        "debug_steps": debug_steps,
    }

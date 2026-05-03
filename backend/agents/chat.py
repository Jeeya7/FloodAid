import json
import os
from pathlib import Path
from typing import Any
from openrouter_client import chat as openrouter_chat

BASE_DIR = Path(__file__).resolve().parent
AGENT_RESPONSE_DIR = BASE_DIR.parent / "agent_response"
FLOOD_DATA_PATH = AGENT_RESPONSE_DIR / "risk_region_agent.json"
RESOURCE_DATA_PATH = AGENT_RESPONSE_DIR / "emergency_resource_agent.json"
ENV_PATH = BASE_DIR.parent / ".env"


def _load_local_env() -> None:
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


def _load_flood_data() -> dict[str, Any]:
    try:
        with FLOOD_DATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _load_resource_data() -> dict[str, Any]:
    try:
        with RESOURCE_DATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _build_system_prompt() -> str:
    flood_data = _load_flood_data()
    resource_data = _load_resource_data()

    # Only send what Droppy actually needs — not the full raw packets
    regions_slim = [
        {
            "name": r.get("name"),
            "risk_level": r.get("risk_level"),
            "confidence": r.get("confidence"),
            "recommended_action": r.get("recommended_action"),
            "reasoning_summary": r.get("reasoning_summary"),
        }
        for r in flood_data.get("regions", [])
    ]

    resources_slim = {
        "hospital": [
            {"name": r.get("name"), "distance_miles": r.get("distance_miles"), "status": r.get("status")}
            for r in resource_data.get("recommended_resources", {}).get("hospital", [])
        ],
        "shelter": [
            {"name": r.get("name"), "distance_miles": r.get("distance_miles"), "status": r.get("status")}
            for r in resource_data.get("recommended_resources", {}).get("shelter", [])
        ],
        "food": [
            {"name": r.get("name"), "distance_miles": r.get("distance_miles"), "status": r.get("status")}
            for r in resource_data.get("recommended_resources", {}).get("food", [])
        ],
    }

    return f"""You are Droppy, the FloodAid emergency assistant — calm, warm, and supportive.
You help people stay safe during flood emergencies near Newport, OR and the Yaquina River area.

RULES:
- Reply directly in under 60 words. Never explain your reasoning.
- Only use the data below. Never invent locations or risk levels.
- For medical emergencies: say call 911 first.
- For danger: use risk_level and recommended_action.
- For food/shelter/hospital: use the resource data below.

FLOOD DATA:
{json.dumps(regions_slim, indent=2)}

RESOURCES:
{json.dumps(resources_slim, indent=2)}
"""


def chat(msg, history):
    # Build conversation context into the user message
    # openrouter_client.chat() takes system + user strings
    # so we fold history into the user turn
    history_text = ""
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_text += f"{role}: {content}\n"

    user_message = f"{history_text}user: {msg}"

    try:
        reply = openrouter_chat(
            system=_build_system_prompt(),
            user=user_message,
            temperature=0.3,
            max_tokens=150,
        )
    except RuntimeError as e:
        reply = f"I'm having trouble connecting right now. Please call 911 for emergencies. (Error: {str(e)})"

    return {"response": reply}




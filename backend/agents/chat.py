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
    return f"""You are Droppy, the FloodAid emergency assistant — calm, warm, and supportive.
You help people stay safe during flood emergencies near Newport, OR and the Yaquina River area.

IMPORTANT: Reply directly and concisely. Never show your thinking or reasoning process.
Never start with "Okay," or "Let me check" or explain what you are doing.
Just give the answer directly as if talking to someone in an emergency.

RULES:
- Only use the real-time flood data provided below. Never invent locations, distances, or risk levels.
- Always mention active flood alerts when relevant.
- Keep responses under 60 words. Be brief and direct.
- Speak plainly — the user may be scared. Be reassuring but honest.
- For danger questions: use risk_level and confidence from regions[].
- For weather questions: use the weather evidence and alert_level.
- For river questions: use hydrology evidence and trend.
- For action questions: use recommended_action from the region.
- For food/shelter questions: say you don't have that data and direct them to call 211 for local resources.
- For medical emergencies: always say call 911 first.
- Never explain your reasoning. Just answer.

CURRENT REAL-TIME FLOOD DATA:
{json.dumps(flood_data, indent=2)}

CURRENT EMERGENCY RESOURCE DATA:
{json.dumps(resource_data, indent=2)}
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




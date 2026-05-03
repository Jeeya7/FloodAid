import json
import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
from openrouter_client import chat as openrouter_chat

load_dotenv()

router = APIRouter()

# Load flood data from existing agent response
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "agent_response", "risk_region_agent.json"), "r") as f:
    FLOOD_DATA = json.load(f)

SYSTEM_PROMPT = f"""You are Droppy, the FloodAid emergency assistant — calm, warm, and supportive.
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
{json.dumps(FLOOD_DATA, indent=2)}
"""


class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []


@router.post("/chat")
async def chat(req: ChatRequest):
    # Build conversation context into the user message
    # openrouter_client.chat() takes system + user strings
    # so we fold history into the user turn
    history_text = ""
    for msg in req.history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_text += f"{role}: {content}\n"

    user_message = f"{history_text}user: {req.message}"

    try:
        reply = openrouter_chat(
            system=SYSTEM_PROMPT,
            user=user_message,
            temperature=0.3,
            max_tokens=150,
        )
    except RuntimeError as e:
        reply = f"I'm having trouble connecting right now. Please call 911 for emergencies. (Error: {str(e)})"

    return {"response": reply}
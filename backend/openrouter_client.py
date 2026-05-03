# openrouter_client.py
# Thin wrapper around the OpenRouter chat completions endpoint.
# No extra dependencies — uses only the standard-library `urllib` module.

import json
import os
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

# Read from environment — never hardcode
_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")


def chat(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """
    Send a single chat-completion request to OpenRouter and return the
    raw content string from the first choice.

    Raises RuntimeError on HTTP errors or missing API key.
    """
    if not _API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )

    payload = json.dumps({
        "model": MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"OpenRouter request failed: {exc.code} {exc.reason} — {exc.read().decode()}"
        ) from exc

    return body["choices"][0]["message"]["content"]


def parse_json_response(raw: str) -> dict[str, Any]:
    """
    Parse a JSON string returned by the model.
    Handles the common case where the model wraps output in ```json fences.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    return json.loads(text)

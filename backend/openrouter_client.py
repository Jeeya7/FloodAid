# openrouter_client.py
# Thin wrapper around the OpenRouter chat completions endpoint.
# No extra dependencies — uses only the standard-library `urllib` module.
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 3, 6]


def chat(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )

    payload = json.dumps({
        "model": MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning": {"effort": "none"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        if attempt > 0:
            time.sleep(_RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)])

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"OpenRouter request failed: {exc.code} {exc.reason} — {exc.read().decode()}"
            ) from exc

        choice = body.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content")

        provider_error = choice.get("error")
        if provider_error:
            error_code = provider_error.get("code")
            error_type = provider_error.get("metadata", {}).get("error_type", "")
            last_error = RuntimeError(
                f"Provider error (code={error_code}, type={error_type}): "
                f"{provider_error.get('message')}"
            )
            if error_code == 502 or error_type == "provider_unavailable":
                continue
            raise last_error

        if content is None:
            last_error = RuntimeError(
                f"OpenRouter returned null content "
                f"(finish_reason={choice.get('finish_reason')!r}, model={MODEL})"
            )
            continue

        return content

    raise RuntimeError(
        f"OpenRouter failed after {_MAX_RETRIES} attempts. Last error: {last_error}"
    )


def parse_json_response(raw: str) -> dict[str, Any]:
    if not raw:
        raise ValueError(f"Cannot parse empty or null LLM response: {raw!r}")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    return json.loads(text)
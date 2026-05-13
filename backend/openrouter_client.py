# openrouter_client.py
# Thin wrapper around the OpenRouter chat completions endpoint.


import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# the AI model we're using for all agent calls
MODEL = "nvidia/nemotron-3-super-120b-a12b"

# retry settings — if the API fails we try up to 3 times before giving up
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 3, 6]  # seconds to wait between retries


def chat(
    system: str,       # the system prompt — tells the AI what role it's playing
    user: str,         # the actual message/data we're sending
    temperature: float = 0.2,   # low temperature = more consistent, less random responses
    max_tokens: int = 2048,     # max length of the response
) -> str:
    # grab the API key from environment — set in .env file
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )

    # build the request body in OpenAI-compatible format
    # OpenRouter uses the same format as OpenAI so switching models is easy
    payload = json.dumps({
        "model":       MODEL,
        "temperature": temperature,
        "max_tokens":  max_tokens,
        "reasoning":   {"effort": "none"},  # skip chain-of-thought to save tokens
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

    # retry loop — handles temporary API failures gracefully
    for attempt in range(_MAX_RETRIES):
        # wait before retrying — longer each time so we don't hammer the API
        if attempt > 0:
            time.sleep(_RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)])

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"OpenRouter request failed: {exc.code} {exc.reason} — {exc.read().decode()}"
            ) from exc

        # pull the actual response out of the API response structure
        choice  = body.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content")

        # sometimes the underlying model provider fails even if OpenRouter responds 200
        # in that case we get an error object instead of content
        provider_error = choice.get("error")
        if provider_error:
            error_code = provider_error.get("code")
            error_type = provider_error.get("metadata", {}).get("error_type", "")
            last_error = RuntimeError(
                f"Provider error (code={error_code}, type={error_type}): "
                f"{provider_error.get('message')}"
            )
            # 502 or provider_unavailable means the model is temporarily down — retry
            if error_code == 502 or error_type == "provider_unavailable":
                continue
            # any other provider error is not retryable — fail immediately
            raise last_error

        # sometimes content comes back as null — retry if that happens
        if content is None:
            last_error = RuntimeError(
                f"OpenRouter returned null content "
                f"(finish_reason={choice.get('finish_reason')!r}, model={MODEL})"
            )
            continue

        # success — return the response text
        return content

    # if we get here all retries failed
    raise RuntimeError(
        f"OpenRouter failed after {_MAX_RETRIES} attempts. Last error: {last_error}"
    )


def parse_json_response(raw: str) -> dict[str, Any]:
    # the LLM sometimes wraps its JSON in markdown code blocks like ```json ... ```
    # this strips those out so we can parse the JSON cleanly
    if not raw:
        raise ValueError(f"Cannot parse empty or null LLM response: {raw!r}")

    text = raw.strip()

    # strip markdown code fences if present
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()

    return json.loads(text)
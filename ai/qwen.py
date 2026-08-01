import base64
import logging
import os
import time

import requests

logger = logging.getLogger("rain_logger")

PROVIDERS = {
    "llama-cpp": {"base_url": "http://127.0.0.1:8080", "needs_key": False},
    "openai": {"base_url": "https://api.openai.com/v1", "needs_key": True},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "needs_key": True},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "needs_key": True},
    "together": {"base_url": "https://api.together.xyz/v1", "needs_key": True},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "needs_key": True},
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "needs_key": True,
    },
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "needs_key": True},
}


class AIError(Exception):
    pass


def resolve_endpoint(ai_config):
    provider = (ai_config.get("provider") or "llama-cpp").lower()
    if provider == "custom":
        base_url = (ai_config.get("base_url") or "").rstrip("/")
        if not base_url:
            raise AIError(
                "AI provider 'custom' requires a base_url in config.yaml."
            )
    elif provider in PROVIDERS:
        base_url = (ai_config.get("base_url") or "").rstrip("/") or PROVIDERS[
            provider
        ]["base_url"]
    else:
        raise AIError(
            f"Unknown AI provider '{provider}'. Supported providers: "
            f"{', '.join(sorted(PROVIDERS))}, custom."
        )

    api_key = ""
    key_env = ai_config.get("api_key_env") or ""
    if key_env:
        api_key = os.environ.get(key_env, "")

    if provider in PROVIDERS and PROVIDERS[provider]["needs_key"] and not api_key:
        raise AIError(
            f"AI provider '{provider}' requires an API key. "
            f"Set ai.api_key_env in config.yaml to the env var holding the key."
        )
    return base_url, api_key


def check_reachable(base_url, timeout=5, api_key=""):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = requests.get(
            base_url.rstrip("/") + "/v1/models", headers=headers, timeout=timeout
        )
        return response.ok
    except requests.RequestException:
        return False


def send_image(base_url, model, image_path, system_message, timeout=120,
               api_key="", max_tokens=1024, temperature=0.2,
               frequency_penalty=0.0):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    return _send(
        base_url, model, image_bytes, system_message, timeout, api_key,
        max_tokens, temperature, frequency_penalty,
    )


def send_bytes(base_url, model, image_bytes, system_message, timeout=120,
               api_key="", max_tokens=1024, temperature=0.2,
               frequency_penalty=0.0):
    return _send(base_url, model, image_bytes, system_message, timeout,
                 api_key, max_tokens, temperature, frequency_penalty)


def _send(base_url, model, image_bytes, system_message, timeout, api_key,
          max_tokens, temperature=0.2, frequency_penalty=0.0):
    timeout = timeout if (timeout and timeout > 0) else None
    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze the stitched image and report "
                        "rainfall conditions exactly as instructed. "
                        "Do not think out loud; output only the fields.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                ],
            },
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = requests.post(
            base_url.rstrip("/") + "/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIError(f"AI request failed: {exc}") from exc
    data = response.json()
    try:
        content = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("Malformed AI response.") from exc
    if not content.strip():
        raise AIError("AI returned empty content.")
    return content


def _retry(base_url, model, image_bytes, system_message, attempts,
           backoff_seconds, max_backoff_seconds, timeout, api_key, max_tokens,
           temperature, frequency_penalty):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            logger.info("Sent image to AI (attempt %d/%d).", attempt, attempts)
            return _send(
                base_url, model, image_bytes, system_message, timeout, api_key,
                max_tokens, temperature, frequency_penalty,
            )
        except AIError as exc:
            last_error = exc
            if attempt == attempts:
                break
            wait = min(
                backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds
            )
            logger.warning(
                "AI attempt %d/%d failed (%s); retrying in %.1fs.",
                attempt,
                attempts,
                exc,
                wait,
            )
            time.sleep(wait)
    raise AIError(
        f"AI request failed after {attempts} attempts: {last_error}"
    )


def send_with_retry(base_url, model, image_path, system_message,
                    attempts=3, backoff_seconds=2, max_backoff_seconds=30,
                    timeout=120, api_key="", max_tokens=1024, temperature=0.2,
                    frequency_penalty=0.0):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    return _retry(
        base_url, model, image_bytes, system_message, attempts,
        backoff_seconds, max_backoff_seconds, timeout, api_key, max_tokens,
        temperature, frequency_penalty,
    )


def send_bytes_with_retry(base_url, model, image_bytes, system_message,
                          attempts=3, backoff_seconds=2, max_backoff_seconds=30,
                          timeout=120, api_key="", max_tokens=1024,
                          temperature=0.2, frequency_penalty=0.0):
    return _retry(
        base_url, model, image_bytes, system_message, attempts,
        backoff_seconds, max_backoff_seconds, timeout, api_key, max_tokens,
        temperature, frequency_penalty,
    )

import json
import logging
from collections.abc import Callable

import requests

log = logging.getLogger(__name__)


def translate(
    text: str,
    base_url: str,
    model: str,
    source_lang: str,
    target_lang: str,
    on_partial: Callable[[str], None] | None = None,
) -> str:
    """Send text to an OpenAI-compatible /chat/completions endpoint for translation.

    Returns the translated string, or raises an exception on failure.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Translate the following segment into {target_lang} language, "
                    "without additional explanation.\n\n"
                    f"{text}"
                ),
            },
        ],
        "temperature": 0.1,
    }

    log.info("POST %s", url)
    log.debug("Request payload:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))

    if on_partial is not None:
        try:
            return _translate_streaming(url=url, payload=payload, on_partial=on_partial)
        except Exception as exc:
            # Any streaming problem should transparently fallback to non-stream.
            log.info("Streaming failed (%s). Falling back to non-stream.", exc)

    return _translate_non_stream(url=url, payload=payload)


def _translate_non_stream(url: str, payload: dict) -> str:
    response = requests.post(url, json=payload, timeout=30)

    log.info("Response status: %s", response.status_code)
    log.debug("Response body:\n%s", response.text)

    response.raise_for_status()

    data = response.json()
    translated = data["choices"][0]["message"]["content"].strip()

    log.info("Translation result: %s", translated)
    return translated


def _translate_streaming(url: str, payload: dict, on_partial: Callable[[str], None]) -> str:
    """Streaming chat completions (SSE) with partial updates.

    Expects OpenAI-compatible SSE: lines like `data: {...}` and final `data: [DONE]`.
    """
    payload = dict(payload)
    payload["stream"] = True

    # Long reads are expected during generation.
    response = requests.post(url, json=payload, stream=True, timeout=(10, 300))
    log.info("Streaming response status: %s", response.status_code)
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/event-stream" not in content_type:
        # Some servers still stream without correct header; keep going if data: lines appear.
        log.debug("Unexpected streaming Content-Type: %r", content_type)

    text_so_far = ""
    saw_data_line = False

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("data:"):
            continue

        saw_data_line = True
        data_str = line[len("data:") :].strip()
        if data_str == "[DONE]":
            break

        try:
            data = json.loads(data_str)
        except Exception:
            # Not valid JSON in data line => treat as streaming failure.
            raise ValueError(f"Invalid SSE JSON chunk: {data_str[:120]!r}")

        try:
            choice0 = (data.get("choices") or [])[0]
            delta = choice0.get("delta") or {}
            chunk = delta.get("content")
        except Exception:
            chunk = None

        if isinstance(chunk, str) and chunk:
            text_so_far += chunk
            on_partial(text_so_far)

    if not saw_data_line:
        raise ValueError("No SSE data lines received (streaming not supported?)")

    return text_so_far.strip()

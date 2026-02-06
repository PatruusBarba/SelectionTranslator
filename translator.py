import json
import logging

import requests

log = logging.getLogger(__name__)


def translate(text: str, base_url: str, model: str, source_lang: str, target_lang: str) -> str:
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

    response = requests.post(url, json=payload, timeout=30)

    log.info("Response status: %s", response.status_code)
    log.debug("Response body:\n%s", response.text)

    response.raise_for_status()

    data = response.json()
    translated = data["choices"][0]["message"]["content"].strip()

    log.info("Translation result: %s", translated)
    return translated

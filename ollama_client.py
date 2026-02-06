from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlparse

import requests


def _ollama_root_from_base_url(base_url: str) -> str:
    """
    Convert an OpenAI-compatible base URL like:
      http://localhost:11434/v1
    into an Ollama root like:
      http://localhost:11434
    """
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base_url: {base_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def list_models(base_url: str) -> set[str]:
    """Return a set of installed model names from Ollama (/api/tags)."""
    root = _ollama_root_from_base_url(base_url)
    url = f"{root}/api/tags"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    models = set()
    for item in data.get("models", []) or []:
        name = item.get("name")
        if isinstance(name, str) and name:
            models.add(name)
    return models


def pull_model(
    base_url: str,
    model: str,
    on_progress: Callable[[str, int | None], None] | None = None,
) -> None:
    """
    Pull a model via Ollama (/api/pull) with streamed progress.

    Calls on_progress(status, percent) where percent may be None if unknown.
    """
    root = _ollama_root_from_base_url(base_url)
    url = f"{root}/api/pull"
    payload = {"name": model, "stream": True}

    with requests.post(url, json=payload, stream=True, timeout=60) as resp:
        resp.raise_for_status()

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                evt = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            status = evt.get("status")
            if not isinstance(status, str):
                status = "Downloading"

            percent = None
            completed = evt.get("completed")
            total = evt.get("total")
            if isinstance(completed, (int, float)) and isinstance(total, (int, float)) and total:
                percent = int(max(0, min(100, (completed / total) * 100)))

            if on_progress:
                on_progress(status, percent)


def list_running_models(base_url: str) -> list[str]:
    """Return list of models currently loaded into memory (/api/ps)."""
    root = _ollama_root_from_base_url(base_url)
    url = f"{root}/api/ps"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    running = []
    for item in data.get("models", []) or []:
        name = item.get("model")
        if isinstance(name, str) and name:
            running.append(name)
    return running


def unload_model(base_url: str, model: str) -> None:
    """Unload one model from memory using keep_alive=0."""
    root = _ollama_root_from_base_url(base_url)
    url = f"{root}/api/generate"
    payload = {"model": model, "keep_alive": 0}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()


def unload_all_running_models(base_url: str) -> list[str]:
    """Unload all running models (best-effort). Returns list attempted."""
    running = list_running_models(base_url)
    attempted = []
    for name in running:
        attempted.append(name)
        try:
            unload_model(base_url, name)
        except Exception:
            # Best-effort; continue unloading others.
            pass
    return attempted

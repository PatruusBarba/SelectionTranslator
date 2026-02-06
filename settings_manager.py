import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "base_url": "http://localhost:8000/v1",
    "model": "HY-MT1.5-1.8B",
    "source_lang": "English",
    "target_lang": "Russian",
    "hotkey": "ctrl+alt+t",
}


def load_settings() -> dict:
    """Load settings from settings.json, returning defaults for any missing keys."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            settings.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings: dict) -> None:
    """Persist settings dict to settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

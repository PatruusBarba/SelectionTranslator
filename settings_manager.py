import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    # Flattened values (derived from active_profile on load)
    "base_url": "http://localhost:1234/v1",
    "model": "hy-mt1.5-1.8b",
    "source_lang": "English",
    "target_lang": "Russian",
    "hotkey": "ctrl+alt+t",
    "active_profile": "LM Studio",
    "profiles": {
        "LM Studio": {
            "base_url": "http://localhost:1234/v1",
            "model": "hy-mt1.5-1.8b",
            "model_presets": ["hy-mt1.5-1.8b"],
        },
        "Ollama": {
            "base_url": "http://localhost:11434/v1",
            "model": "huihui_ai/hy-mt1.5-abliterated:1.8b",
            "model_presets": [
                "huihui_ai/hy-mt1.5-abliterated:1.8b",
                "huihui_ai/hy-mt1.5-abliterated:7b",
            ],
        },
        "Custom": {
            "base_url": "http://localhost:1234/v1",
            "model": "",
            "model_presets": [],
        },
    },
}


def load_settings() -> dict:
    """Load settings from settings.json, returning defaults for any missing keys."""
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                settings.update(stored)
        except (json.JSONDecodeError, OSError):
            pass

    # --- Migration from legacy schema (top-level base_url/model only) ---
    profiles = settings.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    active_profile = settings.get("active_profile")
    if not isinstance(active_profile, str) or not active_profile:
        active_profile = "Custom"

    # Ensure standard profiles exist (do not clobber if user customized them)
    for name, defaults in DEFAULT_SETTINGS["profiles"].items():
        if name not in profiles or not isinstance(profiles.get(name), dict):
            profiles[name] = json.loads(json.dumps(defaults))
        else:
            # fill missing keys
            for k, v in defaults.items():
                if k not in profiles[name]:
                    profiles[name][k] = json.loads(json.dumps(v))
            # merge default model presets (append missing)
            default_presets = defaults.get("model_presets")
            if isinstance(default_presets, list):
                existing_presets = profiles[name].get("model_presets")
                if not isinstance(existing_presets, list):
                    existing_presets = []
                for m in default_presets:
                    if m and m not in existing_presets:
                        existing_presets.append(m)
                profiles[name]["model_presets"] = existing_presets

    # If legacy values were present, store them into Custom profile
    legacy_base_url = settings.get("base_url")
    legacy_model = settings.get("model")
    if isinstance(legacy_base_url, str) and legacy_base_url and (
        "base_url" not in profiles.get("Custom", {}) or profiles["Custom"].get("base_url") in (None, "")
    ):
        profiles["Custom"]["base_url"] = legacy_base_url
    if isinstance(legacy_model, str) and legacy_model and (
        "model" not in profiles.get("Custom", {}) or profiles["Custom"].get("model") in (None, "")
    ):
        profiles["Custom"]["model"] = legacy_model
        # Ensure the legacy model appears in the dropdown at least once
        presets = profiles["Custom"].get("model_presets")
        if not isinstance(presets, list):
            presets = []
        if legacy_model not in presets:
            presets.append(legacy_model)
        profiles["Custom"]["model_presets"] = presets

    # If active_profile points to something unknown, fallback to Custom
    if active_profile not in profiles:
        active_profile = "Custom"

    # Flatten base_url/model from active profile for the rest of the app
    active = profiles.get(active_profile, {})
    settings["profiles"] = profiles
    settings["active_profile"] = active_profile
    settings["base_url"] = str(active.get("base_url", settings.get("base_url", "")) or "")
    settings["model"] = str(active.get("model", settings.get("model", "")) or "")
    return settings


def save_settings(settings: dict) -> None:
    """Persist settings dict to settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

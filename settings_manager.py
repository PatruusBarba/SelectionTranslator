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

    # Ensure hotkey string is present and normalize legacy "scNN" tokens.
    hotkey = settings.get("hotkey")
    if not isinstance(hotkey, str) or not hotkey.strip():
        hotkey = DEFAULT_SETTINGS["hotkey"]
    hotkey = _normalize_hotkey(hotkey)
    settings["hotkey"] = hotkey

    # Remove stale scan-code keys that are no longer used.
    settings.pop("hotkey_scancodes", None)
    settings.pop("hotkey_display", None)

    return settings


# Scan-code → QWERTY key name (for normalizing legacy "scNN" hotkey strings).
_SC_TO_NAME: dict[int, str] = {
    16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u", 23: "i",
    24: "o", 25: "p", 30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h",
    36: "j", 37: "k", 38: "l", 44: "z", 45: "x", 46: "c", 47: "v", 48: "b",
    49: "n", 50: "m",
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    57: "space", 28: "enter", 1: "escape", 15: "tab",
    59: "f1", 60: "f2", 61: "f3", 62: "f4", 63: "f5", 64: "f6",
    65: "f7", 66: "f8", 67: "f9", 68: "f10", 87: "f11", 88: "f12",
    29: "ctrl", 285: "ctrl", 56: "alt", 312: "alt",
    42: "shift", 54: "shift", 91: "windows", 92: "windows",
}


def _normalize_hotkey(hotkey: str) -> str:
    """Replace legacy 'scNN' tokens with human-readable QWERTY names."""
    import re
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    normalized: list[str] = []
    for p in parts:
        m = re.fullmatch(r"sc(\d+)", p)
        if m:
            sc = int(m.group(1))
            name = _SC_TO_NAME.get(sc, p)
            normalized.append(name)
        else:
            normalized.append(p)
    return "+".join(normalized)


def save_settings(settings: dict) -> None:
    """Persist settings dict to settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

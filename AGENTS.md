# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Clipboard Translator is a Python desktop app (system-tray) that translates selected text via a global hotkey using an OpenAI-compatible LLM endpoint. See `README.md` for full feature list and settings.

### Platform support

- **Windows**: Uses Win32 APIs (`ctypes.windll`) for hotkeys and key simulation. This is the primary platform.
- **Linux**: Uses `pynput` for hotkeys and key simulation. Requires `xclip` for clipboard, `python3-tk` for GUI, `python3-dev` for building `evdev` (pynput dependency).

### Virtual environment

The project uses a Python venv at `.venv/`. Activate it before running anything:

```bash
source /workspace/.venv/bin/activate
```

### Running the app on Linux

```bash
DISPLAY=:1 python3 main.py --show-settings
```

- `--show-settings` keeps the Settings window visible on startup (required on Linux since pystray's xorg backend cannot dock in a system tray without a tray manager).
- pystray will log "Failed to dock icon" errors — this is expected and non-blocking.
- The global hotkey (default `Ctrl+Alt+T`) is registered via `pynput.keyboard.GlobalHotKeys`.

### Mock LLM server for testing

Use `mock_llm_server.py` on port 1234 to test translations without a real LLM:

```bash
python3 mock_llm_server.py
```

The default "LM Studio" profile points to `http://localhost:1234/v1`, which matches this mock server.

### Linting

Ruff is installed in the venv. Run from project root:

```bash
ruff check .
```

Pre-existing E402 warnings in `main.py` are intentional (logging config before imports).

### Key gotchas

- **Hotkey conflict on Linux**: The default hotkey `Ctrl+Alt+T` conflicts with the desktop environment's "open terminal" shortcut. For testing on Linux, either change the hotkey in settings (e.g., to `Ctrl+Alt+Y`) or disable the OS shortcut via `xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Primary><Alt>t" -r` (for Xfce).
- The `keyboard` library (used in `ui.py` for hotkey recording) needs root access on Linux. The "Record" button in Settings may not work without root. The rest of the app works fine without root.
- `pyperclip` needs `xclip` installed on Linux (`sudo apt-get install xclip`).
- On Linux, `pynput` needs `python3-dev` to build `evdev`. Install via `sudo apt-get install python3-dev`.
- No automated test suite exists. Verification is done via linting, compile checks, import tests, and manual GUI testing.

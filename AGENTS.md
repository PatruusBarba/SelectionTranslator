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

### Running Ollama for real translations

Start Ollama and pull the default translation model:

```bash
ollama serve &
ollama pull huihui_ai/hy-mt1.5-abliterated:1.8b
```

The app's "Ollama" profile is pre-configured to `http://localhost:11434/v1` with this model. Ollama runs on CPU in the Cloud Agent VM; translation takes ~5-10 seconds per sentence.

### Mock LLM server (optional)

Use `mock_llm_server.py` on port 1234 for fast testing without a real model:

```bash
python3 mock_llm_server.py
```

Switch the app to the "LM Studio" profile (`http://localhost:1234/v1`) to use it.

### Linting

Ruff is installed in the venv. Run from project root:

```bash
ruff check .
```

Pre-existing E402 warnings in `main.py` are intentional (logging config before imports).

### Key gotchas

- **Hotkey conflict on Linux**: The default hotkey `Ctrl+Alt+T` conflicts with the desktop environment's "open terminal" shortcut. Disable it: `xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Primary><Alt>t" -r`.
- **Cyrillic in Mousepad**: Install fonts (`sudo apt-get install fonts-noto`) and set Mousepad encoding to UTF-8 (`xfconf-query -c mousepad -p /preferences/file/default-encoding -n -t string -s "UTF-8"`). Pasting Cyrillic via pynput's Ctrl+V may still show mojibake in Mousepad due to a GTK clipboard MIME type issue. The actual clipboard data is correct UTF-8 — verify with `xclip -o -selection clipboard`. Opening the same text from a file renders properly.
- The `keyboard` library (used in `ui.py` for hotkey recording) needs root access on Linux. The "Record" button in Settings may not work without root.
- `pyperclip` needs `xclip` installed on Linux (`sudo apt-get install xclip`).
- On Linux, `pynput` needs `python3-dev` to build `evdev`. Install via `sudo apt-get install python3-dev`.
- No automated test suite exists. Verification is done via linting, compile checks, import tests, and manual GUI testing.

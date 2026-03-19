# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Clipboard Translator is a **Windows-only** Python desktop app (system-tray) that translates selected text via a global hotkey using an OpenAI-compatible LLM endpoint. See `README.md` for full feature list and settings.

### Platform constraint

The application uses Win32 APIs (`ctypes.windll` in `hotkey_handler.py`) and cannot run on Linux. On Linux-based Cloud Agent VMs, you can:

- Install dependencies and run static analysis / linting
- Import and test platform-independent modules (`translator.py`, `settings_manager.py`, `ollama_client.py`, `overlay.py`, `ui.py`)
- `hotkey_handler.py` and `main.py` will fail to import on Linux due to `ctypes.windll`

### Virtual environment

The project uses a Python venv at `.venv/`. Activate it before running anything:

```bash
source /workspace/.venv/bin/activate
```

### Linting

Ruff is installed in the venv. Run from project root:

```bash
ruff check .
```

Pre-existing E402 warnings in `main.py` are intentional (logging config before imports).

### Syntax / compile check

```bash
python3 -m py_compile <file.py>
```

All `.py` files compile cleanly.

### Testing platform-independent code

No automated test suite exists. To verify platform-independent modules work, you can:

1. Import and call `settings_manager.load_settings()` — returns default settings dict
2. Run `translator.translate()` against a mock or real OpenAI-compatible endpoint
3. Import `ollama_client` functions for Ollama REST API interactions

### No automated tests

This repository has no test framework or test files. Verification is done via compile checks, linting, and manual import tests.

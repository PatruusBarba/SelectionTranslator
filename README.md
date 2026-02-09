# Clipboard Translator

A system-tray Python app that translates selected text in any application via a global hotkey. It copies the selection, sends it to an OpenAI-compatible LLM endpoint, and pastes the translation back — replacing the original text.

## Features

- Global hotkey (default `Ctrl+Alt+T`) works in any application
- Configurable source and target languages
- Connects to any OpenAI-compatible API (`/v1/chat/completions`)
- Settings UI built with Tkinter
- Minimizes to the system tray; error notifications via tray balloon
- Settings persist to `settings.json`

## Requirements

- Python 3.10+
- Windows (uses `keyboard` library for global hotkeys and key simulation)

## Installation

```bash
pip install -r requirements.txt
```

## Build Artifact (PyInstaller)

Build a standalone Windows app so end users do not need Python installed.

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Build from the existing spec file:

```bash
pyinstaller --noconfirm ClipboardTranslator.spec
```

3. Output artifact:
- `dist/ClipboardTranslator/` for `onedir` build (recommended for reliability/startup)
- `dist/ClipboardTranslator.exe` for `onefile` build (if configured in spec)

Optional direct build commands (without spec):

```bash
# onedir
pyinstaller --noconfirm --windowed --onedir --name ClipboardTranslator main.py

# onefile
pyinstaller --noconfirm --windowed --onefile --name ClipboardTranslator main.py
```

Notes:
- Close any running instance of the app before building.
- Test the built artifact on a clean Windows machine.
- `settings.json` should remain user-local (do not bundle personal settings into the artifact).

## Usage

```bash
python main.py
```

The app starts minimized to the system tray. Right-click the tray icon to open **Settings** or **Quit**.

### Ollama

This app uses an **OpenAI-compatible** Chat Completions API (`/v1/chat/completions`).

- If you use Ollama locally, set **Base URL** to `http://localhost:11434/v1`.
- Keep **Model ID** as the Ollama model name (for example: `llama3`, `qwen2.5`, etc.).
- If the selected Ollama model is missing, the app can **download it automatically** and shows progress in:
  - the global overlay, and
  - the Settings window (Download button + progress bar).

### Logs (see the exact LLM request)

Run the app from a terminal. The console will show:

- `POST .../chat/completions`
- The full JSON request payload (including messages)
- Response status and body

### Settings

| Field           | Description                                       | Default                      |
|-----------------|---------------------------------------------------|------------------------------|
| Profile         | Preset that sets Base URL + Model ID together     | `LM Studio`                  |
| Base URL        | LLM server endpoint                               | `http://localhost:8000/v1`   |
| Model ID        | Model name passed to the API                      | `HY-MT1.5-1.8B`             |
| Source language  | Language of the selected text                     | `English`                    |
| Target language  | Language to translate into                        | `Russian`                    |
| Hotkey          | Global key combination to trigger translation      | `ctrl+alt+t`                 |

Notes:
- Each **Profile** keeps its own **Model ID dropdown list**. If you type a new model and press **Save**, it will be added to that profile's list.
- Default presets:
  - **LM Studio**: `http://localhost:1234/v1`, model `hy-mt1.5-1.8b`
  - **Ollama**: `http://localhost:11434/v1`, model `huihui_ai/hy-mt1.5-abliterated:1.8b`

### Workflow

1. Select text in any application.
2. Press the hotkey.
3. The app copies the selection, sends it to the LLM for translation, and pastes the result in place.

## Project Structure

| File                 | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `main.py`            | Entry point, system tray icon, wiring                    |
| `ui.py`              | Tkinter settings window                                  |
| `hotkey_handler.py`  | Global hotkey listener, copy-translate-paste orchestration|
| `translator.py`      | LLM API call (`/v1/chat/completions`)                    |
| `settings_manager.py`| Load/save `settings.json`                                |

---

## Features to add

1. [x] Overlay when translation is generating (preferably with a simple animation).
2. [x] Make language selection into a dropbox (with ability to write custom text as input).
3. [x] Ollama support.
4. [x] Use streaming for LLM and show translation progress (generating text) in overlay.
5. [x] Make model id drop down with a few predefined values (HY-MT1.5-1.8B for example).
6. [ ] Backward translation keybind.
7. [ ] Smart language selection keybind?
8. [ ] Change default port from 8080 to ollama default in release artefact.

import threading
import time

import keyboard
import pyperclip

from translator import translate


class HotkeyHandler:
    """Manages global hotkey registration and the copy-translate-paste flow."""

    def __init__(self, settings: dict, on_error=None, on_busy_start=None, on_busy_end=None):
        self._settings = dict(settings)
        self._on_error = on_error  # callback(str) for error notifications
        self._on_busy_start = on_busy_start  # callback() when translation begins
        self._on_busy_end = on_busy_end  # callback() when translation ends
        self._hotkey_handle = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_settings(self, settings: dict) -> None:
        """Apply new settings and re-register the hotkey."""
        self._settings = dict(settings)
        self.register()

    def register(self) -> None:
        """(Re-)register the global hotkey."""
        self.unregister()
        hotkey = self._settings.get("hotkey", "ctrl+alt+t")
        try:
            self._hotkey_handle = keyboard.add_hotkey(
                hotkey,
                self._on_hotkey,
                suppress=True,
                trigger_on_release=True,
            )
        except Exception as exc:
            if self._on_error:
                self._on_error(f"Failed to register hotkey '{hotkey}': {exc}")

    def unregister(self) -> None:
        """Remove the currently registered hotkey, if any."""
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except (KeyError, ValueError):
                pass
            self._hotkey_handle = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_hotkey(self) -> None:
        """Kick off the translate flow in a background thread."""
        threading.Thread(target=self._translate_flow, daemon=True).start()

    def _translate_flow(self) -> None:
        try:
            # 1. Save current clipboard content
            try:
                original_clipboard = pyperclip.paste()
            except Exception:
                original_clipboard = ""

            # 2. Simulate Ctrl+C to copy selected text
            # Release modifiers from the hotkey to avoid accidental combos
            # (some keyboard drivers/hooks can misbehave otherwise).
            for key_name in ("ctrl", "alt", "shift", "windows"):
                try:
                    keyboard.release(key_name)
                except Exception:
                    pass

            time.sleep(0.03)
            keyboard.press_and_release("ctrl+c")
            time.sleep(0.2)

            # 3. Read the clipboard
            selected_text = pyperclip.paste()

            # 4. If nothing was copied (or same as before), skip
            if not selected_text or selected_text == original_clipboard:
                return

            # 5. Translate via LLM (show overlay while in-flight)
            try:
                if self._on_busy_start:
                    self._on_busy_start()

                translated = translate(
                    text=selected_text,
                    base_url=self._settings["base_url"],
                    model=self._settings["model"],
                    source_lang=self._settings["source_lang"],
                    target_lang=self._settings["target_lang"],
                )
            finally:
                if self._on_busy_end:
                    self._on_busy_end()

            if not translated:
                return

            # 6. Write translation to clipboard and paste
            pyperclip.copy(translated)
            time.sleep(0.05)
            keyboard.press_and_release("ctrl+v")

            # 7. Restore original clipboard after a short delay
            time.sleep(0.5)
            pyperclip.copy(original_clipboard)

        except Exception as exc:
            if self._on_error:
                self._on_error(str(exc))

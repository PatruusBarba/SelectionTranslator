import threading
import time

import keyboard
import pyperclip
import requests

from translator import translate
from ollama_client import list_models, pull_model, unload_all_running_models


class HotkeyHandler:
    """Manages global hotkey registration and the copy-translate-paste flow."""

    def __init__(
        self,
        settings: dict,
        on_error=None,
        on_busy_start=None,
        on_busy_end=None,
        on_overlay_message=None,
        on_overlay_progress=None,
        on_download_progress=None,
    ):
        self._settings = dict(settings)
        self._on_error = on_error  # callback(str) for error notifications
        self._on_busy_start = on_busy_start  # callback() when translation begins
        self._on_busy_end = on_busy_end  # callback() when translation ends
        self._on_overlay_message = on_overlay_message  # callback(str)
        self._on_overlay_progress = on_overlay_progress  # callback(int|None)
        self._on_download_progress = on_download_progress  # callback(bool,str,int|None)
        self._hotkey_handle = None
        self._run_lock = threading.Lock()

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

    def download_model_async(self, base_url: str, model: str) -> None:
        """Download (pull) an Ollama model in a background thread."""
        if not self._run_lock.acquire(blocking=False):
            return
        threading.Thread(
            target=self._download_worker,
            args=(base_url, model),
            daemon=True,
        ).start()

    def _is_ollama_profile(self) -> bool:
        return self._settings.get("active_profile") == "Ollama"

    def unload_ollama_models_sync(self) -> None:
        """Unload all running Ollama models from memory (best-effort)."""
        if not self._is_ollama_profile():
            return
        if not self._run_lock.acquire(blocking=False):
            return
        try:
            if self._on_busy_start:
                self._on_busy_start()
            if self._on_overlay_message:
                self._on_overlay_message("Unloading models from memory...")
            if self._on_overlay_progress:
                self._on_overlay_progress(None)
            self._notify_download(True, "Unloading models from memory...", None)

            base_url = self._settings.get("base_url", "")
            attempted = unload_all_running_models(base_url)

            msg = "Unloaded models." if attempted else "No running models."
            if self._on_overlay_message:
                self._on_overlay_message(msg)
            self._notify_download(False, msg, None)
        except Exception as exc:
            self._notify_download(False, f"Unload failed: {exc}", None)
            if self._on_error:
                self._on_error(str(exc))
        finally:
            if self._on_busy_end:
                self._on_busy_end()
            try:
                self._run_lock.release()
            except RuntimeError:
                pass

    def unload_ollama_models_async(self) -> None:
        """Unload all running Ollama models from memory in a background thread."""
        if not self._is_ollama_profile():
            return
        threading.Thread(target=self.unload_ollama_models_sync, daemon=True).start()

    def _notify_download(self, in_progress: bool, status: str, percent: int | None) -> None:
        if self._on_download_progress:
            self._on_download_progress(in_progress, status, percent)

    def _pull_model_with_progress(self, base_url: str, model: str) -> None:
        if self._on_overlay_message:
            self._on_overlay_message(f"Downloading model: {model}")
        if self._on_overlay_progress:
            self._on_overlay_progress(None)
        self._notify_download(True, f"Downloading model: {model}", None)

        def on_progress(status: str, percent: int | None) -> None:
            if self._on_overlay_message:
                self._on_overlay_message(status)
            if self._on_overlay_progress:
                self._on_overlay_progress(percent)
            self._notify_download(True, status, percent)

        pull_model(base_url=base_url, model=model, on_progress=on_progress)

        if self._on_overlay_progress:
            self._on_overlay_progress(100)
        self._notify_download(False, "Download complete", 100)

    def _download_worker(self, base_url: str, model: str) -> None:
        try:
            if self._on_busy_start:
                self._on_busy_start()
            self._pull_model_with_progress(base_url, model)
        except Exception as exc:
            self._notify_download(False, f"Download failed: {exc}", None)
            if self._on_error:
                self._on_error(str(exc))
        finally:
            if self._on_busy_end:
                self._on_busy_end()
            try:
                self._run_lock.release()
            except RuntimeError:
                pass

    def _ensure_ollama_model(self, base_url: str, model: str) -> None:
        models = list_models(base_url)
        if model in models:
            return
        # Pull the model with progress (blocking inside current worker thread)
        self._pull_model_with_progress(base_url, model)

    def _is_model_not_found_error(self, exc: Exception, model: str) -> bool:
        if not isinstance(exc, requests.HTTPError) or exc.response is None:
            return False
        try:
            data = exc.response.json()
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        err = data.get("error")
        if not isinstance(err, dict):
            return False
        msg = err.get("message")
        return isinstance(msg, str) and ("not found" in msg) and (model in msg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_hotkey(self) -> None:
        """Kick off the translate flow in a background thread."""
        if not self._run_lock.acquire(blocking=False):
            return
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

                base_url = self._settings["base_url"]
                model = self._settings["model"]

                if self._is_ollama_profile():
                    self._ensure_ollama_model(base_url, model)

                try:
                    translated = translate(
                        text=selected_text,
                        base_url=base_url,
                        model=model,
                        source_lang=self._settings["source_lang"],
                        target_lang=self._settings["target_lang"],
                    )
                except Exception as exc:
                    if self._is_ollama_profile() and self._is_model_not_found_error(exc, model):
                        self._ensure_ollama_model(base_url, model)
                        translated = translate(
                            text=selected_text,
                            base_url=base_url,
                            model=model,
                            source_lang=self._settings["source_lang"],
                            target_lang=self._settings["target_lang"],
                        )
                    else:
                        raise
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
        finally:
            try:
                self._run_lock.release()
            except RuntimeError:
                pass

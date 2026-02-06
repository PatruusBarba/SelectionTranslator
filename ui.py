import tkinter as tk
from tkinter import ttk, messagebox

import keyboard
import threading
import time

from ollama_client import list_models

from settings_manager import load_settings, save_settings


class SettingsWindow:
    """Tkinter settings UI for the Clipboard Translator."""

    def __init__(self, on_settings_saved=None, on_close=None, on_download_model=None, on_unload_models=None):
        """
        Args:
            on_settings_saved: callback(settings_dict) invoked after Save.
            on_close: callback() invoked when the window is closed (minimize to tray).
            on_download_model: callback(base_url, model) to start download.
            on_unload_models: callback() to unload models from memory (Ollama).
        """
        self._on_settings_saved = on_settings_saved
        self._on_close = on_close
        self._on_download_model = on_download_model
        self._on_unload_models = on_unload_models
        self._recording_hotkey = False
        self._download_in_progress = False
        self._model_check_job = None

        # -- Root window ---------------------------------------------------
        self.root = tk.Tk()
        self.root.title("Clipboard Translator — Settings")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        # -- Style ----------------------------------------------------------
        style = ttk.Style(self.root)
        style.theme_use("clam")

        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.grid(sticky="nsew")

        # -- Fields ---------------------------------------------------------
        settings = load_settings()
        profiles = settings.get("profiles", {})
        active_profile = settings.get("active_profile", "Custom")
        row = 0

        ttk.Label(main_frame, text="Profile:").grid(row=row, column=0, sticky="w", pady=4)
        self._profile_var = tk.StringVar(value=active_profile)
        self._profile_combo = ttk.Combobox(
            main_frame,
            textvariable=self._profile_var,
            values=("LM Studio", "Ollama", "Custom"),
            state="readonly",
            width=45,
        )
        self._profile_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0))
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_changed)

        row += 1
        ttk.Label(main_frame, text="Base URL:").grid(row=row, column=0, sticky="w", pady=4)
        self._base_url_var = tk.StringVar(value=settings["base_url"])
        self._base_url_combo = ttk.Combobox(
            main_frame,
            textvariable=self._base_url_var,
            values=("http://localhost:1234/v1", "http://localhost:11434/v1"),
            state="normal",
            width=45,
        )
        self._base_url_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0))

        row += 1
        ttk.Label(main_frame, text="Model ID:").grid(row=row, column=0, sticky="w", pady=4)
        self._model_var = tk.StringVar(value=settings["model"])
        model_presets = ()
        if isinstance(profiles, dict) and isinstance(profiles.get(active_profile), dict):
            presets = profiles[active_profile].get("model_presets", [])
            if isinstance(presets, list):
                model_presets = tuple(str(x) for x in presets if x)
        self._model_combo = ttk.Combobox(
            main_frame,
            textvariable=self._model_var,
            values=model_presets,
            state="normal",
            width=45,
        )
        self._model_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0))

        row += 1
        self._model_status_var = tk.StringVar(value="")
        ttk.Label(main_frame, text="Model status:").grid(row=row, column=0, sticky="w", pady=4)
        self._model_status_label = ttk.Label(main_frame, textvariable=self._model_status_var)
        self._model_status_label.grid(row=row, column=1, sticky="w", pady=4, padx=(8, 4))
        self._download_btn = ttk.Button(
            main_frame,
            text="Download model",
            command=self._on_download_clicked,
            state="disabled",
        )
        self._download_btn.grid(row=row, column=2, sticky="e", pady=4)

        row += 1
        self._unload_btn = ttk.Button(
            main_frame,
            text="Выгрузить модели из памяти",
            command=self._on_unload_clicked,
            state="disabled",
        )
        self._unload_btn.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0))
        self._unload_btn.grid_remove()

        row += 1
        self._download_percent_var = tk.StringVar(value="")
        self._download_progress_var = tk.IntVar(value=0)
        self._download_progress = ttk.Progressbar(
            main_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self._download_progress_var,
            length=260,
        )
        self._download_progress.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 4))
        self._download_progress_label = ttk.Label(main_frame, textvariable=self._download_percent_var)
        self._download_progress_label.grid(row=row, column=2, sticky="e", pady=4)
        self._download_progress.grid_remove()
        self._download_progress_label.grid_remove()

        row += 1
        ttk.Label(main_frame, text="Source language:").grid(row=row, column=0, sticky="w", pady=4)
        self._source_lang_var = tk.StringVar(value=settings["source_lang"])
        self._source_lang_combo = ttk.Combobox(
            main_frame,
            textvariable=self._source_lang_var,
            values=("English", "Russian"),
            state="normal",
            width=45,
        )
        self._source_lang_combo.grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0)
        )

        row += 1
        ttk.Label(main_frame, text="Target language:").grid(row=row, column=0, sticky="w", pady=4)
        self._target_lang_var = tk.StringVar(value=settings["target_lang"])
        self._target_lang_combo = ttk.Combobox(
            main_frame,
            textvariable=self._target_lang_var,
            values=("English", "Russian"),
            state="normal",
            width=45,
        )
        self._target_lang_combo.grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0)
        )

        row += 1
        ttk.Label(main_frame, text="Hotkey:").grid(row=row, column=0, sticky="w", pady=4)
        self._hotkey_var = tk.StringVar(value=settings.get("hotkey", "ctrl+alt+t"))
        self._hotkey_entry = ttk.Entry(
            main_frame, textvariable=self._hotkey_var, width=25, state="readonly"
        )
        self._hotkey_entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 4))
        self._record_btn = ttk.Button(
            main_frame, text="Record", command=self._start_recording
        )
        self._record_btn.grid(row=row, column=2, sticky="e", pady=4)

        # -- Buttons --------------------------------------------------------
        row += 1
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=(16, 0))

        self._save_btn = ttk.Button(btn_frame, text="Save", command=self._save)
        self._save_btn.pack(side="left", padx=4)
        self._cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._handle_close)
        self._cancel_btn.pack(side="left", padx=4)

        # Apply profile values once at startup (ensures vars match selected profile)
        self._apply_profile_to_fields()

        # Re-check model status when model text changes
        self._model_var.trace_add("write", lambda *_: self._schedule_model_check())

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        """Enter hotkey-recording mode: wait for a key combo, then store it."""
        if self._recording_hotkey:
            return
        self._recording_hotkey = True
        self._record_btn.configure(text="Press keys...")
        threading.Thread(target=self._record_hotkey_thread, daemon=True).start()

    # Scan-code → QWERTY name map (physical key regardless of layout)
    _SC_TO_QWERTY: dict[int, str] = {
        29: "ctrl", 56: "alt", 42: "shift", 54: "shift",
        91: "windows", 92: "windows",
        # We also handle left/right ctrl and alt (some keyboards report different codes)
        285: "ctrl", 312: "alt",
        # Letters (QWERTY physical scan codes on standard keyboards)
        16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u", 23: "i",
        24: "o", 25: "p", 30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h",
        36: "j", 37: "k", 38: "l", 44: "z", 45: "x", 46: "c", 47: "v", 48: "b",
        49: "n", 50: "m",
        # Digits
        2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8",
        10: "9", 11: "0",
        # Misc
        57: "space", 28: "enter", 1: "escape", 15: "tab",
        59: "f1", 60: "f2", 61: "f3", 62: "f4", 63: "f5", 64: "f6",
        65: "f7", 66: "f8", 67: "f9", 68: "f10", 87: "f11", 88: "f12",
    }

    def _record_hotkey_thread(self) -> None:
        """Record a physical hotkey combo and store it as a QWERTY name string."""
        captured: dict[int, str] = {}
        pressed: set[int] = set()
        last_event_t = time.time()
        start_t = time.time()

        def on_event(event: keyboard.KeyboardEvent) -> None:
            nonlocal last_event_t
            try:
                last_event_t = time.time()
                sc = int(getattr(event, "scan_code", 0) or 0)
                if event.event_type == keyboard.KEY_DOWN:
                    pressed.add(sc)
                    if sc not in captured:
                        # Map scan code → QWERTY name (layout-independent!)
                        qwerty_name = self._SC_TO_QWERTY.get(sc)
                        if qwerty_name:
                            captured[sc] = qwerty_name
                        else:
                            # Fallback: use the name reported by `keyboard`, if any
                            name = getattr(event, "name", "") or ""
                            if name:
                                captured[sc] = name.lower()
                elif event.event_type == keyboard.KEY_UP:
                    pressed.discard(sc)
            except Exception:
                pass

        hook = keyboard.hook(on_event, suppress=False)
        try:
            while True:
                if captured and not pressed and (time.time() - last_event_t) > 0.25:
                    break
                if (time.time() - start_t) > 6.0:
                    break
                time.sleep(0.01)
        finally:
            try:
                keyboard.unhook(hook)
            except Exception:
                pass

        # Build a display string: modifiers first (ctrl, alt, shift, win), then other keys
        _mod_priority = {"ctrl": 0, "alt": 1, "shift": 2, "windows": 3}

        def sort_key(sc: int) -> tuple[int, int]:
            name = captured.get(sc, "")
            return (_mod_priority.get(name, 10), sc)

        ordered = sorted(captured.keys(), key=sort_key)
        parts = [captured[sc] for sc in ordered]
        # Deduplicate (e.g. left+right ctrl both map to "ctrl")
        seen: set[str] = set()
        deduped: list[str] = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                deduped.append(p)

        display = "+".join(deduped) if deduped else ""
        self.root.after(0, self._finish_recording, display)

    def _finish_recording(self, display: str) -> None:
        self._recording_hotkey = False
        self._record_btn.configure(text="Record")
        if display:
            self._hotkey_var.set(display)

    # ------------------------------------------------------------------
    # Save / close
    # ------------------------------------------------------------------

    def _on_profile_changed(self, event=None) -> None:  # noqa: ARG002
        self._apply_profile_to_fields()
        self._schedule_model_check()

    def _apply_profile_to_fields(self) -> None:
        settings = load_settings()
        profiles = settings.get("profiles", {})
        profile = self._profile_var.get() or "Custom"
        if not isinstance(profiles, dict) or not isinstance(profiles.get(profile), dict):
            return

        p = profiles[profile]
        self._base_url_var.set(str(p.get("base_url", "")))
        self._model_var.set(str(p.get("model", "")))

        presets = p.get("model_presets", [])
        if not isinstance(presets, list):
            presets = []
        self._model_combo.configure(values=tuple(str(x) for x in presets if x))
        self._schedule_model_check()

    def _is_ollama_profile_selected(self) -> bool:
        return (self._profile_var.get() or "") == "Ollama"

    def _schedule_model_check(self) -> None:
        if self._download_in_progress:
            return
        if self._model_check_job is not None:
            try:
                self.root.after_cancel(self._model_check_job)
            except Exception:
                pass
            self._model_check_job = None

        self._model_check_job = self.root.after(400, self._start_model_check_thread)

    def _start_model_check_thread(self) -> None:
        self._model_check_job = None
        if not self._is_ollama_profile_selected():
            self._model_status_var.set("")
            self._download_btn.configure(state="disabled")
            return

        base_url = self._base_url_var.get().strip()
        model = self._model_var.get().strip()
        if not base_url or not model:
            self._model_status_var.set("Missing")
            self._download_btn.configure(state="disabled")
            return

        def worker() -> None:
            installed = False
            try:
                models = list_models(base_url)
                installed = model in models
            except Exception:
                installed = False
            self.root.after(0, self._apply_model_status, installed)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_model_status(self, installed: bool) -> None:
        if not self._is_ollama_profile_selected():
            self._model_status_var.set("")
            self._download_btn.configure(state="disabled")
            self._unload_btn.grid_remove()
            return
        # On Ollama profile: show unload button
        self._unload_btn.grid()
        self._unload_btn.configure(state=("disabled" if self._download_in_progress else "normal"))
        if installed:
            self._model_status_var.set("Installed")
            self._download_btn.configure(state="disabled")
        else:
            self._model_status_var.set("Missing")
            # Enable only if we have a model name
            self._download_btn.configure(
                state=("normal" if self._model_var.get().strip() else "disabled")
            )

    def _set_controls_enabled(self, enabled: bool) -> None:
        if enabled:
            self._profile_combo.configure(state="readonly")
            self._base_url_combo.configure(state="normal")
            self._model_combo.configure(state="normal")
            self._source_lang_combo.configure(state="normal")
            self._target_lang_combo.configure(state="normal")
            self._record_btn.configure(state="normal")
            self._save_btn.configure(state="normal")
            self._unload_btn.configure(state=("normal" if self._is_ollama_profile_selected() else "disabled"))
        else:
            self._profile_combo.configure(state="disabled")
            self._base_url_combo.configure(state="disabled")
            self._model_combo.configure(state="disabled")
            self._source_lang_combo.configure(state="disabled")
            self._target_lang_combo.configure(state="disabled")
            self._record_btn.configure(state="disabled")
            self._save_btn.configure(state="disabled")
            self._unload_btn.configure(state="disabled")

    def _on_download_clicked(self) -> None:
        if not self._is_ollama_profile_selected():
            return
        base_url = self._base_url_var.get().strip()
        model = self._model_var.get().strip()
        if not base_url or not model:
            return
        if not self._on_download_model:
            messagebox.showwarning("Download", "Download handler is not configured.")
            return
        # Optimistically set UI state; progress updates will refine it.
        self.set_download_progress_threadsafe(True, "Starting download...", None)
        self._on_download_model(base_url, model)

    def _on_unload_clicked(self) -> None:
        if not self._is_ollama_profile_selected():
            return
        if self._download_in_progress:
            return
        if not self._on_unload_models:
            messagebox.showwarning("Unload", "Unload handler is not configured.")
            return
        self.set_download_progress_threadsafe(True, "Unloading models from memory...", None)
        self._on_unload_models()

    def set_download_model_callback(self, cb) -> None:
        self._on_download_model = cb

    def set_unload_models_callback(self, cb) -> None:
        self._on_unload_models = cb

    def set_download_progress_threadsafe(self, in_progress: bool, status: str, percent: int | None) -> None:
        self.root.after(0, self._set_download_progress, in_progress, status, percent)

    def _set_download_progress(self, in_progress: bool, status: str, percent: int | None) -> None:
        if in_progress:
            self._download_in_progress = True
            self._set_controls_enabled(False)
            self._download_btn.configure(state="disabled")
            self._model_status_var.set(status)
            self._download_progress.grid()
            self._download_progress_label.grid()

            if percent is None:
                self._download_percent_var.set("")
                self._download_progress.configure(mode="indeterminate")
                self._download_progress.start(10)
            else:
                self._download_progress.stop()
                self._download_progress.configure(mode="determinate")
                self._download_progress_var.set(int(percent))
                self._download_percent_var.set(f"{int(percent)}%")
        else:
            # Done or failed
            self._download_in_progress = False
            try:
                self._download_progress.stop()
            except Exception:
                pass
            self._download_progress.grid_remove()
            self._download_progress_label.grid_remove()
            self._set_controls_enabled(True)
            # After download attempt, re-check installed status
            self._schedule_model_check()

    def _save(self) -> None:
        loaded = load_settings()
        profiles = loaded.get("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}

        active_profile = (self._profile_var.get() or "Custom").strip() or "Custom"
        if active_profile not in profiles or not isinstance(profiles.get(active_profile), dict):
            profiles[active_profile] = {"base_url": "", "model": "", "model_presets": []}

        base_url = self._base_url_var.get().strip()
        model = self._model_var.get().strip()

        settings = {
            # flattened (derived) values
            "base_url": base_url,
            "model": model,
            # profile schema
            "active_profile": active_profile,
            "profiles": profiles,
            # hotkey (QWERTY name string, parsed by Windows RegisterHotKey)
            "hotkey": self._hotkey_var.get().strip(),
            # rest
            "source_lang": self._source_lang_var.get().strip(),
            "target_lang": self._target_lang_var.get().strip(),
        }

        if not settings["base_url"]:
            messagebox.showwarning("Validation", "Base URL cannot be empty.")
            return
        if not settings["model"]:
            messagebox.showwarning("Validation", "Model ID cannot be empty.")
            return

        # Update active profile values + per-profile model presets
        profile_obj = settings["profiles"][active_profile]
        profile_obj["base_url"] = base_url
        profile_obj["model"] = model
        presets = profile_obj.get("model_presets", [])
        if not isinstance(presets, list):
            presets = []
        if model and model not in presets:
            presets.append(model)
        profile_obj["model_presets"] = presets

        save_settings(settings)

        if self._on_settings_saved:
            self._on_settings_saved(settings)

        messagebox.showinfo("Saved", "Settings saved successfully.")
        self._schedule_model_check()

    def _handle_close(self) -> None:
        """Hide the window instead of destroying it (minimize to tray)."""
        self.root.withdraw()
        if self._on_close:
            self._on_close()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show / restore the settings window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def reload_fields(self) -> None:
        """Re-read settings.json and update entry fields."""
        settings = load_settings()
        self._profile_var.set(settings.get("active_profile", "Custom"))
        self._base_url_var.set(settings["base_url"])
        self._model_var.set(settings["model"])
        self._source_lang_var.set(settings["source_lang"])
        self._target_lang_var.set(settings["target_lang"])
        self._hotkey_var.set(settings.get("hotkey", "ctrl+alt+t"))
        self._apply_profile_to_fields()

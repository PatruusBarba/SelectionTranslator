import tkinter as tk
from tkinter import ttk, messagebox

import keyboard

from settings_manager import load_settings, save_settings


class SettingsWindow:
    """Tkinter settings UI for the Clipboard Translator."""

    def __init__(self, on_settings_saved=None, on_close=None):
        """
        Args:
            on_settings_saved: callback(settings_dict) invoked after Save.
            on_close: callback() invoked when the window is closed (minimize to tray).
        """
        self._on_settings_saved = on_settings_saved
        self._on_close = on_close
        self._recording_hotkey = False

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
        self._hotkey_var = tk.StringVar(value=settings["hotkey"])
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

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._handle_close).pack(side="left", padx=4)

        # Apply profile values once at startup (ensures vars match selected profile)
        self._apply_profile_to_fields()

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def _start_recording(self) -> None:
        """Enter hotkey-recording mode: wait for a key combo, then store it."""
        if self._recording_hotkey:
            return
        self._recording_hotkey = True
        self._record_btn.configure(text="Press keys...")
        # Use keyboard.read_hotkey in a thread so the UI doesn't block
        import threading

        threading.Thread(target=self._record_hotkey_thread, daemon=True).start()

    def _record_hotkey_thread(self) -> None:
        try:
            hotkey = keyboard.read_hotkey(suppress=False)
            # Normalize (keyboard lib returns something like 'ctrl+alt+t')
            self.root.after(0, self._finish_recording, hotkey)
        except Exception:
            self.root.after(0, self._finish_recording, None)

    def _finish_recording(self, hotkey: str | None) -> None:
        self._recording_hotkey = False
        self._record_btn.configure(text="Record")
        if hotkey:
            self._hotkey_var.set(hotkey)

    # ------------------------------------------------------------------
    # Save / close
    # ------------------------------------------------------------------

    def _on_profile_changed(self, event=None) -> None:  # noqa: ARG002
        self._apply_profile_to_fields()

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
            # rest
            "source_lang": self._source_lang_var.get().strip(),
            "target_lang": self._target_lang_var.get().strip(),
            "hotkey": self._hotkey_var.get().strip(),
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
        self._hotkey_var.set(settings["hotkey"])
        self._apply_profile_to_fields()

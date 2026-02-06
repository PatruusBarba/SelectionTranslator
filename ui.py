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

        row = 0

        ttk.Label(main_frame, text="Base URL:").grid(row=row, column=0, sticky="w", pady=4)
        self._base_url_var = tk.StringVar(value=settings["base_url"])
        ttk.Entry(main_frame, textvariable=self._base_url_var, width=45).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0)
        )

        row += 1
        ttk.Label(main_frame, text="Model ID:").grid(row=row, column=0, sticky="w", pady=4)
        self._model_var = tk.StringVar(value=settings["model"])
        ttk.Entry(main_frame, textvariable=self._model_var, width=45).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 0)
        )

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

    def _save(self) -> None:
        settings = {
            "base_url": self._base_url_var.get().strip(),
            "model": self._model_var.get().strip(),
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
        self._base_url_var.set(settings["base_url"])
        self._model_var.set(settings["model"])
        self._source_lang_var.set(settings["source_lang"])
        self._target_lang_var.set(settings["target_lang"])
        self._hotkey_var.set(settings["hotkey"])

import tkinter as tk
from tkinter import ttk


class TranslatingOverlay:
    """A small always-on-top overlay shown during translation."""

    def __init__(self, root: tk.Tk, bottom_padding_px: int = 80):
        self._root = root
        self._bottom_padding_px = bottom_padding_px

        self._window = tk.Toplevel(self._root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.wm_attributes("-topmost", True)

        # Basic look
        frame = ttk.Frame(self._window, padding=(14, 10))
        frame.grid()
        self._label_var = tk.StringVar(value="Translating")
        ttk.Label(frame, textvariable=self._label_var).grid()

        self._anim_job = None
        self._anim_step = 0

    # ------------------------------------------------------------------
    # Public API (UI thread)
    # ------------------------------------------------------------------

    def show(self) -> None:
        self._position_bottom_center()
        self._window.deiconify()
        self._window.lift()
        self._start_animation()

    def hide(self) -> None:
        self._stop_animation()
        self._window.withdraw()

    # ------------------------------------------------------------------
    # Thread-safe helpers
    # ------------------------------------------------------------------

    def show_threadsafe(self) -> None:
        self._root.after(0, self.show)

    def hide_threadsafe(self) -> None:
        self._root.after(0, self.hide)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _position_bottom_center(self) -> None:
        self._window.update_idletasks()
        win_w = self._window.winfo_width()
        win_h = self._window.winfo_height()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()

        x = (screen_w - win_w) // 2
        y = screen_h - win_h - self._bottom_padding_px
        self._window.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def _start_animation(self) -> None:
        if self._anim_job is not None:
            return
        self._anim_step = 0
        self._tick_animation()

    def _tick_animation(self) -> None:
        dots = "." * (self._anim_step % 4)
        self._label_var.set(f"Translating{dots}")
        self._anim_step += 1
        self._anim_job = self._window.after(250, self._tick_animation)

    def _stop_animation(self) -> None:
        if self._anim_job is None:
            return
        try:
            self._window.after_cancel(self._anim_job)
        except Exception:
            pass
        self._anim_job = None

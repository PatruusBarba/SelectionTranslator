import tkinter as tk
from tkinter import ttk


class TranslatingOverlay:
    """A small always-on-top overlay shown during translation."""

    def __init__(self, root: tk.Tk, bottom_padding_px: int = 80):
        self._root = root
        self._bottom_padding_px = bottom_padding_px
        self._max_width_px = 400

        self._window = tk.Toplevel(self._root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.wm_attributes("-topmost", True)
        self._window.columnconfigure(0, weight=1)
        self._window.rowconfigure(0, weight=1)

        # Basic look
        frame = ttk.Frame(self._window, padding=(14, 10))
        frame.grid(sticky="ew")
        frame.columnconfigure(0, weight=1)
        self._message_var = tk.StringVar(value="Translating")
        self._detail_var = tk.StringVar(value="")
        self._message_label = ttk.Label(
            frame,
            textvariable=self._message_var,
            wraplength=self._max_width_px,
            justify="left",
        )
        self._message_label.grid(sticky="ew")
        self._detail_label = ttk.Label(
            frame,
            textvariable=self._detail_var,
            wraplength=self._max_width_px,
            justify="left",
        )
        self._detail_label.grid(sticky="ew")

        self._anim_job = None
        self._anim_step = 0
        self._indeterminate = True
        self._manual_detail = False

    # ------------------------------------------------------------------
    # Public API (UI thread)
    # ------------------------------------------------------------------

    def show(self) -> None:
        self._position_bottom_center()
        self._window.deiconify()
        self._window.lift()
        # Default: translating animation
        self._message_var.set("Translating")
        self._manual_detail = False
        self._set_progress(None)

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

    def set_message_threadsafe(self, text: str) -> None:
        self._root.after(0, self._set_message, text)

    def set_progress_threadsafe(self, percent: int | None) -> None:
        self._root.after(0, self._set_progress, percent)

    def set_detail_threadsafe(self, text: str) -> None:
        self._root.after(0, self._set_detail, text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _position_bottom_center(self) -> None:
        self._window.update_idletasks()
        # Use requested size so window can grow when text wraps to more lines.
        win_w = self._window.winfo_reqwidth()
        win_h = self._window.winfo_reqheight()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()

        x = (screen_w - win_w) // 2
        y = screen_h - win_h - self._bottom_padding_px
        self._window.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def _set_progress(self, percent: int | None) -> None:
        if percent is None:
            self._indeterminate = True
            self._start_animation()
        else:
            self._indeterminate = False
            self._stop_animation()
            self._manual_detail = False
            self._detail_var.set(f"{int(percent)}%")
            self._root.after_idle(self._position_bottom_center)

    def _set_message(self, text: str) -> None:
        self._message_var.set(text)
        self._root.after_idle(self._position_bottom_center)

    def _set_detail(self, text: str) -> None:
        # When streaming partials are shown, do not let dot animation overwrite detail.
        self._manual_detail = True
        self._detail_var.set(text)
        self._root.after_idle(self._position_bottom_center)

    def _start_animation(self) -> None:
        if self._anim_job is not None:
            return
        self._anim_step = 0
        self._tick_animation()

    def _tick_animation(self) -> None:
        dots = "." * (self._anim_step % 4)
        if self._indeterminate and not self._manual_detail:
            self._detail_var.set(dots)
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

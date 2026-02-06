"""Clipboard Translator — entry point.

Starts the system-tray icon and the Tkinter settings UI.
Global hotkey is registered on startup.
"""

import logging
import threading

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from PIL import Image, ImageDraw
import pystray

from settings_manager import load_settings
from hotkey_handler import HotkeyHandler
from overlay import TranslatingOverlay
from ui import SettingsWindow


# ---------------------------------------------------------------
# Tray icon helper
# ---------------------------------------------------------------

def _create_tray_image(size: int = 64) -> Image.Image:
    """Generate a simple coloured-square icon for the system tray."""
    img = Image.new("RGB", (size, size), "#2196F3")
    draw = ImageDraw.Draw(img)
    # Draw a white "T" in the centre
    margin = size // 5
    bar_h = size // 8
    stem_w = size // 6
    # Top bar
    draw.rectangle(
        [margin, margin, size - margin, margin + bar_h], fill="white"
    )
    # Vertical stem
    cx = size // 2
    draw.rectangle(
        [cx - stem_w // 2, margin + bar_h, cx + stem_w // 2, size - margin],
        fill="white",
    )
    return img


# ---------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------

_tray_icon: pystray.Icon | None = None


def _notify_error(message: str) -> None:
    """Show a brief notification via the tray icon."""
    if _tray_icon is not None:
        try:
            _tray_icon.notify(message, title="Translator Error")
        except Exception:
            pass


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main() -> None:
    global _tray_icon

    settings = load_settings()

    # -- Settings window (Tkinter) --------------------------------------
    handler = None  # assigned after overlay is created

    def on_settings_saved(new_settings: dict) -> None:
        if handler is not None:
            handler.update_settings(new_settings)

    win = SettingsWindow(on_settings_saved=on_settings_saved)

    # -- Translating overlay --------------------------------------------
    overlay = TranslatingOverlay(win.root, bottom_padding_px=80)

    # -- Hotkey handler --------------------------------------------------
    handler = HotkeyHandler(
        settings,
        on_error=_notify_error,
        on_busy_start=overlay.show_threadsafe,
        on_busy_end=overlay.hide_threadsafe,
        on_overlay_message=overlay.set_message_threadsafe,
        on_overlay_progress=overlay.set_progress_threadsafe,
        on_download_progress=win.set_download_progress_threadsafe,
    )
    win.set_download_model_callback(handler.download_model_async)
    win.set_unload_models_callback(handler.unload_ollama_models_async)

    # -- System tray icon ------------------------------------------------
    def on_show_settings(icon, item):  # noqa: ARG001
        win.root.after(0, win.show)

    def on_quit(icon, item):  # noqa: ARG001
        # Best-effort: unload Ollama models from memory before exiting.
        try:
            handler.unload_ollama_models_sync()
        except Exception:
            pass
        handler.unregister()
        icon.stop()
        win.root.after(0, win.root.destroy)

    menu = pystray.Menu(
        pystray.MenuItem("Settings", on_show_settings, default=True),
        pystray.MenuItem("Quit", on_quit),
    )

    _tray_icon = pystray.Icon(
        name="ClipboardTranslator",
        icon=_create_tray_image(),
        title="Clipboard Translator",
        menu=menu,
    )

    # Register hotkey now that everything is wired up
    handler.register()

    # Hide the settings window on start (tray only)
    win.root.withdraw()

    # Run pystray in its own thread so Tkinter mainloop stays on the main thread
    tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
    tray_thread.start()

    # Tkinter mainloop (must be on the main thread)
    win.root.mainloop()


if __name__ == "__main__":
    main()

import ctypes
import ctypes.wintypes
import logging
import threading
import time

import pyperclip
import requests

from translator import translate
from ollama_client import list_models, pull_model, unload_all_running_models

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Windows RegisterHotKey via ctypes — with explicit function signatures
# ---------------------------------------------------------------------------
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# RegisterHotKey / UnregisterHotKey
_user32.RegisterHotKey.argtypes = [
    ctypes.wintypes.HWND, ctypes.c_int, ctypes.wintypes.UINT, ctypes.wintypes.UINT,
]
_user32.RegisterHotKey.restype = ctypes.wintypes.BOOL

_user32.UnregisterHotKey.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = ctypes.wintypes.BOOL

# GetMessageW (blocking)
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
_user32.GetMessageW.restype = ctypes.wintypes.BOOL

# PostThreadMessageW (to unblock GetMessageW from another thread)
_user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD, ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
_user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL

_kernel32.GetCurrentThreadId.argtypes = []
_kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_HOTKEY_ID = 1  # arbitrary unique id within our thread

# Virtual-key codes for A-Z and digits (layout-independent!)
_VK_MAP: dict[str, int] = {}
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _VK_MAP[_ch] = 0x41 + _i
for _i in range(10):
    _VK_MAP[str(_i)] = 0x30 + _i
_VK_MAP.update({
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "escape": 0x1B, "esc": 0x1B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
})

_MOD_NAMES: dict[str, int] = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "left ctrl": MOD_CONTROL, "right ctrl": MOD_CONTROL,
    "alt": MOD_ALT,
    "left alt": MOD_ALT, "right alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "left shift": MOD_SHIFT, "right shift": MOD_SHIFT,
    "windows": MOD_WIN, "win": MOD_WIN,
    "left windows": MOD_WIN, "right windows": MOD_WIN,
}

# Scan-code → VK code map (for legacy "scNN" keys saved by the old recorder).
# Standard Set-1 scan codes for QWERTY physical keys.
_SC_TO_VK: dict[int, int] = {
    # Letters
    16: 0x51,  # Q
    17: 0x57,  # W
    18: 0x45,  # E
    19: 0x52,  # R
    20: 0x54,  # T
    21: 0x59,  # Y
    22: 0x55,  # U
    23: 0x49,  # I
    24: 0x4F,  # O
    25: 0x50,  # P
    30: 0x41,  # A
    31: 0x53,  # S
    32: 0x44,  # D
    33: 0x46,  # F
    34: 0x47,  # G
    35: 0x48,  # H
    36: 0x4A,  # J
    37: 0x4B,  # K
    38: 0x4C,  # L
    44: 0x5A,  # Z
    45: 0x58,  # X
    46: 0x43,  # C
    47: 0x56,  # V
    48: 0x42,  # B
    49: 0x4E,  # N
    50: 0x4D,  # M
    # Digits
    2: 0x31, 3: 0x32, 4: 0x33, 5: 0x34, 6: 0x35,
    7: 0x36, 8: 0x37, 9: 0x38, 10: 0x39, 11: 0x30,
    # Misc
    57: 0x20,  # Space
    28: 0x0D,  # Enter
    1: 0x1B,   # Escape
    15: 0x09,  # Tab
    59: 0x70, 60: 0x71, 61: 0x72, 62: 0x73,  # F1-F4
    63: 0x74, 64: 0x75, 65: 0x76, 66: 0x77,  # F5-F8
    67: 0x78, 68: 0x79, 87: 0x7A, 88: 0x7B,  # F9-F12
}

# Modifier scan codes (these should be parsed as modifiers, not main keys).
_SC_TO_MOD: dict[int, int] = {
    29: MOD_CONTROL, 285: MOD_CONTROL,   # Left/Right Ctrl
    56: MOD_ALT, 312: MOD_ALT,           # Left/Right Alt
    42: MOD_SHIFT, 54: MOD_SHIFT,        # Left/Right Shift
    91: MOD_WIN, 92: MOD_WIN,            # Left/Right Win
}


def _parse_hotkey_string(hotkey: str) -> tuple[int, int]:
    """Parse 'ctrl+alt+t' → (modifier_flags, vk_code).

    Also handles legacy 'scNN' format from old scan-code recorder.
    Returns (0, 0) on failure.
    """
    parts = [p.strip().lower() for p in (hotkey or "").split("+") if p.strip()]
    modifiers = 0
    vk = 0
    for p in parts:
        if p in _MOD_NAMES:
            modifiers |= _MOD_NAMES[p]
        elif p in _VK_MAP:
            vk = _VK_MAP[p]
        elif p.startswith("sc") and p[2:].isdigit():
            # Legacy scan-code format: "sc20" → scan code 20 → VK_T
            sc = int(p[2:])
            if sc in _SC_TO_MOD:
                modifiers |= _SC_TO_MOD[sc]
            elif sc in _SC_TO_VK:
                vk = _SC_TO_VK[sc]
            else:
                log.warning("Unknown scan code in hotkey: %r (sc=%d)", p, sc)
        else:
            log.warning("Unknown key part in hotkey: %r", p)
    log.debug("Parsed hotkey %r → modifiers=0x%04X, vk=0x%04X", hotkey, modifiers, vk)
    return (modifiers, vk)


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
        on_overlay_detail=None,
        on_download_progress=None,
    ):
        self._settings = dict(settings)
        self._on_error = on_error
        self._on_busy_start = on_busy_start
        self._on_busy_end = on_busy_end
        self._on_overlay_message = on_overlay_message
        self._on_overlay_progress = on_overlay_progress
        self._on_overlay_detail = on_overlay_detail  # callback(str) for streaming partials
        self._on_download_progress = on_download_progress
        self._run_lock = threading.Lock()

        # Windows hotkey thread state
        self._winhk_thread: threading.Thread | None = None
        self._winhk_thread_id: int | None = None
        # _winhk_registered is set once the hotkey thread finishes its RegisterHotKey call.
        self._winhk_registered = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_settings(self, settings: dict) -> None:
        """Apply new settings and re-register the hotkey."""
        self._settings = dict(settings)
        self.register()

    def register(self) -> None:
        """(Re-)register the global hotkey using Windows RegisterHotKey."""
        self.unregister()

        hotkey_str = self._settings.get("hotkey", "ctrl+alt+t")
        modifiers, vk = _parse_hotkey_string(hotkey_str)
        if not vk:
            err_msg = f"Could not parse hotkey '{hotkey_str}' — no main key found."
            log.error(err_msg)
            if self._on_error:
                self._on_error(err_msg)
            return

        self._winhk_registered = threading.Event()

        def _thread_func(mod: int, vk_code: int) -> None:
            tid = _kernel32.GetCurrentThreadId()
            self._winhk_thread_id = tid
            log.info(
                "Hotkey thread started (tid=%d). Registering hotkey mod=0x%04X vk=0x%04X ...",
                tid, mod, vk_code,
            )

            ok = _user32.RegisterHotKey(None, _HOTKEY_ID, mod | MOD_NOREPEAT, vk_code)
            if not ok:
                err = ctypes.GetLastError()
                err_msg = f"RegisterHotKey failed (WinError {err}). Hotkey may be in use."
                log.error(err_msg)
                if self._on_error:
                    self._on_error(err_msg)
                self._winhk_registered.set()
                return

            log.info("RegisterHotKey succeeded. Entering message loop.")
            self._winhk_registered.set()

            msg = ctypes.wintypes.MSG()
            # Blocking GetMessageW loop — proper Windows message pump.
            # Returns 0 on WM_QUIT, -1 on error.
            while True:
                ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    # 0 = WM_QUIT, -1 = error → exit loop
                    log.info("Hotkey message loop exiting (GetMessageW returned %d).", ret)
                    break
                if msg.message == WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                    log.debug("WM_HOTKEY received — triggering translation flow.")
                    self._on_hotkey()

            _user32.UnregisterHotKey(None, _HOTKEY_ID)
            log.info("UnregisterHotKey done.")

        self._winhk_thread = threading.Thread(
            target=_thread_func, args=(modifiers, vk), daemon=True
        )
        self._winhk_thread.start()

        # Wait until registration attempt finishes so errors are reported immediately.
        self._winhk_registered.wait(timeout=3)

    def unregister(self) -> None:
        """Remove the currently registered hotkey."""
        if self._winhk_thread is not None:
            tid = self._winhk_thread_id
            if tid is not None:
                # Post WM_QUIT to break GetMessageW loop
                log.debug("Posting WM_QUIT to hotkey thread (tid=%d).", tid)
                _user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
            self._winhk_thread.join(timeout=3)
            self._winhk_thread = None
            self._winhk_thread_id = None

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
        log.info("Hotkey triggered!")
        if not self._run_lock.acquire(blocking=False):
            log.warning("Hotkey ignored — another operation is in progress.")
            return
        threading.Thread(target=self._translate_flow, daemon=True).start()

    def _translate_flow(self) -> None:
        try:
            # 1. Save current clipboard content
            try:
                original_clipboard = pyperclip.paste()
            except Exception:
                original_clipboard = ""
            log.debug("Original clipboard: %r", original_clipboard[:80] if original_clipboard else "")

            # 2. Simulate Ctrl+C to copy selected text
            log.debug("Sending Ctrl+C...")
            _send_ctrl_c()
            time.sleep(0.25)

            # 3. Read the clipboard
            selected_text = pyperclip.paste()
            log.debug("Clipboard after Ctrl+C: %r", selected_text[:80] if selected_text else "")

            # 4. If nothing was copied (or same as before), skip
            if not selected_text or selected_text == original_clipboard:
                log.info("No new text copied — skipping translation.")
                return

            # 5. Translate via LLM (show overlay while in-flight)
            try:
                if self._on_busy_start:
                    self._on_busy_start()

                base_url = self._settings["base_url"]
                model = self._settings["model"]

                if self._is_ollama_profile():
                    self._ensure_ollama_model(base_url, model)

                last_ui_update_t = 0.0

                def on_partial(text_so_far: str) -> None:
                    nonlocal last_ui_update_t
                    if not self._on_overlay_detail:
                        return
                    now = time.time()
                    if (now - last_ui_update_t) < 0.08:
                        return
                    last_ui_update_t = now

                    tail = text_so_far[-80:].replace("\n", " ").strip()
                    detail = f"{len(text_so_far)} chars — {tail}"
                    self._on_overlay_detail(detail)

                try:
                    translated = translate(
                        text=selected_text,
                        base_url=base_url,
                        model=model,
                        source_lang=self._settings["source_lang"],
                        target_lang=self._settings["target_lang"],
                        on_partial=on_partial,
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
                            on_partial=on_partial,
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
            _send_ctrl_v()

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


# ---------------------------------------------------------------------------
# Low-level key simulation via Win32 keybd_event (layout-independent)
# ---------------------------------------------------------------------------

KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_MENU = 0x12      # Alt
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_C = 0x43
VK_V = 0x56


def _keybd_event(vk: int, flags: int = 0) -> None:
    _user32.keybd_event(vk, 0, flags, 0)


def _release_all_modifiers() -> None:
    """Release all modifier keys that may be physically held from the hotkey."""
    for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN):
        _keybd_event(vk, KEYEVENTF_KEYUP)


def _send_ctrl_c() -> None:
    _release_all_modifiers()
    time.sleep(0.05)
    _keybd_event(VK_CONTROL)
    _keybd_event(VK_C)
    _keybd_event(VK_C, KEYEVENTF_KEYUP)
    _keybd_event(VK_CONTROL, KEYEVENTF_KEYUP)


def _send_ctrl_v() -> None:
    _release_all_modifiers()
    time.sleep(0.05)
    _keybd_event(VK_CONTROL)
    _keybd_event(VK_V)
    _keybd_event(VK_V, KEYEVENTF_KEYUP)
    _keybd_event(VK_CONTROL, KEYEVENTF_KEYUP)

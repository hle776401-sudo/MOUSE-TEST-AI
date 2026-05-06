"""
context_manager.py - Context-Aware Gesture Engine: Window Context Detector
===========================================================================
Phat hien cua so dang active tren Windows va phan loai thanh context chuan:
  browser | presentation | document | media | default

Chi DETECT context, khong route action, khong goi pyautogui.
Duoc thiet ke de goi moi frame ma khong block camera loop (co cache/throttle).
"""

import ctypes
import ctypes.wintypes
import time
from typing import Optional

import config


# ---------------------------------------------------------------------------
# Windows API setup (khong can dependency ngoai)
# ---------------------------------------------------------------------------
_user32 = ctypes.windll.user32  # type: ignore[attr-defined]


def _get_foreground_window_title() -> str:
    """Lay title cua so dang active bang Windows API (ctypes).

    Returns:
        Title cua so active, hoac chuoi rong neu loi.
    """
    hwnd: Optional[int] = _user32.GetForegroundWindow()
    if not hwnd:
        return ""

    # GetWindowTextLengthW tra ve so ky tu (khong tinh null terminator)
    length: int = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""

    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


# ---------------------------------------------------------------------------
# ContextManager
# ---------------------------------------------------------------------------

# Thu tu uu tien classify (cao -> thap)
_PRIORITY_ORDER = ["presentation", "document", "media", "browser"]

# Map context -> keyword list (lay tu config)
_KEYWORD_MAP: dict[str, list[str]] = {
    "presentation": config.CONTEXT_PRESENTATION_KEYWORDS,
    "document":     config.CONTEXT_DOCUMENT_KEYWORDS,
    "media":        config.CONTEXT_MEDIA_KEYWORDS,
    "browser":      config.CONTEXT_BROWSER_KEYWORDS,
}

# Label hien thi ngan tren HUD
_DISPLAY_LABEL: dict[str, str] = {
    "browser":      "Browser",
    "presentation": "Presentation",
    "document":     "Document",
    "media":        "Media",
    "default":      "Default",
}


class ContextManager:
    """Phat hien va phan loai context cua so dang active.

    Attributes:
        _context:       Context hien tai ("browser" | "presentation" |
                        "document" | "media" | "default").
        _window_title:  Title cua so lay lan cuoi.
        _last_update:   Thoi diem cap nhat cuoi (time.monotonic).
    """

    def __init__(self) -> None:
        self._context: str = "default"
        self._window_title: str = ""
        self._last_update: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self) -> None:
        """Cap nhat context neu da het CONTEXT_CACHE_INTERVAL.

        Goi moi frame; thuc su query Windows API theo chu ky cache.
        Khong throw exception ra ngoai — moi loi duoc xu ly noi bo.
        """
        if not config.ENABLE_CONTEXT_AWARE:
            # Feature tat: giu default, khong lam gi them
            self._context = "default"
            return

        now = time.monotonic()
        if now - self._last_update < config.CONTEXT_CACHE_INTERVAL:
            return  # Chua het chu ky cache, giu ket qua cu

        self._last_update = now
        self._refresh()

    def get_current_context(self) -> str:
        """Tra ve context hien tai.

        Returns:
            Mot trong: "browser" | "presentation" | "document" |
            "media" | "default".
        """
        return self._context

    def get_current_window_title(self) -> str:
        """Tra ve title cua so active lan cap nhat gan nhat.

        Returns:
            Title string, hoac chuoi rong neu chua lay duoc.
        """
        return self._window_title

    def classify_window(self, title: str) -> str:
        """Phan loai title cua so thanh context chuan.

        Thu tu uu tien: presentation > document > media > browser > default.
        So sanh case-insensitive.

        Args:
            title: Title cua so can phan loai.

        Returns:
            Context string chuan.
        """
        title_lower = title.lower()
        for ctx in _PRIORITY_ORDER:
            keywords = _KEYWORD_MAP.get(ctx, [])
            for kw in keywords:
                if kw.lower() in title_lower:
                    return ctx
        return "default"

    def get_context_display(self) -> str:
        """Tra ve chuoi hien thi ngan cho HUD overlay.

        Returns:
            Vi du: "CTX: Presentation", "CTX: Default"
        """
        label = _DISPLAY_LABEL.get(self._context, self._context.capitalize())
        return f"CTX: {label}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Thuc hien query Windows API va cap nhat context."""
        try:
            title = _get_foreground_window_title()
        except Exception:
            # Bao ve: neu Windows API loi (UAC window, v.v.) -> fallback
            title = ""

        self._window_title = title

        if not title:
            self._context = "default"
            return

        self._context = self.classify_window(title)


# ---------------------------------------------------------------------------
# Quick test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("ContextManager - Quick Test")
    print(f"  ENABLE_CONTEXT_AWARE   = {config.ENABLE_CONTEXT_AWARE}")
    print(f"  CONTEXT_CACHE_INTERVAL = {config.CONTEXT_CACHE_INTERVAL}s")
    print("=" * 60)
    print("Bam Ctrl+C de thoat.\n")

    mgr = ContextManager()

    try:
        while True:
            mgr.update()
            title   = mgr.get_current_window_title()
            context = mgr.get_current_context()
            display = mgr.get_context_display()

            print(f"[{time.strftime('%H:%M:%S')}]  {display:<22}  | Title: {title[:80]!r}")
            time.sleep(config.CONTEXT_CACHE_INTERVAL)
    except KeyboardInterrupt:
        print("\nDone.")

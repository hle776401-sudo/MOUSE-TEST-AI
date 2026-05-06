"""
action_router.py - Context-Aware Gesture Engine: Action Router
==============================================================
Anh xa gesture_name + context -> action_name.

Khong execute action, khong goi pyautogui.
MouseController (tang sau) moi thuc hien hanh dong that.

Pipeline:
    gesture_name  ->  normalize  ->  resolve context  ->  lookup table  ->  action_name
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import config

if TYPE_CHECKING:
    from context_manager import ContextManager


# ---------------------------------------------------------------------------
# Routing table: ACTION_TABLE[gesture][context] = action_name
# ---------------------------------------------------------------------------

ACTION_TABLE: dict[str, dict[str, str]] = {
    "swipe_left": {
        "browser":      "browser_forward",
        "presentation": "next_slide",
        "document":     "page_down",
        "media":        "next_track",
        "default":      "default_swipe_left",
    },
    "swipe_right": {
        "browser":      "browser_back",
        "presentation": "previous_slide",
        "document":     "page_up",
        "media":        "previous_track",
        "default":      "default_swipe_right",
    },
    "zoom_in": {
        "browser":      "browser_zoom_in",
        "presentation": "presentation_zoom_in",
        "document":     "document_zoom_in",
        "media":        "volume_up",
        "default":      "default_zoom_in",
    },
    "zoom_out": {
        "browser":      "browser_zoom_out",
        "presentation": "presentation_zoom_out",
        "document":     "document_zoom_out",
        "media":        "volume_down",
        "default":      "default_zoom_out",
    },
}

# SWIPE_MODE string -> context string
_SWIPE_MODE_MAP: dict[str, str] = {
    "slide":   "presentation",
    "pdf":     "document",
    "image":   "document",
    "browser": "browser",
}

# Gesture display name -> normalized snake_case
_GESTURE_NORMALIZE_MAP: dict[str, str] = {
    "swipe left":  "swipe_left",
    "swipe right": "swipe_right",
    "zoom in":     "zoom_in",
    "zoom out":    "zoom_out",
}

_VALID_CONTEXTS = frozenset(ACTION_TABLE["swipe_left"].keys())  # browser/presentation/document/media/default
_SWIPE_GESTURES = frozenset({"swipe_left", "swipe_right"})


# ---------------------------------------------------------------------------
# ActionRouter
# ---------------------------------------------------------------------------

class ActionRouter:
    """Anh xa (gesture_name, context) -> action_name.

    Khong phu thuoc pyautogui. Chi thuc hien logic routing.

    Args:
        context_manager: Instance cua ContextManager (tuy chon).
                         Neu None, context lay tu config.CONTEXT_MODE
                         hoac fallback "default".
    """

    def __init__(self, context_manager: Optional["ContextManager"] = None) -> None:
        self._context_manager = context_manager
        self._last_action: str = "no_action"
        self._last_context: str = "default"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, gesture_name: str) -> str:
        """Giai quyet gesture -> action_name day du.

        Args:
            gesture_name: Ten gesture (raw hoac normalized).

        Returns:
            action_name string. Tra "no_action" neu gesture khong ho tro.
        """
        norm = self.normalize_gesture_name(gesture_name)
        if norm not in ACTION_TABLE:
            self._last_action = "no_action"
            self._last_context = "default"
            return "no_action"

        ctx = self.get_effective_context(norm)
        self._last_context = ctx

        # Lookup voi fallback ve "default" neu context la, theo nao do
        gesture_map = ACTION_TABLE[norm]
        action = gesture_map.get(ctx) or gesture_map.get("default", "no_action")

        self._last_action = action
        return action

    def get_effective_context(self, gesture_name: str) -> str:
        """Tinh context thuc su can dung cho gesture nay.

        Ap dung theo thu tu uu tien:
        1. SWIPE_MODE override (chi cho swipe gesture)
        2. CONTEXT_MODE override (neu != "auto")
        3. Context thuc tu ContextManager
        4. Fallback "default"

        Args:
            gesture_name: Gesture da duoc normalize.

        Returns:
            Context string chuan.
        """
        # --- Lay context nen tu ContextManager ---
        real_ctx = self._get_real_context()

        # --- SWIPE_MODE override (chi cho swipe, khong anh huong zoom) ---
        if gesture_name in _SWIPE_GESTURES:
            swipe_mode = getattr(config, "SWIPE_MODE", "auto")
            if swipe_mode != "auto" and swipe_mode in _SWIPE_MODE_MAP:
                return _SWIPE_MODE_MAP[swipe_mode]

        # --- CONTEXT_MODE override (anh huong tat ca gesture) ---
        ctx_mode = getattr(config, "CONTEXT_MODE", "auto")
        if ctx_mode != "auto":
            if ctx_mode in _VALID_CONTEXTS:
                return ctx_mode
            # Gia tri khong hop le: dung context thuc, khong crash

        return real_ctx

    def normalize_gesture_name(self, gesture_name: str) -> str:
        """Chuan hoa ten gesture ve dang snake_case.

        Vi du:
            "Swipe Left" -> "swipe_left"
            "swipe_left" -> "swipe_left"
            "Zoom In"    -> "zoom_in"

        Args:
            gesture_name: Ten gesture raw.

        Returns:
            Ten gesture normalized, hoac chuoi goc lowercase neu khong khop.
        """
        lowered = gesture_name.strip().lower()
        # Thu map tu bang tra cuu truoc
        if lowered in _GESTURE_NORMALIZE_MAP:
            return _GESTURE_NORMALIZE_MAP[lowered]
        # Neu da la snake_case hop le hoac dang khac, tra ve lowercase
        return lowered

    def get_last_action(self) -> str:
        """Tra ve action_name tu lan resolve() gan nhat."""
        return self._last_action

    def get_last_context(self) -> str:
        """Tra ve context da duoc su dung trong lan resolve() gan nhat."""
        return self._last_context

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_real_context(self) -> str:
        """Lay context thuc tu ContextManager (neu co) hoac fallback "default"."""
        if self._context_manager is not None:
            try:
                ctx = self._context_manager.get_current_context()
                if ctx in _VALID_CONTEXTS:
                    return ctx
            except Exception:
                pass
        return "default"


# ---------------------------------------------------------------------------
# Quick test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 65)
    print("ActionRouter - Quick Test (route table verification)")
    print(f"  CONTEXT_MODE = {getattr(config, 'CONTEXT_MODE', 'auto')!r}")
    print(f"  SWIPE_MODE   = {getattr(config, 'SWIPE_MODE', 'auto')!r}")
    print("=" * 65)

    router = ActionRouter(context_manager=None)  # Khong can ContextManager de test

    gestures_raw = ["Swipe Left", "Swipe Right", "Zoom In", "Zoom Out", "swipe_left", "zoom_out", "unknown_gesture"]
    contexts_to_test = ["browser", "presentation", "document", "media", "default"]

    # --- Kiem tra normalize ---
    print("\n[1] Normalize test:")
    for g in gestures_raw:
        print(f"  {g!r:20s} -> {router.normalize_gesture_name(g)!r}")

    # --- Full routing table ---
    print("\n[2] Route table (CONTEXT_MODE=auto, no ContextManager -> all default):")
    header = f"  {'Gesture':<18} {'Context':<16} {'Action'}"
    print(header)
    print("  " + "-" * 55)

    for ctx in contexts_to_test:
        # Gia lap context bang cach monkey-patch _get_real_context
        router._context_manager = type("_Fake", (), {"get_current_context": lambda self, c=ctx: c})()
        for g in ["Swipe Left", "Swipe Right", "Zoom In", "Zoom Out"]:
            norm = router.normalize_gesture_name(g)
            action = router.resolve(g)
            print(f"  {norm:<18} {ctx:<16} {action}")
        print()

    # --- Test fallback ---
    router._context_manager = None
    print("[3] Fallback test (unsupported gesture):")
    print(f"  resolve('unknown') -> {router.resolve('unknown')!r}")
    print(f"  get_last_action()  -> {router.get_last_action()!r}")
    print(f"  get_last_context() -> {router.get_last_context()!r}")

    print("\nDone.")

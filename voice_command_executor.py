"""
voice_command_executor.py - Thuc thi Voice Command theo whitelist
=================================================================
Nhan intent dict tu voice_intent.py va thuc thi hanh dong tuong ung.

Thiet ke:
- Chi thuc thi intent trong whitelist da dinh nghia.
- Khong chay shell command tu do tu input user.
- dry_run=True: chi print, khong mo app/url that.
- system_on/off: dua vao callback inject tu ngoai vao (tay voi main.py sau).
- Moi loi duoc catch noi bo, khong crash app chinh.

Dependency: chi dung built-in (webbrowser, subprocess, pathlib, urllib.parse, os).
"""

import os
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import pyautogui


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Whitelist intent duoc phep execute
_INTENT_WHITELIST = {
    "open_youtube",
    "open_music",
    "web_search",
    "open_word",
    "open_chrome",
    "open_coccoc",
    "system_on",
    "system_off",
    "next_action",
    "previous_action",
    "newline",
    "new_paragraph",
}

# Whitelist an toan cho demo (VOICE_DEMO_SAFE_MODE = True)
_DEMO_SAFE_WHITELIST = {
    "next_action",
    "previous_action",
    "web_search",
    "system_on",
    "system_off",
    "open_word",
    "newline",
    "new_paragraph",
}

# Common paths cho Chrome tren Windows
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
]

# Common paths cho Coc Coc tren Windows
_COCCOC_PATHS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"CocCoc\Browser\Application\browser.exe"),
    r"C:\Program Files\CocCoc\Browser\Application\browser.exe",
    r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe",
]


# ==============================================================================
# EXECUTOR
# ==============================================================================

class VoiceCommandExecutor:
    """Thuc thi intent dict tu VoiceIntentParser theo whitelist.

    Attributes:
        dry_run:             Neu True, chi print log, khong mo app/url that.
        system_on_callback:  Callable() duoc goi khi intent=system_on.
        system_off_callback: Callable() duoc goi khi intent=system_off.
    """

    def __init__(
        self,
        dry_run: bool = False,
        system_on_callback=None,
        system_off_callback=None,
        context_getter=None,
        demo_safe_mode: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.system_on_callback  = system_on_callback
        self.system_off_callback = system_off_callback
        self.context_getter      = context_getter       # callable() -> str (context)
        self.demo_safe_mode      = demo_safe_mode       # True = chi cho phep safe whitelist
        self.last_context        = "default"             # Context su dung lan execute gan nhat

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, intent: dict) -> bool:
        """Thuc thi intent dict.

        Args:
            intent: Dict tra ve boi VoiceIntentParser.parse().

        Returns:
            True neu thuc thi thanh cong (hoac dry_run+valid).
            False neu bo qua (type=text, khong whitelist, loi).
        """
        if not intent or intent.get("type") != "command":
            return False

        intent_name = intent.get("intent", "")
        query       = intent.get("query", "")

        if intent_name not in _INTENT_WHITELIST:
            print(f"[VOICE_CMD] Intent '{intent_name}' not in whitelist — skipped.")
            return False

        # Demo safe mode: chi cho phep intent an toan
        if self.demo_safe_mode and intent_name not in _DEMO_SAFE_WHITELIST:
            print(f"[VOICE_CMD] Intent '{intent_name}' blocked by VOICE_DEMO_SAFE_MODE.")
            return False

        # Validate query bat buoc truoc khi dispatch (nhat quan ca dry_run va real mode)
        _NEEDS_QUERY = {"open_music", "web_search"}
        if intent_name in _NEEDS_QUERY and not query:
            print(f"[VOICE_CMD] {intent_name}: query rong — skipped.")
            return False

        if self.dry_run:
            action_desc = self._describe(intent_name, query)
            print(f"[VOICE_CMD][DRY_RUN] intent={intent_name}  action={action_desc}")
            return True

        # --- Dispatch ---
        dispatch = {
            "open_youtube": self._open_youtube,
            "open_music":   lambda: self._open_music(query),
            "web_search":   lambda: self._web_search(query),
            "open_word":    self._open_word,
            "open_chrome":  self._open_chrome,
            "open_coccoc":  self._open_coccoc,
            "system_on":    self._system_on,
            "system_off":   self._system_off,
            "next_action":  self._next_action,
            "previous_action": self._previous_action,
            "newline":      self._newline,
            "new_paragraph": self._new_paragraph,
        }
        handler = dispatch.get(intent_name)
        if handler is None:
            return False
        return handler()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _open_youtube(self) -> bool:
        """Mo YouTube homepage."""
        return self._open_url("https://www.youtube.com")

    def _open_music(self, query: str) -> bool:
        """Mo YouTube search cho query."""
        if not query:
            print("[VOICE_CMD] open_music: query rong — skipped.")
            return False
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        return self._open_url(url)

    def _web_search(self, query: str) -> bool:
        """Mo Google search cho query."""
        if not query:
            print("[VOICE_CMD] web_search: query rong — skipped.")
            return False
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        return self._open_url(url)

    def _open_word(self) -> bool:
        """Mo Microsoft Word."""
        # Thu lenh 'winword' qua cmd start (tim trong PATH va registry)
        if self._try_popen(["cmd", "/c", "start", "", "winword"]):
            return True
        # Thu cac path cung ten pho bien
        word_paths = [
            # Office 365 / 2019 / 2016 (x64)
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
            # Office (x86)
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Office\Office16\WINWORD.EXE",
        ]
        for p in word_paths:
            if Path(p).exists():
                if self._try_popen([p]):
                    return True
        print("[VOICE_CMD] open_word: Khong tim thay Microsoft Word.")
        return False

    def _open_chrome(self) -> bool:
        """Mo Google Chrome."""
        # Thu lenh 'chrome' trong PATH truoc
        if self._try_popen(["chrome"]):
            return True
        for p in _CHROME_PATHS:
            exp = self._expand_env_path(p)
            if Path(exp).exists():
                if self._try_popen([exp]):
                    return True
        print("[VOICE_CMD] open_chrome: Khong tim thay Google Chrome.")
        return False

    def _open_coccoc(self) -> bool:
        """Mo Coc Coc Browser."""
        for p in _COCCOC_PATHS:
            exp = self._expand_env_path(p)
            if Path(exp).exists():
                if self._try_popen([exp]):
                    return True
        print("[VOICE_CMD] open_coccoc: Khong tim thay Coc Coc.")
        return False

    def _system_on(self) -> bool:
        """Bat he thong qua callback."""
        if self.system_on_callback is not None:
            try:
                self.system_on_callback()
                print("[VOICE_CMD] system_on: callback da duoc goi.")
                return True
            except Exception as e:
                print(f"[VOICE_CMD] system_on callback error: {e}")
                return False
        print("[VOICE_CMD] system_on: chua co callback — skipped.")
        return False

    def _system_off(self) -> bool:
        """Tat he thong qua callback."""
        if self.system_off_callback is not None:
            try:
                self.system_off_callback()
                print("[VOICE_CMD] system_off: callback da duoc goi.")
                return True
            except Exception as e:
                print(f"[VOICE_CMD] system_off callback error: {e}")
                return False
        print("[VOICE_CMD] system_off: chua co callback — skipped.")
        return False

    def _get_context(self) -> str:
        """Lay context hien tai tu context_getter callback."""
        if self.context_getter is not None:
            try:
                ctx = self.context_getter()
                if ctx:
                    self.last_context = ctx
                    return ctx
            except Exception:
                pass
        self.last_context = "default"
        return "default"

    def _next_action(self) -> bool:
        """Chuyen tiep / next — xu ly theo context."""
        ctx = self._get_context()
        try:
            if ctx == "presentation":
                pyautogui.press("right")
                print(f"[VOICE_CMD] next_action: press right (presentation)")
            elif ctx == "browser":
                pyautogui.hotkey("alt", "right")
                print(f"[VOICE_CMD] next_action: alt+right (browser forward)")
            elif ctx == "document":
                pyautogui.press("pagedown")
                print(f"[VOICE_CMD] next_action: pagedown (document)")
            else:
                pyautogui.press("right")
                print(f"[VOICE_CMD] next_action: press right (default)")
            return True
        except Exception as e:
            print(f"[VOICE_CMD] next_action error: {e}")
            return False

    def _previous_action(self) -> bool:
        """Quay lai / previous — xu ly theo context."""
        ctx = self._get_context()
        try:
            if ctx == "presentation":
                pyautogui.press("left")
                print(f"[VOICE_CMD] previous_action: press left (presentation)")
            elif ctx == "browser":
                pyautogui.hotkey("alt", "left")
                print(f"[VOICE_CMD] previous_action: alt+left (browser back)")
            elif ctx == "document":
                pyautogui.press("pageup")
                print(f"[VOICE_CMD] previous_action: pageup (document)")
            else:
                pyautogui.press("left")
                print(f"[VOICE_CMD] previous_action: press left (default)")
            return True
        except Exception as e:
            print(f"[VOICE_CMD] previous_action error: {e}")
            return False

    def _newline(self) -> bool:
        """Xuong dong — press Enter 1 lan."""
        try:
            pyautogui.press("enter")
            print("[VOICE_CMD] newline: press enter")
            return True
        except Exception as e:
            print(f"[VOICE_CMD] newline error: {e}")
            return False

    def _new_paragraph(self) -> bool:
        """Xuong doan — press Enter 2 lan."""
        try:
            pyautogui.press("enter")
            pyautogui.press("enter")
            print("[VOICE_CMD] new_paragraph: press enter x2")
            return True
        except Exception as e:
            print(f"[VOICE_CMD] new_paragraph error: {e}")
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _open_url(self, url: str) -> bool:
        """Mo URL bang webbrowser.open().

        Args:
            url: URL hop le.

        Returns:
            True neu webbrowser bao thanh cong.
        """
        try:
            result = webbrowser.open(url)
            if result:
                print(f"[VOICE_CMD] Opened URL: {url}")
            else:
                print(f"[VOICE_CMD] webbrowser.open returned False for: {url}")
            return bool(result)
        except Exception as e:
            print(f"[VOICE_CMD] _open_url error: {e}")
            return False

    @staticmethod
    def _try_popen(cmd: list) -> bool:
        """Chay lenh bang subprocess.Popen.

        Khong doi ket qua — chi khoi dong process.
        Catch moi loi (FileNotFoundError, PermissionError...).

        Args:
            cmd: List lenh va tham so.

        Returns:
            True neu Popen khong raise exception.
        """
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return True
        except (FileNotFoundError, PermissionError, OSError):
            return False
        except Exception as e:
            print(f"[VOICE_CMD] _try_popen unexpected error: {e}")
            return False

    @staticmethod
    def _expand_env_path(path: str) -> str:
        """Mo rong bien moi truong trong path.

        Vi du: '%LOCALAPPDATA%\\CocCoc\\...' -> duong dan that.

        Args:
            path: Path co the chua bien moi truong Windows.

        Returns:
            Path da duoc expand.
        """
        return os.path.expandvars(path)

    @staticmethod
    def _describe(intent_name: str, query: str) -> str:
        """Tao mo ta ngan cho dry_run log."""
        if intent_name == "open_youtube":
            return "open https://www.youtube.com"
        if intent_name == "open_music":
            return f"open youtube search: {repr(query)}"
        if intent_name == "web_search":
            return f"google search: {repr(query)}"
        if intent_name == "open_word":
            return "launch Microsoft Word"
        if intent_name == "open_chrome":
            return "launch Google Chrome"
        if intent_name == "open_coccoc":
            return "launch Coc Coc Browser"
        if intent_name == "system_on":
            return "call system_on_callback()"
        if intent_name == "system_off":
            return "call system_off_callback()"
        if intent_name == "next_action":
            return "context-aware next (right/alt+right/pagedown)"
        if intent_name == "previous_action":
            return "context-aware previous (left/alt+left/pageup)"
        if intent_name == "newline":
            return "press enter (xuong dong)"
        if intent_name == "new_paragraph":
            return "press enter x2 (xuong doan)"
        return f"execute {intent_name}"


# ==============================================================================
# MODULE-LEVEL SHORTCUT
# ==============================================================================

def execute_intent(
    intent: dict,
    dry_run: bool = False,
    system_on_callback=None,
    system_off_callback=None,
) -> bool:
    """Module-level shortcut.

    Args:
        intent:              Dict tu VoiceIntentParser.parse().
        dry_run:             Neu True, khong mo app/url that.
        system_on_callback:  Callable() cho system_on.
        system_off_callback: Callable() cho system_off.

    Returns:
        True neu thuc thi thanh cong.
    """
    executor = VoiceCommandExecutor(
        dry_run=dry_run,
        system_on_callback=system_on_callback,
        system_off_callback=system_off_callback,
    )
    return executor.execute(intent)


# ==============================================================================
# QUICK TEST
# ==============================================================================

if __name__ == "__main__":
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    def _make_command(intent_name: str, query: str = "", raw: str = "") -> dict:
        return {
            "type":            "command",
            "intent":          intent_name,
            "query":           query,
            "raw_text":        raw or intent_name,
            "normalized_text": intent_name,
        }

    def _make_text(text: str) -> dict:
        return {
            "type":            "text",
            "intent":          "type_text",
            "text":            text,
            "raw_text":        text,
            "normalized_text": text.lower(),
        }

    # Callback mau cho system_on/off
    def _on_system_on():
        print("  [CALLBACK] he_thong = ON")

    def _on_system_off():
        print("  [CALLBACK] he_thong = OFF")

    executor = VoiceCommandExecutor(
        dry_run=True,
        system_on_callback=_on_system_on,
        system_off_callback=_on_system_off,
    )

    TEST_INTENTS = [
        ("open_youtube",  _make_command("open_youtube")),
        ("open_music",    _make_command("open_music", query="Son Tung MTP", raw="mo nhac Son Tung MTP")),
        ("web_search",    _make_command("web_search", query="tri tue nhan tao", raw="tim kiem tri tue nhan tao")),
        ("open_word",     _make_command("open_word")),
        ("open_chrome",   _make_command("open_chrome")),
        ("open_coccoc",   _make_command("open_coccoc")),
        ("system_on",     _make_command("system_on")),
        ("system_off",    _make_command("system_off")),
        ("invalid intent",_make_command("open_tiktok")),    # khong whitelist -> False
        ("text intent",   _make_text("xin chao thay co")), # type=text -> False
        ("open_music no query", _make_command("open_music", query="")),  # -> False
    ]

    print("=" * 65)
    print("  VoiceCommandExecutor - Quick Test (dry_run=True)")
    print("=" * 65)

    for label, intent_dict in TEST_INTENTS:
        print(f"\n--- {label} ---")
        result = executor.execute(intent_dict)
        print(f"    => execute() returned: {result}")

    print("\n" + "=" * 65)
    print("Done. (Khong mo app/URL that vi dry_run=True)")

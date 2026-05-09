"""
voice_intent.py - Rule-based Voice Intent Parser
=================================================
Phan tich text tu gong noi -> dict intent de Voice Command Mode xu ly.

Thiet ke:
- Khong dung LLM/API, khong dependency ngoai.
- Ho tro tieng Viet co dau va khong dau.
- raw_text giu nguyen input goc (co dau).
- normalized_text dung de match command (thuong + khong dau + gop khoang trang).
- Neu khong match bat ky command nao -> fallback ve "text" mode.
- Neu command can query (open_music, web_search) ma query rong -> fallback ve "text".

Output dict:
  - type:            "text" | "command"
  - intent:          "type_text" | <intent_name>
  - text:            original text (chi o type=text)
  - query:           query string co dau neu co (chi o type=command)
  - raw_text:        original text (luon co)
  - normalized_text: da chuan hoa (luon co)

Tro choi vai:  Module phu tro khong thay the text typing mode hien tai.
"""

import re
import unicodedata


# ==============================================================================
# NORMALIZE
# ==============================================================================

def normalize_text(text: str) -> str:
    """Chuan hoa text de match command.

    Cac buoc:
      1. Strip khoang trang hai dau.
      2. Lowercase.
      3. Chuyen 'đ' -> 'd' (NFD khong xu ly duoc ky tu nay).
      4. Gom nhieu khoang trang thanh 1.
      5. Bo dau tieng Viet con lai (NFD -> strip combining marks).

    Args:
        text: Chuoi input bat ky.

    Returns:
        Chuoi da chuan hoa, khong dau, thuong, gon.
    """
    if not text:
        return ""
    text = text.strip().lower()
    # 'đ' khong duoc NFD decompose thanh 'd' + combining mark
    # -> phai xu ly thu cong truoc khi NFD
    text = text.replace("đ", "d")
    # Gop khoang trang
    text = re.sub(r"\s+", " ", text)
    # Bo dau unicode (NFD decompose -> loai Mn category)
    nfd = unicodedata.normalize("NFD", text)
    ascii_text = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return ascii_text


# ==============================================================================
# INTENT RULES
# ==============================================================================
# Moi rule la 1 tuple:
#   (intent_name, [prefix_patterns], needs_query)
#
# prefix_patterns: list cac prefix (da normalize) can khop voi dau normalized_text.
# needs_query:     True  -> chi chap nhan norm.startswith(prefix + " ") voi query khac rong.
#                  False -> chi chap nhan norm == prefix (exact match).
#                           Neu co them chu sau prefix -> fallback text (tranh nhan nhau).
#
# Thu tu quan trong: pattern dai hon phai kiem tra truoc neu co chong chep.

_INTENT_RULES: list[tuple[str, list[str], bool]] = [
    # --- open_youtube ---
    ("open_youtube",    ["mo youtube", "mo web youtube"], False),

    # --- open_word ---
    ("open_word",       ["mo word", "mo microsoft word"], False),

    # --- open_chrome ---
    ("open_chrome",     ["mo chrome", "mo google chrome"], False),

    # --- open_coccoc ---
    ("open_coccoc",     ["mo coc coc"], False),

    # --- open_music (needs_query=True) ---
    # 'mo bai' bi bo vi de nhan nhau: 'mo bai tap', 'mo bai bao cao'...
    ("open_music",      ["mo nhac", "mo bai hat"], True),

    # --- web_search (needs_query=True) ---
    ("web_search",      ["tim kiem", "tra cuu", "search", "google"], True),

    # --- system_on ---
    ("system_on",       ["bat he thong", "bat dieu khien", "mo he thong"], False),

    # --- system_off ---
    # Giu dang da normalize (khong dau); 'tắt he thong' bi bo vi chua normalize dung.
    ("system_off",      ["tat he thong", "tat dieu khien"], False),
]


# ==============================================================================
# PARSER
# ==============================================================================

class VoiceIntentParser:
    """Rule-based parser: text -> intent dict.

    Khong co trang thai (stateless). Co the goi parse() nhieu lan.
    """

    def parse(self, text: str) -> dict:
        """Phan tich text noi va tra ve intent dict.

        Args:
            text: Chuoi van ban tu gong noi (co the co dau hoac khong dau).

        Returns:
            dict voi cac key:
              - type:            "text" | "command"
              - intent:          "type_text" | <intent_name>
              - text:            original text (chi co khi type="text")
              - query:           query string goc co dau (chi co khi type="command")
              - raw_text:        input goc
              - normalized_text: da chuan hoa
        """
        raw = text.strip() if text else ""
        norm = normalize_text(raw)

        if not norm:
            return self._text_result(raw, norm)

        # Chay qua tung rule theo thu tu
        for intent_name, prefixes, needs_query in _INTENT_RULES:
            for prefix in prefixes:
                if norm == prefix:
                    # Khop chinh xac
                    if needs_query:
                        # Khong co query -> fallback text
                        return self._text_result(raw, norm)
                    return self._command_result(intent_name, "", raw, norm)

                if norm.startswith(prefix + " "):
                    if needs_query:
                        # Prefix match + needs_query: lay query, tra command.
                        norm_query = norm[len(prefix):].strip()
                        if not norm_query:
                            return self._text_result(raw, norm)
                        raw_query = self._extract_raw_query(raw, prefix)
                        return self._command_result(intent_name, raw_query, raw, norm)
                    else:
                        # Prefix match + NO query: tu choi, fallback text.
                        # Tranh nhan nhau: "mo word bai bao cao" != open_word.
                        return self._text_result(raw, norm)

        # Khong match bat ky command nao -> text mode
        return self._text_result(raw, norm)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_raw_query(raw_text: str, norm_prefix: str) -> str:
        """Lay phan query giu nguyen dau tu raw_text.

        Vi du:
          raw_text   = "Mo nhac Son Tung MTP"  hoac  "mo nhạc Sơn Tùng MTP"
          norm_prefix = "mo nhac"
          -> phan con lai raw = "Son Tung MTP" hoac "Sơn Tùng MTP"

        Thuat toan:
          Chia raw_text thanh cac token, so voi so token trong norm_prefix
          -> bo phan prefix, giu phan con lai.
        """
        prefix_token_count = len(norm_prefix.split())
        raw_tokens = raw_text.strip().split()
        if len(raw_tokens) <= prefix_token_count:
            return ""
        return " ".join(raw_tokens[prefix_token_count:])

    @staticmethod
    def _text_result(raw: str, norm: str) -> dict:
        return {
            "type":            "text",
            "intent":          "type_text",
            "text":            raw,
            "raw_text":        raw,
            "normalized_text": norm,
        }

    @staticmethod
    def _command_result(intent: str, query: str, raw: str, norm: str) -> dict:
        return {
            "type":            "command",
            "intent":          intent,
            "query":           query,
            "raw_text":        raw,
            "normalized_text": norm,
        }


# ==============================================================================
# MODULE-LEVEL SHORTCUT
# ==============================================================================

_parser = VoiceIntentParser()


def parse_intent(text: str) -> dict:
    """Module-level shortcut: parse_intent(text) thay vi phai tao instance.

    Args:
        text: Chuoi van ban tu gong noi.

    Returns:
        Intent dict (xem VoiceIntentParser.parse).
    """
    return _parser.parse(text)


# ==============================================================================
# QUICK TEST
# ==============================================================================

if __name__ == "__main__":
    import sys as _sys
    # Reconfigure stdout to UTF-8 de in tieng Viet tren Windows terminal
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    TEST_CASES = [
        "mo youtube",
        "Mo YouTube",
        "mo nhac Son Tung MTP",
        "mo nhạc Sơn Tùng MTP",
        "mo bai hat Chung ta cua tuong lai",
        "mo bài hát Chúng ta của tương lai",
        "tim kiem tri tue nhan tao",
        "tìm kiếm trí tuệ nhân tạo",
        "mo word",
        "mo chrome",
        "mo coc coc",
        "bat he thong",
        "tat he thong",
        "xin chao thay co em xin trinh bay do an",
        "xin chào thầy cô em xin trình bày đồ án",
        # Edge: needs_query nhung khong co query -> fallback text
        "mo nhac",
        "tim kiem",
        # Edge: rong
        "",
        # --- Regression: exact-only commands khong duoc prefix match ---
        "mo word bai bao cao cua toi",      # -> text (khong phai open_word)
        "mo youtube la mot vi du",           # -> text (khong phai open_youtube)
        "bat he thong nay",                 # -> text (khong phai system_on)
        # --- open_music van prefix match khi co query ---
        "mo bai hat Chung ta cua tuong lai",  # -> open_music OK
        "mo nhac Son Tung MTP",               # -> open_music OK
        # --- 'mo bai tap' khong con nhan nhau do da bo 'mo bai' ---
        "mo bai tap",                          # -> text
        # --- Fix: 'đ' -> 'd' trong normalize, test tieng Viet co dau ---
        "bật điều khiển",    # -> system_on
        "tắt điều khiển",    # -> system_off
        "bật hệ thống",      # -> system_on
        "tắt hệ thống",      # -> system_off
        "điều khiển",        # -> type_text (cau don, khong match command)
        "mở điều khiển",     # -> type_text (prefix 'mo dieu khien' khong co trong rules)
    ]

    parser = VoiceIntentParser()

    print("=" * 65)
    print("  VoiceIntentParser - Quick Test")
    print("=" * 65)

    for i, tc in enumerate(TEST_CASES, 1):
        result = parser.parse(tc)
        t = result["type"]
        intent = result["intent"]
        label = f"[{t.upper():<7}] {intent}"

        if t == "command":
            q = result.get("query", "")
            extra = f"  query={repr(q)}" if q else ""
        else:
            extra = f"  text={repr(result['text'][:40])}" if result["text"] else ""

        print(f"{i:>2}. input={repr(tc)[:45]:<47}")
        print(f"    {label}{extra}")
        print(f"    norm={repr(result['normalized_text'])}")
        print()

    print("=" * 65)
    print("Done.")

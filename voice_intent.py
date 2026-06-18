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

Pipeline:
  1. Normalize text (lower, strip dau, bo punctuation)
  2. Exact / prefix match (original rules)
  3. Fuzzy alias match (STT misrecognition corrections)
  4. Keyword fallback (partial captures)
  5. Single-word match (khi STT chi nghe duoc 1 tu)
  6. Fallback to type_text

Output dict:
  - type:            "text" | "command"
  - intent:          "type_text" | <intent_name>
  - text:            original text (chi o type=text)
  - query:           query string co dau neu co (chi o type=command)
  - raw_text:        original text (luon co)
  - normalized_text: da chuan hoa (luon co)
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
      4. Bo dau cau thuong gap (.,;:!?-).
      5. Gom nhieu khoang trang thanh 1.
      6. Bo dau tieng Viet con lai (NFD -> strip combining marks).

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
    # Bo dau cau thuong gap (STT doi khi tra ve dau cham, phay...)
    text = re.sub(r"[.,;:!?\-–—\(\)\[\]{}\"\']", " ", text)
    # Gop khoang trang
    text = re.sub(r"\s+", " ", text).strip()
    # Bo dau unicode (NFD decompose -> loai Mn category)
    nfd = unicodedata.normalize("NFD", text)
    ascii_text = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return ascii_text


# ==============================================================================
# INTENT RULES (Stage 1: Exact / prefix match)
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
    # 'open world' la loi STT thuong gap khi noi 'open word'
    ("open_word",       ["mo word", "mo microsoft word", "mo van ban", "open word", "open world"], False),

    # --- open_chrome ---
    ("open_chrome",     ["mo chrome", "mo google chrome"], False),

    # --- open_coccoc ---
    ("open_coccoc",     ["mo coc coc"], False),

    # --- open_music (needs_query=True) ---
    ("open_music",      ["mo nhac", "mo bai hat"], True),

    # --- web_search (needs_query=True) ---
    ("web_search",      ["tim kiem", "tra cuu", "search", "google"], True),

    # --- next_action (chuyen tiep / tiep theo / trang tiep) ---
    ("next_action",     ["chuyen tiep", "tiep theo", "trang tiep", "trang sau",
                         "sang trang", "di tiep", "qua trang", "trang ke"], False),

    # --- previous_action (quay lai / trang truoc / lui lai) ---
    ("previous_action", ["quay lai", "trang truoc", "lui lai", "lui trang",
                         "quay trang", "tro ve", "ve truoc", "lui lai"], False),

    # --- newline (xuong dong / dong moi) ---
    ("newline",         ["xuong dong", "dong moi"], False),

    # --- new_paragraph (xuong doan / doan moi) ---
    ("new_paragraph",   ["xuong doan", "doan moi"], False),

    # --- system_on ---
    ("system_on",       ["bat he thong", "bat dieu khien", "mo he thong",
                         "khoi dong he thong"], False),

    # --- system_off ---
    ("system_off",      ["tat he thong", "tat dieu khien", "dung he thong",
                         "tat may", "ngung he thong", "he thong tat",
                         "dung dieu khien"], False),
]


# ==============================================================================
# FUZZY ALIASES — STT misrecognition corrections (Stage 2)
# ==============================================================================
# Map normalized text that STT commonly returns wrongly -> correct intent.
# Only for KNOWN misrecognition patterns.

_FUZZY_ALIASES: dict[str, str] = {
    # --- "trang trước" often misrecognized as ---
    "khoang truoc":     "previous_action",
    "khoan truoc":      "previous_action",
    "trong truoc":      "previous_action",
    "trang chuc":       "previous_action",
    "tran truoc":       "previous_action",
    "chang truoc":      "previous_action",
    "trang chuoc":      "previous_action",
    "trang chuc":       "previous_action",
    # --- "quay lại" misrecognized ---
    "quay lai":         "previous_action",
    "way lai":          "previous_action",
    "quay lai quay lai": "previous_action",
    # --- "lùi lại" / "trở về" / "về trước" misrecognized ---
    "lui lai":          "previous_action",
    "tro ve":           "previous_action",
    "ve truoc":         "previous_action",
    "cho ve":           "previous_action",
    # --- "trang sau" / "chuyển tiếp" misrecognized as ---
    "trang xau":        "next_action",
    "chang tiep":       "next_action",
    "trang diep":       "next_action",
    "truyen tiep":      "next_action",
    "chuyen diep":      "next_action",
    "chan tiep":        "next_action",
    "trang xao":       "next_action",
    # --- "tiếp theo" / "sang trang" / "trang kế" misrecognized ---
    "tiep teo":         "next_action",
    "diep theo":        "next_action",
    "xang trang":       "next_action",
    "trang ke":         "next_action",
    # --- repeated (STT captures echo) ---
    "trang truoc trang truoc": "previous_action",
    "trang sau trang sau":     "next_action",
    "tiep theo tiep theo":     "next_action",
    # --- "tắt hệ thống" partial / misrecognized ---
    "he thong":         "system_off",    # STT missed "tat", most likely intent
    "tat he trong":     "system_off",
    "tat he":           "system_off",
    "cat he thong":     "system_off",
    "tap he thong":     "system_off",
    # --- "bật hệ thống" partial / misrecognized ---
    "bat he trong":     "system_on",
    "bat he":           "system_on",
    "mat he thong":     "system_on",
    # --- "mở văn bản" misrecognized ---
    "ma van ban":       "open_word",
    # --- "xuống đoạn" partial ---
    "xuong don":        "new_paragraph",
    "suong doan":       "new_paragraph",
}


# ==============================================================================
# KEYWORD FALLBACK — Partial captures (Stage 3)
# ==============================================================================
# When exact/prefix/fuzzy match fails, check if normalized text CONTAINS keywords.
# Longer phrases first to avoid false positives.

_KEYWORD_FALLBACK: list[tuple[str, list[str]]] = [
    ("system_off",      ["tat he thong", "he thong tat", "dung he thong",
                         "ngung he thong"]),
    ("system_on",       ["bat he thong", "he thong bat", "mo he thong"]),
    ("new_paragraph",   ["xuong doan"]),
    ("newline",         ["xuong dong"]),
    ("next_action",     ["tiep theo", "chuyen tiep", "trang tiep",
                         "sang trang", "qua trang", "trang ke"]),
    ("previous_action", ["quay lai", "trang truoc", "lui lai",
                         "tro ve", "ve truoc"]),
]

# So tu toi da de keyword fallback (Stage 3) duoc chap nhan.
# Cau dai hon bi coi la text, khong match command.
# VD: "hom nay em noi ve trang truoc cua bao cao" (9 tu) -> text, khong phai previous_action.
_KEYWORD_MAX_WORDS = 5


# ==============================================================================
# SINGLE-WORD INTENTS — When STT captures only 1 word (Stage 4)
# ==============================================================================
# Very conservative: only unambiguous single words.

_SINGLE_WORD_MAP: dict[str, str] = {
    "tat":      "system_off",
    "bat":      "system_on",
    "dung":     "system_off",
    "tiep":     "next_action",
    "truoc":    "previous_action",
    "lai":      "previous_action",
}


# ==============================================================================
# PARSER
# ==============================================================================

class VoiceIntentParser:
    """Rule-based parser: text -> intent dict.

    Pipeline:
      1. Normalize text
      2. Exact/prefix match (original rules)
      3. Fuzzy alias match (STT misrecognition)
      4. Keyword fallback (partial captures)
      5. Single-word match
      6. Fallback to type_text
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

        # --- Stage 1: Exact / prefix match ---
        for intent_name, prefixes, needs_query in _INTENT_RULES:
            for prefix in prefixes:
                if norm == prefix:
                    if needs_query:
                        print(f"[VOICE_PARSE] EXACT match '{norm}'=='{prefix}' "
                              f"but needs_query -> fallback text")
                        return self._text_result(raw, norm)
                    print(f"[VOICE_PARSE] EXACT match: '{norm}' -> {intent_name}")
                    return self._command_result(intent_name, "", raw, norm)

                if norm.startswith(prefix + " "):
                    if needs_query:
                        norm_query = norm[len(prefix):].strip()
                        if not norm_query:
                            return self._text_result(raw, norm)
                        raw_query = self._extract_raw_query(raw, prefix)
                        print(f"[VOICE_PARSE] PREFIX match: '{norm}' -> "
                              f"{intent_name} query='{raw_query}'")
                        return self._command_result(intent_name, raw_query, raw, norm)
                    else:
                        # Extra text after exact command
                        # Kiem tra: neu phan du chinh la prefix lap lai
                        # VD: "trang sau trang sau" -> remainder = "trang sau" == prefix
                        _remainder = norm[len(prefix):].strip()
                        if _remainder == prefix:
                            print(f"[VOICE_PARSE] REPEAT match: '{norm}' "
                                  f"('{prefix}' x2) -> {intent_name}")
                            return self._command_result(intent_name, "", raw, norm)
                        # Khong phai lap -> text (tranh nhan nhau)
                        return self._text_result(raw, norm)

        # --- Stage 2: Fuzzy alias match ---
        if norm in _FUZZY_ALIASES:
            intent_name = _FUZZY_ALIASES[norm]
            print(f"[VOICE_PARSE] FUZZY match: '{norm}' -> {intent_name}")
            return self._command_result(intent_name, "", raw, norm)

        # --- Stage 3: Keyword fallback (contains) ---
        # Guard: chi match keyword khi cau ngan (<= _KEYWORD_MAX_WORDS tu)
        # De tranh "hom nay em noi ve trang truoc cua bao cao" -> previous_action
        _word_count = len(norm.split())
        if _word_count <= _KEYWORD_MAX_WORDS:
            for intent_name, keywords in _KEYWORD_FALLBACK:
                for kw in keywords:
                    if kw in norm:
                        print(f"[VOICE_PARSE] KEYWORD match: '{norm}' "
                              f"contains '{kw}' -> {intent_name}")
                        return self._command_result(intent_name, "", raw, norm)
        else:
            print(f"[VOICE_PARSE] KEYWORD skip: '{norm}' "
                  f"has {_word_count} words (max {_KEYWORD_MAX_WORDS}) -> skip keyword stage")

        # --- Stage 4: Single-word match ---
        words = norm.split()
        if len(words) == 1 and words[0] in _SINGLE_WORD_MAP:
            intent_name = _SINGLE_WORD_MAP[words[0]]
            print(f"[VOICE_PARSE] SINGLE-WORD match: '{norm}' -> {intent_name}")
            return self._command_result(intent_name, "", raw, norm)

        # --- Stage 4.5: Repeated command detection ---
        # Khi nguoi dung noi lap "trang sau trang sau", STT tra ve chuoi lap.
        # Kiem tra: neu norm = prefix + " " + prefix thi van match intent.
        for intent_name, prefixes, needs_query in _INTENT_RULES:
            if needs_query:
                continue  # Chi xu ly command khong can query
            for prefix in prefixes:
                repeated = prefix + " " + prefix
                if norm == repeated:
                    print(f"[VOICE_PARSE] REPEAT match: '{norm}' "
                          f"('{prefix}' x2) -> {intent_name}")
                    return self._command_result(intent_name, "", raw, norm)

        # --- Stage 5: No match -> text ---
        print(f"[VOICE_PARSE] COMMAND mode no match, fallback text: '{norm}'")
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
        # --- Original tests ---
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
        "mo nhac",
        "tim kiem",
        "",
        "mo word bai bao cao cua toi",
        "mo youtube la mot vi du",
        "bat he thong nay",
        "mo bai hat Chung ta cua tuong lai",
        "mo nhac Son Tung MTP",
        "mo bai tap",
        "bật điều khiển",
        "tắt điều khiển",
        "bật hệ thống",
        "tắt hệ thống",
        "điều khiển",
        "mở điều khiển",
        # --- New: Fuzzy / partial / single-word tests ---
        "hệ thống",             # -> system_off (fuzzy alias)
        "khoang trước",         # -> previous_action (fuzzy alias)
        "xuống",                # -> type_text (khong du ro, 'xuong' khong trong single_word)
        "xuống đoạn",           # -> new_paragraph (exact match)
        "tắt",                  # -> system_off (single word)
        "bật",                  # -> system_on (single word)
        "tiếp",                 # -> next_action (single word)
        "trước",                # -> previous_action (single word)
        "trang sau",            # -> next_action (exact match)
        "xin chào mọi người",  # -> type_text (no match)
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

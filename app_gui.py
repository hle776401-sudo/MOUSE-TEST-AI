"""
app_gui.py - AI Gesture Mouse Controller: Desktop Control Panel
===============================================================
GUI launcher / control panel cho he thong AI Gesture Mouse Controller.
Chay main.py bang subprocess — khong sua bat ky file core nao.

Yeu cau:  pip install customtkinter
Chay:     python app_gui.py
Phase:    GUI-2 v3 (Mockup Polish)
"""

import csv, os, subprocess, sys, threading
from collections import Counter
from pathlib import Path
from statistics import mean
from tkinter import messagebox

try:
    import customtkinter as ctk
except ImportError:
    print("[ERROR] customtkinter chua duoc cai dat.\n  Chay: pip install customtkinter")
    sys.exit(1)

# ==============================================================================
# Safe config import
# ==============================================================================
_BASE_DIR = Path(__file__).parent.resolve()
try:
    sys.path.insert(0, str(_BASE_DIR))
    import config as _cfg
    _CFG_HOTKEY       = getattr(_cfg, "VOICE_HOTKEY",                "ctrl+alt+v").upper()
    _CFG_LANGUAGE     = getattr(_cfg, "VOICE_LANGUAGE",               "vi-VN")
    _CFG_CONTEXT      = "Bật" if getattr(_cfg, "ENABLE_CONTEXT_AWARE",        True) else "Tắt"
    _CFG_VOICE        = "Bật" if getattr(_cfg, "ENABLE_VOICE_INPUT",          True) else "Tắt"
    _CFG_VOICE_CMD    = "Bật" if getattr(_cfg, "ENABLE_VOICE_COMMANDS",       True) else "Tắt"
    _CFG_GESTURE_TRIG = "Bật" if getattr(_cfg, "ENABLE_GESTURE_VOICE_TRIGGER",True) else "Tắt"
    _CFG_LOG_ENABLED  = "Bật" if getattr(_cfg, "ENABLE_GESTURE_LOGGING",      True) else "Tắt"
    _CFG_LOG_DIR      = getattr(_cfg, "GESTURE_LOG_DIR", "logs")
    _CFG_OK           = True
except Exception as _e:
    _CFG_HOTKEY="CTRL+ALT+V"; _CFG_LANGUAGE="vi-VN"; _CFG_CONTEXT="?"
    _CFG_VOICE="?"; _CFG_VOICE_CMD="?"; _CFG_GESTURE_TRIG="?"; _CFG_LOG_ENABLED="?"
    _CFG_LOG_DIR="logs"; _CFG_OK=False

# ==============================================================================
# Safe analyze_logs import
# ==============================================================================
_HAS_ANALYZER = False
try:
    from analyze_logs import read_events as _al_read_events
    from analyze_logs import find_latest_log as _al_find_latest
    _HAS_ANALYZER = True
except Exception: pass

def _read_events_safe(p):
    if _HAS_ANALYZER:
        try: return _al_read_events(p)
        except Exception: pass
    evts = []
    try:
        for enc in ("utf-8-sig","utf-8","cp1252"):
            try:
                with open(p, newline="", encoding=enc) as f: evts=list(csv.DictReader(f))
                break
            except UnicodeDecodeError: continue
    except Exception: pass
    return evts

def _find_latest_log_safe(d):
    if _HAS_ANALYZER:
        try: return _al_find_latest(d)
        except Exception: pass
    p=Path(d)
    if not p.exists(): return None
    fs=sorted(p.glob("gesture_events_*.csv"), key=lambda f: f.stat().st_mtime)
    return fs[-1] if fs else None

# ==============================================================================
# Color Palette — (light, dark) tuples from user spec
# ==============================================================================
C_BG       = ("#f3f6fb",  "#0b1220")
C_HEADER   = ("#ffffff",  "#0b1220")
C_PANEL    = ("#ffffff",  "#111c2b")
C_CARD     = ("#ffffff",  "#132236")
C_TILE     = ("#eef3f8",  "#172536")
C_CHIP     = ("#eef3f8",  "#172536")
C_BORDER   = ("#d6dee8",  "#223247")
C_DIVIDER  = ("#e2e8f0",  "#1e3350")
C_TBL_ALT  = ("#f3f6fb",  "#111820")
C_TEXT     = ("#0f172a",  "#f8fafc")
C_TEXT2    = ("#475569",  "#94a3b8")
C_ACCENT   = ("#14b8a6",  "#14b8a6")
C_ACC_HVR  = ("#0d9488",  "#0d9488")
C_BLUE     = ("#2563eb",  "#38bdf8")
C_GREEN    = ("#16a34a",  "#22c55e")
C_YELLOW   = ("#d97706",  "#f59e0b")
C_RED      = ("#ef4444",  "#ef4444")
C_RED_HVR  = ("#dc2626",  "#dc2626")
C_PURPLE   = ("#7c3aed",  "#a78bfa")
C_ORANGE   = ("#d97706",  "#f59e0b")
C_BTN      = ("#e5e9ef",  "#1e2e42")
C_BTN_HVR  = ("#d5dbe5",  "#2a4060")
C_STOP_DIS = ("#fee2e2",  "#5f2d35")
C_STOP_DTX = ("#b91c1c",  "#e88da0")
C_START_DIS= ("#d1e8e4",  "#1a3d3a")
C_LOG_BG   = ("#f3f6fb",  "#0d1117")
C_LOG_TXT  = ("#0e7c5f",  "#3fb950")
C_TAB_SEL  = ("#2563eb",  "#1a3050")
C_TAB_SHVR = ("#1d4ed8",  "#203650")
C_TAB_UNS  = ("#cbd5e1",  "#0b1220")
C_TAB_UHVR = ("#94a3b8",  "#131e2e")

# Fixed icon badge colors
_IC_BLUE   = "#3b82f6"
_IC_PURPLE = "#8b5cf6"
_IC_GREEN  = "#10b981"
_IC_ORANGE = "#f59e0b"
_IC_TEAL   = "#14b8a6"
_IC_APP    = "#14b8a6"      # teal for app icon

# ==============================================================================
# Constants
# ==============================================================================
APP_TITLE   = "Bộ điều khiển chuột bằng cử chỉ tay"
APP_VERSION = "v1.0  |  Phase GUI-2"
WIN_W, WIN_H = 1060, 740
WIN_MIN_W, WIN_MIN_H = 900, 620

STATUS_STOPPED  = "Đã dừng"
STATUS_STARTING = "Đang khởi động..."
STATUS_RUNNING  = "Đang chạy"
DESC_STOPPED  = "Hệ thống đang ở trạng thái dừng. Nhấn 'Khởi động' để bắt đầu."
DESC_STARTING = "Hệ thống đang khởi động, vui lòng chờ..."
DESC_RUNNING  = "Hệ thống đang xử lý webcam và nhận dạng cử chỉ."

TAB_CTRL = "Điều khiển"
TAB_GUIDE = "Hướng dẫn"
TAB_ANALYZE = "Phân tích"

_F = lambda sz, bold=False: ctk.CTkFont(family="Segoe UI", size=sz,
                                          weight="bold" if bold else "normal")

# ==============================================================================
# Main App
# ==============================================================================
class GestureControllerApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self._proc = None
        self._analyze_thread = None
        self._stat_labels = {}
        self._setup_window()
        self._build_ui()
        self._poll_proc()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Window ──────────────────────────────────────────────────────────────
    def _setup_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.configure(fg_color=C_BG)
        self.update_idletasks()
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        w = min(WIN_W, scr_w - 80)
        h = min(WIN_H, scr_h - 80)
        x = max(0, (scr_w - w) // 2)
        y = max(0, (scr_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(WIN_MIN_W, WIN_MIN_H)

    # ── Master layout ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=0)  # header
        self.grid_rowconfigure(1, weight=0)  # status panel
        self.grid_rowconfigure(2, weight=1)  # tabs (expand)
        self.grid_rowconfigure(3, weight=0)  # footer
        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_status_panel()
        self._build_tabs()
        self._build_footer()

    # ── Header ──────────────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color=C_HEADER, corner_radius=0, height=52)
        h.grid(row=0, column=0, sticky="ew"); h.grid_propagate(False)
        h.grid_columnconfigure(1, weight=1)

        # App icon — teal rounded square 30x30 with border
        ctk.CTkLabel(h, text="▣", font=_F(14,True),
            text_color=("#ffffff","#ffffff"), fg_color=(_IC_APP,_IC_APP),
            width=30, height=30, corner_radius=8).grid(row=0, column=0, padx=(24,10), pady=11)

        ctk.CTkLabel(h, text=APP_TITLE, font=_F(15,True),
            text_color=C_TEXT, anchor="w").grid(row=0, column=1, sticky="w")

        tf = ctk.CTkFrame(h, fg_color="transparent")
        tf.grid(row=0, column=2, padx=(0,24))
        ctk.CTkLabel(tf, text="Giao diện", font=_F(11),
            text_color=C_TEXT2).pack(side="left", padx=(0,8))

        self._btn_light = ctk.CTkButton(tf, text="☀", width=30, height=28,
            corner_radius=14, font=_F(12), fg_color=C_BTN, hover_color=C_BTN_HVR,
            text_color=C_TEXT2, command=lambda: self._set_theme("light"))
        self._btn_light.pack(side="left", padx=1)
        self._btn_dark = ctk.CTkButton(tf, text="●", width=30, height=28,
            corner_radius=14, font=_F(11), fg_color=C_ACCENT, hover_color=C_ACC_HVR,
            text_color=("#fff","#fff"), command=lambda: self._set_theme("dark"))
        self._btn_dark.pack(side="left", padx=1)

    # ── Status Panel ────────────────────────────────────────────────────────
    def _build_status_panel(self):
        wrap = ctk.CTkFrame(self, fg_color=C_BG)
        wrap.grid(row=1, column=0, sticky="ew", padx=20, pady=(8,4))

        pnl = ctk.CTkFrame(wrap, fg_color=C_PANEL, corner_radius=16,
            border_width=1, border_color=C_BORDER, height=110)
        pnl.pack(fill="x"); pnl.pack_propagate(False)
        pnl.grid_columnconfigure(0, weight=1); pnl.grid_columnconfigure(1, weight=0)

        lf = ctk.CTkFrame(pnl, fg_color="transparent")
        lf.grid(row=0, column=0, sticky="nsw", padx=24, pady=18)
        sr = ctk.CTkFrame(lf, fg_color="transparent"); sr.pack(fill="x")

        self._sdot = ctk.CTkLabel(sr, text="●", font=_F(20), text_color=C_GREEN)
        self._sdot.pack(side="left", padx=(0,10))
        self._slbl = ctk.CTkLabel(sr, text=STATUS_STOPPED,
            font=_F(20,True), text_color=C_TEXT, anchor="w")
        self._slbl.pack(side="left")
        self._sdesc = ctk.CTkLabel(lf, text=DESC_STOPPED,
            font=_F(12), text_color=C_TEXT2, anchor="w")
        self._sdesc.pack(fill="x", pady=(4,0))

        rf = ctk.CTkFrame(pnl, fg_color="transparent")
        rf.grid(row=0, column=1, padx=24, pady=18)
        self._btn_start = ctk.CTkButton(rf, text="▶   Khởi động", font=_F(14,True),
            fg_color=C_ACCENT, hover_color=C_ACC_HVR, text_color=("#fff","#fff"),
            height=48, width=170, corner_radius=12, command=self.start_controller)
        self._btn_start.pack(side="left", padx=(0,10))
        self._btn_stop = ctk.CTkButton(rf, text="■   Dừng", font=_F(14,True),
            fg_color=C_STOP_DIS, hover_color=C_STOP_DIS, text_color=C_STOP_DTX,
            height=48, width=130, corner_radius=12, state="disabled",
            command=self.stop_controller)
        self._btn_stop.pack(side="left")

    # ── Tabs ────────────────────────────────────────────────────────────────
    def _build_tabs(self):
        self._tabs = ctk.CTkTabview(self, fg_color=C_BG,
            segmented_button_fg_color=C_BG,
            segmented_button_selected_color=C_TAB_SEL,
            segmented_button_unselected_color=C_TAB_UNS,
            segmented_button_selected_hover_color=C_TAB_SHVR,
            segmented_button_unselected_hover_color=C_TAB_UHVR,
            corner_radius=8, border_width=0, anchor="w")
        # Fix tab text visibility in light theme
        try:
            self._tabs._segmented_button.configure(
                text_color=("#0f172a", "#f8fafc"),
                font=_F(12, True))
        except Exception:
            pass
        self._tabs.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0,0))

        t1 = self._tabs.add(TAB_CTRL)
        t2 = self._tabs.add(TAB_GUIDE)
        t3 = self._tabs.add(TAB_ANALYZE)

        self._build_tab_ctrl(t1)
        self._build_tab_guide(t2)
        self._build_tab_analysis(t3)

    # ── Tab 1: Điều khiển (NO scrollbar) ────────────────────────────────────
    def _build_tab_ctrl(self, parent):
        box = ctk.CTkFrame(parent, fg_color=C_BG)
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(0, weight=1, uniform="c")
        box.grid_columnconfigure(1, weight=1, uniform="c")

        left = ctk.CTkFrame(box, fg_color=C_BG)
        left.grid(row=0, column=0, sticky="new", padx=(0,8))
        right = ctk.CTkFrame(box, fg_color=C_BG)
        right.grid(row=0, column=1, sticky="new", padx=(8,0))

        self._card_quick(left)
        self._card_tips(left)
        self._card_config(right)
        self._card_modules(right)

    # ---- Quick Access ----
    def _card_quick(self, parent):
        c = self._card(parent, "Truy cập nhanh", "≡"); c.pack(fill="x", pady=(0,10))
        g = ctk.CTkFrame(c, fg_color="transparent")
        g.pack(fill="x", padx=16, pady=(0,16))
        g.grid_columnconfigure(0, weight=1, uniform="t")
        g.grid_columnconfigure(1, weight=1, uniform="t")

        tiles = [
            (_IC_BLUE,   "LOG", "Thư mục log",  "Mở thư mục chứa log",    self.open_logs),
            (_IC_PURPLE, "AN",  "Phân tích log", "Xem và phân tích log",    self._analyze_switch),
            (_IC_GREEN,  "DOC", "README",        "Xem tài liệu hướng dẫn", self.open_readme),
            (_IC_ORANGE, "RPT", "Báo cáo",       "Xem báo cáo hệ thống",   self.open_report),
        ]
        for i,(clr,ico,ttl,sub,cmd) in enumerate(tiles):
            r,col = divmod(i,2)
            self._tile(g, clr, ico, ttl, sub, cmd).grid(
                row=r, column=col, padx=4, pady=4, sticky="nsew")

    def _tile(self, parent, color, icon_txt, title, subtitle, cmd):
        t = ctk.CTkFrame(parent, fg_color=C_TILE, corner_radius=12, cursor="hand2")
        inner = ctk.CTkFrame(t, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        # Icon badge with text
        ctk.CTkLabel(inner, text=icon_txt, font=_F(10,True),
            text_color=("#fff","#fff"), fg_color=(color,color),
            width=42, height=42, corner_radius=10).pack(side="left", padx=(0,12))

        mid = ctk.CTkFrame(inner, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(mid, text=title, font=_F(12,True),
            text_color=C_TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(mid, text=subtitle, font=_F(10),
            text_color=C_TEXT2, anchor="w").pack(fill="x")

        ctk.CTkLabel(inner, text="›", font=_F(16),
            text_color=C_TEXT2).pack(side="right", padx=(6,0))

        self._click(t, cmd)
        return t

    # ---- Tóm tắt nhanh ----
    def _card_tips(self, parent):
        c = self._card(parent, "Tóm tắt nhanh", "▸"); c.pack(fill="x", pady=(0,10))
        ct = ctk.CTkFrame(c, fg_color="transparent")
        ct.pack(fill="x", padx=16, pady=(0,14))

        tips = [
            (_IC_TEAL,  "BT", "Bật/Tắt hệ thống",  "Xòe 5 ngón tay trái, giữ 3 giây"),
            (_IC_GREEN, "DC", "Di chuyển con trỏ",   "Giơ ngón trỏ tay phải"),
            (_IC_BLUE,  "GN", "Nhập giọng nói",      f"Nhấn {_CFG_HOTKEY} hoặc pose [0,1,1,1,0]"),
        ]
        for clr, ico, ttl, desc in tips:
            row = ctk.CTkFrame(ct, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=ico, font=_F(7,True),
                text_color=("#fff","#fff"), fg_color=(clr,clr),
                width=28, height=28, corner_radius=7).pack(side="left", padx=(0,10))

            ctk.CTkLabel(row, text=ttl, font=_F(11,True),
                text_color=C_TEXT, anchor="w", width=160).pack(side="left")
            ctk.CTkLabel(row, text=desc, font=_F(10),
                text_color=C_TEXT2, anchor="e").pack(side="right")

    # ---- Cấu hình hệ thống ----
    def _card_config(self, parent):
        c = self._card(parent, "Cấu hình hệ thống", "⚙"); c.pack(fill="x", pady=(0,10))
        ct = ctk.CTkFrame(c, fg_color="transparent")
        ct.pack(fill="x", padx=16, pady=(0,12))

        items = [
            ("Phím tắt giọng nói",    _CFG_HOTKEY,       C_BLUE,  False),
            ("Ngôn ngữ",              _CFG_LANGUAGE,     C_BLUE,  False),
            ("Nhập liệu giọng nói",   _CFG_VOICE,        C_GREEN, _CFG_VOICE=="Bật"),
            ("Lệnh giọng nói",        _CFG_VOICE_CMD,    C_GREEN, _CFG_VOICE_CMD=="Bật"),
            ("Kích hoạt bằng cử chỉ", _CFG_GESTURE_TRIG, C_GREEN, _CFG_GESTURE_TRIG=="Bật"),
            ("Nhận biết ngữ cảnh",    _CFG_CONTEXT,      C_GREEN, _CFG_CONTEXT=="Bật"),
        ]
        for idx,(lbl,val,vcol,dot) in enumerate(items):
            row = ctk.CTkFrame(ct, fg_color="transparent", height=44)
            row.pack(fill="x"); row.pack_propagate(False)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=lbl, font=_F(11),
                text_color=C_TEXT2, anchor="w").grid(row=0, column=0, sticky="w")

            rf = ctk.CTkFrame(row, fg_color="transparent")
            rf.grid(row=0, column=1, sticky="e")

            if dot:
                ctk.CTkLabel(rf, text="●", font=_F(8),
                    text_color=C_GREEN).pack(side="left", padx=(0,4))
            ctk.CTkLabel(rf, text=val, font=_F(11,True),
                text_color=vcol, anchor="e").pack(side="left")
            ctk.CTkLabel(rf, text="›", font=_F(14),
                text_color=C_TEXT2).pack(side="left", padx=(8,0))

            if idx < len(items)-1:
                ctk.CTkFrame(ct, fg_color=C_DIVIDER, height=1).pack(fill="x")

    # ---- Tình trạng mô-đun ----
    def _card_modules(self, parent):
        c = self._card(parent, "Tình trạng mô-đun", "◆"); c.pack(fill="x", pady=(0,10))
        g = ctk.CTkFrame(c, fg_color="transparent")
        g.pack(fill="x", padx=16, pady=(0,14))
        for i in range(4): g.grid_columnconfigure(i, weight=1, uniform="m")

        mods = [
            (_IC_GREEN,  "CAM", "Camera",     "Sẵn sàng",       C_GREEN),
            (_IC_BLUE,   "MIC", "Giọng nói",  _CFG_VOICE,        C_GREEN if _CFG_VOICE=="Bật" else C_TEXT2),
            (_IC_PURPLE, "CTX", "Ngữ cảnh",   _CFG_CONTEXT,      C_GREEN if _CFG_CONTEXT=="Bật" else C_TEXT2),
            (_IC_ORANGE, "LOG", "Ghi log",
             "Đang hoạt động" if (_CFG_OK and _CFG_LOG_ENABLED=="Bật") else "Tắt",
             C_GREEN if (_CFG_OK and _CFG_LOG_ENABLED=="Bật") else C_TEXT2),
        ]
        for i,(clr,ico,name,status,scol) in enumerate(mods):
            ch = ctk.CTkFrame(g, fg_color=C_CHIP, corner_radius=10)
            ch.grid(row=0, column=i, padx=3, sticky="nsew")

            ctk.CTkLabel(ch, text=ico, font=_F(9,True),
                text_color=("#fff","#fff"), fg_color=(clr,clr),
                width=36, height=36, corner_radius=8).pack(pady=(10,4))
            ctk.CTkLabel(ch, text=name, font=_F(11,True),
                text_color=C_TEXT).pack()
            ctk.CTkLabel(ch, text=status, font=_F(10),
                text_color=scol).pack(pady=(0,10))

    # ── Tab 2: Hướng dẫn ────────────────────────────────────────────────────
    def _build_tab_guide(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color=C_BG)
        sc.pack(fill="both", expand=True)

        self._guide_tbl(sc, "Tay chính — điều khiển chuột", [
            ("Di chuyển con trỏ",  "Giơ ngón trỏ tay phải"),
            ("Click trái",         "Chụm ngón cái và ngón trỏ"),
            ("Click phải",         "Chụm ngón cái và ngón giữa"),
            ("Nhấp đúp",           "Thực hiện click trái 2 lần nhanh"),
            ("Kéo thả",            "Chụm ngón cái và ngón trỏ, giữ rồi di chuyển"),
            ("Cuộn trang",         "Tư thế cuộn và di chuyển tay theo chiều dọc"),
        ])
        self._guide_tbl(sc, "Tay phụ — thao tác hỗ trợ", [
            ("Bật/Tắt hệ thống",    "Xòe 5 ngón tay trái, giữ 3 giây"),
            ("Vuốt trái",           "Vuốt tay trái sang trái"),
            ("Vuốt phải",           "Vuốt tay trái sang phải"),
            ("Zoom In",             "Thực hiện cử chỉ phóng to"),
            ("Zoom Out",            "Thực hiện cử chỉ thu nhỏ"),
            ("Kích hoạt giọng nói", f"Dùng pose giọng nói hoặc {_CFG_HOTKEY}"),
        ])
        cd = self._card(sc, "Điều kiện sử dụng tốt nhất", "●"); cd.pack(fill="x", pady=(0,10))
        ct = ctk.CTkFrame(cd, fg_color="transparent")
        ct.pack(fill="x", padx=18, pady=(0,14))
        for n in ["Đặt tay trong vùng quan sát của webcam.",
                   "Không để tay quá gần hoặc quá xa camera.",
                   "Sử dụng trong môi trường đủ sáng.",
                   "Thực hiện cử chỉ rõ ràng, không quá nhanh.",
                   "Tránh che khuất các ngón tay.",
                   "Khi click hoặc kéo thả, cần thao tác dứt khoát."]:
            r = ctk.CTkFrame(ct, fg_color="transparent"); r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text="●", font=_F(6), text_color=C_YELLOW
                ).pack(side="left", padx=(0,8), anchor="n", pady=5)
            ctk.CTkLabel(r, text=n, font=_F(11), text_color=C_TEXT,
                anchor="w", wraplength=480).pack(side="left", fill="x", expand=True)

    def _guide_tbl(self, parent, title, rows):
        cd = self._card(parent, title, "▸"); cd.pack(fill="x", pady=(0,10))
        hdr = ctk.CTkFrame(cd, fg_color="transparent"); hdr.pack(fill="x", padx=18)
        hdr.grid_columnconfigure(0, weight=1); hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="Cử chỉ", font=_F(10,True),
            text_color=C_BLUE, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Hành động", font=_F(10,True),
            text_color=C_BLUE, anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkFrame(cd, fg_color=C_DIVIDER, height=1).pack(fill="x", padx=18, pady=(2,4))
        bd = ctk.CTkFrame(cd, fg_color="transparent"); bd.pack(fill="x", padx=18, pady=(0,14))
        bd.grid_columnconfigure(0, weight=1); bd.grid_columnconfigure(1, weight=1)
        for i,(g,a) in enumerate(rows):
            ctk.CTkLabel(bd, text=g, font=_F(11,True), text_color=C_TEXT,
                anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            ctk.CTkLabel(bd, text=a, font=_F(11), text_color=C_TEXT2,
                anchor="w").grid(row=i, column=1, sticky="w", pady=3)

    # ── Tab 3: Phân tích ────────────────────────────────────────────────────
    def _build_tab_analysis(self, parent):
        sc = ctk.CTkScrollableFrame(parent, fg_color=C_BG)
        sc.pack(fill="both", expand=True)

        # Stats
        c1 = self._card(sc, "Thống kê nhanh", "■"); c1.pack(fill="x", pady=(0,10))
        sg = ctk.CTkFrame(c1, fg_color="transparent")
        sg.pack(fill="x", padx=14, pady=(0,12))
        for i in range(6): sg.grid_columnconfigure(i, weight=1, uniform="s")
        self._stat_labels = {}
        for i,(k,l) in enumerate([("total","Tổng sự kiện"),("gestures","Nhận dạng"),
            ("executed","Đã thực thi"),("fps","FPS TB"),("top","Phổ biến"),("errors","Lỗi")]):
            ch = ctk.CTkFrame(sg, fg_color=C_CHIP, corner_radius=8)
            ch.grid(row=0, column=i, padx=3, sticky="nsew")
            v = ctk.CTkLabel(ch, text="—", font=_F(20,True), text_color=C_ACCENT)
            v.pack(pady=(10,2)); self._stat_labels[k]=v
            ctk.CTkLabel(ch, text=l, font=_F(10), text_color=C_TEXT2).pack(pady=(0,10))

        # File info label — hien thi ten file CSV dang doc
        self._log_file_label = ctk.CTkLabel(c1, text="\U0001F4C4 Ch\u01b0a t\u1ea3i log",
            font=_F(10), text_color=C_TEXT2, anchor="w")
        self._log_file_label.pack(fill="x", padx=18, pady=(0,10))

        # Events
        c2 = self._card(sc, "Sự kiện gần nhất", "▸"); c2.pack(fill="x", pady=(0,10))
        self._ev_ct = ctk.CTkFrame(c2, fg_color="transparent")
        self._ev_ct.pack(fill="x", padx=14, pady=(0,14))
        ctk.CTkLabel(self._ev_ct, text="Chưa có dữ liệu log.\nHãy chạy hệ thống trước.",
            font=_F(11), text_color=C_TEXT2, justify="center").pack(pady=14)

        # Frequency
        c3 = self._card(sc, "Tần suất cử chỉ", "■"); c3.pack(fill="x", pady=(0,10))
        self._freq_ct = ctk.CTkFrame(c3, fg_color="transparent")
        self._freq_ct.pack(fill="x", padx=14, pady=(0,14))
        ctk.CTkLabel(self._freq_ct, text="Chưa có dữ liệu.",
            font=_F(10), text_color=C_TEXT2).pack(pady=8)

        # Tools
        c4 = self._card(sc, "Công cụ phân tích", "⚙"); c4.pack(fill="x", pady=(0,10))
        tg = ctk.CTkFrame(c4, fg_color="transparent")
        tg.pack(fill="x", padx=14, pady=(0,14))
        for i in range(4): tg.grid_columnconfigure(i, weight=1)
        bk = dict(height=36, corner_radius=8, font=_F(11),
                  fg_color=C_BTN, hover_color=C_BTN_HVR, text_color=C_TEXT)
        ctk.CTkButton(tg, text="Tải lại log", command=self._refresh_analysis,
            **bk).grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        self._btn_az = ctk.CTkButton(tg, text="Phân tích log",
            command=self.analyze_logs, **bk)
        self._btn_az.grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        ctk.CTkButton(tg, text="Mở thư mục log", command=self.open_logs,
            **bk).grid(row=0, column=2, padx=3, pady=3, sticky="ew")
        ctk.CTkButton(tg, text="Xuất báo cáo", command=self.open_report,
            **bk).grid(row=0, column=3, padx=3, pady=3, sticky="ew")

        # Log output
        ctk.CTkLabel(sc, text="Kết quả phân tích chi tiết", font=_F(11,True),
            text_color=C_BLUE, anchor="w").pack(fill="x", padx=4, pady=(0,4))
        self._logbox = ctk.CTkTextbox(sc, height=160, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=C_LOG_BG, text_color=C_LOG_TXT, wrap="word", state="disabled")
        self._logbox.pack(fill="x", pady=(0,8))
        self._set_log("Nhấn \"Tải lại log\" hoặc \"Phân tích log\" để xem kết quả.")
        self.after(400, self._refresh_analysis)

    # ── Footer ──────────────────────────────────────────────────────────────
    def _build_footer(self):
        ft = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0, height=34)
        ft.grid(row=3, column=0, sticky="ew"); ft.grid_propagate(False)
        ft.grid_columnconfigure(0, weight=1)
        self._flbl = ctk.CTkLabel(ft, text="ⓘ  Hệ thống hoạt động ổn định",
            font=_F(10), text_color=C_TEXT2, anchor="w")
        self._flbl.grid(row=0, column=0, sticky="w", padx=20, pady=6)
        ctk.CTkLabel(ft, text=APP_VERSION, font=_F(9),
            text_color=C_TEXT2, anchor="e").grid(row=0, column=1, sticky="e", padx=20, pady=6)

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _card(self, parent, title="", icon=""):
        cd = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=16,
            border_width=1, border_color=C_BORDER)
        if title:
            h = ctk.CTkFrame(cd, fg_color="transparent")
            h.pack(fill="x", padx=18, pady=(14,6))
            if icon:
                ctk.CTkLabel(h, text=icon, font=_F(13),
                    text_color=C_TEXT2).pack(side="left", padx=(0,8))
            ctk.CTkLabel(h, text=title, font=_F(14,True),
                text_color=C_TEXT).pack(side="left")
        return cd

    def _click(self, w, cmd):
        w.bind("<Button-1>", lambda e: cmd())
        try:
            for ch in w.winfo_children(): self._click(ch, cmd)
        except: pass

    def _set_theme(self, mode):
        if mode == "light":
            ctk.set_appearance_mode("light")
            self._btn_light.configure(fg_color=C_ACCENT, text_color=("#fff","#fff"))
            self._btn_dark.configure(fg_color=C_BTN, text_color=C_TEXT2)
        else:
            ctk.set_appearance_mode("dark")
            self._btn_light.configure(fg_color=C_BTN, text_color=C_TEXT2)
            self._btn_dark.configure(fg_color=C_ACCENT, text_color=("#fff","#fff"))

    # ── Controller lifecycle (logic UNCHANGED) ──────────────────────────────
    def start_controller(self):
        if self._proc is not None and self._proc.poll() is None: return
        ms = _BASE_DIR / "main.py"
        if not ms.exists():
            messagebox.showerror("Lỗi", f"Không tìm thấy main.py:\n{ms}"); return
        try:
            self._proc = subprocess.Popen([sys.executable, str(ms)], cwd=str(_BASE_DIR))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khởi động:\n{e}"); return
        self._set_status(STATUS_STARTING, C_YELLOW, DESC_STARTING)
        self._btn_start.configure(state="disabled", fg_color=C_START_DIS)
        self._btn_stop.configure(state="normal", fg_color=C_RED, hover_color=C_RED_HVR,
            text_color=("#fff","#fff"))
        self._uf("Đang khởi động hệ thống...")
        self.after(1500, self._confirm_running)

    def _confirm_running(self):
        if self._proc and self._proc.poll() is None:
            self._set_status(STATUS_RUNNING, C_GREEN, DESC_RUNNING)
            self._uf("Hệ thống đang hoạt động")
        else:
            c = self._proc.returncode if self._proc else "N/A"
            self._set_log(f"[CẢNH BÁO] Hệ thống thoát ngay (mã: {c}).\nKiểm tra webcam.")
            self._uf("Lỗi: hệ thống thoát bất thường"); self._on_stopped()

    def stop_controller(self):
        if self._proc is None or self._proc.poll() is not None:
            self._on_stopped(); return
        try: self._proc.terminate()
        except Exception as e: print(f"[GUI] terminate(): {e}")
        threading.Thread(target=self._wait_then_kill, daemon=True).start()

    def _wait_then_kill(self):
        try: self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try: self._proc.kill()
            except: pass
        except: pass
        finally: self.after(0, self._on_stopped)

    def _on_stopped(self):
        self._set_status(STATUS_STOPPED, C_GREEN, DESC_STOPPED)
        self._btn_start.configure(state="normal", fg_color=C_ACCENT, hover_color=C_ACC_HVR,
            text_color=("#fff","#fff"))
        self._btn_stop.configure(state="disabled", fg_color=C_STOP_DIS,
            hover_color=C_STOP_DIS, text_color=C_STOP_DTX)
        self._uf("Hệ thống hoạt động ổn định")
        # Auto-reload log sau khi dung, delay 1.5s de logger dong file
        self.after(1500, self._refresh_analysis)

    def _poll_proc(self):
        if self._proc is not None and self._proc.poll() is not None: self._on_stopped()
        self.after(500, self._poll_proc)

    # ── Quick access (logic UNCHANGED) ──────────────────────────────────────
    def open_logs(self):
        ld = _BASE_DIR / _CFG_LOG_DIR
        if not ld.exists():
            messagebox.showinfo("Thông tin",
                f"Thư mục '{_CFG_LOG_DIR}/' chưa tồn tại.\nHãy chạy hệ thống trước."); return
        try: os.startfile(str(ld))
        except Exception as e: messagebox.showerror("Lỗi", f"Không thể mở:\n{e}")

    def _analyze_switch(self):
        self._tabs.set(TAB_ANALYZE); self.analyze_logs()

    def analyze_logs(self):
        if self._analyze_thread and self._analyze_thread.is_alive(): return
        self._btn_az.configure(state="disabled", text="Đang phân tích...")
        self._set_log("[THÔNG TIN] Đang chạy analyze_logs.py ...")
        self._analyze_thread = threading.Thread(target=self._run_analyze, daemon=True)
        self._analyze_thread.start()

    def _run_analyze(self):
        s = _BASE_DIR / "analyze_logs.py"
        if not s.exists():
            self.after(0, lambda: self._finish_analyze("[LỖI] analyze_logs.py không tìm thấy.")); return
        try:
            r = subprocess.run([sys.executable, str(s)], cwd=str(_BASE_DIR),
                capture_output=True, text=True, timeout=15)
            o = r.stdout.strip() or r.stderr.strip() or "(Không có kết quả)"
        except subprocess.TimeoutExpired: o = "[LỖI] Quá thời gian chờ."
        except Exception as e: o = f"[LỖI] {e}"
        self.after(0, lambda: self._finish_analyze(o))

    def _finish_analyze(self, text):
        self._set_log(text); self._btn_az.configure(state="normal", text="Phân tích log")

    def open_readme(self): self._open_file("README.md")
    def open_report(self): self._open_file("BAO_CAO_HE_THONG.md")

    def _open_file(self, fn):
        p = _BASE_DIR / fn
        if not p.exists():
            messagebox.showinfo("Thông tin", f"File '{fn}' không tìm thấy.\n{p}"); return
        try: os.startfile(str(p))
        except Exception as e: messagebox.showerror("Lỗi", f"Không thể mở {fn}:\n{e}")

    # ── Analysis data ───────────────────────────────────────────────────────
    def _refresh_analysis(self):
        ld = str(_BASE_DIR / _CFG_LOG_DIR)
        lt = _find_latest_log_safe(ld)
        if lt is None:
            self._stats_empty(); self._ev_empty(); self._freq_empty()
            if hasattr(self, '_log_file_label'):
                self._log_file_label.configure(text="\U0001F4C4 Kh\u00f4ng t\u00ecm th\u1ea5y file log")
            return
        ev = _read_events_safe(lt)
        if not ev:
            self._stats_empty(); self._ev_empty(); self._freq_empty()
            if hasattr(self, '_log_file_label'):
                self._log_file_label.configure(text=f"\U0001F4C4 {Path(lt).name} (tr\u1ed1ng)")
            return
        # Hien thi ten file + so event
        if hasattr(self, '_log_file_label'):
            self._log_file_label.configure(
                text=f"\U0001F4C4 {Path(lt).name}  \u2022  {len(ev)} s\u1ef1 ki\u1ec7n")
        self._stats_fill(ev); self._ev_fill(ev); self._freq_fill(ev)

    def _stats_fill(self, ev):
        t=len(ev); ng=sum(1 for e in ev if e.get("gesture","").strip())
        nx=sum(1 for e in ev if str(e.get("executed","0")).strip()=="1")
        fps=[]
        for e in ev:
            try:
                v=float(e.get("fps","0") or "0")
                if v>0: fps.append(v)
            except: pass
        af=f"{mean(fps):.1f}" if fps else "—"
        gc=Counter(e.get("gesture","").strip() for e in ev if e.get("gesture","").strip())
        tp=gc.most_common(1)[0][0][:10] if gc else "—"
        for k,v in {"total":str(t),"gestures":str(ng),"executed":str(nx),
                     "fps":af,"top":tp,"errors":str(t-nx)}.items():
            if k in self._stat_labels: self._stat_labels[k].configure(text=v)

    def _stats_empty(self):
        for k in self._stat_labels: self._stat_labels[k].configure(text="—")

    def _ev_fill(self, ev):
        for w in self._ev_ct.winfo_children(): w.destroy()
        cols=["Thời gian","Cử chỉ","Hành động","Ngữ cảnh","Trạng thái"]; cw=[2,2,2,1,1]
        hf=ctk.CTkFrame(self._ev_ct, fg_color="transparent"); hf.pack(fill="x")
        for i in range(5): hf.grid_columnconfigure(i, weight=cw[i])
        for i,c in enumerate(cols):
            ctk.CTkLabel(hf, text=c, font=_F(10,True), text_color=C_BLUE,
                anchor="w").grid(row=0, column=i, sticky="w", padx=4)
        ctk.CTkFrame(self._ev_ct, fg_color=C_DIVIDER, height=1).pack(fill="x", pady=2)
        for idx,e in enumerate(reversed(ev[-10:])):
            ts=e.get("timestamp","").strip()
            if len(ts)>8: ts=ts[-12:]
            g=e.get("gesture","").strip() or "—"
            a=e.get("action","").strip() or "—"
            cx=e.get("context","").strip() or "—"
            ex=str(e.get("executed","0")).strip()
            st="OK" if ex=="1" else "Lỗi"; sc=C_GREEN if ex=="1" else C_RED
            rf=ctk.CTkFrame(self._ev_ct,
                fg_color=C_TBL_ALT if idx%2==0 else "transparent", corner_radius=4)
            rf.pack(fill="x", pady=1)
            for i in range(5): rf.grid_columnconfigure(i, weight=cw[i])
            for i,v in enumerate([ts,g,a,cx]):
                ctk.CTkLabel(rf, text=v, font=ctk.CTkFont(family="Consolas", size=10),
                    text_color=C_TEXT, anchor="w").grid(row=0, column=i, sticky="w", padx=4, pady=2)
            ctk.CTkLabel(rf, text=st, font=_F(10), text_color=sc,
                anchor="w").grid(row=0, column=4, sticky="w", padx=4, pady=2)

    def _ev_empty(self):
        for w in self._ev_ct.winfo_children(): w.destroy()
        ctk.CTkLabel(self._ev_ct, text="Chưa có dữ liệu log.\nHãy chạy hệ thống trước.",
            font=_F(11), text_color=C_TEXT2, justify="center").pack(pady=14)

    def _freq_fill(self, ev):
        for w in self._freq_ct.winfo_children(): w.destroy()
        gc=Counter(e.get("gesture","").strip() for e in ev if e.get("gesture","").strip())
        if not gc: self._freq_empty(); return
        tt=sum(gc.values())
        for name,cnt in gc.most_common(6):
            fr=cnt/tt if tt>0 else 0
            r=ctk.CTkFrame(self._freq_ct, fg_color="transparent"); r.pack(fill="x", pady=2)
            r.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(r, text=name, width=110, font=_F(10), text_color=C_TEXT,
                anchor="w").grid(row=0, column=0, sticky="w", padx=(0,8))
            bar=ctk.CTkProgressBar(r, height=14, corner_radius=4,
                fg_color=C_CHIP, progress_color=C_ACCENT)
            bar.grid(row=0, column=1, sticky="ew", padx=(0,8)); bar.set(fr)
            ctk.CTkLabel(r, text=f"{fr*100:.0f}% ({cnt})", width=70, font=_F(10),
                text_color=C_TEXT2, anchor="e").grid(row=0, column=2, sticky="e")

    def _freq_empty(self):
        for w in self._freq_ct.winfo_children(): w.destroy()
        ctk.CTkLabel(self._freq_ct, text="Chưa có dữ liệu.",
            font=_F(10), text_color=C_TEXT2).pack(pady=8)

    # ── Status / log helpers ────────────────────────────────────────────────
    def _set_status(self, txt, clr, desc=""):
        self._slbl.configure(text=txt); self._sdot.configure(text_color=clr)
        if desc: self._sdesc.configure(text=desc)

    def _set_log(self, txt):
        self._logbox.configure(state="normal")
        self._logbox.delete("1.0","end"); self._logbox.insert("1.0", txt)
        self._logbox.configure(state="disabled")

    def _uf(self, txt): self._flbl.configure(text=f"ⓘ  {txt}")

    # ── Window close (logic UNCHANGED) ──────────────────────────────────────
    def _on_close(self):
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate(); self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try: self._proc.kill()
                except: pass
            except: pass
        self.destroy()


if __name__ == "__main__":
    GestureControllerApp().mainloop()

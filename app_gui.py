"""
app_gui.py - AI Gesture Mouse Controller: Desktop Control Panel
===============================================================
GUI launcher / control panel cho he thong AI Gesture Mouse Controller.

Chay main.py bang subprocess — khong sua bat ky file core nao.

Yeu cau:
    pip install customtkinter

Chay:
    python app_gui.py

Phase: GUI-1 Launcher MVP
"""

import os
import subprocess
import sys
import threading
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:
    print("[ERROR] customtkinter chua duoc cai dat.")
    print("  Chay: pip install customtkinter")
    sys.exit(1)

# ==============================================================================
# Safe config import — GUI khong crash neu config loi
# ==============================================================================
_BASE_DIR = Path(__file__).parent.resolve()

try:
    sys.path.insert(0, str(_BASE_DIR))
    import config as _cfg

    _CFG_HOTKEY        = getattr(_cfg, "VOICE_HOTKEY",               "ctrl+alt+v").upper()
    _CFG_LANGUAGE      = getattr(_cfg, "VOICE_LANGUAGE",              "vi-VN")
    _CFG_CONTEXT       = "Enabled"  if getattr(_cfg, "ENABLE_CONTEXT_AWARE",        True) else "Disabled"
    _CFG_VOICE         = "Enabled"  if getattr(_cfg, "ENABLE_VOICE_INPUT",          True) else "Disabled"
    _CFG_VOICE_CMD     = "Enabled"  if getattr(_cfg, "ENABLE_VOICE_COMMANDS",       True) else "Disabled"
    _CFG_GESTURE_TRIG  = "Enabled"  if getattr(_cfg, "ENABLE_GESTURE_VOICE_TRIGGER",True) else "Disabled"
    _CFG_LOG_DIR       = getattr(_cfg, "GESTURE_LOG_DIR", "logs")
    _CFG_PHRASE_LIMIT  = str(getattr(_cfg, "VOICE_PHRASE_TIME_LIMIT", 30)) + "s"
    _CFG_OK            = True

except Exception as _cfg_err:
    print(f"[GUI] Config import warning: {_cfg_err} — using defaults")
    _CFG_HOTKEY        = "CTRL+ALT+V"
    _CFG_LANGUAGE      = "vi-VN"
    _CFG_CONTEXT       = "Unknown"
    _CFG_VOICE         = "Unknown"
    _CFG_VOICE_CMD     = "Unknown"
    _CFG_GESTURE_TRIG  = "Unknown"
    _CFG_LOG_DIR       = "logs"
    _CFG_PHRASE_LIMIT  = "30s"
    _CFG_OK            = False

# ==============================================================================
# Constants
# ==============================================================================

APP_TITLE   = "AI Gesture Mouse Controller"
APP_SUB     = "Desktop Control Panel"
APP_VERSION = "v1.0  |  Phase GUI-1"

WIN_W, WIN_H = 520, 800

# Colors
C_BG      = "#1a1a2e"
C_CARD    = "#16213e"
C_ACCENT  = "#e94560"
C_GREEN   = "#00b894"
C_YELLOW  = "#fdcb6e"
C_GRAY    = "#636e72"
C_TEXT    = "#dfe6e9"
C_SUB     = "#b2bec3"
C_SECTION = "#74b9ff"
C_LOG     = "#55efc4"
C_BTN     = "#2d3436"
C_BTN_HVR = "#4a5568"

STATUS_STOPPED  = "STOPPED"
STATUS_STARTING = "STARTING ..."
STATUS_RUNNING  = "RUNNING"


# ==============================================================================
# Main App
# ==============================================================================

class GestureControllerApp(ctk.CTk):
    """Desktop Control Panel — launches main.py as a subprocess."""

    def __init__(self):
        super().__init__()
        self._proc: "subprocess.Popen | None" = None
        self._analyze_thread: "threading.Thread | None" = None

        self._setup_window()
        self._build_ui()
        self._poll_proc()                           # Start 500ms polling timer
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------------------------------------------------------------------------
    # Window setup
    # -------------------------------------------------------------------------

    def _setup_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(fg_color=C_BG)

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=C_BG, width=WIN_W - 16)
        scroll.pack(fill="both", expand=True)

        f = scroll
        self._build_header(f)
        self._build_status(f)
        self._build_controls(f)
        self._build_quick_access(f)
        self._build_system_info(f)
        self._build_cheat_sheet(f)
        self._build_log_panel(f)
        self._build_footer(f)

    # --- Helpers ---

    def _section(self, parent, title: str):
        """Render a section divider label."""
        ctk.CTkLabel(
            parent, text=f"  {title}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C_SECTION, anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkFrame(parent, height=1, fg_color=C_SECTION).pack(
            fill="x", padx=16, pady=(0, 8)
        )

    def _card(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10, **kwargs)

    # --- Sections ---

    def _build_header(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=0, height=78)
        hdr.pack(fill="x", pady=(0, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text=APP_TITLE,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C_ACCENT,
        ).pack(pady=(16, 1))
        ctk.CTkLabel(
            hdr, text=APP_SUB,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_SUB,
        ).pack()

    def _build_status(self, parent):
        self._section(parent, "CONTROLLER STATUS")
        card = self._card(parent, height=52)
        card.pack(fill="x", padx=16, pady=(0, 4))
        card.pack_propagate(False)

        self._dot = ctk.CTkLabel(
            card, text="●",
            font=ctk.CTkFont(size=20),
            text_color=C_GRAY,
        )
        self._dot.pack(side="left", padx=(18, 6))

        self._status_lbl = ctk.CTkLabel(
            card, text=STATUS_STOPPED,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C_GRAY, anchor="w",
        )
        self._status_lbl.pack(side="left")

    def _build_controls(self, parent):
        self._section(parent, "CONTROLS")
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 4))

        self._btn_start = ctk.CTkButton(
            row, text="START CONTROLLER",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C_GREEN, hover_color="#00a381",
            height=42, corner_radius=8,
            command=self.start_controller,
        )
        self._btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_stop = ctk.CTkButton(
            row, text="STOP",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C_ACCENT, hover_color="#c0392b",
            height=42, corner_radius=8,
            state="disabled",
            command=self.stop_controller,
        )
        self._btn_stop.pack(side="left", expand=True, fill="x")

    def _build_quick_access(self, parent):
        self._section(parent, "QUICK ACCESS")
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(0, 4))

        btn_kw = dict(
            height=36, corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=C_BTN, hover_color=C_BTN_HVR,
        )

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkButton(
            row1, text="Open Logs Folder",
            command=self.open_logs, **btn_kw,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_analyze = ctk.CTkButton(
            row1, text="Analyze Logs",
            command=self.analyze_logs, **btn_kw,
        )
        self._btn_analyze.pack(side="left", expand=True, fill="x")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            row2, text="Open README",
            command=self.open_readme, **btn_kw,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            row2, text="Open Report (BAO CAO)",
            command=self.open_report, **btn_kw,
        ).pack(side="left", expand=True, fill="x")

    def _build_system_info(self, parent):
        self._section(parent, "SYSTEM CONFIGURATION")

        warn = "" if _CFG_OK else "  [defaults — config.py not loaded]"
        if warn:
            ctk.CTkLabel(
                parent, text=warn,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=C_YELLOW,
            ).pack(fill="x", padx=20, pady=(0, 4))

        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(0, 4))

        info = [
            ("Voice Hotkey",       _CFG_HOTKEY),
            ("Voice Language",     _CFG_LANGUAGE),
            ("Voice Input",        _CFG_VOICE),
            ("Voice Commands",     _CFG_VOICE_CMD),
            ("Gesture Trigger",    _CFG_GESTURE_TRIG),
            ("Context-Aware",      _CFG_CONTEXT),
            ("Max Phrase Length",  _CFG_PHRASE_LIMIT),
            ("Log Directory",      _CFG_LOG_DIR + "/"),
        ]
        for label, value in info:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(
                r, text=f"{label}:",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=C_SUB, width=148, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                r, text=value,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=C_TEXT, anchor="w",
            ).pack(side="left")

        ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

    def _build_cheat_sheet(self, parent):
        self._section(parent, "GESTURE REFERENCE")
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(0, 4))

        sections = [
            ("RIGHT HAND  (Cursor Control)", [
                ("Index finger only",            "Move Cursor"),
                ("Thumb+Index pinch  < 0.6s",    "Left Click"),
                ("Thumb+Index pinch >= 0.6s",    "Drag & Drop"),
                ("Thumb+Middle pinch",            "Right Click"),
                ("Fist + move vertically",        "Scroll Up / Down"),
            ]),
            ("LEFT HAND  (System Control)", [
                ("All 5 fingers, hold >= 3s",     "System Toggle ON / OFF"),
                ("4 fingers [0,1,1,1,1] + swipe", "Swipe Left / Right"),
                ("2 fingers [0,1,1,0,0] pinch",   "Zoom In / Out"),
                ("[0,1,1,1,0] hold 1.2s",          "Voice Trigger"),
            ]),
        ]

        for sec_title, rows in sections:
            ctk.CTkLabel(
                card, text=sec_title,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=C_SECTION, anchor="w",
            ).pack(fill="x", padx=14, pady=(10, 3))

            for gesture, action in rows:
                r = ctk.CTkFrame(card, fg_color="transparent")
                r.pack(fill="x", padx=14, pady=1)
                ctk.CTkLabel(
                    r, text=gesture,
                    font=ctk.CTkFont(family="Consolas", size=11),
                    text_color=C_SUB, width=230, anchor="w",
                ).pack(side="left")
                ctk.CTkLabel(
                    r, text=action,
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=C_TEXT, anchor="w",
                ).pack(side="left")

        ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

    def _build_log_panel(self, parent):
        self._section(parent, "ANALYZE OUTPUT")
        card = self._card(parent)
        card.pack(fill="x", padx=16, pady=(0, 4))

        self._log_box = ctk.CTkTextbox(
            card, height=160,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0d1117", text_color=C_LOG,
            wrap="word", state="disabled",
        )
        self._log_box.pack(fill="x", padx=10, pady=10)
        self._set_log("Click  'Analyze Logs'  to display statistics from the latest session.")

    def _build_footer(self, parent):
        ctk.CTkLabel(
            parent, text=APP_VERSION,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C_GRAY,
        ).pack(pady=(8, 14))

    # -------------------------------------------------------------------------
    # Controller lifecycle
    # -------------------------------------------------------------------------

    def start_controller(self):
        """Spawn main.py. Guard: no-op if a live process exists."""
        if self._proc is not None and self._proc.poll() is None:
            return  # Already running

        main_script = _BASE_DIR / "main.py"
        if not main_script.exists():
            self._set_log(f"[ERROR] main.py not found at:\n{main_script}")
            return

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(main_script)],
                cwd=str(_BASE_DIR),
                # stdout/stderr NOT redirected — avoids buffer deadlock.
                # main.py opens its own OpenCV window.
            )
        except Exception as exc:
            self._set_log(f"[ERROR] Failed to start controller:\n{exc}")
            return

        self._set_status(STATUS_STARTING, C_YELLOW)
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")

        # Verify process is still alive after 1.5s
        self.after(1500, self._confirm_running)

    def _confirm_running(self):
        if self._proc and self._proc.poll() is None:
            self._set_status(STATUS_RUNNING, C_GREEN)
        else:
            code = self._proc.returncode if self._proc else "N/A"
            self._set_log(
                f"[WARN] Controller exited immediately (exit code: {code}).\n"
                "Check that your webcam is connected and all dependencies are installed."
            )
            self._on_stopped()

    def stop_controller(self):
        """Request graceful stop: terminate → wait 3s → kill (in background thread)."""
        if self._proc is None or self._proc.poll() is not None:
            self._on_stopped()
            return

        try:
            self._proc.terminate()
        except Exception as exc:
            print(f"[GUI] terminate() warning: {exc}")

        # Wait / kill in background to keep GUI responsive
        threading.Thread(target=self._wait_then_kill, daemon=True).start()

    def _wait_then_kill(self):
        """Background thread: wait for process exit, force-kill if needed."""
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                self._proc.kill()
                print("[GUI] Process force-killed (did not exit within 3s).")
            except Exception as exc:
                print(f"[GUI] kill() warning: {exc}")
        except Exception as exc:
            print(f"[GUI] wait() warning: {exc}")
        finally:
            # Schedule UI update on the main thread
            self.after(0, self._on_stopped)

    def _on_stopped(self):
        """Update UI to STOPPED state (always called on main thread)."""
        self._set_status(STATUS_STOPPED, C_GRAY)
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")

    def _poll_proc(self):
        """Check every 500ms if the subprocess exited externally (e.g. user pressed Q)."""
        if self._proc is not None and self._proc.poll() is not None:
            self._on_stopped()
        self.after(500, self._poll_proc)

    # -------------------------------------------------------------------------
    # Quick access
    # -------------------------------------------------------------------------

    def open_logs(self):
        log_dir = _BASE_DIR / _CFG_LOG_DIR
        if not log_dir.exists():
            self._set_log(
                f"[INFO] Log directory '{_CFG_LOG_DIR}/' not found.\n"
                "Run the controller first to generate session log files."
            )
            return
        try:
            os.startfile(str(log_dir))
        except Exception as exc:
            self._set_log(f"[ERROR] Cannot open logs folder:\n{exc}")

    def analyze_logs(self):
        """Run analyze_logs.py in a background thread; show output via self.after()."""
        if self._analyze_thread and self._analyze_thread.is_alive():
            return  # Already running

        self._btn_analyze.configure(state="disabled", text="Analyzing ...")
        self._set_log("[INFO] Running analyze_logs.py ...")
        self._analyze_thread = threading.Thread(
            target=self._run_analyze, daemon=True
        )
        self._analyze_thread.start()

    def _run_analyze(self):
        """Worker: runs analyze_logs.py, posts result back to main thread."""
        script = _BASE_DIR / "analyze_logs.py"
        if not script.exists():
            self.after(0, lambda: self._finish_analyze("[ERROR] analyze_logs.py not found."))
            return

        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(_BASE_DIR),
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout.strip()
            if not output:
                output = result.stderr.strip() or "(No output — no log files found?)"
        except subprocess.TimeoutExpired:
            output = "[ERROR] analyze_logs.py timed out (>15s)."
        except Exception as exc:
            output = f"[ERROR] {exc}"

        self.after(0, lambda: self._finish_analyze(output))

    def _finish_analyze(self, text: str):
        self._set_log(text)
        self._btn_analyze.configure(state="normal", text="Analyze Logs")

    def open_readme(self):
        self._open_file("README.md")

    def open_report(self):
        self._open_file("BAO_CAO_HE_THONG.md")

    def _open_file(self, filename: str):
        path = _BASE_DIR / filename
        if not path.exists():
            self._set_log(f"[ERROR] File not found: {filename}")
            return
        try:
            os.startfile(str(path))
        except Exception as exc:
            self._set_log(f"[ERROR] Cannot open {filename}:\n{exc}")

    # -------------------------------------------------------------------------
    # UI helpers
    # -------------------------------------------------------------------------

    def _set_status(self, text: str, color: str):
        self._status_lbl.configure(text=text, text_color=color)
        self._dot.configure(text_color=color)

    def _set_log(self, text: str):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.insert("1.0", text)
        self._log_box.configure(state="disabled")

    # -------------------------------------------------------------------------
    # Window close
    # -------------------------------------------------------------------------

    def _on_close(self):
        """Terminate subprocess (if running) before destroying the window."""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            except Exception as exc:
                print(f"[GUI] Close cleanup warning: {exc}")
        self.destroy()


# ==============================================================================
# Entry point
# ==============================================================================

if __name__ == "__main__":
    app = GestureControllerApp()
    app.mainloop()

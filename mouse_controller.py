"""
mouse_controller.py - Module điều khiển chuột và hệ thống
=========================================================
Nhận action từ GestureRecognizer, thực thi lệnh điều khiển qua PyAutoGUI.

Trách nhiệm duy nhất:
  - Nhận gesture result dict → gọi PyAutoGUI tương ứng
  - Quản lý smoothing tọa độ chuột (tránh jitter)
  - Mapping tọa độ camera → màn hình
  - Không chứa logic nhận diện gesture
  - Execute action_name từ ActionRouter (Context-Aware Gestures)

Actions:
  - move_cursor(): Di chuyển con trỏ chuột
  - left_click(): Click chuột trái
  - double_click(): Double click chuột trái
  - right_click(): Click chuột phải
  - drag_start() / drag_move() / drag_end(): Kéo-thả
  - scroll(): Cuộn trang
  - swipe_action(): Swipe (context-aware nếu có ActionRouter)
  - zoom_in() / zoom_out(): Zoom (context-aware nếu có ActionRouter)
  - execute_action(): Thực thi action_name từ ActionRouter
"""

import pyautogui
import config as cfg
from utils import map_range, smooth_point, clamp

# Tắt failsafe và pause để tăng performance
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


class MouseController:
    """
    Class điều khiển chuột qua PyAutoGUI với smoothing.

    Attributes:
        screen_w, screen_h: Kích thước màn hình thực
        prev_x, prev_y: Tọa độ chuột frame trước (cho smoothing)
        is_dragging: Trạng thái đang kéo-thả
    """

    def __init__(self, smoothing_factor=cfg.SMOOTHING_FACTOR, action_router=None,
                 event_logger=None):
        self.screen_w, self.screen_h = pyautogui.size()
        self.smoothing_factor = smoothing_factor
        self.prev_x = self.screen_w // 2
        self.prev_y = self.screen_h // 2
        self.is_dragging = False
        self._click_freeze_until = 0    # Freeze cursor until this timestamp

        # --- Context-Aware Gestures (optional) ---
        self.action_router = action_router          # ActionRouter instance hoac None
        self.last_routed_action: str = "no_action"  # Action name tu lan route gan nhat
        self.last_routed_context: str = "default"   # Context tu lan route gan nhat
        self._action_warning_printed: set = set()   # Tranh spam warning cung 1 action

        # --- Gesture Logging (optional) ---
        self.event_logger = event_logger            # GestureLogger instance hoac None

    def process_gesture(self, gesture_result):
        """
        Xử lý gesture result — entry point chính.
        Dispatch gesture name → action tương ứng.
        """
        from gesture_recognition import (
            GESTURE_MOVE, GESTURE_LEFT_CLICK, GESTURE_DOUBLE_CLICK,
            GESTURE_RIGHT_CLICK,
            GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END,
            GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN,
            GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
            GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT
        )

        gesture = gesture_result["gesture"]

        # --- Move Cursor ---
        if gesture == GESTURE_MOVE:
            if gesture_result["cursor_pos"]:
                self.move_cursor(gesture_result["cursor_pos"],
                                 gesture_result.get("click_freeze_until", 0))

        # --- Left Click ---
        elif gesture == GESTURE_LEFT_CLICK:
            self.left_click(gesture_result.get("click_anchor"))

        # --- Double Click ---
        elif gesture == GESTURE_DOUBLE_CLICK:
            self.double_click(gesture_result.get("click_anchor"))

        # --- Right Click ---
        elif gesture == GESTURE_RIGHT_CLICK:
            self.right_click(gesture_result.get("click_anchor"))

        # --- Drag Start ---
        elif gesture == GESTURE_DRAG_START:
            if gesture_result["drag_pos"]:
                self.move_cursor(gesture_result["drag_pos"])
            self.drag_start()

        # --- Dragging ---
        elif gesture == GESTURE_DRAGGING:
            if gesture_result["drag_pos"]:
                self.drag_move(gesture_result["drag_pos"])

        # --- Drag End ---
        elif gesture == GESTURE_DRAG_END:
            self.drag_end()

        # --- Scroll ---
        elif gesture in (GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN):
            if gesture_result["scroll_delta"] is not None:
                self.scroll(gesture_result["scroll_delta"])

        # --- Swipe ---
        elif gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT):
            self.swipe_action(gesture)

        # --- Zoom ---
        elif gesture == GESTURE_ZOOM_IN:
            self.zoom_in()
        elif gesture == GESTURE_ZOOM_OUT:
            self.zoom_out()

    def move_cursor(self, camera_pos, click_freeze_until=0):
        """Di chuyển chuột với smoothing + ROI mapping + deadzone + freeze."""
        import time as _time

        # Freeze: không move nếu đang trong khoảng freeze sau click
        now = _time.time()
        freeze_ts = click_freeze_until or self._click_freeze_until
        if now < freeze_ts:
            return

        cam_x, cam_y = camera_pos

        # Clamp vào ROI
        cam_x = clamp(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX)
        cam_y = clamp(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX)

        # Map ROI → màn hình (thẳng, không đảo X vì đã flip mirror)
        screen_x = map_range(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX,
                             0, self.screen_w)
        screen_y = map_range(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX,
                             0, self.screen_h)

        # Smoothing
        smooth_x, smooth_y = smooth_point(
            self.prev_x, self.prev_y,
            screen_x, screen_y,
            self.smoothing_factor
        )

        # Clamp vào giới hạn màn hình
        smooth_x = clamp(int(smooth_x), 0, self.screen_w - 1)
        smooth_y = clamp(int(smooth_y), 0, self.screen_h - 1)

        # Deadzone: không move nếu target quá gần current (đứng yên → giảm rung)
        dx = abs(smooth_x - self.prev_x)
        dy = abs(smooth_y - self.prev_y)
        if dx <= cfg.MOVE_DEADZONE and dy <= cfg.MOVE_DEADZONE:
            return

        pyautogui.moveTo(smooth_x, smooth_y)
        self.prev_x = smooth_x
        self.prev_y = smooth_y

    def _move_to_anchor(self, anchor_cam_pos):
        """
        Di chuyển cursor tới vị trí anchor (camera coords) trước khi click.
        Bỏ qua smoothing để click chính xác tại đúng vị trí anchor.
        """
        if not anchor_cam_pos:
            return
        cam_x, cam_y = anchor_cam_pos
        cam_x = clamp(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX)
        cam_y = clamp(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX)
        screen_x = int(map_range(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX,
                                 0, self.screen_w))
        screen_y = int(map_range(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX,
                                 0, self.screen_h))
        screen_x = clamp(screen_x, 0, self.screen_w - 1)
        screen_y = clamp(screen_y, 0, self.screen_h - 1)
        pyautogui.moveTo(screen_x, screen_y)
        self.prev_x = screen_x
        self.prev_y = screen_y
        import time as _time
        self._click_freeze_until = _time.time() + cfg.CLICK_FREEZE_TIME

    def left_click(self, anchor_cam_pos=None):
        """Click chuot trai. Move to anchor truoc neu co."""
        if anchor_cam_pos:
            self._move_to_anchor(anchor_cam_pos)
        pyautogui.click()

    def double_click(self, anchor_cam_pos=None):
        """Double click chuot trai. Move to anchor truoc neu co."""
        if anchor_cam_pos:
            self._move_to_anchor(anchor_cam_pos)
        pyautogui.doubleClick()

    def right_click(self, anchor_cam_pos=None):
        """Click chuot phai. Move to anchor truoc neu co."""
        if anchor_cam_pos:
            self._move_to_anchor(anchor_cam_pos)
        pyautogui.rightClick()

    def drag_start(self):
        """Nhấn giữ chuột trái."""
        if not self.is_dragging:
            pyautogui.mouseDown(button='left')
            self.is_dragging = True

    def drag_move(self, camera_pos):
        """Di chuyển chuột trong khi đang drag."""
        if self.is_dragging:
            self.move_cursor(camera_pos)

    def drag_end(self):
        """Thả chuột trái."""
        if self.is_dragging:
            pyautogui.mouseUp(button='left')
            self.is_dragging = False

    def scroll(self, amount):
        """Cuộn trang."""
        pyautogui.scroll(int(amount))

    # ------------------------------------------------------------------
    # Context-Aware Action Executor
    # ------------------------------------------------------------------

    def execute_action(self, action_name: str) -> bool:
        """Thuc thi action_name bang pyautogui.

        Duoc goi boi swipe_action() va zoom_in()/zoom_out() khi co ActionRouter.
        Khong goi truc tiep tu process_gesture().

        Args:
            action_name: Ten action tu ActionRouter.resolve().

        Returns:
            True neu da thuc thi action, False neu no_action hoac khong hop le.
        """
        try:
            if action_name == "no_action":
                return False

            # --- Browser ---
            elif action_name == "browser_back":
                pyautogui.hotkey("alt", "left")
            elif action_name == "browser_forward":
                pyautogui.hotkey("alt", "right")

            # --- Presentation ---
            elif action_name == "next_slide":
                pyautogui.press("right")
            elif action_name == "previous_slide":
                pyautogui.press("left")

            # --- Document ---
            elif action_name == "page_down":
                pyautogui.press("pagedown")
            elif action_name == "page_up":
                pyautogui.press("pageup")

            # --- Zoom (browser / presentation / document) ---
            elif action_name in ("browser_zoom_in", "presentation_zoom_in", "document_zoom_in", "default_zoom_in"):
                pyautogui.hotkey("ctrl", "=")
            elif action_name in ("browser_zoom_out", "presentation_zoom_out", "document_zoom_out", "default_zoom_out"):
                pyautogui.hotkey("ctrl", "-")

            # --- Media (volume / track) ---
            elif action_name == "volume_up":
                pyautogui.press("volumeup")
            elif action_name == "volume_down":
                pyautogui.press("volumedown")
            elif action_name == "next_track":
                pyautogui.press("nexttrack")
            elif action_name == "previous_track":
                pyautogui.press("prevtrack")

            # --- Default swipe (Left=lùi, Right=tiến) ---
            elif action_name == "default_swipe_left":
                pyautogui.press("left")
            elif action_name == "default_swipe_right":
                pyautogui.press("right")

            else:
                # action_name chua duoc map -> bo qua, khong crash
                return False

            print(f"[ACTION] {action_name}")
            return True

        except Exception as e:
            # Media key (nexttrack/prevtrack/volumeup/volumedown) co the loi tren
            # mot so he thong. Print once per action_name, khong spam.
            if action_name not in self._action_warning_printed:
                print(f"[ACTION] Warning: execute_action('{action_name}') failed: {e}")
                self._action_warning_printed.add(action_name)
            return False

    # DEPRECATED: kept for backward compatibility — su dung context_manager.py thay the
    def get_active_window_title(self):
        """
        Lay title cua cua so dang active tren Windows.
        Dung ctypes (built-in), khong can cai them gi.
        Tra ve chuoi lowercase de so sanh keyword de hon.
        """
        import ctypes
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value.lower()
        except Exception:
            return ""

    # DEPRECATED: kept for backward compatibility — su dung context_manager.py thay the
    def detect_swipe_context(self, window_title):
        """
        Xac dinh context tu window title.

        Thu tu uu tien: slide > pdf > image > browser > default
        Ly do: Google Slides chay trong Chrome, nen 'slide' phai
        duoc check truoc 'browser'.

        Args:
            window_title: Title cua cua so active (da lowercase)

        Returns:
            str: "slide" | "pdf" | "image" | "browser" | "default"
        """
        # 1. Slide (uu tien cao nhat)
        for kw in cfg.SWIPE_SLIDE_KEYWORDS:
            if kw in window_title:
                return "slide"

        # 2. PDF
        for kw in cfg.SWIPE_PDF_KEYWORDS:
            if kw in window_title:
                return "pdf"

        # 3. Image
        for kw in cfg.SWIPE_IMAGE_KEYWORDS:
            if kw in window_title:
                return "image"

        # 4. Browser
        for kw in cfg.SWIPE_BROWSER_KEYWORDS:
            if kw in window_title:
                return "browser"

        # 5. Default
        return "default"

    # DEPRECATED: kept for backward compatibility — su dung action_router.py thay the
    def _resolve_swipe_mode(self):
        """
        Xac dinh swipe mode hien tai.
        Neu cfg.SWIPE_MODE = "auto" -> detect tu active window.
        Neu khac -> dung gia tri config truc tiep (manual override).

        Returns:
            (str, str): (mode, window_title_or_empty)
        """
        if cfg.SWIPE_MODE == "auto":
            title = self.get_active_window_title()
            context = self.detect_swipe_context(title)
            return context, title
        else:
            return cfg.SWIPE_MODE, ""

    def swipe_action(self, gesture_name):
        """
        Context-Aware Swipe — tu dong chon phim theo ung dung dang active.

        Neu co ActionRouter va ENABLE_CONTEXT_AWARE = True:
          gesture_name -> ActionRouter.resolve() -> execute_action()
        Neu khong:
          Giu logic cu (SWIPE_MODE / detect_swipe_context).
        """
        # --- Context-Aware path (ActionRouter) ---
        if cfg.ENABLE_CONTEXT_AWARE and self.action_router is not None:
            action_name = self.action_router.resolve(gesture_name)
            self.last_routed_action = action_name
            self.last_routed_context = self.action_router.get_last_context()
            print(f"[SWIPE] context={self.last_routed_context} -> {action_name}")
            executed = self.execute_action(action_name)
            # --- Log swipe event ---
            if self.event_logger is not None:
                try:
                    self.event_logger.log_event(
                        context=self.last_routed_context,
                        gesture=gesture_name,
                        action=action_name,
                        executed=bool(executed),
                        note="swipe",
                    )
                except Exception:
                    pass  # Logger loi khong anh huong app
            return executed

        # --- Legacy path (fallback) ---
        mode, title = self._resolve_swipe_mode()
        if title:
            print(f"[SWIPE] Active window: {title}")
        print(f"[SWIPE] Context: {mode}")

        if gesture_name == "Swipe Left":
            if mode == "pdf":
                pyautogui.press('pagedown')
                print("[ACTION] Swipe Left -> press('pagedown')")
            elif mode == "browser":
                pyautogui.hotkey('alt', 'right')
                print("[ACTION] Swipe Left -> hotkey('alt','right')")
            else:
                pyautogui.press('right')
                print("[ACTION] Swipe Left -> press('right')")

        elif gesture_name == "Swipe Right":
            if mode == "pdf":
                pyautogui.press('pageup')
                print("[ACTION] Swipe Right -> press('pageup')")
            elif mode == "browser":
                pyautogui.hotkey('alt', 'left')
                print("[ACTION] Swipe Right -> hotkey('alt','left')")
            else:
                pyautogui.press('left')
                print("[ACTION] Swipe Right -> press('left')")

    def zoom_in(self):
        """Zoom In - context-aware neu co ActionRouter, fallback Ctrl+=."""
        if cfg.ENABLE_CONTEXT_AWARE and self.action_router is not None:
            action_name = self.action_router.resolve("zoom_in")
            self.last_routed_action = action_name
            self.last_routed_context = self.action_router.get_last_context()
            print(f"[ZOOM] context={self.last_routed_context} -> {action_name}")
            executed = self.execute_action(action_name)
            if self.event_logger is not None:
                try:
                    self.event_logger.log_event(
                        context=self.last_routed_context,
                        gesture="Zoom In",
                        action=action_name,
                        executed=bool(executed),
                        note="zoom",
                    )
                except Exception:
                    pass
            return executed
        # Legacy
        pyautogui.hotkey('ctrl', '=')
        print("[ACTION] Zoom In -> Ctrl+=")

    def zoom_out(self):
        """Zoom Out - context-aware neu co ActionRouter, fallback Ctrl+-."""
        if cfg.ENABLE_CONTEXT_AWARE and self.action_router is not None:
            action_name = self.action_router.resolve("zoom_out")
            self.last_routed_action = action_name
            self.last_routed_context = self.action_router.get_last_context()
            print(f"[ZOOM] context={self.last_routed_context} -> {action_name}")
            executed = self.execute_action(action_name)
            if self.event_logger is not None:
                try:
                    self.event_logger.log_event(
                        context=self.last_routed_context,
                        gesture="Zoom Out",
                        action=action_name,
                        executed=bool(executed),
                        note="zoom",
                    )
                except Exception:
                    pass
            return executed
        # Legacy
        pyautogui.hotkey('ctrl', '-')
        print("[ACTION] Zoom Out -> Ctrl+-")

    def type_text(self, text):
        """
        Go text vao o dang duoc focus bang cach:
          1. Copy text vao clipboard qua Windows API (ctypes) -- KHONG steal focus
          2. Paste bang Ctrl+V

        Ly do dung ctypes thay vi tkinter:
          - tkinter.Tk() steal focus khoi browser du da withdraw()
          - Ctrl+V se paste vao cua so sai neu focus bi mat
          - ctypes goi thang Windows clipboard API, khong tao window, khong mat focus

        Args:
            text: Chuoi can go. Neu rong thi khong lam gi.
        """
        import time as _time
        import ctypes
        from ctypes import wintypes

        if not text:
            return

        try:
            # --- Copy text vao clipboard qua Windows API (khong steal focus) ---
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            kernel32 = ctypes.windll.kernel32
            user32   = ctypes.windll.user32

            # Khai bao restype de xu ly 64-bit pointer dung
            kernel32.GlobalAlloc.restype  = ctypes.c_void_p
            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalLock.restype   = ctypes.c_void_p
            kernel32.GlobalLock.argtypes  = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_bool
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype  = ctypes.c_bool
            user32.EmptyClipboard.restype = ctypes.c_bool
            user32.SetClipboardData.restype  = ctypes.c_void_p
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.CloseClipboard.restype = ctypes.c_bool

            text_bytes = text.encode('utf-16-le') + b'\x00\x00'

            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
            if not h_mem:
                raise RuntimeError("GlobalAlloc failed")

            mem_ptr = kernel32.GlobalLock(h_mem)
            if not mem_ptr:
                raise RuntimeError("GlobalLock failed")

            ctypes.memmove(mem_ptr, text_bytes, len(text_bytes))
            kernel32.GlobalUnlock(h_mem)

            if not user32.OpenClipboard(None):
                raise RuntimeError("OpenClipboard failed")
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            user32.CloseClipboard()

            # Delay nho truoc khi paste
            _time.sleep(cfg.VOICE_TYPING_SPEED)

            # Paste bang Ctrl+V vao cua so dang focus (browser van giu focus)
            pyautogui.hotkey('ctrl', 'v')

            print(f"[VOICE] Typed: '{text}'")

        except Exception as e:
            print(f"[VOICE] type_text error: {e}")

    def press_enter(self):
        """
        Nhan phim Enter.
        Dung sau type_text() neu VOICE_AUTO_ENTER = True.
        """
        pyautogui.press('enter')
        print("[VOICE] Pressed Enter")

    def get_screen_size(self):
        return (self.screen_w, self.screen_h)

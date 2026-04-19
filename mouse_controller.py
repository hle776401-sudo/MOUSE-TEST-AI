"""
mouse_controller.py - Module điều khiển chuột và hệ thống
=========================================================
Nhận action từ GestureRecognizer, thực thi lệnh điều khiển qua PyAutoGUI.

Trách nhiệm duy nhất:
  - Nhận gesture result dict → gọi PyAutoGUI tương ứng
  - Quản lý smoothing tọa độ chuột (tránh jitter)
  - Mapping tọa độ camera → màn hình
  - Không chứa logic nhận diện gesture

Actions:
  - move_cursor(): Di chuyển con trỏ chuột
  - left_click(): Click chuột trái
  - double_click(): Double click chuột trái
  - right_click(): Click chuột phải
  - drag_start() / drag_move() / drag_end(): Kéo-thả
  - scroll(): Cuộn trang
  - swipe_action(): Chuyển slide trình chiếu (Right/Left arrow)
  - zoom_in() / zoom_out(): Zoom (Ctrl+= / Ctrl+-)
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

    def __init__(self, smoothing_factor=cfg.SMOOTHING_FACTOR):
        self.screen_w, self.screen_h = pyautogui.size()
        self.smoothing_factor = smoothing_factor
        self.prev_x = self.screen_w // 2
        self.prev_y = self.screen_h // 2
        self.is_dragging = False
        self._click_freeze_until = 0   # Freeze cursor until this timestamp

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

    def swipe_action(self, gesture_name):
        """
        Hanh dong swipe — dieu khien trinh chieu / trinh duyet.

        Mapping:
          Vuot trai  = Noi dung ke tiep
          Vuot phai  = Noi dung truoc

        Config cfg.SWIPE_MODE:
          "arrow"   -> press('right'/'left')     (PowerPoint, Google Slides)
          "page"    -> press('pagedown'/'pageup') (PDF viewer)
          "browser" -> hotkey('alt','right'/'left') (trinh duyet web)
        """
        mode = cfg.SWIPE_MODE

        if gesture_name == "Swipe Left":
            if mode == "page":
                pyautogui.press('pagedown')
                print("[ACTION] Swipe Left -> press('pagedown')")
            elif mode == "browser":
                pyautogui.hotkey('alt', 'right')
                print("[ACTION] Swipe Left -> hotkey('alt','right')")
            else:
                pyautogui.press('right')
                print("[ACTION] Swipe Left -> press('right')")

        elif gesture_name == "Swipe Right":
            if mode == "page":
                pyautogui.press('pageup')
                print("[ACTION] Swipe Right -> press('pageup')")
            elif mode == "browser":
                pyautogui.hotkey('alt', 'left')
                print("[ACTION] Swipe Right -> hotkey('alt','left')")
            else:
                pyautogui.press('left')
                print("[ACTION] Swipe Right -> press('left')")

    def zoom_in(self):
        """Zoom In -> Ctrl + ="""
        pyautogui.hotkey('ctrl', '=')
        print("[ACTION] Zoom In -> Ctrl+=")

    def zoom_out(self):
        """Zoom Out -> Ctrl + -"""
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

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
  - swipe_action(): Hành động swipe (demo: chỉ print)
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
            GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT
        )

        gesture = gesture_result["gesture"]

        # --- Move Cursor ---
        if gesture == GESTURE_MOVE:
            if gesture_result["cursor_pos"]:
                self.move_cursor(gesture_result["cursor_pos"])

        # --- Left Click (không move cursor — vị trí đã đúng từ frame MOVE trước) ---
        elif gesture == GESTURE_LEFT_CLICK:
            self.left_click()

        # --- Double Click ---
        elif gesture == GESTURE_DOUBLE_CLICK:
            self.double_click()

        # --- Right Click ---
        elif gesture == GESTURE_RIGHT_CLICK:
            self.right_click()

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

        # --- Swipe (demo: chỉ hiển thị, chưa thực hiện action) ---
        elif gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT):
            self.swipe_action(gesture)

    def move_cursor(self, camera_pos):
        """Di chuyển chuột với smoothing + ROI mapping."""
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

        pyautogui.moveTo(smooth_x, smooth_y)
        self.prev_x = smooth_x
        self.prev_y = smooth_y

    def left_click(self):
        """Click chuột trái."""
        pyautogui.click()

    def double_click(self):
        """Double click chuột trái."""
        pyautogui.doubleClick()

    def right_click(self):
        """Click chuột phải."""
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
        Hành động swipe:
          Swipe Left  → Alt+Left  (Back trên trình duyệt / Explorer)
          Swipe Right → Alt+Right (Forward trên trình duyệt / Explorer)
        """
        if gesture_name == "Swipe Left":
            pyautogui.hotkey('alt', 'left')
            print("[SWIPE] ← Back")
        elif gesture_name == "Swipe Right":
            pyautogui.hotkey('alt', 'right')
            print("[SWIPE] → Forward")

    def get_screen_size(self):
        return (self.screen_w, self.screen_h)

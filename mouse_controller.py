"""
mouse_controller.py - Module điều khiển chuột và hệ thống
=========================================================
Nhận action từ GestureRecognizer, thực thi lệnh điều khiển qua PyAutoGUI.

Trách nhiệm duy nhất:
  - Nhận gesture result dict → gọi PyAutoGUI tương ứng
  - Quản lý smoothing tọa độ chuột (tránh jitter)
  - Mapping tọa độ camera → màn hình
  - Không chứa logic nhận diện gesture (đó là việc của gesture_recognition.py)

MVP Actions:
  - move_cursor(): Di chuyển con trỏ chuột
  - left_click(): Click chuột trái
  - right_click(): Click chuột phải
  - drag_start() / drag_move() / drag_end(): Kéo-thả
  - scroll(): Cuộn trang
"""

import pyautogui
import config as cfg
from utils import map_range, smooth_point, clamp

# Tắt PyAutoGUI failsafe (di chuột vào góc trái-trên sẽ không crash)
# Lưu ý: Trong production nên để True để an toàn
pyautogui.FAILSAFE = False

# Tắt pause mặc định của PyAutoGUI (tăng performance)
pyautogui.PAUSE = 0


class MouseController:
    """
    Class điều khiển chuột qua PyAutoGUI với smoothing.

    Quy trình:
    1. Nhận tọa độ từ camera (640x480)
    2. Clamp vào vùng ROI
    3. Map sang tọa độ màn hình (ví dụ 1920x1080)
    4. Smoothing bằng linear interpolation
    5. Gọi PyAutoGUI để di chuyển/click/drag/scroll

    Attributes:
        screen_w, screen_h: Kích thước màn hình thực
        prev_x, prev_y: Tọa độ chuột frame trước (cho smoothing)
        is_dragging: Trạng thái đang kéo-thả
    """

    def __init__(self, smoothing_factor=cfg.SMOOTHING_FACTOR):
        """
        Khởi tạo MouseController.

        Args:
            smoothing_factor: Hệ số làm mượt chuột (>= 1, càng cao càng mượt)
        """
        # Kích thước màn hình
        self.screen_w, self.screen_h = pyautogui.size()

        # Smoothing
        self.smoothing_factor = smoothing_factor
        self.prev_x = self.screen_w // 2   # Bắt đầu ở giữa màn hình
        self.prev_y = self.screen_h // 2

        # Trạng thái drag
        self.is_dragging = False

    def process_gesture(self, gesture_result):
        """
        Xử lý gesture result từ GestureRecognizer — entry point chính.

        Args:
            gesture_result: Dict từ GestureRecognizer.recognize() với các key:
                - "gesture": Tên cử chỉ (str)
                - "cursor_pos": Tọa độ camera (tuple hoặc None)
                - "scroll_delta": Giá trị scroll (int hoặc None)
                - "drag_pos": Tọa độ drag camera (tuple hoặc None)
                - "system_active": Trạng thái hệ thống (bool)
        """
        # Import gesture names tại đây để tránh circular import
        from gesture_recognition import (
            GESTURE_MOVE, GESTURE_LEFT_CLICK, GESTURE_RIGHT_CLICK,
            GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END,
            GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN
        )

        gesture = gesture_result["gesture"]

        # --- Move Cursor ---
        if gesture == GESTURE_MOVE:
            if gesture_result["cursor_pos"]:
                self.move_cursor(gesture_result["cursor_pos"])

        # --- Left Click ---
        elif gesture == GESTURE_LEFT_CLICK:
            if gesture_result["cursor_pos"]:
                self.move_cursor(gesture_result["cursor_pos"])
            self.left_click()

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

    def move_cursor(self, camera_pos):
        """
        Di chuyển con trỏ chuột với smoothing.

        Quy trình:
        1. Clamp tọa độ camera vào vùng ROI
        2. Map từ ROI → tọa độ màn hình qua np.interp
        3. Đảo trục X (vì camera mirror)
        4. Smooth bằng linear interpolation
        5. Di chuyển chuột

        Args:
            camera_pos: Tuple (x, y) tọa độ từ camera (pixels)
        """
        cam_x, cam_y = camera_pos

        # Step 1: Clamp vào vùng ROI
        cam_x = clamp(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX)
        cam_y = clamp(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX)

        # Step 2: Map từ ROI → màn hình
        # Frame đã được flip mirror trong main.py (cv2.flip),
        # nên mapping thẳng (không đảo X nữa)
        screen_x = map_range(cam_x, cfg.ROI_X_MIN, cfg.ROI_X_MAX,
                             0, self.screen_w)
        screen_y = map_range(cam_y, cfg.ROI_Y_MIN, cfg.ROI_Y_MAX,
                             0, self.screen_h)

        # Step 3: Smoothing
        smooth_x, smooth_y = smooth_point(
            self.prev_x, self.prev_y,
            screen_x, screen_y,
            self.smoothing_factor
        )

        # Step 4: Clamp vào giới hạn màn hình (an toàn)
        smooth_x = clamp(int(smooth_x), 0, self.screen_w - 1)
        smooth_y = clamp(int(smooth_y), 0, self.screen_h - 1)

        # Step 5: Di chuyển
        pyautogui.moveTo(smooth_x, smooth_y)

        # Lưu vị trí cho frame sau
        self.prev_x = smooth_x
        self.prev_y = smooth_y

    def left_click(self):
        """
        Thực hiện click chuột trái tại vị trí hiện tại.
        """
        pyautogui.click()

    def right_click(self):
        """
        Thực hiện click chuột phải tại vị trí hiện tại.
        """
        pyautogui.rightClick()

    def drag_start(self):
        """
        Bắt đầu kéo-thả: nhấn giữ chuột trái.
        """
        if not self.is_dragging:
            pyautogui.mouseDown(button='left')
            self.is_dragging = True

    def drag_move(self, camera_pos):
        """
        Di chuyển chuột trong khi đang kéo-thả.

        Args:
            camera_pos: Tuple (x, y) tọa độ từ camera
        """
        if self.is_dragging:
            self.move_cursor(camera_pos)

    def drag_end(self):
        """
        Kết thúc kéo-thả: thả chuột trái.
        """
        if self.is_dragging:
            pyautogui.mouseUp(button='left')
            self.is_dragging = False

    def scroll(self, amount):
        """
        Cuộn trang.

        Args:
            amount: Giá trị scroll (dương = lên, âm = xuống)
        """
        pyautogui.scroll(int(amount))

    def get_screen_size(self):
        """
        Lấy kích thước màn hình hiện tại.

        Returns:
            Tuple (width, height)
        """
        return (self.screen_w, self.screen_h)

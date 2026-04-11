"""
gesture_recognition.py - Module nhận diện cử chỉ bàn tay (Rule-based)
=====================================================================
Phân tích dữ liệu landmarks từ HandDetector để nhận diện cử chỉ.

Kiến trúc:
  - GestureRecognizer: Class chính xử lý nhận diện
  - Unified Pinch Handler: Gộp Click và Drag vào 1 flow duy nhất
    + Pinch ngắn (< 250ms) rồi thả = Left Click
    + Pinch giữ lâu (>= 250ms) = Drag
  - Cooldown/Debounce: Chống kích hoạt trùng lặp cho event gestures
  - Phân loại gesture: EVENT (click, toggle) vs CONTINUOUS (move, scroll, drag)

MVP Gestures:
  1. Move Cursor      - Ngón trỏ giơ lên (chỉ trỏ)
  2. Left Click       - Thumb + Index pinch ngắn (< 250ms)
  3. Right Click      - Thumb + Middle pinch
  4. Drag and Drop    - Thumb + Index pinch giữ lâu (>= 250ms)
  5. Scroll           - Nắm tay + di chuyển dọc
  6. System On/Off    - 5 ngón tay giơ + giữ 3 giây

Phase 2 (sau khi MVP ổn):
  7. Double Click     - 2 lần left click nhanh
  8. Zoom In/Out      - Thumb + Index khoảng cách thay đổi
  9. Swipe            - Di chuyển ngang nhanh
"""

import time
import config as cfg
from utils import calculate_distance, cooldown_passed


# ==============================================================================
# GESTURE NAMES (hằng số tên cử chỉ)
# ==============================================================================
GESTURE_NONE = "None"
GESTURE_MOVE = "Move Cursor"
GESTURE_LEFT_CLICK = "Left Click"
GESTURE_RIGHT_CLICK = "Right Click"
GESTURE_DRAG_START = "Drag Start"
GESTURE_DRAGGING = "Dragging"
GESTURE_DRAG_END = "Drag End"
GESTURE_SCROLL_UP = "Scroll Up"
GESTURE_SCROLL_DOWN = "Scroll Down"
GESTURE_SYSTEM_TOGGLE = "System Toggle"
GESTURE_OPEN_PALM = "Open Palm"       # 5 ngón giơ (trước khi đủ thời gian toggle)

# Phase 2 gesture names (chưa dùng trong MVP)
# GESTURE_DOUBLE_CLICK = "Double Click"
# GESTURE_ZOOM_IN = "Zoom In"
# GESTURE_ZOOM_OUT = "Zoom Out"


# ==============================================================================
# PINCH STATE MACHINE (Unified Click + Drag)
# ==============================================================================
class PinchState:
    """
    Enum trạng thái pinch — dùng chung cho cả Click và Drag.
    Click và Drag đều bắt đầu bằng pinch thumb-index, chỉ khác ở thời gian giữ.
    """
    IDLE = "idle"             # Không có pinch
    PREPARING = "preparing"   # Đang pinch, chờ phân biệt click vs drag
    DRAGGING = "dragging"     # Đã xác nhận là drag (giữ > threshold)


# ==============================================================================
# GESTURE RECOGNIZER
# ==============================================================================
class GestureRecognizer:
    """
    Class nhận diện cử chỉ bàn tay dựa trên luật (rule-based).

    Quy trình xử lý mỗi frame:
    1. Nhận landmark_list và fingers_up từ HandDetector
    2. Kiểm tra system toggle trước (ưu tiên cao nhất)
    3. Nếu system ON → nhận diện gesture theo priority:
       Pinch (Click/Drag) > Right Click > Scroll > Move
    4. Trả về tên gesture + dữ liệu bổ sung (tọa độ, hướng scroll, v.v.)

    Attributes:
        system_active: Trạng thái hệ thống ON/OFF
        pinch_state: Trạng thái pinch hiện tại (IDLE/PREPARING/DRAGGING)
        current_gesture: Tên cử chỉ đang nhận diện
    """

    def __init__(self):
        """Khởi tạo GestureRecognizer với tất cả state và timer."""

        # --- Trạng thái hệ thống ---
        self.system_active = cfg.SYSTEM_ACTIVE_DEFAULT
        self.current_gesture = GESTURE_NONE

        # --- System Toggle ---
        self._toggle_start_time = 0         # Thời điểm bắt đầu giơ 5 ngón
        self._toggle_active = False          # Đang đếm thời gian toggle?
        self._toggle_cooldown_time = 0       # Cooldown sau khi toggle

        # --- Unified Pinch (Click + Drag) ---
        self.pinch_state = PinchState.IDLE
        self._pinch_start_time = 0           # Thời điểm bắt đầu pinch
        self._left_click_time = 0            # Thời điểm left click cuối (cooldown)

        # --- Right Click (Thumb + Middle — flow riêng, không conflic với pinch) ---
        self._right_click_time = 0           # Thời điểm right click cuối
        self._right_click_was_pinching = False

        # --- Scroll ---
        self._scroll_prev_y = None           # Tọa độ Y trước đó của bàn tay

        # --- Zoom (Phase 2 - chưa dùng trong MVP) ---
        self._zoom_prev_distance = None
        self._zoom_cooldown_time = 0

        # --- Velocity tracking ---
        self._prev_index_pos = None          # Vị trí ngón trỏ frame trước
        self._prev_hand_center = None        # Vị trí tâm bàn tay frame trước

    def recognize(self, landmark_list, fingers, palm_size=0, hand_center=None):
        """
        Nhận diện cử chỉ chính — gọi mỗi frame.

        Args:
            landmark_list: List [(id, x, y), ...] từ HandDetector.find_position()
            fingers: List [thumb, index, middle, ring, pinky] từ fingers_up()
            palm_size: Kích thước bàn tay (pixel) từ get_palm_size()
            hand_center: Tuple (cx, cy) tâm bàn tay từ get_hand_center()

        Returns:
            dict: Kết quả nhận diện với các key:
                - "gesture": Tên cử chỉ (str)
                - "cursor_pos": Tọa độ ngón trỏ nếu cần di chuyển (tuple hoặc None)
                - "scroll_delta": Giá trị scroll (int hoặc None)
                - "drag_pos": Tọa độ khi kéo (tuple hoặc None)
                - "system_active": Trạng thái hệ thống (bool)
        """
        now = time.time()

        # Kết quả mặc định
        result = {
            "gesture": GESTURE_NONE,
            "cursor_pos": None,
            "scroll_delta": None,
            "drag_pos": None,
            "system_active": self.system_active
        }

        # Kiểm tra dữ liệu đầu vào
        if not landmark_list or len(landmark_list) < 21 or not fingers:
            self._reset_continuous_states()
            self.current_gesture = GESTURE_NONE
            return result

        # ------------------------------------------------------------------
        # STEP 1: SYSTEM TOGGLE (luôn kiểm tra, bất kể system ON/OFF)
        # ------------------------------------------------------------------
        toggle_result = self._check_system_toggle(fingers, now)
        if toggle_result is not None:
            result["gesture"] = toggle_result
            result["system_active"] = self.system_active
            self.current_gesture = toggle_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # Nếu system OFF → chỉ hiển thị trạng thái, không xử lý gesture
        if not self.system_active:
            if sum(fingers) == 5:
                result["gesture"] = GESTURE_OPEN_PALM
            self._reset_continuous_states()
            self.current_gesture = result["gesture"]
            return result

        # ------------------------------------------------------------------
        # STEP 2: NHẬN DIỆN CỬ CHỈ (System ON)
        # Priority: Pinch (Click/Drag) > Right Click > Scroll > Move
        # ------------------------------------------------------------------

        # Lấy tọa độ các landmarks cần thiết
        thumb_tip = (landmark_list[cfg.THUMB_TIP][1], landmark_list[cfg.THUMB_TIP][2])
        index_tip = (landmark_list[cfg.INDEX_TIP][1], landmark_list[cfg.INDEX_TIP][2])
        middle_tip = (landmark_list[cfg.MIDDLE_TIP][1], landmark_list[cfg.MIDDLE_TIP][2])

        # Tính khoảng cách
        thumb_index_dist = calculate_distance(thumb_tip, index_tip)
        thumb_middle_dist = calculate_distance(thumb_tip, middle_tip)

        # Tính threshold (adaptive theo palm_size)
        pinch_threshold = self._get_pinch_threshold(palm_size)

        # --- 2A: UNIFIED PINCH — Click + Drag (Priority cao nhất) ---
        pinch_result = self._check_pinch_action(
            fingers, index_tip, thumb_index_dist, pinch_threshold, now
        )
        if pinch_result is not None:
            result["gesture"] = pinch_result
            # Gán vị trí tùy theo loại gesture
            if pinch_result == GESTURE_LEFT_CLICK:
                result["cursor_pos"] = index_tip
            elif pinch_result in (GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END):
                result["drag_pos"] = index_tip
            self.current_gesture = pinch_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2B: RIGHT CLICK (Thumb + Middle pinch — flow riêng) ---
        right_click_result = self._check_right_click(
            fingers, thumb_middle_dist, pinch_threshold, now
        )
        if right_click_result is not None:
            result["gesture"] = right_click_result
            self.current_gesture = right_click_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2C: SCROLL (Nắm tay + di chuyển dọc) ---
        scroll_result = self._check_scroll(fingers, hand_center)
        if scroll_result is not None:
            result["gesture"] = scroll_result[0]
            result["scroll_delta"] = scroll_result[1]
            self.current_gesture = scroll_result[0]
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2D: MOVE CURSOR (Chỉ ngón trỏ giơ lên) ---
        move_result = self._check_move_cursor(fingers, index_tip)
        if move_result is not None:
            result["gesture"] = GESTURE_MOVE
            result["cursor_pos"] = move_result
            self.current_gesture = GESTURE_MOVE
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # Không nhận diện được gesture nào
        self.current_gesture = GESTURE_NONE
        self._update_prev_positions(landmark_list, hand_center)
        return result

    # ======================================================================
    # PRIVATE: SYSTEM TOGGLE
    # ======================================================================
    def _check_system_toggle(self, fingers, now):
        """
        Kiểm tra cử chỉ bật/tắt hệ thống.
        Rule: Giơ 5 ngón tay giữ liên tục >= SYSTEM_TOGGLE_HOLD_TIME giây.

        Sử dụng sliding window: bắt đầu đếm khi 5 ngón giơ, reset nếu
        có ngón nào cụp trước khi đủ thời gian.

        Returns:
            str: Tên gesture nếu toggle xảy ra, None nếu không
        """
        # Cooldown sau khi vừa toggle (tránh toggle liên tục)
        if not cooldown_passed(self._toggle_cooldown_time,
                               cfg.SYSTEM_TOGGLE_COOLDOWN, now):
            return None

        finger_count = sum(fingers)

        if finger_count == cfg.SYSTEM_TOGGLE_FINGERS:
            if not self._toggle_active:
                # Bắt đầu đếm thời gian
                self._toggle_start_time = now
                self._toggle_active = True
                return GESTURE_OPEN_PALM  # Feedback: đang giơ 5 ngón

            # Đang đếm → kiểm tra đã đủ thời gian chưa
            elapsed = now - self._toggle_start_time
            if elapsed >= cfg.SYSTEM_TOGGLE_HOLD_TIME:
                # Toggle!
                self.system_active = not self.system_active
                self._toggle_active = False
                self._toggle_cooldown_time = now
                self._reset_continuous_states()
                return GESTURE_SYSTEM_TOGGLE

            # Chưa đủ thời gian, trả về OPEN_PALM làm feedback
            return GESTURE_OPEN_PALM
        else:
            # Có ngón cụp → reset đếm
            self._toggle_active = False
            return None

    # ======================================================================
    # PRIVATE: UNIFIED PINCH (Click + Drag)
    # ======================================================================
    def _check_pinch_action(self, fingers, index_tip, thumb_index_dist,
                            threshold, now):
        """
        Unified Pinch Handler — gộp Left Click và Drag vào 1 flow.

        Flow:
          Thumb + Index pinch detected → vào PREPARING
          ├─ Thả trước PINCH_HOLD_THRESHOLD (250ms) → LEFT_CLICK
          ├─ Giữ >= PINCH_HOLD_THRESHOLD → DRAGGING, emit DRAG_START
          └─ Đang DRAGGING mà thả → DRAG_END, về IDLE

        Tại sao gộp? Vì click và drag đều bắt đầu bằng cùng 1 gesture
        (thumb-index pinch). Nếu tách riêng, drag state machine sẽ
        "nuốt" mất left click do tranh chấp ưu tiên.

        Args:
            fingers: List [thumb, index, middle, ring, pinky]
            index_tip: Tuple (x, y) tọa độ đầu ngón trỏ
            thumb_index_dist: Khoảng cách pixel thumb-index
            threshold: Ngưỡng pinch (pixels, đã adaptive)
            now: Timestamp hiện tại

        Returns:
            str: Gesture name nếu có action, None nếu không
        """
        is_pinching = thumb_index_dist < threshold

        # --- State: IDLE ---
        if self.pinch_state == PinchState.IDLE:
            if is_pinching and fingers[1] == 1:
                # Bắt đầu pinch → chuyển sang PREPARING
                self.pinch_state = PinchState.PREPARING
                self._pinch_start_time = now
            return None  # Chưa có action

        # --- State: PREPARING (đang pinch, chờ phân biệt click vs drag) ---
        if self.pinch_state == PinchState.PREPARING:
            if not is_pinching:
                # Thả sớm → LEFT CLICK (pinch ngắn < hold_threshold)
                self.pinch_state = PinchState.IDLE

                # Check cooldown để tránh click liên tục
                if cooldown_passed(self._left_click_time,
                                   cfg.CLICK_COOLDOWN, now):
                    self._left_click_time = now
                    return GESTURE_LEFT_CLICK
                return None  # Trong cooldown, bỏ qua

            # Vẫn đang pinch → kiểm tra đã đủ lâu chưa
            hold_duration = now - self._pinch_start_time
            if hold_duration >= cfg.PINCH_HOLD_THRESHOLD:
                # Đủ lâu → xác nhận là DRAG
                self.pinch_state = PinchState.DRAGGING
                return GESTURE_DRAG_START

            return None  # Chưa đủ lâu, chờ tiếp

        # --- State: DRAGGING ---
        if self.pinch_state == PinchState.DRAGGING:
            if not is_pinching:
                # Thả ra → về IDLE, emit DRAG_END đúng 1 lần
                self.pinch_state = PinchState.IDLE
                return GESTURE_DRAG_END

            # Vẫn đang pinch → tiếp tục drag
            return GESTURE_DRAGGING

        return None

    # ======================================================================
    # PRIVATE: MOVE CURSOR
    # ======================================================================
    def _check_move_cursor(self, fingers, index_tip):
        """
        Kiểm tra cử chỉ di chuyển chuột.
        Rule: Chỉ ngón trỏ giơ lên, 3 ngón còn lại (giữa, áp út, út) cụp.
        Ngón cái có thể giơ/cụp tùy tư thế tay.

        Returns:
            Tuple (x, y): Tọa độ ngón trỏ nếu là move gesture, None nếu không
        """
        if (fingers[1] == 1 and
            fingers[2] == 0 and
            fingers[3] == 0 and
            fingers[4] == 0):
            return index_tip
        return None

    # ======================================================================
    # PRIVATE: RIGHT CLICK
    # ======================================================================
    def _check_right_click(self, fingers, thumb_middle_dist, threshold, now):
        """
        Kiểm tra cử chỉ click phải.
        Rule: Thumb + Middle finger pinch (chạm rồi thả).
        Yêu cầu ngón giữa phải giơ lên (fingers[2] == 1).

        Dùng edge detection tương tự left click: phát hiện khoảnh khắc THẢ.

        Args:
            fingers: List [thumb, index, middle, ring, pinky]
            thumb_middle_dist: Khoảng cách pixel thumb-middle
            threshold: Ngưỡng pinch (pixels, đã adaptive)
            now: Timestamp hiện tại

        Returns:
            str: GESTURE_RIGHT_CLICK nếu phát hiện, None nếu không
        """
        # Ngón giữa phải giơ lên
        if fingers[2] == 0:
            self._right_click_was_pinching = False
            return None

        is_pinching = thumb_middle_dist < threshold

        # EDGE DETECTION: phát hiện khoảnh khắc THẢ pinch
        if self._right_click_was_pinching and not is_pinching:
            if cooldown_passed(self._right_click_time, cfg.CLICK_COOLDOWN, now):
                self._right_click_time = now
                self._right_click_was_pinching = False
                return GESTURE_RIGHT_CLICK

        self._right_click_was_pinching = is_pinching
        return None

    # ======================================================================
    # PRIVATE: SCROLL
    # ======================================================================
    def _check_scroll(self, fingers, hand_center):
        """
        Kiểm tra cử chỉ cuộn (scroll).
        Rule: Nắm tay (4 ngón chính cụp) + di chuyển bàn tay theo trục Y.

        Scroll liên tục (continuous) — không cần cooldown.
        Tốc độ scroll được kiểm soát bằng SCROLL_SENSITIVITY (ngưỡng delta tối thiểu).

        Returns:
            Tuple (gesture_name, scroll_amount) nếu scroll, None nếu không
        """
        # Kiểm tra nắm tay: 4 ngón chính phải cụp
        is_fist = (fingers[1] == 0 and fingers[2] == 0 and
                   fingers[3] == 0 and fingers[4] == 0)

        if not is_fist or hand_center is None:
            self._scroll_prev_y = None
            return None

        current_y = hand_center[1]

        if self._scroll_prev_y is None:
            # Frame đầu tiên nắm tay → lưu vị trí, chưa scroll
            self._scroll_prev_y = current_y
            return None

        # Tính delta Y (trong OpenCV, Y tăng = xuống dưới)
        delta_y = current_y - self._scroll_prev_y

        if abs(delta_y) >= cfg.SCROLL_SENSITIVITY:
            self._scroll_prev_y = current_y  # Cập nhật vị trí

            if delta_y > 0:
                # Tay di xuống → Scroll Down
                return (GESTURE_SCROLL_DOWN, -cfg.SCROLL_SPEED)
            else:
                # Tay di lên → Scroll Up
                return (GESTURE_SCROLL_UP, cfg.SCROLL_SPEED)

        return None

    # ======================================================================
    # PRIVATE: HELPER METHODS
    # ======================================================================
    def _reset_continuous_states(self):
        """
        Reset tất cả trạng thái continuous gesture.
        Gọi khi: mất tracking, system toggle, hoặc chuyển gesture.
        """
        # Pinch: về IDLE trực tiếp (không emit event khi reset)
        self.pinch_state = PinchState.IDLE

        # Scroll
        self._scroll_prev_y = None

        # Zoom (Phase 2)
        self._zoom_prev_distance = None

        # Right click state
        self._right_click_was_pinching = False

        # Previous positions
        self._prev_index_pos = None
        self._prev_hand_center = None

    def _update_prev_positions(self, landmark_list, hand_center):
        """
        Cập nhật vị trí frame trước cho velocity tracking.
        """
        if landmark_list and len(landmark_list) > cfg.INDEX_TIP:
            self._prev_index_pos = (
                landmark_list[cfg.INDEX_TIP][1],
                landmark_list[cfg.INDEX_TIP][2]
            )
        self._prev_hand_center = hand_center

    def get_toggle_progress(self):
        """
        Lấy tiến trình toggle (0.0 - 1.0) để hiển thị progress bar.

        Returns:
            float: 0.0 nếu không đang toggle, 0.0-1.0 nếu đang đếm
        """
        if not self._toggle_active:
            return 0.0

        elapsed = time.time() - self._toggle_start_time
        progress = min(elapsed / cfg.SYSTEM_TOGGLE_HOLD_TIME, 1.0)
        return progress

    def get_state_info(self):
        """
        Lấy thông tin trạng thái hiện tại của recognizer (dùng cho debug).

        Returns:
            dict: Thông tin debug
        """
        return {
            "system_active": self.system_active,
            "current_gesture": self.current_gesture,
            "pinch_state": self.pinch_state,
            "toggle_progress": self.get_toggle_progress(),
            "right_click_pinching": self._right_click_was_pinching,
        }

    # ======================================================================
    # PRIVATE: THRESHOLD HELPERS
    # ======================================================================
    def _get_pinch_threshold(self, palm_size):
        """
        Tính ngưỡng pinch: adaptive theo palm_size nếu có, fallback pixel cố định.

        Args:
            palm_size: Kích thước bàn tay (pixel) từ HandDetector.get_palm_size()

        Returns:
            float: Ngưỡng khoảng cách (pixels) để xác định pinch
        """
        if palm_size > 0:
            # Adaptive: ngưỡng tỷ lệ theo kích thước bàn tay
            return palm_size * cfg.PINCH_THRESHOLD_NORMALIZED
        else:
            # Fallback: dùng giá trị pixel cố định từ config
            return cfg.CLICK_DISTANCE_THRESHOLD

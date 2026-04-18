"""
gesture_recognition.py - Module nhận diện cử chỉ bàn tay (Rule-based)
=====================================================================
Phân tích dữ liệu landmarks từ HandDetector để nhận diện cử chỉ.

Kiến trúc:
  - GestureRecognizer: Class chính xử lý nhận diện
  - Unified Pinch Handler: Click + Drag + Double Click trong 1 flow
  - Zoom Handler: Index + Middle guard, thumb-index distance delta
  - Swipe Handler: Open palm + chuyển động ngang nhanh
  - Hysteresis: Ngưỡng enter/exit riêng để tránh flickering
  - Post-action cooldown: Neutral gap sau event gestures

Gestures:
  1. Move Cursor      - Ngón trỏ giơ lên (chỉ trỏ)
  2. Left Click       - Thumb + Index pinch ngắn (< 300ms)
  3. Double Click     - 2 lần Left Click liên tiếp trong 0.5s
  4. Right Click      - Thumb + Middle pinch
  5. Drag and Drop    - Thumb + Index pinch giữ lâu (>= 300ms)
  6. Scroll           - Nắm tay + di chuyển dọc
  7. Swipe Left/Right - Mở bàn tay + vuốt ngang nhanh
  8. Zoom In/Out      - Index + Middle guard, thumb-index distance delta
  9. System On/Off    - 5 ngón tay giơ + giữ 3 giây
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
GESTURE_DOUBLE_CLICK = "Double Click"
GESTURE_RIGHT_CLICK = "Right Click"
GESTURE_DRAG_START = "Drag Start"
GESTURE_DRAGGING = "Dragging"
GESTURE_DRAG_END = "Drag End"
GESTURE_SCROLL_UP = "Scroll Up"
GESTURE_SCROLL_DOWN = "Scroll Down"
GESTURE_SWIPE_LEFT = "Swipe Left"
GESTURE_SWIPE_RIGHT = "Swipe Right"
GESTURE_ZOOM_IN = "Zoom In"
GESTURE_ZOOM_OUT = "Zoom Out"
GESTURE_SYSTEM_TOGGLE = "System Toggle"
GESTURE_OPEN_PALM = "Open Palm"


# ==============================================================================
# PINCH STATE MACHINE (Unified Click + Drag)
# ==============================================================================
class PinchState:
    """Trạng thái pinch — dùng chung cho Click, Double Click, và Drag."""
    IDLE = "idle"
    PREPARING = "preparing"   # Đang pinch, chờ phân biệt click vs drag
    DRAGGING = "dragging"     # Đã xác nhận là drag


# ==============================================================================
# GESTURE RECOGNIZER
# ==============================================================================
class GestureRecognizer:
    """
    Class nhận diện cử chỉ bàn tay dựa trên luật (rule-based).

    Pipeline mỗi frame:
    1. System Toggle (ưu tiên cao nhất, luôn check)
    2. Nếu system ON → priority:
       Pinch (Click/Drag) > Zoom > Right Click > Swipe > Scroll > Move
    3. Hysteresis + post-action cooldown + frame stability chống loạn

    Attributes:
        system_active: Trạng thái hệ thống ON/OFF
        pinch_state: Trạng thái pinch hiện tại
        current_gesture: Tên cử chỉ đang nhận diện
        click_anchor_pos: Vị trí anchor khi bắt đầu pinch (cho visual feedback)
    """

    def __init__(self):
        """Khởi tạo GestureRecognizer với tất cả state và timer."""

        # --- Trạng thái hệ thống ---
        self.system_active = cfg.SYSTEM_ACTIVE_DEFAULT
        self.current_gesture = GESTURE_NONE

        # --- System Toggle ---
        self._toggle_start_time = 0
        self._toggle_active = False
        self._toggle_cooldown_time = 0
        self._five_fingers_start = 0     # Thời điểm bắt đầu thấy 5 ngón (grace period)

        # --- Unified Pinch (Click + Drag + Double Click) ---
        self.pinch_state = PinchState.IDLE
        self._pinch_start_time = 0
        self._left_click_time = 0       # Thời điểm left click cuối
        self._is_pinching_prev = False   # Trạng thái pinch frame trước (hysteresis)
        self.click_anchor_pos = None    # Vi tri on dinh khi bat dau pinch (cho feedback + click)

        # --- Double Click ---
        self._first_click_time = 0      # Thời điểm click lần 1 (chờ click lần 2)
        self._waiting_double = False    # Đang chờ click 2?

        # --- Right Click ---
        self._right_click_time = 0
        self._right_click_was_pinching = False

        # --- Scroll ---
        self._scroll_prev_y = None

        # --- Swipe ---
        self._swipe_tracking = False    # Đang track chuyển động ngang?
        self._swipe_start_x = 0        # Vị trí X khi bắt đầu track
        self._swipe_start_time = 0     # Thời điểm bắt đầu track
        self._swipe_cooldown_time = 0  # Cooldown sau khi swipe
        self._swipe_frame_count = 0    # Đếm frame liên tục thỏa điều kiện swipe

        # --- Zoom (1 tay: index + middle guard) ---
        self._zoom_active = False       # Đang ở zoom mode?
        self._zoom_prev_distance = 0    # Khoảng cách thumb-index frame trước
        self._zoom_delta_acc = 0        # Accumulator delta (gom nhiều frame nhỏ)
        self._zoom_cooldown_time = 0    # Cooldown sau zoom trigger
        self._zoom_frame_count = 0     # Đếm frame liên tục ở zoom mode

        # --- Post-action cooldown ---
        self._post_action_time = 0     # Thời điểm event cuối (click/swipe/etc.)
        self._click_freeze_until = 0   # Thời điểm hết freeze cursor sau click

        # --- Velocity tracking ---
        self._prev_index_pos = None
        self._prev_hand_center = None

    def recognize(self, landmark_list, fingers, palm_size=0, hand_center=None):
        """
        Nhận diện cử chỉ chính — gọi mỗi frame.

        Args:
            landmark_list: List [(id, x, y), ...] từ HandDetector
            fingers: List [thumb, index, middle, ring, pinky] từ fingers_up()
            palm_size: Kích thước bàn tay (pixel)
            hand_center: Tuple (cx, cy) tâm bàn tay

        Returns:
            dict: {"gesture", "cursor_pos", "scroll_delta", "drag_pos", "system_active"}
        """
        now = time.time()

        # Kết quả mặc định
        result = {
            "gesture": GESTURE_NONE,
            "cursor_pos": None,
            "scroll_delta": None,
            "drag_pos": None,
            "system_active": self.system_active,
            "click_anchor": None,
            "click_freeze_until": 0,
        }

        # Kiểm tra dữ liệu đầu vào
        if not landmark_list or len(landmark_list) < 21 or not fingers:
            self._reset_continuous_states()
            self.current_gesture = GESTURE_NONE
            return result

        # ------------------------------------------------------------------
        # STEP 1: SYSTEM TOGGLE (luôn kiểm tra, bất kể ON/OFF)
        # ------------------------------------------------------------------
        toggle_result = self._check_system_toggle(fingers, hand_center, now)
        if toggle_result is not None:
            result["gesture"] = toggle_result
            result["system_active"] = self.system_active
            self.current_gesture = toggle_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # Nếu system OFF → chỉ hiển thị, không xử lý gesture
        if not self.system_active:
            if sum(fingers) == 5:
                result["gesture"] = GESTURE_OPEN_PALM
            self._reset_continuous_states()
            self.current_gesture = result["gesture"]
            # Vẫn cập nhật prev positions để toggle track được chuyển động
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # ------------------------------------------------------------------
        # POST-ACTION COOLDOWN: neutral gap sau event gestures
        # Chống loạn khi tay đang chuyển tư thế sau click/swipe
        # Ngoại trừ: drag đang chạy, hoặc đang chờ double click
        # ------------------------------------------------------------------
        if not cooldown_passed(self._post_action_time,
                               cfg.POST_ACTION_COOLDOWN, now):
            in_active_flow = (
                self.pinch_state == PinchState.DRAGGING or
                self.pinch_state == PinchState.PREPARING or
                self._waiting_double
            )
            if not in_active_flow:
                self.current_gesture = GESTURE_NONE
                self._update_prev_positions(landmark_list, hand_center)
                return result

        # ------------------------------------------------------------------
        # STEP 2: NHẬN DIỆN CỬ CHỈ (System ON)
        # Priority: Pinch > Zoom > Right Click > Swipe > Scroll > Move
        # ------------------------------------------------------------------

        # Lấy tọa độ landmarks
        thumb_tip = (landmark_list[cfg.THUMB_TIP][1], landmark_list[cfg.THUMB_TIP][2])
        index_tip = (landmark_list[cfg.INDEX_TIP][1], landmark_list[cfg.INDEX_TIP][2])
        middle_tip = (landmark_list[cfg.MIDDLE_TIP][1], landmark_list[cfg.MIDDLE_TIP][2])

        # Tính khoảng cách
        thumb_index_dist = calculate_distance(thumb_tip, index_tip)
        thumb_middle_dist = calculate_distance(thumb_tip, middle_tip)

        # Tính threshold (adaptive + hysteresis)
        pinch_enter = self._get_pinch_threshold(palm_size)
        pinch_exit = pinch_enter * cfg.PINCH_EXIT_MULTIPLIER

        # --- 2A: UNIFIED PINCH — Click + Drag + Double Click ---
        # Guard: khi fingers[2]==1 (ngón giữa giơ) → Pinch skip, nhường Zoom
        pinch_result = self._check_pinch_action(
            fingers, index_tip, thumb_index_dist,
            pinch_enter, pinch_exit, now
        )
        if pinch_result is not None:
            result["gesture"] = pinch_result
            if pinch_result in (GESTURE_LEFT_CLICK, GESTURE_DOUBLE_CLICK):
                result["cursor_pos"] = index_tip
                result["click_anchor"] = self.click_anchor_pos
                result["click_freeze_until"] = self._click_freeze_until
            elif pinch_result in (GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END):
                result["drag_pos"] = index_tip
            self.current_gesture = pinch_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2B: ZOOM IN / OUT ---
        # Guard gesture: index + middle up, ring + pinky down
        # Thumb-index distance delta → Zoom In (tăng) / Zoom Out (giảm)
        # Truyền thumb_middle_dist để guard khi đang là right-click candidate
        zoom_result = self._check_zoom(fingers, thumb_index_dist, thumb_middle_dist,
                                        pinch_enter, now)
        if zoom_result is not None:
            result["gesture"] = zoom_result
            self.current_gesture = zoom_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2C: RIGHT CLICK (chi khi KHONG o zoom mode) ---
        right_click_result = self._check_right_click(
            fingers, thumb_middle_dist, thumb_index_dist,
            pinch_enter, pinch_exit, now
        )
        if right_click_result is not None:
            result["gesture"] = right_click_result
            # Lưu anchor cho right click feedback
            self.click_anchor_pos = middle_tip
            result["click_anchor"] = self.click_anchor_pos
            result["click_freeze_until"] = self._click_freeze_until
            self.current_gesture = right_click_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2C: SWIPE LEFT / RIGHT ---
        swipe_result = self._check_swipe(fingers, hand_center, now)
        if swipe_result is not None:
            result["gesture"] = swipe_result
            self.current_gesture = swipe_result
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2D: SCROLL ---
        scroll_result = self._check_scroll(fingers, hand_center)
        if scroll_result is not None:
            result["gesture"] = scroll_result[0]
            result["scroll_delta"] = scroll_result[1]
            self.current_gesture = scroll_result[0]
            self._update_prev_positions(landmark_list, hand_center)
            return result

        # --- 2E: MOVE CURSOR ---
        # Guard: không move khi đang ở zoom mode hoặc swipe tracking
        # Để tránh cursor nhảy khi đang thao tác mode khác
        if not self._zoom_active and not self._swipe_tracking:
            move_result = self._check_move_cursor(fingers, index_tip)
            if move_result is not None:
                result["gesture"] = GESTURE_MOVE
                result["cursor_pos"] = move_result
                result["click_freeze_until"] = self._click_freeze_until
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
    def _check_system_toggle(self, fingers, hand_center, now):
        """
        Rule: Giơ 5 ngón tay giữ yên >= SYSTEM_TOGGLE_HOLD_TIME giây.

        Grace period:
          - 5 ngón xuất hiện lần đầu → bắt đầu grace (0.4s)
          - Trong grace period: return None → cho swipe chạy
          - Sau grace (tay giữ yên) → bắt đầu đếm toggle + hiện OPEN_PALM
          - Nếu tay di chuyển ngang nhanh bất cứ lúc nào → reset, nhường cho swipe
        """
        if not cooldown_passed(self._toggle_cooldown_time,
                               cfg.SYSTEM_TOGGLE_COOLDOWN, now):
            return None

        finger_count = sum(fingers)

        if finger_count == cfg.SYSTEM_TOGGLE_FINGERS:
            # Bypass nếu đang track swipe
            if self._swipe_tracking:
                self._toggle_active = False
                self._five_fingers_start = 0
                return None

            # Bypass nếu tay đang di chuyển ngang nhanh
            if (self._prev_hand_center is not None and
                    hand_center is not None):
                dx = abs(hand_center[0] - self._prev_hand_center[0])
                if dx > cfg.SWIPE_THRESHOLD_X * 0.3:
                    self._toggle_active = False
                    self._five_fingers_start = 0
                    return None

            # Grace period: lần đầu thấy 5 ngón
            if self._five_fingers_start == 0:
                self._five_fingers_start = now
                return None  # Cho swipe có cơ hội check trước

            # Vẫn trong grace period?
            if (now - self._five_fingers_start) < cfg.OPEN_PALM_GRACE_PERIOD:
                return None  # Vẫn cho swipe chạy

            # Hết grace period, tay giữ yên → bắt đầu toggle
            if not self._toggle_active:
                self._toggle_start_time = now
                self._toggle_active = True
                return GESTURE_OPEN_PALM

            elapsed = now - self._toggle_start_time
            if elapsed >= cfg.SYSTEM_TOGGLE_HOLD_TIME:
                self.system_active = not self.system_active
                self._toggle_active = False
                self._toggle_cooldown_time = now
                self._five_fingers_start = 0
                self._reset_continuous_states()
                return GESTURE_SYSTEM_TOGGLE

            return GESTURE_OPEN_PALM
        else:
            self._toggle_active = False
            self._five_fingers_start = 0
            return None

    # ======================================================================
    # PRIVATE: UNIFIED PINCH (Click + Drag + Double Click)
    # ======================================================================
    def _check_pinch_action(self, fingers, index_tip, thumb_index_dist,
                            enter_threshold, exit_threshold, now):
        """
        Unified Pinch Handler — Click, Double Click, và Drag trong 1 flow.

        Hysteresis:
          - Enter pinch khi distance < enter_threshold
          - Exit pinch khi distance > exit_threshold (exit > enter)
          - Tránh flickering ở biên ngưỡng

        Double Click:
          - Left Click lần 1 → bắn ngay + ghi nhận thời điểm
          - Left Click lần 2 trong DOUBLE_CLICK_TIME_WINDOW → bắn DOUBLE_CLICK
        """
        # GUARD: Ngón giữa giơ = zoom mode → skip Pinch
        # Trừ khi đang DRAGGING (cho phép kết thúc drag dù ngón giữa giơ)
        if fingers[2] == 1 and self.pinch_state != PinchState.DRAGGING:
            return None

        # Hysteresis: dùng threshold khác nhau cho enter vs exit
        if self._is_pinching_prev:
            is_pinching = thumb_index_dist < exit_threshold
        else:
            is_pinching = thumb_index_dist < enter_threshold

        self._is_pinching_prev = is_pinching

        # --- State: IDLE ---
        if self.pinch_state == PinchState.IDLE:
            if is_pinching and fingers[1] == 1:
                self.pinch_state = PinchState.PREPARING
                self._pinch_start_time = now
                self.click_anchor_pos = index_tip  # Lưu vị trí ổn định cho feedback
            return None

        # --- State: PREPARING ---
        if self.pinch_state == PinchState.PREPARING:
            if not is_pinching:
                # Thả sớm → Click (pinch ngắn < hold_threshold)
                self.pinch_state = PinchState.IDLE

                if cooldown_passed(self._left_click_time, cfg.CLICK_COOLDOWN, now):
                    self._left_click_time = now
                    self._post_action_time = now  # Post-action cooldown
                    self._click_freeze_until = now + cfg.CLICK_FREEZE_TIME

                    # Double Click detection
                    if (self._waiting_double and
                            (now - self._first_click_time) <= cfg.DOUBLE_CLICK_TIME_WINDOW):
                        # Click lần 2 trong cửa sổ → Double Click!
                        self._waiting_double = False
                        self._first_click_time = 0
                        return GESTURE_DOUBLE_CLICK
                    else:
                        # Click lần 1 (hoặc hết time window) → Left Click
                        self._first_click_time = now
                        self._waiting_double = True
                        return GESTURE_LEFT_CLICK

                return None

            # Vẫn đang pinch → kiểm tra đủ lâu chưa
            hold_duration = now - self._pinch_start_time
            if hold_duration >= cfg.PINCH_HOLD_THRESHOLD:
                self.pinch_state = PinchState.DRAGGING
                self._waiting_double = False  # Cancel double click nếu đang chờ
                return GESTURE_DRAG_START

            return None

        # --- State: DRAGGING ---
        if self.pinch_state == PinchState.DRAGGING:
            if not is_pinching:
                self.pinch_state = PinchState.IDLE
                self._post_action_time = now
                return GESTURE_DRAG_END

            return GESTURE_DRAGGING

        return None

    # ======================================================================
    # PRIVATE: MOVE CURSOR
    # ======================================================================
    def _check_move_cursor(self, fingers, index_tip):
        """
        Rule: Chỉ ngón trỏ giơ lên, 3 ngón còn lại cụp.
        Ngón cái có thể giơ/cụp tùy tư thế.
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
    def _check_right_click(self, fingers, thumb_middle_dist, thumb_index_dist,
                           enter_threshold, exit_threshold, now):
        """
        Rule: Thumb + Middle pinch (cham roi tha).
        Co hysteresis + edge detection.

        Form (chi check khi ENTERING):
          - middle == 1, ring == 0, pinky == 0
          - thumb-middle dominance: thumb gan middle hon index
          - KHONG bat buoc index == 0 (cho phep index flicker)
        Khi da tracking: chi theo distance, bo qua finger flicker.
        Guard: vo hieu khi dang o zoom mode.
        """
        # GUARD: Zoom mode active -> skip
        if self._zoom_active:
            self._right_click_was_pinching = False
            return None

        # --- Khi CHUA tracking: form check de bat dau ---
        if not self._right_click_was_pinching:
            # middle phai gio, ring+pinky phai cup
            if not (fingers[2] == 1 and fingers[3] == 0 and fingers[4] == 0):
                return None
            # Thumb-middle dominance: thumb phai gan middle hon index
            # Neu thumb gan index hon -> do la pinch/zoom, khong phai right click
            if thumb_middle_dist >= thumb_index_dist:
                return None
            # Check pinch enter
            if thumb_middle_dist < enter_threshold:
                self._right_click_was_pinching = True
            return None

        # --- Dang tracking: chi theo distance, bo qua finger flicker ---
        is_pinching = thumb_middle_dist < exit_threshold

        # Edge detection: THA pinch -> trigger right click
        if not is_pinching:
            self._right_click_was_pinching = False
            if cooldown_passed(self._right_click_time, cfg.CLICK_COOLDOWN, now):
                self._right_click_time = now
                self._post_action_time = now
                self._click_freeze_until = now + cfg.CLICK_FREEZE_TIME
                return GESTURE_RIGHT_CLICK
            return None

        return None

    # ======================================================================
    # PRIVATE: ZOOM IN / OUT
    # ======================================================================
    def _check_zoom(self, fingers, thumb_index_dist, thumb_middle_dist,
                    pinch_enter, now):
        """
        Rule: Zoom mode = index + middle giơ, ring + pinky cụp.
        Thumb tự do — khoảng cách thumb-index thay đổi xác định hướng zoom.

        Guards:
          - Nếu thumb đang gần middle (right-click candidate) → skip zoom
          - Phải đủ ZOOM_STABLE_FRAMES liên tục mới activate

        Logic:
          - Vào zoom mode → ghi prev_distance, chờ frame tiếp
          - Mỗi frame → tính delta, cộng dồn vào accumulator
          - Accumulator > threshold → ZOOM_IN (khoảng cách tăng)
          - Accumulator < -threshold → ZOOM_OUT (khoảng cách giảm)
          - Ra khỏi zoom mode → reset toàn bộ state
        """
        # Kiểm tra zoom mode: index up, middle up, ring down, pinky down
        is_zoom_mode = (
            fingers[1] == 1 and
            fingers[2] == 1 and
            fingers[3] == 0 and
            fingers[4] == 0
        )

        # GUARD: Nếu thumb đang gần middle → right-click candidate, không phải zoom
        if is_zoom_mode and thumb_middle_dist < pinch_enter * 1.5:
            is_zoom_mode = False

        if not is_zoom_mode:
            # Ra khỏi zoom mode → reset
            if self._zoom_active:
                self._zoom_active = False
                self._zoom_prev_distance = 0
                self._zoom_delta_acc = 0
            self._zoom_frame_count = 0
            return None

        # Đếm frame liên tục ở zoom mode — phải đủ ZOOM_STABLE_FRAMES mới bắt đầu
        self._zoom_frame_count += 1
        if self._zoom_frame_count < cfg.ZOOM_STABLE_FRAMES:
            return None

        # Vào zoom mode (sau khi đủ frame ổn định)
        if not self._zoom_active:
            self._zoom_active = True
            self._zoom_prev_distance = thumb_index_dist
            self._zoom_delta_acc = 0
            return None  # Chờ frame tiếp để tính delta

        # Tính delta và cộng dồn vào accumulator
        delta = thumb_index_dist - self._zoom_prev_distance
        self._zoom_prev_distance = thumb_index_dist
        self._zoom_delta_acc += delta

        # Kiểm tra cooldown
        if not cooldown_passed(self._zoom_cooldown_time, cfg.ZOOM_COOLDOWN, now):
            return None

        # Trigger zoom khi accumulator vượt ngưỡng
        if self._zoom_delta_acc > cfg.ZOOM_DELTA_THRESHOLD:
            self._zoom_delta_acc = 0
            self._zoom_cooldown_time = now
            self._post_action_time = now
            return GESTURE_ZOOM_IN

        if self._zoom_delta_acc < -cfg.ZOOM_DELTA_THRESHOLD:
            self._zoom_delta_acc = 0
            self._zoom_cooldown_time = now
            self._post_action_time = now
            return GESTURE_ZOOM_OUT

        return None

    # ======================================================================
    # PRIVATE: SWIPE LEFT / RIGHT
    # ======================================================================
    def _check_swipe(self, fingers, hand_center, now):
        """
        Swipe detection: thumb down + 4 ngon chinh up + vuot ngang nhanh.

        Form:
          ENTERING: fingers = [0, 1, 1, 1, 1] (thumb down, 4 ngon up)
          TRACKING: chi can index+middle+ring+pinky up (bo qua thumb flicker)
          Toggle = 5 ngon -> khong xung dot.
        """
        # 4 ngon chinh phai gio (index, middle, ring, pinky)
        four_fingers_up = (fingers[1] == 1 and fingers[2] == 1 and
                           fingers[3] == 1 and fingers[4] == 1)

        if hand_center is None or not four_fingers_up:
            # 4 ngon chinh khong du -> reset hoan toan
            self._swipe_tracking = False
            self._swipe_frame_count = 0
            return None

        # Khi chua tracking: yeu cau thumb == 0 (form chat)
        # Khi da tracking: cho phep thumb flicker (chi can 4 ngon chinh)
        if not self._swipe_tracking and fingers[0] != 0:
            self._swipe_frame_count = 0
            return None

        # Cooldown
        if not cooldown_passed(self._swipe_cooldown_time, cfg.SWIPE_COOLDOWN, now):
            return None

        current_x = hand_center[0]

        if not self._swipe_tracking:
            # Đếm frame liên tục thỏa điều kiện — phải đủ SWIPE_STABLE_FRAMES
            self._swipe_frame_count += 1
            if self._swipe_frame_count < cfg.SWIPE_STABLE_FRAMES:
                return None

            # Bắt đầu track — dùng prev position nếu có
            self._swipe_tracking = True
            if self._prev_hand_center is not None:
                self._swipe_start_x = self._prev_hand_center[0]
            else:
                self._swipe_start_x = current_x
            self._swipe_start_time = now
            return None

        # Đang tracking → kiểm tra điều kiện
        elapsed = now - self._swipe_start_time

        # Timeout: tay mo nhung khong vuot du nhanh → tat tracking, nhuong cho toggle
        if elapsed > cfg.SWIPE_TIME_WINDOW:
            self._swipe_tracking = False
            self._swipe_frame_count = 0  # Reset de khong bat lai ngay
            return None

        # Tính delta X
        delta_x = current_x - self._swipe_start_x

        if abs(delta_x) >= cfg.SWIPE_THRESHOLD_X:
            # Trigger swipe!
            self._swipe_tracking = False
            self._swipe_cooldown_time = now
            self._post_action_time = now

            if delta_x > 0:
                return GESTURE_SWIPE_RIGHT
            else:
                return GESTURE_SWIPE_LEFT

        return None

    # ======================================================================
    # PRIVATE: SCROLL
    # ======================================================================
    def _check_scroll(self, fingers, hand_center):
        """
        Rule: Nắm tay (4 ngón chính cụp) + di chuyển dọc.
        Continuous gesture — scroll mỗi frame khi delta Y đủ lớn.
        """
        is_fist = (fingers[1] == 0 and fingers[2] == 0 and
                   fingers[3] == 0 and fingers[4] == 0)

        if not is_fist or hand_center is None:
            self._scroll_prev_y = None
            return None

        current_y = hand_center[1]

        if self._scroll_prev_y is None:
            self._scroll_prev_y = current_y
            return None

        delta_y = current_y - self._scroll_prev_y

        if abs(delta_y) >= cfg.SCROLL_SENSITIVITY:
            self._scroll_prev_y = current_y

            if delta_y > 0:
                return (GESTURE_SCROLL_DOWN, -cfg.SCROLL_SPEED)
            else:
                return (GESTURE_SCROLL_UP, cfg.SCROLL_SPEED)

        return None

    # ======================================================================
    # PRIVATE: HELPER METHODS
    # ======================================================================
    def _reset_continuous_states(self):
        """Reset trạng thái gesture (không reset toggle — toggle tự quản lý)."""
        self.pinch_state = PinchState.IDLE
        self._is_pinching_prev = False
        self._scroll_prev_y = None
        self._right_click_was_pinching = False
        self._swipe_tracking = False
        self._swipe_frame_count = 0
        self._waiting_double = False
        self._zoom_active = False
        self._zoom_prev_distance = 0
        self._zoom_delta_acc = 0
        self._zoom_frame_count = 0
        self.click_anchor_pos = None
        self._click_freeze_until = 0
        # Lưu ý: KHÔNG reset _five_fingers_start và _toggle_active ở đây
        # Toggle phải tự quản lý state để hoạt động cả khi system OFF
        self._prev_index_pos = None
        self._prev_hand_center = None

    def _update_prev_positions(self, landmark_list, hand_center):
        """Cập nhật vị trí frame trước cho velocity tracking."""
        if landmark_list and len(landmark_list) > cfg.INDEX_TIP:
            self._prev_index_pos = (
                landmark_list[cfg.INDEX_TIP][1],
                landmark_list[cfg.INDEX_TIP][2]
            )
        self._prev_hand_center = hand_center

    def get_toggle_progress(self):
        """Lấy tiến trình toggle (0.0 - 1.0) cho progress bar."""
        if not self._toggle_active:
            return 0.0
        elapsed = time.time() - self._toggle_start_time
        return min(elapsed / cfg.SYSTEM_TOGGLE_HOLD_TIME, 1.0)

    def get_state_info(self):
        """Thông tin state cho UI và debug."""
        return {
            "system_active": self.system_active,
            "current_gesture": self.current_gesture,
            "pinch_state": self.pinch_state,
            "toggle_progress": self.get_toggle_progress(),
            "waiting_double": self._waiting_double,
            "swipe_tracking": self._swipe_tracking,
            "zoom_active": self._zoom_active,
            "click_freeze_until": self._click_freeze_until,
        }

    # ======================================================================
    # PRIVATE: THRESHOLD HELPERS
    # ======================================================================
    def _get_pinch_threshold(self, palm_size):
        """Ngưỡng pinch ENTER: adaptive theo palm_size, fallback pixel cố định."""
        if palm_size > 0:
            return palm_size * cfg.PINCH_THRESHOLD_NORMALIZED
        else:
            return cfg.CLICK_DISTANCE_THRESHOLD

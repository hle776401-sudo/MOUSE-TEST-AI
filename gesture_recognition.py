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

        # Thumb bo qua hoan toan: MediaPipe detect thumb bang truc X
        # rat khong on dinh, flicker 0/1 lien tuc.
        # Swipe va Toggle phan biet bang HANH VI:
        #   Swipe = vuot nhanh < 0.5s
        #   Toggle = giu yen 3s
        # Toggle code da co guard: if swipe_tracking -> skip toggle

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
        """Nguong pinch ENTER: adaptive theo palm_size, fallback pixel co dinh."""
        if palm_size > 0:
            return palm_size * cfg.PINCH_THRESHOLD_NORMALIZED
        else:
            return cfg.CLICK_DISTANCE_THRESHOLD


# ==============================================================================
# PRIMARY HAND RECOGNIZER (Move, Click, Drag, Scroll)
# ==============================================================================
class PrimaryHandRecognizer:
    """
    Recognizer cho tay chinh (Primary Hand).
    Chi xu ly: Move Cursor, Left Click, Double Click, Right Click, Drag, Scroll.
    Khong xu ly: Swipe, Zoom, Toggle (thuoc Secondary).
    """

    def __init__(self):
        # --- Unified Pinch ---
        self.pinch_state = PinchState.IDLE
        self._pinch_start_time = 0
        self._left_click_time = 0
        self._is_pinching_prev = False
        self.click_anchor_pos = None

        # --- Double Click ---
        self._first_click_time = 0
        self._waiting_double = False

        # --- Right Click ---
        self._right_click_time = 0
        self._right_click_was_pinching = False

        # --- Scroll ---
        self._scroll_prev_y = None

        # --- Stability ---
        self._post_action_time = 0
        self._click_freeze_until = 0
        self.current_gesture = GESTURE_NONE

    def recognize(self, landmark_list, fingers, palm_size=0):
        """
        Nhan dien gesture cho Primary hand.

        Returns:
            dict: {gesture, cursor_pos, scroll_delta, drag_pos,
                   click_anchor, click_freeze_until}
        """
        now = time.time()
        result = {
            "gesture": GESTURE_NONE,
            "cursor_pos": None,
            "scroll_delta": None,
            "drag_pos": None,
            "click_anchor": None,
            "click_freeze_until": 0,
        }

        if not landmark_list or len(landmark_list) < 21 or not fingers:
            self._reset_states()
            return result

        # Post-action cooldown
        if not cooldown_passed(self._post_action_time,
                               cfg.POST_ACTION_COOLDOWN, now):
            in_active_flow = (
                self.pinch_state == PinchState.DRAGGING or
                self.pinch_state == PinchState.PREPARING or
                self._waiting_double
            )
            if not in_active_flow:
                self.current_gesture = GESTURE_NONE
                return result

        # Landmarks
        thumb_tip = (landmark_list[cfg.THUMB_TIP][1], landmark_list[cfg.THUMB_TIP][2])
        index_tip = (landmark_list[cfg.INDEX_TIP][1], landmark_list[cfg.INDEX_TIP][2])
        middle_tip = (landmark_list[cfg.MIDDLE_TIP][1], landmark_list[cfg.MIDDLE_TIP][2])

        thumb_index_dist = calculate_distance(thumb_tip, index_tip)
        thumb_middle_dist = calculate_distance(thumb_tip, middle_tip)

        pinch_enter = self._get_pinch_threshold(palm_size)
        pinch_exit = pinch_enter * cfg.PINCH_EXIT_MULTIPLIER

        # --- PINCH (Click + Drag + Double Click) ---
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
            return result

        # --- RIGHT CLICK ---
        right_click_result = self._check_right_click(
            fingers, thumb_middle_dist, thumb_index_dist,
            pinch_enter, pinch_exit, now
        )
        if right_click_result is not None:
            result["gesture"] = right_click_result
            self.click_anchor_pos = middle_tip
            result["click_anchor"] = self.click_anchor_pos
            result["click_freeze_until"] = self._click_freeze_until
            self.current_gesture = right_click_result
            return result

        # --- SCROLL ---
        scroll_result = self._check_scroll(fingers, landmark_list)
        if scroll_result is not None:
            result["gesture"] = scroll_result[0]
            result["scroll_delta"] = scroll_result[1]
            self.current_gesture = scroll_result[0]
            return result

        # --- MOVE CURSOR ---
        move_result = self._check_move_cursor(fingers, index_tip)
        if move_result is not None:
            result["gesture"] = GESTURE_MOVE
            result["cursor_pos"] = move_result
            result["click_freeze_until"] = self._click_freeze_until
            self.current_gesture = GESTURE_MOVE
            return result

        self.current_gesture = GESTURE_NONE
        return result

    # --- Private methods (reuse logic from GestureRecognizer) ---

    def _check_pinch_action(self, fingers, index_tip, thumb_index_dist,
                            enter_threshold, exit_threshold, now):
        # Guard: middle up -> skip pinch (nhu cu, nhung tren primary
        # khong co zoom nen chi la safety)
        if fingers[2] == 1 and self.pinch_state != PinchState.DRAGGING:
            return None

        if self._is_pinching_prev:
            is_pinching = thumb_index_dist < exit_threshold
        else:
            is_pinching = thumb_index_dist < enter_threshold
        self._is_pinching_prev = is_pinching

        if self.pinch_state == PinchState.IDLE:
            if is_pinching and fingers[1] == 1:
                self.pinch_state = PinchState.PREPARING
                self._pinch_start_time = now
                self.click_anchor_pos = index_tip
            return None

        if self.pinch_state == PinchState.PREPARING:
            if not is_pinching:
                self.pinch_state = PinchState.IDLE
                if cooldown_passed(self._left_click_time, cfg.CLICK_COOLDOWN, now):
                    self._left_click_time = now
                    self._post_action_time = now
                    self._click_freeze_until = now + cfg.CLICK_FREEZE_TIME
                    if (self._waiting_double and
                            (now - self._first_click_time) <= cfg.DOUBLE_CLICK_TIME_WINDOW):
                        self._waiting_double = False
                        self._first_click_time = 0
                        return GESTURE_DOUBLE_CLICK
                    else:
                        self._first_click_time = now
                        self._waiting_double = True
                        return GESTURE_LEFT_CLICK
                return None

            hold_duration = now - self._pinch_start_time
            if hold_duration >= cfg.PINCH_HOLD_THRESHOLD:
                self.pinch_state = PinchState.DRAGGING
                self._waiting_double = False
                return GESTURE_DRAG_START
            return None

        if self.pinch_state == PinchState.DRAGGING:
            if not is_pinching:
                self.pinch_state = PinchState.IDLE
                self._post_action_time = now
                return GESTURE_DRAG_END
            return GESTURE_DRAGGING

        return None

    def _check_right_click(self, fingers, thumb_middle_dist, thumb_index_dist,
                           enter_threshold, exit_threshold, now):
        # Khong can guard zoom vi primary khong co zoom
        if not self._right_click_was_pinching:
            if not (fingers[2] == 1 and fingers[3] == 0 and fingers[4] == 0):
                return None
            if thumb_middle_dist >= thumb_index_dist:
                return None
            if thumb_middle_dist < enter_threshold:
                self._right_click_was_pinching = True
            return None

        is_pinching = thumb_middle_dist < exit_threshold
        if not is_pinching:
            self._right_click_was_pinching = False
            if cooldown_passed(self._right_click_time, cfg.CLICK_COOLDOWN, now):
                self._right_click_time = now
                self._post_action_time = now
                self._click_freeze_until = now + cfg.CLICK_FREEZE_TIME
                return GESTURE_RIGHT_CLICK
            return None
        return None

    def _check_move_cursor(self, fingers, index_tip):
        if (fingers[1] == 1 and fingers[2] == 0 and
                fingers[3] == 0 and fingers[4] == 0):
            return index_tip
        return None

    def _check_scroll(self, fingers, landmark_list):
        is_fist = (fingers[1] == 0 and fingers[2] == 0 and
                   fingers[3] == 0 and fingers[4] == 0)
        if not is_fist:
            self._scroll_prev_y = None
            return None

        # Dung hand center tu landmarks
        current_y = sum(lm[2] for lm in landmark_list) // len(landmark_list)

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

    def _get_pinch_threshold(self, palm_size):
        if palm_size > 0:
            return palm_size * cfg.PINCH_THRESHOLD_NORMALIZED
        return cfg.CLICK_DISTANCE_THRESHOLD

    def _reset_states(self):
        self.pinch_state = PinchState.IDLE
        self._is_pinching_prev = False
        self._scroll_prev_y = None
        self._right_click_was_pinching = False
        self._waiting_double = False
        self.click_anchor_pos = None
        self._click_freeze_until = 0
        self.current_gesture = GESTURE_NONE


# ==============================================================================
# SECONDARY HAND RECOGNIZER (Swipe, Zoom, Toggle)
# ==============================================================================
class SecondaryHandRecognizer:
    """
    Recognizer cho tay phu (Secondary Hand).
    Chi xu ly: Swipe Left/Right, Zoom In/Out, System Toggle.
    Khong xu ly: Move, Click, Drag, Scroll (thuoc Primary).
    """

    def __init__(self):
        self.system_active = cfg.SYSTEM_ACTIVE_DEFAULT

        # --- Toggle ---
        self._toggle_start_time = 0
        self._toggle_active = False
        self._toggle_cooldown_time = 0
        self._five_fingers_start = 0

        # --- Swipe V2 State Machine ---
        # States: IDLE / ARMED / TRACKING / COOLDOWN
        self._swipe_state: str = "IDLE"
        self._swipe_pose_stable_count: int = 0
        self._swipe_start_x: float = 0.0
        self._swipe_start_time: float = 0.0
        self._swipe_last_x: float = 0.0
        self._swipe_last_time: float = 0.0
        self._swipe_lost_frames: int = 0
        self._last_swipe_time: float = 0.0
        # Legacy (V1) compat — dung khi ENABLE_SWIPE_V2 = False
        self._swipe_tracking: bool = False
        self._swipe_frame_count: int = 0
        self._swipe_cooldown_time: float = 0.0
        # Debug info (doc boi get_swipe_debug_info)
        self._swipe_debug: dict = {}

        # --- Zoom ---
        self._zoom_active = False
        self._zoom_prev_distance = 0
        self._zoom_delta_acc = 0
        self._zoom_cooldown_time = 0
        self._zoom_frame_count = 0

        # --- State ---
        self._post_action_time = 0
        self._prev_hand_center = None
        self.current_gesture = GESTURE_NONE

    def recognize(self, landmark_list, fingers, palm_size=0, hand_center=None):
        """
        Nhan dien gesture cho Secondary hand.

        Returns:
            dict: {gesture, system_active}
        """
        now = time.time()
        result = {
            "gesture": GESTURE_NONE,
            "system_active": self.system_active,
        }

        if not landmark_list or len(landmark_list) < 21 or not fingers:
            self._reset_states()
            self.current_gesture = GESTURE_NONE
            self._prev_hand_center = hand_center
            return result

        # --- TOGGLE (luon check) ---
        toggle_result = self._check_system_toggle(fingers, hand_center, now)
        if toggle_result is not None:
            result["gesture"] = toggle_result
            result["system_active"] = self.system_active
            self.current_gesture = toggle_result
            self._prev_hand_center = hand_center
            return result

        # Neu system OFF -> chi hien Open Palm
        if not self.system_active:
            if sum(fingers) == 5:
                result["gesture"] = GESTURE_OPEN_PALM
            self._reset_states()
            self.current_gesture = result["gesture"]
            self._prev_hand_center = hand_center
            return result

        # Post-action cooldown
        if not cooldown_passed(self._post_action_time,
                               cfg.POST_ACTION_COOLDOWN, now):
            self.current_gesture = GESTURE_NONE
            self._prev_hand_center = hand_center
            return result

        # Landmarks
        thumb_tip = (landmark_list[cfg.THUMB_TIP][1], landmark_list[cfg.THUMB_TIP][2])
        index_tip = (landmark_list[cfg.INDEX_TIP][1], landmark_list[cfg.INDEX_TIP][2])
        middle_tip = (landmark_list[cfg.MIDDLE_TIP][1], landmark_list[cfg.MIDDLE_TIP][2])

        thumb_index_dist = calculate_distance(thumb_tip, index_tip)
        thumb_middle_dist = calculate_distance(thumb_tip, middle_tip)

        pinch_enter = self._get_pinch_threshold(palm_size)

        # --- ZOOM (uu tien truoc swipe) ---
        zoom_result = self._check_zoom(fingers, thumb_index_dist,
                                        thumb_middle_dist, pinch_enter, now)
        if zoom_result is not None:
            result["gesture"] = zoom_result
            self.current_gesture = zoom_result
            self._prev_hand_center = hand_center
            return result

        # --- SWIPE ---
        swipe_result = self._check_swipe(fingers, hand_center, now)
        if swipe_result is not None:
            result["gesture"] = swipe_result
            self.current_gesture = swipe_result
            self._prev_hand_center = hand_center
            return result

        self.current_gesture = GESTURE_NONE
        self._prev_hand_center = hand_center
        return result

    # --- Toggle (copy tu GestureRecognizer) ---
    def _check_system_toggle(self, fingers, hand_center, now):
        if not cooldown_passed(self._toggle_cooldown_time,
                               cfg.SYSTEM_TOGGLE_COOLDOWN, now):
            return None

        finger_count = sum(fingers)
        if finger_count == cfg.SYSTEM_TOGGLE_FINGERS:
            if self._swipe_tracking:
                self._toggle_active = False
                self._five_fingers_start = 0
                return None

            if (self._prev_hand_center is not None and hand_center is not None):
                dx = abs(hand_center[0] - self._prev_hand_center[0])
                if dx > cfg.SWIPE_THRESHOLD_X * 0.3:
                    self._toggle_active = False
                    self._five_fingers_start = 0
                    return None

            if self._five_fingers_start == 0:
                self._five_fingers_start = now
                return None

            if (now - self._five_fingers_start) < cfg.OPEN_PALM_GRACE_PERIOD:
                return None

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
                self._reset_states()
                return GESTURE_SYSTEM_TOGGLE

            return GESTURE_OPEN_PALM
        else:
            self._toggle_active = False
            self._five_fingers_start = 0
            return None

    # --- Zoom (copy tu GestureRecognizer) ---
    def _check_zoom(self, fingers, thumb_index_dist, thumb_middle_dist,
                    pinch_enter, now):
        is_zoom_mode = (
            fingers[1] == 1 and fingers[2] == 1 and
            fingers[3] == 0 and fingers[4] == 0
        )
        if is_zoom_mode and thumb_middle_dist < pinch_enter * 1.5:
            is_zoom_mode = False

        if not is_zoom_mode:
            if self._zoom_active:
                self._zoom_active = False
                self._zoom_prev_distance = 0
                self._zoom_delta_acc = 0
            self._zoom_frame_count = 0
            return None

        self._zoom_frame_count += 1
        if self._zoom_frame_count < cfg.ZOOM_STABLE_FRAMES:
            return None

        if not self._zoom_active:
            self._zoom_active = True
            self._zoom_prev_distance = thumb_index_dist
            self._zoom_delta_acc = 0
            return None

        delta = thumb_index_dist - self._zoom_prev_distance
        self._zoom_prev_distance = thumb_index_dist
        self._zoom_delta_acc += delta

        if not cooldown_passed(self._zoom_cooldown_time, cfg.ZOOM_COOLDOWN, now):
            return None

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

    # --- Swipe V2 State Machine ---
    def _check_swipe(self, fingers, hand_center, now):
        """Swipe detection V2 — State Machine + Movement Buffer.

        States:
          IDLE     : Chua thay pose hop le.
          ARMED    : Pose on dinh du SWIPE_V2_POSE_STABLE_FRAMES, cho di chuyen.
          TRACKING : Dang theo doi chuyen dong ngang.
          COOLDOWN : Vua trigger swipe, khoa de tranh re-trigger.

        Pose hop le (Swipe): thumb=0, index=1, middle=1, ring=1, pinky=1
        (4 ngon chinh gio, ngon cai cup — khac Toggle 5 ngon).

        Fallback legacy khi ENABLE_SWIPE_V2 = False.
        """
        # ----------------------------------------------------------------
        # LEGACY FALLBACK (V1)
        # ----------------------------------------------------------------
        if not getattr(cfg, "ENABLE_SWIPE_V2", True):
            return self._check_swipe_legacy(fingers, hand_center, now)

        # ----------------------------------------------------------------
        # CONFIG (getattr de safe khi config chua update)
        # ----------------------------------------------------------------
        POSE_STABLE = getattr(cfg, "SWIPE_V2_POSE_STABLE_FRAMES", 3)
        MIN_DX      = getattr(cfg, "SWIPE_V2_MIN_DISTANCE_X",     60)
        MAX_TIME    = getattr(cfg, "SWIPE_V2_MAX_TIME",           0.9)
        MIN_TIME    = getattr(cfg, "SWIPE_V2_MIN_TIME",          0.12)
        MIN_VEL     = getattr(cfg, "SWIPE_V2_MIN_VELOCITY_X",    120)
        GRACE       = getattr(cfg, "SWIPE_V2_LOST_GRACE_FRAMES",   4)
        COOLDOWN    = getattr(cfg, "SWIPE_V2_COOLDOWN",           0.7)
        INVERT      = getattr(cfg, "SWIPE_V2_INVERT_DIRECTION", False)
        DO_DEBUG    = getattr(cfg, "SWIPE_V2_DEBUG",             True)

        # ----------------------------------------------------------------
        # Swipe pose check: thumb=0, index+middle+ring+pinky=1
        # ----------------------------------------------------------------
        pose_ok = (
            fingers[0] == 0 and
            fingers[1] == 1 and
            fingers[2] == 1 and
            fingers[3] == 1 and
            fingers[4] == 1
        )

        # ----------------------------------------------------------------
        # Lay current_x
        # ----------------------------------------------------------------
        current_x = hand_center[0] if hand_center is not None else None

        # ----------------------------------------------------------------
        # STATE: COOLDOWN
        # ----------------------------------------------------------------
        if self._swipe_state == "COOLDOWN":
            if (now - self._last_swipe_time) >= COOLDOWN:
                self._swipe_state = "IDLE"
                self._swipe_pose_stable_count = 0
            # Trong cooldown: ket thuc ham, khong xu ly gi them
            if DO_DEBUG:
                self._swipe_debug = {
                    "state": "COOLDOWN",
                    "cooldown_remaining": round(COOLDOWN - (now - self._last_swipe_time), 2),
                }
            # Sync legacy flag
            self._swipe_tracking = False
            return None

        # ----------------------------------------------------------------
        # Khong co hand_center -> reset ve IDLE
        # ----------------------------------------------------------------
        if current_x is None:
            self._swipe_state = "IDLE"
            self._swipe_pose_stable_count = 0
            self._swipe_lost_frames = 0
            self._swipe_tracking = False
            return None

        # ----------------------------------------------------------------
        # STATE: IDLE
        # ----------------------------------------------------------------
        if self._swipe_state == "IDLE":
            if pose_ok:
                self._swipe_pose_stable_count += 1
                if self._swipe_pose_stable_count >= POSE_STABLE:
                    # Pose on dinh du frame -> ARMED
                    self._swipe_state = "ARMED"
                    self._swipe_start_x = current_x
                    self._swipe_start_time = now
                    self._swipe_last_x = current_x
                    self._swipe_last_time = now
                    self._swipe_lost_frames = 0
            else:
                self._swipe_pose_stable_count = 0

            if DO_DEBUG:
                self._swipe_debug = {
                    "state": "IDLE",
                    "pose_ok": pose_ok,
                    "stable_count": self._swipe_pose_stable_count,
                }
            self._swipe_tracking = False
            return None

        # ----------------------------------------------------------------
        # STATE: ARMED
        # ----------------------------------------------------------------
        if self._swipe_state == "ARMED":
            if not pose_ok:
                self._swipe_lost_frames += 1
                if self._swipe_lost_frames > GRACE:
                    self._swipe_state = "IDLE"
                    self._swipe_pose_stable_count = 0
                    self._swipe_lost_frames = 0
                    self._swipe_tracking = False
                if DO_DEBUG:
                    self._swipe_debug = {
                        "state": "ARMED",
                        "pose_ok": False,
                        "lost_frames": self._swipe_lost_frames,
                        "last_reason": "pose_lost_grace",
                    }
                return None

            self._swipe_lost_frames = 0

            # Timeout kem theo ARMED
            if (now - self._swipe_start_time) > MAX_TIME:
                self._swipe_state = "IDLE"
                self._swipe_pose_stable_count = 0
                self._swipe_tracking = False
                if DO_DEBUG:
                    self._swipe_debug = {"state": "ARMED", "last_reason": "timeout"}
                return None

            # Co chuyen dong ngang -> chuyen TRACKING
            dx = current_x - self._swipe_start_x
            if abs(dx) > (MIN_DX * 0.25):   # 25% distance = bat dau track
                self._swipe_state = "TRACKING"
                self._swipe_last_x = current_x
                self._swipe_last_time = now
                self._swipe_tracking = True  # sync legacy flag

            if DO_DEBUG:
                self._swipe_debug = {
                    "state": "ARMED",
                    "pose_ok": True,
                    "dx": round(current_x - self._swipe_start_x, 1),
                    "elapsed": round(now - self._swipe_start_time, 3),
                }
            return None

        # ----------------------------------------------------------------
        # STATE: TRACKING
        # ----------------------------------------------------------------
        if self._swipe_state == "TRACKING":
            if not pose_ok:
                self._swipe_lost_frames += 1
                if self._swipe_lost_frames > GRACE:
                    # Mat pose qua lau -> reset
                    self._swipe_state = "IDLE"
                    self._swipe_pose_stable_count = 0
                    self._swipe_lost_frames = 0
                    self._swipe_tracking = False
                if DO_DEBUG:
                    self._swipe_debug = {
                        "state": "TRACKING",
                        "pose_ok": False,
                        "lost_frames": self._swipe_lost_frames,
                    }
                return None

            self._swipe_lost_frames = 0

            dx      = current_x - self._swipe_start_x
            elapsed = now - self._swipe_start_time
            vel_x   = abs(dx) / max(elapsed, 0.001)

            # Cap nhat last position
            self._swipe_last_x    = current_x
            self._swipe_last_time = now

            if DO_DEBUG:
                self._swipe_debug = {
                    "state": "TRACKING",
                    "pose_ok": True,
                    "dx": round(dx, 1),
                    "elapsed": round(elapsed, 3),
                    "velocity_x": round(vel_x, 1),
                    "lost_frames": 0,
                }

            # Timeout
            if elapsed > MAX_TIME:
                self._swipe_state = "IDLE"
                self._swipe_pose_stable_count = 0
                self._swipe_tracking = False
                if DO_DEBUG:
                    self._swipe_debug["last_reason"] = "timeout"
                return None

            # --- Kiem tra dieu kien trigger ---
            if (elapsed  >= MIN_TIME and
                abs(dx)  >= MIN_DX and
                vel_x    >= MIN_VEL):

                # Xac dinh huong
                if INVERT:
                    gesture = GESTURE_SWIPE_LEFT if dx > 0 else GESTURE_SWIPE_RIGHT
                else:
                    gesture = GESTURE_SWIPE_RIGHT if dx > 0 else GESTURE_SWIPE_LEFT

                # Chuyen sang COOLDOWN
                self._swipe_state      = "COOLDOWN"
                self._last_swipe_time  = now
                self._swipe_tracking   = False
                self._post_action_time = now

                if DO_DEBUG:
                    self._swipe_debug["state"]       = "COOLDOWN"
                    self._swipe_debug["last_reason"]  = "triggered"
                    self._swipe_debug["triggered"]    = gesture

                return gesture

            return None

        # Khong vao case nao -> fallback IDLE
        self._swipe_state = "IDLE"
        return None

    def _check_swipe_legacy(self, fingers, hand_center, now):
        """Swipe V1 (legacy) — giu nguyen de fallback khi ENABLE_SWIPE_V2=False."""
        four_fingers_up = (fingers[1] == 1 and fingers[2] == 1 and
                           fingers[3] == 1 and fingers[4] == 1)

        if hand_center is None or not four_fingers_up:
            self._swipe_tracking = False
            self._swipe_frame_count = 0
            return None

        if not self._swipe_tracking and fingers[0] != 0:
            self._swipe_frame_count = 0
            return None

        if not cooldown_passed(self._swipe_cooldown_time, cfg.SWIPE_COOLDOWN, now):
            return None

        current_x = hand_center[0]

        if not self._swipe_tracking:
            self._swipe_frame_count += 1
            if self._swipe_frame_count < cfg.SWIPE_STABLE_FRAMES:
                return None
            self._swipe_tracking = True
            self._swipe_start_x = (self._prev_hand_center[0]
                                   if self._prev_hand_center else current_x)
            self._swipe_start_time = now
            return None

        elapsed = now - self._swipe_start_time
        if elapsed > cfg.SWIPE_TIME_WINDOW:
            self._swipe_tracking = False
            self._swipe_frame_count = 0
            return None

        delta_x = current_x - self._swipe_start_x
        if abs(delta_x) >= cfg.SWIPE_THRESHOLD_X:
            self._swipe_tracking = False
            self._swipe_cooldown_time = now
            self._post_action_time = now
            return GESTURE_SWIPE_RIGHT if delta_x > 0 else GESTURE_SWIPE_LEFT

        return None

    # --- Helpers ---
    def get_toggle_progress(self):
        if not self._toggle_active:
            return 0.0
        elapsed = time.time() - self._toggle_start_time
        return min(elapsed / cfg.SYSTEM_TOGGLE_HOLD_TIME, 1.0)

    def get_state_info(self):
        """Thong tin state cho UI (tuong thich voi draw_mode_indicator)."""
        return {
            "system_active": self.system_active,
            "current_gesture": self.current_gesture,
            "pinch_state": "idle",
            "toggle_progress": self.get_toggle_progress(),
            "waiting_double": False,
            "swipe_tracking": (
                self._swipe_state == "TRACKING"
                if getattr(cfg, "ENABLE_SWIPE_V2", True)
                else self._swipe_tracking
            ),
            "zoom_active": self._zoom_active,
            "click_freeze_until": 0,
        }

    def get_swipe_debug_info(self) -> dict:
        """Tra ve debug info cua Swipe V2 (doc boi main.py de hien thi HUD).

        Returns:
            dict voi cac key: state, pose_ok, stable_count, dx, elapsed,
            velocity_x, lost_frames, cooldown_remaining, last_reason.
            Tra ve {} neu ENABLE_SWIPE_V2 = False.
        """
        if not getattr(cfg, "ENABLE_SWIPE_V2", True):
            return {}
        return dict(self._swipe_debug)

    def _get_pinch_threshold(self, palm_size):
        if palm_size > 0:
            return palm_size * cfg.PINCH_THRESHOLD_NORMALIZED
        return cfg.CLICK_DISTANCE_THRESHOLD

    def _reset_states(self):
        self._swipe_state = "IDLE"
        self._swipe_pose_stable_count = 0
        self._swipe_start_x = 0.0
        self._swipe_start_time = 0.0
        self._swipe_last_x = 0.0
        self._swipe_last_time = 0.0
        self._swipe_lost_frames = 0
        # Legacy compat
        self._swipe_tracking = False
        self._swipe_frame_count = 0
        self._swipe_cooldown_time = 0.0
        # Zoom
        self._zoom_active = False
        self._zoom_prev_distance = 0
        self._zoom_delta_acc = 0
        self._zoom_frame_count = 0
        self.current_gesture = GESTURE_NONE


# ==============================================================================
# GESTURE COORDINATOR (dieu phoi 2 tay)
# ==============================================================================
class GestureCoordinator:
    """
    Dieu phoi gesture giua Primary va Secondary hand.

    - Goi PrimaryHandRecognizer cho tay chinh
    - Goi SecondaryHandRecognizer cho tay phu
    - Ap lock giua hai tay
    - Quan ly system_active toan cuc
    """

    def __init__(self):
        self.primary_recognizer = PrimaryHandRecognizer()
        self.secondary_recognizer = SecondaryHandRecognizer()

    @property
    def system_active(self):
        return self.secondary_recognizer.system_active

    @system_active.setter
    def system_active(self, value):
        self.secondary_recognizer.system_active = value

    def process(self, primary_hand, secondary_hand):
        """
        Xu ly gesture cho ca 2 tay.

        Args:
            primary_hand: dict tu get_all_hands_data() hoac None
            secondary_hand: dict tu get_all_hands_data() hoac None

        Returns:
            dict: {
                primary_result: dict gesture result cho primary,
                secondary_result: dict gesture result cho secondary,
                system_active: bool
            }
        """
        # --- Secondary truoc (vi Toggle anh huong system_active) ---
        secondary_result = {"gesture": GESTURE_NONE, "system_active": self.system_active}

        if secondary_hand:
            secondary_result = self.secondary_recognizer.recognize(
                secondary_hand["landmarks"],
                secondary_hand["fingers"],
                secondary_hand["palm_size"],
                secondary_hand["center"]
            )

        # --- Primary (chi chay khi system ON) ---
        primary_result = {
            "gesture": GESTURE_NONE,
            "cursor_pos": None,
            "scroll_delta": None,
            "drag_pos": None,
            "click_anchor": None,
            "click_freeze_until": 0,
        }

        if primary_hand and self.system_active:
            # LOCK: neu secondary dang zoom -> primary van chay binh thuong
            # (2 tay khac nhau, khong xung dot)
            primary_result = self.primary_recognizer.recognize(
                primary_hand["landmarks"],
                primary_hand["fingers"],
                primary_hand["palm_size"]
            )

        elif primary_hand and not self.system_active:
            # System OFF -> reset primary states
            self.primary_recognizer._reset_states()

        # LOCK: neu primary dang dragging -> block secondary swipe/zoom
        if self.primary_recognizer.pinch_state == PinchState.DRAGGING:
            sec_gesture = secondary_result.get("gesture", GESTURE_NONE)
            if sec_gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
                               GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
                secondary_result["gesture"] = GESTURE_NONE

        return {
            "primary_result": primary_result,
            "secondary_result": secondary_result,
            "system_active": self.system_active,
        }

    def get_toggle_progress(self):
        return self.secondary_recognizer.get_toggle_progress()


"""
main.py - Luồng xử lý chính + Demo UI
=======================================
Hệ thống điều khiển máy tính bằng cử chỉ tay qua Webcam.

Pipeline mỗi frame:
  1. Đọc frame từ webcam → flip mirror
  2. HandDetector: detect tay → landmarks, fingers, palm_size
  3. GestureRecognizer: nhận diện gesture → result dict
  4. MouseController: thực thi action
  5. Vẽ demo overlay: gesture banner, mode indicator, feedback, ROI, HUD
  6. Hiển thị → lặp lại

Demo UI:
  - Gesture Banner: text lớn ở trung tâm-trên, màu theo gesture
  - Mode Indicator: [ZOOM MODE] / [SWIPE TRACKING] khi đang trong mode
  - Progress bar cho system toggle
  - Visual feedback: click flash (anchor), drag line, scroll/swipe arrows, zoom line

Điều khiển:
  - Giơ 5 ngón 3 giây: Bật/Tắt hệ thống
  - Nhấn 'q': Thoát
  - Nhấn 's': Toggle điều khiển ON/OFF nhanh
"""

import cv2
import time
import traceback
import threading
import config as cfg
from hand_tracking import HandDetector
from gesture_recognition import (
    GestureRecognizer, GestureCoordinator,
    GESTURE_NONE, GESTURE_MOVE,
    GESTURE_LEFT_CLICK, GESTURE_DOUBLE_CLICK, GESTURE_RIGHT_CLICK,
    GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END,
    GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN,
    GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
    GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT,
    GESTURE_SYSTEM_TOGGLE, GESTURE_OPEN_PALM
)
from mouse_controller import MouseController

# --- Context-Aware Gestures: safe import ---
try:
    from context_manager import ContextManager
    from action_router import ActionRouter
    _CONTEXT_MODULES_OK = True
except Exception as _ctx_import_err:
    print(f"[WARN] Context-Aware modules import failed: {_ctx_import_err}")
    _CONTEXT_MODULES_OK = False

# --- Gesture Logging: safe import ---
try:
    from gesture_logger import GestureLogger
    _LOGGER_MODULE_OK = True
except Exception as _log_import_err:
    print(f"[WARN] GestureLogger import failed: {_log_import_err}")
    _LOGGER_MODULE_OK = False

# --- Voice Command Mode: safe import ---
try:
    from voice_intent import VoiceIntentParser
    from voice_command_executor import VoiceCommandExecutor
    _VOICE_CMD_MODULES_OK = True
except Exception as _vcmd_import_err:
    print(f"[WARN] Voice Command modules import failed: {_vcmd_import_err}")
    _VOICE_CMD_MODULES_OK = False

if cfg.ENABLE_VOICE_INPUT:
    import keyboard
    from voice_input import VoiceInputManager, VoiceState


# ==============================================================================
# GESTURE → MÀU SẮC MAPPING (cho banner + feedback)
# ==============================================================================
GESTURE_COLORS = {
    GESTURE_NONE:         cfg.COLOR_WHITE,
    GESTURE_MOVE:         cfg.COLOR_SUCCESS,
    GESTURE_LEFT_CLICK:   cfg.COLOR_CLICK,
    GESTURE_DOUBLE_CLICK: cfg.COLOR_DOUBLE_CLICK,
    GESTURE_RIGHT_CLICK:  cfg.COLOR_PURPLE,
    GESTURE_DRAG_START:   cfg.COLOR_PURPLE,
    GESTURE_DRAGGING:     cfg.COLOR_PURPLE,
    GESTURE_DRAG_END:     cfg.COLOR_SUCCESS,
    GESTURE_SCROLL_UP:    cfg.COLOR_INFO,
    GESTURE_SCROLL_DOWN:  cfg.COLOR_INFO,
    GESTURE_SWIPE_LEFT:   cfg.COLOR_SWIPE,
    GESTURE_SWIPE_RIGHT:  cfg.COLOR_SWIPE,
    GESTURE_ZOOM_IN:      cfg.COLOR_ZOOM,
    GESTURE_ZOOM_OUT:     cfg.COLOR_ZOOM,
    GESTURE_SYSTEM_TOGGLE: cfg.COLOR_SUCCESS,
    GESTURE_OPEN_PALM:    cfg.COLOR_SECONDARY,
}


def draw_gesture_banner(frame, gesture_name, system_active, linger_counter):
    """
    Vẽ banner gesture lớn ở trung tâm-trên frame.
    Đây là phần visual chính cho demo.

    Args:
        frame: Frame ảnh
        gesture_name: Tên gesture hiện tại
        system_active: Trạng thái hệ thống
        linger_counter: Số frame còn lại để giữ event gesture trên banner

    Returns:
        str: Text đang hiển thị trên banner
    """
    # Xác định text hiển thị
    if not system_active and gesture_name not in (GESTURE_SYSTEM_TOGGLE, GESTURE_OPEN_PALM):
        display_text = "System OFF"
        color = cfg.COLOR_DANGER
    elif gesture_name == GESTURE_SYSTEM_TOGGLE:
        display_text = "System ON" if system_active else "System OFF"
        color = cfg.COLOR_SUCCESS if system_active else cfg.COLOR_DANGER
    elif gesture_name == GESTURE_NONE or gesture_name == GESTURE_MOVE:
        if linger_counter > 0:
            return None  # Sẽ được xử lý bởi linger display bên ngoài
        display_text = "Waiting for gesture..." if system_active else "System OFF"
        color = cfg.COLOR_ROI_BORDER if system_active else cfg.COLOR_DANGER
    else:
        display_text = gesture_name
        color = GESTURE_COLORS.get(gesture_name, cfg.COLOR_WHITE)

    # Tính vị trí trung tâm
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(display_text, font,
                                cfg.BANNER_FONT_SCALE, cfg.BANNER_FONT_THICKNESS)[0]
    text_x = (cfg.CAMERA_WIDTH - text_size[0]) // 2
    text_y = cfg.BANNER_Y

    # Vẽ nền bán trong suốt cho banner
    pad = 12
    overlay = frame.copy()
    cv2.rectangle(overlay,
                  (text_x - pad, text_y - text_size[1] - pad),
                  (text_x + text_size[0] + pad, text_y + pad),
                  cfg.COLOR_BLACK, -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Vẽ viền
    cv2.rectangle(frame,
                  (text_x - pad, text_y - text_size[1] - pad),
                  (text_x + text_size[0] + pad, text_y + pad),
                  color, 2)

    # Vẽ text
    cv2.putText(frame, display_text, (text_x, text_y), font,
                cfg.BANNER_FONT_SCALE, color, cfg.BANNER_FONT_THICKNESS)

    return display_text


def draw_linger_banner(frame, gesture_name, linger_counter):
    """
    Vẽ banner cho event gesture đang linger (vẫn hiển thị sau khi event kết thúc).
    Giúp user nhìn thấy feedback rõ ràng cho click/swipe/etc.
    """
    if linger_counter <= 0 or not gesture_name:
        return

    color = GESTURE_COLORS.get(gesture_name, cfg.COLOR_WHITE)

    # Fade effect: giảm opacity theo linger_counter
    alpha = min(1.0, linger_counter / cfg.BANNER_LINGER_FRAMES)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(gesture_name, font,
                                cfg.BANNER_FONT_SCALE, cfg.BANNER_FONT_THICKNESS)[0]
    text_x = (cfg.CAMERA_WIDTH - text_size[0]) // 2
    text_y = cfg.BANNER_Y

    # Nền
    pad = 12
    overlay = frame.copy()
    cv2.rectangle(overlay,
                  (text_x - pad, text_y - text_size[1] - pad),
                  (text_x + text_size[0] + pad, text_y + pad),
                  cfg.COLOR_BLACK, -1)
    cv2.addWeighted(overlay, 0.6 * alpha, frame, 1.0 - 0.6 * alpha, 0, frame)

    # Viền + text
    cv2.rectangle(frame,
                  (text_x - pad, text_y - text_size[1] - pad),
                  (text_x + text_size[0] + pad, text_y + pad),
                  color, 2)
    cv2.putText(frame, gesture_name, (text_x, text_y), font,
                cfg.BANNER_FONT_SCALE, color, cfg.BANNER_FONT_THICKNESS)


def draw_toggle_progress(frame, progress):
    """Vẽ progress bar cho system toggle."""
    if progress <= 0:
        return

    bar_width = 200
    bar_height = 20
    x = (cfg.CAMERA_WIDTH - bar_width) // 2
    y = cfg.CAMERA_HEIGHT - 50

    # Nền
    cv2.rectangle(frame, (x, y), (x + bar_width, y + bar_height),
                  cfg.COLOR_ROI_BORDER, -1)

    # Fill
    fill_width = int(bar_width * progress)
    color = cfg.COLOR_CLICK if progress >= 0.7 else cfg.COLOR_SUCCESS
    cv2.rectangle(frame, (x, y), (x + fill_width, y + bar_height), color, -1)

    # Viền
    cv2.rectangle(frame, (x, y), (x + bar_width, y + bar_height),
                  cfg.COLOR_WHITE, 1)

    # Text
    cv2.putText(frame, f"Toggle: {int(progress * 100)}%", (x, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, cfg.COLOR_WHITE, 1)


def draw_gesture_feedback(frame, gesture_name, landmark_list, recognizer=None):
    """Vẽ visual feedback trên tay: click flash (anchor), drag line, scroll/swipe arrows, zoom line."""
    if not landmark_list or len(landmark_list) < 21:
        return

    thumb_tip = (landmark_list[cfg.THUMB_TIP][1], landmark_list[cfg.THUMB_TIP][2])
    index_tip = (landmark_list[cfg.INDEX_TIP][1], landmark_list[cfg.INDEX_TIP][2])
    middle_tip = (landmark_list[cfg.MIDDLE_TIP][1], landmark_list[cfg.MIDDLE_TIP][2])

    # --- Left Click: flash circle tại anchor (vị trí ổn định từ lúc bắt đầu pinch) ---
    if gesture_name == GESTURE_LEFT_CLICK:
        anchor = (recognizer.click_anchor_pos if recognizer and recognizer.click_anchor_pos
                  else index_tip)
        cv2.circle(frame, anchor, 20, cfg.COLOR_CLICK, 3)
        cv2.circle(frame, anchor, 30, cfg.COLOR_CLICK, 1)

    # --- Double Click: double flash tại anchor ---
    elif gesture_name == GESTURE_DOUBLE_CLICK:
        anchor = (recognizer.click_anchor_pos if recognizer and recognizer.click_anchor_pos
                  else index_tip)
        cv2.circle(frame, anchor, 20, cfg.COLOR_DOUBLE_CLICK, 3)
        cv2.circle(frame, anchor, 30, cfg.COLOR_DOUBLE_CLICK, 2)
        cv2.circle(frame, anchor, 40, cfg.COLOR_DOUBLE_CLICK, 1)

    # --- Right Click: flash tại ngón giữa ---
    elif gesture_name == GESTURE_RIGHT_CLICK:
        cv2.circle(frame, middle_tip, 20, cfg.COLOR_PURPLE, 3)
        cv2.circle(frame, middle_tip, 30, cfg.COLOR_PURPLE, 1)

    # --- Drag: đường nối thumb-index + highlight ---
    elif gesture_name in (GESTURE_DRAG_START, GESTURE_DRAGGING):
        cv2.line(frame, thumb_tip, index_tip, cfg.COLOR_PURPLE, 3)
        cv2.circle(frame, index_tip, 12, cfg.COLOR_PURPLE, -1)
        mid_x = (thumb_tip[0] + index_tip[0]) // 2
        mid_y = (thumb_tip[1] + index_tip[1]) // 2
        cv2.putText(frame, "DRAG", (mid_x - 20, mid_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, cfg.COLOR_PURPLE, 2)

    elif gesture_name == GESTURE_DRAG_END:
        cv2.circle(frame, index_tip, 25, cfg.COLOR_SUCCESS, 3)

    # --- Scroll: mũi tên lên/xuống ---
    elif gesture_name in (GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN):
        cx = cfg.CAMERA_WIDTH // 2
        if gesture_name == GESTURE_SCROLL_UP:
            cv2.arrowedLine(frame, (cx, 100), (cx, 60), cfg.COLOR_INFO, 3, tipLength=0.5)
        else:
            cv2.arrowedLine(frame, (cx, 60), (cx, 100), cfg.COLOR_INFO, 3, tipLength=0.5)

    # --- Swipe: mũi tên ngang lớn ---
    elif gesture_name == GESTURE_SWIPE_LEFT:
        cy = cfg.CAMERA_HEIGHT // 2
        cv2.arrowedLine(frame, (400, cy), (240, cy), cfg.COLOR_SWIPE, 4, tipLength=0.3)
        cv2.putText(frame, "<<", (260, cy - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, cfg.COLOR_SWIPE, 3)

    elif gesture_name == GESTURE_SWIPE_RIGHT:
        cy = cfg.CAMERA_HEIGHT // 2
        cv2.arrowedLine(frame, (240, cy), (400, cy), cfg.COLOR_SWIPE, 4, tipLength=0.3)
        cv2.putText(frame, ">>", (340, cy - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, cfg.COLOR_SWIPE, 3)

    # --- Zoom: đường nối thumb-index + text ---
    elif gesture_name in (GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
        cv2.line(frame, thumb_tip, index_tip, cfg.COLOR_ZOOM, 3)
        cv2.circle(frame, thumb_tip, 8, cfg.COLOR_ZOOM, -1)
        cv2.circle(frame, index_tip, 8, cfg.COLOR_ZOOM, -1)
        mid_x = (thumb_tip[0] + index_tip[0]) // 2
        mid_y = (thumb_tip[1] + index_tip[1]) // 2
        label = "ZOOM IN" if gesture_name == GESTURE_ZOOM_IN else "ZOOM OUT"
        cv2.putText(frame, label, (mid_x - 30, mid_y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, cfg.COLOR_ZOOM, 2)


# ==============================================================================
# EVENT GESTURES (dùng để xác định linger)
# ==============================================================================
EVENT_GESTURES = {
    GESTURE_LEFT_CLICK, GESTURE_DOUBLE_CLICK, GESTURE_RIGHT_CLICK,
    GESTURE_DRAG_END, GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
    GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT,
    GESTURE_SYSTEM_TOGGLE
}


def draw_mode_indicator(frame, recognizer):
    """
    Vẽ mode indicator dưới banner: [ZOOM MODE], [SWIPE TRACKING].
    Cho người xem biết hệ thống đang ở mode nào trước khi trigger.
    """
    state = recognizer.get_state_info()
    labels = []
    if state.get("zoom_active"):
        labels.append("ZOOM MODE")
    if state.get("swipe_tracking"):
        labels.append("SWIPE TRACKING")
    if not labels:
        return

    y = 85  # Dưới banner chính
    for label in labels:
        text = f"[ {label} ]"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        tx = (cfg.CAMERA_WIDTH - tw) // 2
        # Nền bán trong suốt
        overlay = frame.copy()
        cv2.rectangle(overlay, (tx - 8, y - th - 4), (tx + tw + 8, y + 6),
                      (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        # Text
        color = cfg.COLOR_ZOOM if "ZOOM" in label else cfg.COLOR_SWIPE
        cv2.putText(frame, text, (tx, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        y += 30


def draw_hotkey_help(frame, system_active):
    """Hiển thị phím tắt ở góc dưới-phải."""
    lines = [
        "Q: Quit",
        f"S: {'Disable' if system_active else 'Enable'} control",
    ]
    y = cfg.CAMERA_HEIGHT - 15
    for line in reversed(lines):
        (tw, _), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(frame, line, (cfg.CAMERA_WIDTH - tw - 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, cfg.COLOR_WHITE, 1)
        y -= 18


def draw_context_hud(frame, context_manager, controller):
    """Ve Context-Aware HUD o goc tren-phai neu SHOW_CONTEXT_HUD = True.

    An toan khi context_manager hoac controller la None.
    Khong block camera loop.

    Args:
        frame:           Frame OpenCV
        context_manager: ContextManager instance hoac None
        controller:      MouseController instance hoac None
    """
    if not cfg.SHOW_CONTEXT_HUD:
        return
    if context_manager is None:
        return

    try:
        ctx        = context_manager.get_current_context()
        ctx_label  = context_manager.get_context_display()
        raw_title  = context_manager.get_current_window_title()
        short_title = (raw_title[:32] + "...") if len(raw_title) > 32 else raw_title

        last_action = "no_action"
        if controller is not None:
            last_action = getattr(controller, "last_routed_action", "no_action")

        # Mau sac vien/tieu de theo context (BGR format - OpenCV)
        ctx_color_map = {
            "browser":      (  0, 255, 255),   # Vang tuoi    BGR(0,255,255)
            "presentation": (  0, 255,   0),   # Xanh la tuoi BGR(0,255,0)
            "document":     (255, 160,  60),   # Xanh duong   BGR(255,160,60)
            "media":        (255,   0, 255),   # Tim hong     BGR(255,0,255)
            "default":      (160, 160, 160),   # Xam
        }
        color = ctx_color_map.get(ctx, cfg.COLOR_WHITE)

        # Mau dong ACT: xanh la sang neu co action, xam neu no_action
        act_color = (0, 230, 100) if last_action != "no_action" else (120, 120, 120)

        lines = [
            ctx_label,
            f"ACT: {last_action}",
            f"WIN: {short_title}",
        ]
        line_colors = [color, act_color, cfg.COLOR_WHITE]

        font       = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.48
        thickness  = 1
        line_h     = 20
        pad        = 6

        # Tinh chieu rong toi da
        max_w = max(cv2.getTextSize(l, font, font_scale, thickness)[0][0] for l in lines)
        box_w = max_w + pad * 2
        box_h = line_h * len(lines) + pad * 2

        # Goc tren-phai
        x0 = cfg.CAMERA_WIDTH - box_w - 4
        y0 = 4

        # Nen ban trong suot
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        # Vien mau theo context (2px de nhin ro hon)
        cv2.rectangle(frame, (x0, y0), (x0 + box_w, y0 + box_h), color, 2)

        # Text lines
        for i, line in enumerate(lines):
            ty = y0 + pad + line_h * (i + 1) - 2
            cv2.putText(frame, line, (x0 + pad, ty),
                        font, font_scale, line_colors[i], thickness)

    except Exception:
        pass  # Tuyet doi khong crash camera loop


# ==============================================================================
# DUPLICATE HAND FILTER — Loai truong hop MediaPipe nhan 1 tay thanh 2
# ==============================================================================

def _compute_iou(bbox_a, bbox_b):
    """Tinh Intersection over Union giua 2 bbox (x1, y1, x2, y2).

    Returns:
        (iou, overlap_area): float IoU [0,1] va dien tich overlap (px^2)
    """
    if bbox_a is None or bbox_b is None:
        return 0.0, 0

    x1 = max(bbox_a[0], bbox_b[0])
    y1 = max(bbox_a[1], bbox_b[1])
    x2 = min(bbox_a[2], bbox_b[2])
    y2 = min(bbox_a[3], bbox_b[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    overlap_area = inter_w * inter_h

    area_a = max(0, (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1]))
    area_b = max(0, (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1]))
    union = area_a + area_b - overlap_area

    if union <= 0:
        return 0.0, 0

    return overlap_area / union, overlap_area


def _filter_duplicate_hands(all_hands):
    """Loc duplicate: neu 2 hand thuc chat la 1 ban tay, chi giu 1.

    Logic hybrid (theo yeu cau):
      - IoU > DUPLICATE_HAND_IOU_THRESHOLD  => duplicate ro rang
      - center_dist < DUPLICATE_HAND_CENTER_DISTANCE
          AND 0.6 <= size_ratio <= 1.6
          AND overlap_area > 0             => duplicate phong thu

    Khi duplicate, uu tien giu hand co label khop PRIMARY_HAND_LABEL.
    Neu ca 2 cung label, giu hand co confidence cao hon (qua MediaPipe score
    luu trong hand data, hien tai fallback giu hand dau tien).

    Args:
        all_hands: list[dict] tu get_all_hands_data()

    Returns:
        list[dict]: da loc duplicate
    """
    if len(all_hands) < 2:
        return all_hands

    iou_thresh = getattr(cfg, 'DUPLICATE_HAND_IOU_THRESHOLD', 0.35)
    center_thresh = getattr(cfg, 'DUPLICATE_HAND_CENTER_DISTANCE', 80)
    min_palm = getattr(cfg, 'MIN_PALM_SIZE', 30)

    # --- Loc hand co palm_size qua nho (detection loi) ---
    valid_hands = []
    for hd in all_hands:
        ps = hd.get("palm_size", 0)
        if ps >= min_palm:
            valid_hands.append(hd)
        else:
            print(f"[DUP_FILTER] Removed hand idx={hd['hand_index']} "
                  f"palm_size={ps:.0f} < {min_palm}")

    if len(valid_hands) < 2:
        return valid_hands

    # --- Kiem tra tung cap hand ---
    # Voi MAX_NUM_HANDS=2, toi da 2 hand, chi can kiem tra 1 cap
    to_remove = set()

    for i in range(len(valid_hands)):
        if i in to_remove:
            continue
        for j in range(i + 1, len(valid_hands)):
            if j in to_remove:
                continue

            h_a = valid_hands[i]
            h_b = valid_hands[j]

            bbox_a = h_a.get("bbox")
            bbox_b = h_b.get("bbox")

            # Tinh IoU
            iou, overlap_area = _compute_iou(bbox_a, bbox_b)

            # Tinh center distance
            ca = h_a.get("center")
            cb = h_b.get("center")
            if ca and cb:
                center_dist = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
            else:
                center_dist = 9999

            # Tinh size ratio
            ps_a = h_a.get("palm_size", 1)
            ps_b = h_b.get("palm_size", 1)
            size_ratio = ps_a / ps_b if ps_b > 0 else 999

            # --- Hybrid logic ---
            is_duplicate = (
                iou > iou_thresh
                or (
                    center_dist < center_thresh
                    and 0.6 <= size_ratio <= 1.6
                    and overlap_area > 0
                )
            )

            if is_duplicate:
                # Uu tien giu hand co label = PRIMARY_HAND_LABEL
                primary_label = getattr(cfg, 'PRIMARY_HAND_LABEL', 'Right')
                if h_a["handedness"] == primary_label and h_b["handedness"] != primary_label:
                    to_remove.add(j)
                elif h_b["handedness"] == primary_label and h_a["handedness"] != primary_label:
                    to_remove.add(i)
                else:
                    # Ca 2 cung label hoac ca 2 khong phai primary → giu hand dau
                    to_remove.add(j)

                print(f"[DUP_FILTER] Duplicate detected! "
                      f"IoU={iou:.2f} center_dist={center_dist:.0f} "
                      f"size_ratio={size_ratio:.2f} overlap={overlap_area} "
                      f"— removed hand idx={valid_hands[list(to_remove)[-1]]['hand_index']} "
                      f"label={valid_hands[list(to_remove)[-1]]['handedness']}")

    result = [h for idx, h in enumerate(valid_hands) if idx not in to_remove]
    return result


def _are_hands_separated(hand_a, hand_b):
    """Kiem tra 2 tay thuc su tach biet (defense in depth cho mode switching).

    Returns:
        True neu 2 tay du xa + khong overlap qua nhieu + palm_size hop le.
        False neu 2 tay co dau hieu la duplicate hoac overlap lon.
    """
    if hand_a is None or hand_b is None:
        return False

    iou_thresh = getattr(cfg, 'DUPLICATE_HAND_IOU_THRESHOLD', 0.35)
    center_thresh = getattr(cfg, 'DUPLICATE_HAND_CENTER_DISTANCE', 80)
    min_palm = getattr(cfg, 'MIN_PALM_SIZE', 30)

    # Palm size check
    ps_a = hand_a.get("palm_size", 0)
    ps_b = hand_b.get("palm_size", 0)
    if ps_a < min_palm or ps_b < min_palm:
        return False

    # IoU check
    iou, overlap_area = _compute_iou(hand_a.get("bbox"), hand_b.get("bbox"))
    if iou > iou_thresh:
        return False

    # Center distance + size ratio check
    ca = hand_a.get("center")
    cb = hand_b.get("center")
    if ca and cb:
        center_dist = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
        size_ratio = ps_a / ps_b if ps_b > 0 else 999
        if (center_dist < center_thresh
                and 0.6 <= size_ratio <= 1.6
                and overlap_area > 0):
            return False

    return True


def main():
    """Hàm chính — khởi tạo modules, chạy vòng lặp real-time."""
    print("=" * 50)
    print("  AI Mouse Controller - Starting...")
    print("=" * 50)

    # Webcam
    cap = cv2.VideoCapture(cfg.CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_HEIGHT)
    # Giam camera buffer de frame luon moi nhat — giam input lag
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass  # Khong phai backend nao cung ho tro

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam!")
        return

    # Modules
    detector = HandDetector()
    coordinator = GestureCoordinator()          # 2-hand mode
    fallback_recognizer = GestureRecognizer()   # 1-hand fallback

    # --- Context-Aware Gestures: khoi tao an toan ---
    context_manager = None
    action_router   = None
    if cfg.ENABLE_CONTEXT_AWARE and _CONTEXT_MODULES_OK:
        try:
            context_manager = ContextManager()
            action_router   = ActionRouter(context_manager)
            print("  Context-Aware Gestures: ON")
        except Exception as _e:
            print(f"  [WARN] Context-Aware init failed: {_e} — fallback legacy")
            context_manager = None
            action_router   = None
    else:
        if not cfg.ENABLE_CONTEXT_AWARE:
            print("  Context-Aware Gestures: OFF (ENABLE_CONTEXT_AWARE=False)")

    controller = MouseController(action_router=action_router)

    def _update_runtime_ctx():
        """Cap nhat runtime context cho controller truoc khi dispatch gesture.

        Dung duoc o moi nhanh (TWO_HAND / grace / fallback).
        Boc try/except: khong bao gio crash camera loop.
        "INIT" duoc chuan hoa thanh "ONE_HAND" de log khong chua gia tri noi bo.
        """
        try:
            runtime_mode = current_mode if current_mode != "INIT" else "ONE_HAND"
            controller.set_runtime_context(
                mode=runtime_mode,
                system_active=system_active,
                fps=fps,
                window_title=(
                    context_manager.get_current_window_title()
                    if context_manager is not None else ""
                ),
            )
        except Exception:
            pass

    # --- Gesture Logger ---
    gesture_logger = None
    if getattr(cfg, "ENABLE_GESTURE_LOGGING", False) and _LOGGER_MODULE_OK:
        try:
            gesture_logger = GestureLogger(
                enabled=cfg.ENABLE_GESTURE_LOGGING,
                log_dir=getattr(cfg, "GESTURE_LOG_DIR", "logs"),
            )
            controller.event_logger = gesture_logger
        except Exception as _log_init_err:
            print(f"  [WARN] GestureLogger init failed: {_log_init_err} -- logging disabled")
            gesture_logger = None

    # --- Voice Command Mode ---
    voice_intent_parser   = None
    voice_cmd_executor    = None
    _voice_cmd_active     = (
        cfg.ENABLE_VOICE_INPUT
        and getattr(cfg, "ENABLE_VOICE_COMMANDS", False)
        and _VOICE_CMD_MODULES_OK
    )

    if _voice_cmd_active:
        try:
            def _voice_system_on():
                coordinator.system_active = True
                print("[VOICE_CMD] System ON via voice command")

            def _voice_system_off():
                coordinator.system_active = False
                if controller.is_dragging:
                    controller.drag_end()
                print("[VOICE_CMD] System OFF via voice command")

            voice_intent_parser = VoiceIntentParser()
            voice_cmd_executor  = VoiceCommandExecutor(
                dry_run=getattr(cfg, "VOICE_COMMAND_DRY_RUN", False),
                system_on_callback=_voice_system_on,
                system_off_callback=_voice_system_off,
            )
        except Exception as _vcmd_init_err:
            print(f"  [WARN] Voice Command init failed: {_vcmd_init_err} -- disabled")
            voice_intent_parser = None
            voice_cmd_executor  = None
            _voice_cmd_active   = False

    # --- Voice Input ---
    if cfg.ENABLE_VOICE_INPUT:
        voice_manager = VoiceInputManager()
        voice_thread = None             # Thread hien tai (None = chua chay)
        voice_state = VoiceState.IDLE   # State hien thi tren UI
        voice_result_text = ""          # Text nhan duoc gan nhat

        def _on_voice_hotkey():
            """Callback khi nguoi dung nhan global hotkey."""
            nonlocal voice_thread, voice_state, voice_result_text
            if voice_thread is not None and voice_thread.is_alive():
                print("[VOICE] Already listening, please wait...")
                return
            voice_manager.reset()
            voice_state = VoiceState.LISTENING
            voice_result_text = ""
            print(f"[VOICE] Triggered via {cfg.VOICE_HOTKEY} — listening...")

            def _voice_worker():
                nonlocal voice_state, voice_result_text
                result = voice_manager.listen_and_recognize()
                if result["state"] == VoiceState.DONE:
                    raw_text = result["text"]
                    voice_result_text = raw_text
                    voice_state = VoiceState.TYPING

                    # --- Voice Command routing ---
                    _handled_as_command = False
                    if _voice_cmd_active and voice_intent_parser is not None and voice_cmd_executor is not None:
                        try:
                            intent = voice_intent_parser.parse(raw_text)
                            if getattr(cfg, "VOICE_COMMAND_PRINT_RESULT", True):
                                print(f"[VOICE_CMD] Parse: type={intent['type']} intent={intent['intent']}")

                            if intent["type"] == "command":
                                ok = voice_cmd_executor.execute(intent)
                                if ok:
                                    print(f"[VOICE_CMD] Executed: {intent['intent']}")
                                else:
                                    print(f"[VOICE_CMD] Failed/skipped: {intent['intent']}")
                                voice_result_text = f"CMD: {intent['intent']}"
                                _handled_as_command = True
                        except Exception as _vcmd_err:
                            print(f"[VOICE_CMD] Error: {_vcmd_err} -- fallback to text")

                    # --- Text mode (fallback hoac khong co command mode) ---
                    if not _handled_as_command:
                        controller.type_text(raw_text)
                        if cfg.VOICE_AUTO_ENTER:
                            time.sleep(0.5)
                            controller.press_enter()
                            print("[VOICE] Auto Enter")

                    voice_state = VoiceState.DONE
                else:
                    voice_result_text = ""
                    voice_state = VoiceState.ERROR
                    print(f"[VOICE] Error: {result['error']}")

            voice_thread = threading.Thread(target=_voice_worker, daemon=True)
            voice_thread.start()

        keyboard.add_hotkey(cfg.VOICE_HOTKEY, _on_voice_hotkey)
        print(f"  Voice Input: ON (hotkey: {cfg.VOICE_HOTKEY.upper()})")

    # --- Gesture Voice Trigger helper (goi sau tung frame) ---
    def _check_gesture_voice_trigger():
        """Poll voice_trigger_fired tu secondary_recognizer va goi _on_voice_hotkey.

        An toan khi ENABLE_VOICE_INPUT=False hoac voice chua init.
        Goi sau toan bo dispatch moi frame de bat tat ca nhanh.
        """
        if not getattr(cfg, "ENABLE_GESTURE_VOICE_TRIGGER", False):
            return
        if not cfg.ENABLE_VOICE_INPUT:
            return
        rec = coordinator.secondary_recognizer
        if not getattr(rec, "voice_trigger_fired", False):
            return
        rec.voice_trigger_fired = False  # reset ngay truoc khi goi
        print("[GESTURE] Voice Trigger -> start voice input")
        try:
            _on_voice_hotkey()
        except Exception as _vt_err:
            print(f"[GESTURE] Voice Trigger callback error: {_vt_err}")

    # Track which mode is active
    is_two_hand_mode = False

    # --- Mode switching hysteresis ---
    # Tranh nhay mode khi MediaPipe hut tay 1-2 frame
    two_hand_count = 0      # So frame lien tuc thay 2 tay
    one_hand_count = 0      # So frame lien tuc thay <= 1 tay
    current_mode = "INIT"   # "TWO_HAND" / "ONE_HAND" / "INIT"

    # FPS
    prev_time = 0
    fps = 0
    fps_sum = 0.0        # Session stats: tong FPS
    fps_count = 0        # Session stats: so frame
    total_gestures = 0   # Session stats: tong gesture != None
    total_actions = 0    # Session stats: tong action dispatched

    # Lost hand grace
    lost_hand_frames = 0
    grace_limit = getattr(cfg, 'LOST_HAND_GRACE_FRAMES', 5)

    # Banner linger
    linger_gesture = None
    linger_counter = 0

    screen_w, screen_h = controller.get_screen_size()
    print(f"  Webcam: {cfg.CAMERA_WIDTH}x{cfg.CAMERA_HEIGHT}")
    print(f"  Screen: {screen_w}x{screen_h}")
    print(f"  Smoothing: {cfg.SMOOTHING_FACTOR}")
    print(f"  Two-Hand Mode: {cfg.ENABLE_TWO_HAND_MODE}")
    print(f"  Dominant Hand: {cfg.DOMINANT_HAND}")
    print(f"  DEMO_MODE: {'ON' if cfg.DEMO_MODE else 'OFF'}")
    if gesture_logger and gesture_logger.get_log_path():
        print(f"  Gesture Log: {gesture_logger.get_log_path()}")
    else:
        print(f"  Gesture Log: OFF")
    if cfg.ENABLE_VOICE_INPUT:
        if _voice_cmd_active:
            dry_tag = "  [DRY_RUN]" if getattr(cfg, "VOICE_COMMAND_DRY_RUN", False) else ""
            print(f"  Voice Commands: ON{dry_tag}")
        else:
            print(f"  Voice Commands: OFF")
    print(f"  System: OFF (hold 5 fingers on secondary hand 3s to enable)")
    print("=" * 50)
    print("  Press 'q' to quit | 's' to toggle control | 'd' to toggle DEMO")
    print("=" * 50)

    # --- Tao cua so OpenCV co kich thuoc co dinh ---
    cv2.namedWindow(cfg.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(cfg.WINDOW_NAME, cfg.CAMERA_WIDTH, cfg.CAMERA_HEIGHT)

    try:
        while True:
            # --- Đọc frame ---
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Cannot read frame!")
                break

            frame = cv2.flip(frame, 1)

            # --- Context-Aware: cap nhat context (co cache, khong block loop) ---
            if context_manager is not None:
                context_manager.update()

            # --- Detect ban tay ---
            frame = detector.find_hands(frame, draw=False)

            # --- 2 TAY: lay data cho tat ca tay ---
            all_hands = detector.get_all_hands_data(frame)

            # --- LOC DUPLICATE HAND ---
            # MediaPipe doi khi nhan 1 tay thanh 2 (label "Right" + "Left")
            # Loc truoc khi assign PRIMARY/SECONDARY
            all_hands = _filter_duplicate_hands(all_hands)
            num_hands = len(all_hands)

            # Reset lost hand grace khi co tay tro lai
            if num_hands > 0:
                lost_hand_frames = 0

            # ============================================================
            # HAND ASSIGNMENT (luon gan role bat ke mode)
            # ============================================================
            primary_hand = None
            secondary_hand = None

            if num_hands >= 2:
                for hd in all_hands:
                    if hd["handedness"] == cfg.PRIMARY_HAND_LABEL:
                        primary_hand = hd
                    elif hd["handedness"] == cfg.SECONDARY_HAND_LABEL:
                        secondary_hand = hd
                # Fallback neu 2 tay cung label
                if primary_hand is None and secondary_hand is None:
                    primary_hand = all_hands[0]
                    secondary_hand = all_hands[1]
                elif primary_hand is None:
                    primary_hand = [h for h in all_hands if h != secondary_hand][0]
                elif secondary_hand is None:
                    secondary_hand = [h for h in all_hands if h != primary_hand][0]

            elif num_hands == 1:
                hand = all_hands[0]
                # Luon gan theo dung handedness — khong cho tay phu thanh primary
                if hand["handedness"] == cfg.PRIMARY_HAND_LABEL:
                    primary_hand = hand
                elif hand["handedness"] == cfg.SECONDARY_HAND_LABEL:
                    secondary_hand = hand

            # ============================================================
            # HANDEDNESS DEBUG OVERLAY
            # ============================================================
            if cfg.SHOW_HANDEDNESS_DEBUG:
                font = cv2.FONT_HERSHEY_SIMPLEX
                for i, hd in enumerate(all_hands):
                    raw_label = hd["handedness"]
                    cx, cy = hd["center"] if hd["center"] else (50, 50)
                    if primary_hand and hd is primary_hand:
                        role_tag = "=PRI"
                        role_clr = cfg.COLOR_PRIMARY_HAND
                    elif secondary_hand and hd is secondary_hand:
                        role_tag = "=SEC"
                        role_clr = cfg.COLOR_SECONDARY_HAND
                    else:
                        role_tag = "=???"
                        role_clr = cfg.COLOR_DANGER
                    debug_text = f"MP:{raw_label}{role_tag}"
                    cv2.putText(frame, debug_text, (cx - 50, cy - 40),
                                font, 0.5, role_clr, 2)

                y_debug = 20
                cv2.putText(frame, f"PRI=MP:{cfg.PRIMARY_HAND_LABEL}(R hand)  SEC=MP:{cfg.SECONDARY_HAND_LABEL}(L hand)",
                            (cfg.CAMERA_WIDTH - 400, y_debug),
                            font, 0.35, (0, 255, 255), 1)

            # ============================================================
            # MODE SWITCHING HYSTERESIS
            # ============================================================
            if cfg.ENABLE_TWO_HAND_MODE:
                # Dieu kien vao TWO_HAND: 2 tay + assign thanh cong + tach biet thuc su
                hands_valid_for_two = (
                    num_hands >= 2
                    and primary_hand is not None
                    and secondary_hand is not None
                    and _are_hands_separated(primary_hand, secondary_hand)
                )
                if hands_valid_for_two:
                    two_hand_count += 1
                    one_hand_count = 0
                else:
                    one_hand_count += 1
                    two_hand_count = 0

                # Quyet dinh mode
                prev_mode = current_mode
                if current_mode != "TWO_HAND":
                    # Muon vao 2-hand mode -> phai du N frame lien tuc
                    if two_hand_count >= cfg.MODE_ENTER_TWO_HAND_FRAMES:
                        current_mode = "TWO_HAND"
                        is_two_hand_mode = True
                        if prev_mode != "TWO_HAND":
                            print(f"[MODE] Switched to TWO-HAND MODE")
                else:
                    # Dang o 2-hand mode -> chi roi ve fallback khi mat tay M frame lien tuc
                    if one_hand_count >= cfg.MODE_EXIT_TWO_HAND_FRAMES:
                        current_mode = "ONE_HAND"
                        is_two_hand_mode = False
                        print(f"[MODE] Switched to ONE-HAND FALLBACK MODE")
            else:
                current_mode = "ONE_HAND"
                is_two_hand_mode = False

            # --- Xu ly gesture ---
            gesture_result = None
            current_gesture = GESTURE_NONE
            system_active = False

            if is_two_hand_mode and primary_hand and secondary_hand:
                # ====== 2-HAND MODE ======

                coord_result = coordinator.process(primary_hand, secondary_hand)
                primary_result = coord_result["primary_result"]
                secondary_result = coord_result["secondary_result"]
                system_active = coord_result["system_active"]

                # Thuc thi primary action (move, click, drag, scroll)
                if system_active:
                    controller.process_gesture(primary_result)
                else:
                    if controller.is_dragging:
                        controller.drag_end()

                # Lay gesture name cua tung tay
                pri_g = primary_result.get("gesture", GESTURE_NONE)
                sec_g = secondary_result.get("gesture", GESTURE_NONE)

                # Cap nhat runtime context truoc khi dispatch
                _update_runtime_ctx()

                # Thuc thi secondary action (swipe, zoom)
                # Chi dispatch cac gesture co action that, khong dispatch toggle/open_palm
                if system_active and sec_g in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
                                                GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
                    print(f"[DISPATCH] Secondary: {sec_g}")
                    sec_action = {
                        "gesture": sec_g,
                        "cursor_pos": None,
                        "scroll_delta": None,
                        "drag_pos": None,
                        "click_anchor": None,
                        "click_freeze_until": 0,
                    }
                    controller.process_gesture(sec_action)
                elif not system_active and sec_g in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
                                                      GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
                    print(f"[DISPATCH] BLOCKED (system OFF): {sec_g}")

                # Event gestures uu tien hien thi
                if sec_g in EVENT_GESTURES or sec_g in (GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT,
                                                         GESTURE_SYSTEM_TOGGLE, GESTURE_OPEN_PALM):
                    current_gesture = sec_g
                elif pri_g != GESTURE_NONE:
                    current_gesture = pri_g
                else:
                    current_gesture = sec_g if sec_g != GESTURE_NONE else pri_g

                # Tao gesture_result compatible cho UI
                gesture_result = {
                    "gesture": current_gesture,
                    "cursor_pos": primary_result.get("cursor_pos"),
                    "scroll_delta": primary_result.get("scroll_delta"),
                    "drag_pos": primary_result.get("drag_pos"),
                    "system_active": system_active,
                    "click_anchor": primary_result.get("click_anchor"),
                    "click_freeze_until": primary_result.get("click_freeze_until", 0),
                }

                # Ve landmarks cho primary hand
                if primary_hand:
                    detector.landmark_list = primary_hand["landmarks"]
                    detector.draw_custom_landmarks(frame)
                    draw_gesture_feedback(
                        frame, pri_g,
                        primary_hand["landmarks"],
                        coordinator.primary_recognizer
                    )

                # Ve landmarks cho secondary hand
                if secondary_hand:
                    detector.landmark_list = secondary_hand["landmarks"]
                    detector.draw_custom_landmarks(frame)

            elif is_two_hand_mode and num_hands >= 1 and not (primary_hand and secondary_hand):
                # ====== 2-HAND MODE nhung tam hut 1 tay (hysteresis giu mode) ======
                system_active = coordinator.system_active

                if primary_hand:
                    # Tay chinh con -> van dieu khien cursor
                    detector.landmark_list = primary_hand["landmarks"]
                    primary_result = coordinator.primary_recognizer.recognize(
                        primary_hand["landmarks"],
                        primary_hand["fingers"],
                        primary_hand["palm_size"]
                    )
                    if system_active:
                        controller.process_gesture(primary_result)
                    current_gesture = primary_result.get("gesture", GESTURE_NONE)
                    detector.draw_custom_landmarks(frame)
                    draw_gesture_feedback(
                        frame, current_gesture,
                        primary_hand["landmarks"],
                        coordinator.primary_recognizer
                    )

                elif secondary_hand:
                    # Tay phu con -> Toggle + Swipe + Zoom, KHONG cho cursor/click/drag/scroll
                    detector.landmark_list = secondary_hand["landmarks"]
                    sec_result = coordinator.secondary_recognizer.recognize(
                        secondary_hand["landmarks"],
                        secondary_hand["fingers"],
                        secondary_hand["palm_size"],
                        secondary_hand["center"]
                    )
                    system_active = coordinator.system_active
                    sec_gesture = sec_result.get("gesture", GESTURE_NONE)

                    # Dispatch swipe/zoom action that
                    if system_active and sec_gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
                                                          GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
                        print(f"[DISPATCH] Secondary (grace): {sec_gesture}")
                        _update_runtime_ctx()  # Enrich log voi runtime data that
                        sec_action = {
                            "gesture": sec_gesture,
                            "cursor_pos": None,
                            "scroll_delta": None,
                            "drag_pos": None,
                            "click_anchor": None,
                            "click_freeze_until": 0,
                        }
                        controller.process_gesture(sec_action)

                    current_gesture = sec_gesture if sec_gesture != GESTURE_NONE else GESTURE_NONE
                    detector.draw_custom_landmarks(frame)

                else:
                    current_gesture = GESTURE_NONE

                gesture_result = {
                    "gesture": current_gesture,
                    "cursor_pos": None,
                    "scroll_delta": None,
                    "drag_pos": None,
                    "system_active": system_active,
                    "click_anchor": None,
                    "click_freeze_until": 0,
                }

            elif not is_two_hand_mode and num_hands >= 1:
                # ====== FALLBACK 1-HAND MODE (role-aware) ======

                if primary_hand:
                    # --- TAY PHAI mot minh: Move/Click/Drag/Scroll ---
                    # Dung PrimaryHandRecognizer (KHONG dung fallback_recognizer vi no co swipe/zoom/toggle)
                    detector.landmark_list = primary_hand["landmarks"]

                    primary_result = coordinator.primary_recognizer.recognize(
                        primary_hand["landmarks"],
                        primary_hand["fingers"],
                        primary_hand["palm_size"]
                    )

                    system_active = coordinator.system_active
                    current_gesture = primary_result.get("gesture", GESTURE_NONE)

                    if system_active:
                        controller.process_gesture(primary_result)
                    else:
                        if controller.is_dragging:
                            controller.drag_end()

                    gesture_result = {
                        "gesture": current_gesture,
                        "cursor_pos": primary_result.get("cursor_pos"),
                        "scroll_delta": primary_result.get("scroll_delta"),
                        "drag_pos": primary_result.get("drag_pos"),
                        "system_active": system_active,
                        "click_anchor": primary_result.get("click_anchor"),
                        "click_freeze_until": primary_result.get("click_freeze_until", 0),
                    }

                    detector.draw_custom_landmarks(frame)
                    draw_gesture_feedback(
                        frame, current_gesture,
                        primary_hand["landmarks"], coordinator.primary_recognizer
                    )

                elif secondary_hand:
                    # --- TAY PHU mot minh: Toggle + Swipe + Zoom, KHONG dieu khien chuot ---
                    detector.landmark_list = secondary_hand["landmarks"]

                    sec_result = coordinator.secondary_recognizer.recognize(
                        secondary_hand["landmarks"],
                        secondary_hand["fingers"],
                        secondary_hand["palm_size"],
                        secondary_hand["center"]
                    )
                    system_active = coordinator.system_active
                    sec_gesture = sec_result.get("gesture", GESTURE_NONE)

                    # Dispatch swipe/zoom action that
                    if system_active and sec_gesture in (GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
                                                          GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT):
                        print(f"[DISPATCH] Secondary (fallback): {sec_gesture}")
                        _update_runtime_ctx()  # Enrich log voi runtime data that
                        sec_action = {
                            "gesture": sec_gesture,
                            "cursor_pos": None,
                            "scroll_delta": None,
                            "drag_pos": None,
                            "click_anchor": None,
                            "click_freeze_until": 0,
                        }
                        controller.process_gesture(sec_action)

                    current_gesture = sec_gesture if sec_gesture != GESTURE_NONE else GESTURE_NONE

                    gesture_result = {
                        "gesture": current_gesture,
                        "cursor_pos": None,
                        "scroll_delta": None,
                        "drag_pos": None,
                        "system_active": system_active,
                        "click_anchor": None,
                        "click_freeze_until": 0,
                    }

                    detector.draw_custom_landmarks(frame)
                else:
                    current_gesture = GESTURE_NONE
                    system_active = coordinator.system_active  # Luon dung coordinator lam source chinh
                    gesture_result = {
                        "gesture": GESTURE_NONE,
                        "cursor_pos": None,
                        "scroll_delta": None,
                        "drag_pos": None,
                        "system_active": system_active,
                        "click_anchor": None,
                        "click_freeze_until": 0,
                    }

            elif num_hands == 0:
                # ====== KHONG CO TAY ======
                # Lost hand grace: khong reset ngay, cho vài frame
                lost_hand_frames += 1

                if lost_hand_frames <= grace_limit:
                    # Trong grace: giu state, KHONG action moi
                    current_gesture = GESTURE_NONE
                    system_active = coordinator.system_active
                    gesture_result = {
                        "gesture": GESTURE_NONE,
                        "cursor_pos": None,
                        "scroll_delta": None,
                        "drag_pos": None,
                        "system_active": system_active,
                        "click_anchor": None,
                        "click_freeze_until": 0,
                    }
                    # Khong release drag trong grace
                else:
                    # Qua grace: reset state, release drag an toan
                    current_gesture = GESTURE_NONE
                    system_active = coordinator.system_active
                    gesture_result = {
                        "gesture": GESTURE_NONE,
                        "cursor_pos": None,
                        "scroll_delta": None,
                        "drag_pos": None,
                        "system_active": system_active,
                        "click_anchor": None,
                        "click_freeze_until": 0,
                    }
                    if controller.is_dragging:
                        controller.drag_end()
                        print("[GRACE] Drag released — hand lost too long")

            # --- Ve bbox + label cho tung tay ---
            if primary_hand and primary_hand["bbox"]:
                pri_label = "PRIMARY"
                if is_two_hand_mode:
                    pri_g_name = coordinator.primary_recognizer.current_gesture
                    if pri_g_name != GESTURE_NONE:
                        pri_label += f": {pri_g_name}"
                if system_active:
                    pri_label += " [ON]"
                detector.draw_hand_label(
                    frame, primary_hand["bbox"],
                    pri_label, cfg.COLOR_PRIMARY_HAND
                )

            if secondary_hand and secondary_hand["bbox"]:
                sec_label = "SECONDARY"
                if is_two_hand_mode:
                    sec_g_name = coordinator.secondary_recognizer.current_gesture
                    if sec_g_name != GESTURE_NONE:
                        sec_label += f": {sec_g_name}"
                detector.draw_hand_label(
                    frame, secondary_hand["bbox"],
                    sec_label, cfg.COLOR_SECONDARY_HAND
                )

            # --- Poll Gesture Voice Trigger (sau toan bo dispatch, moi nhanh) ---
            _check_gesture_voice_trigger()

            # --- MODE DISPLAY (hien thi ro rang mode hien tai) ---
            font = cv2.FONT_HERSHEY_SIMPLEX
            if current_mode == "TWO_HAND":
                mode_text = "TWO-HAND MODE ACTIVE"
                mode_color = cfg.COLOR_SUCCESS
            elif current_mode == "ONE_HAND":
                mode_text = "ONE-HAND FALLBACK MODE"
                mode_color = cfg.COLOR_SECONDARY
            else:
                mode_text = f"DETECTING... ({two_hand_count}/{cfg.MODE_ENTER_TWO_HAND_FRAMES})"
                mode_color = cfg.COLOR_ROI_BORDER
            text_size = cv2.getTextSize(mode_text, font, 0.55, 2)[0]
            text_x = (cfg.CAMERA_WIDTH - text_size[0]) // 2
            cv2.putText(frame, mode_text,
                        (text_x, cfg.CAMERA_HEIGHT - 10),
                        font, 0.55, mode_color, 2)

            # --- Cap nhat linger ---
            if current_gesture in EVENT_GESTURES:
                linger_gesture = current_gesture
                linger_counter = cfg.BANNER_LINGER_FRAMES

            # --- Ve Banner ---
            if linger_counter > 0 and current_gesture in (GESTURE_NONE, GESTURE_MOVE):
                draw_linger_banner(frame, linger_gesture, linger_counter)
                linger_counter -= 1
            else:
                banner_result = draw_gesture_banner(
                    frame, current_gesture, system_active, linger_counter
                )
                if banner_result is None and linger_counter > 0:
                    draw_linger_banner(frame, linger_gesture, linger_counter)
                    linger_counter -= 1

            # --- ROI ---
            detector.draw_roi(frame)

            # --- Toggle progress bar ---
            # Luon lay tu coordinator.secondary_recognizer (nguon toggle chinh)
            draw_toggle_progress(frame, coordinator.get_toggle_progress())

            # --- FPS ---
            current_time = time.time()
            if current_time - prev_time > 0:
                fps = 1 / (current_time - prev_time)
            prev_time = current_time
            # Session stats
            fps_sum += fps
            fps_count += 1
            if current_gesture not in (GESTURE_NONE, GESTURE_MOVE, GESTURE_OPEN_PALM):
                total_gestures += 1

            # --- HUD ---
            detector.draw_info(frame, fps, current_gesture, system_active)

            # --- Mode indicator ---
            # Luon lay tu coordinator.secondary_recognizer (nguon zoom/swipe chinh)
            draw_mode_indicator(frame, coordinator.secondary_recognizer)

            # --- Hotkey help ---
            draw_hotkey_help(frame, system_active)

            # --- Context HUD (goc tren-phai) ---
            draw_context_hud(frame, context_manager, controller)

            # --- DEMO MODE overlay ---
            if getattr(cfg, 'DEMO_MODE', False):
                dm_text = "DEMO MODE"
                dm_font = cv2.FONT_HERSHEY_SIMPLEX
                dm_size = cv2.getTextSize(dm_text, dm_font, 0.6, 2)[0]
                dm_x = cfg.CAMERA_WIDTH - dm_size[0] - 10
                dm_y = 60
                # Background
                cv2.rectangle(frame, (dm_x - 5, dm_y - dm_size[1] - 5),
                              (dm_x + dm_size[0] + 5, dm_y + 5),
                              (0, 100, 0), -1)
                cv2.putText(frame, dm_text, (dm_x, dm_y),
                            dm_font, 0.6, (0, 255, 0), 2)

            # --- Voice status overlay ---
            if cfg.ENABLE_VOICE_INPUT and cfg.VOICE_STATUS_DISPLAY:
                is_busy = (voice_thread is not None and voice_thread.is_alive())
                if is_busy or voice_state not in (VoiceState.IDLE, VoiceState.DONE, VoiceState.ERROR):
                    if voice_state == VoiceState.LISTENING:
                        v_text = "[MIC] LISTENING..."
                        v_color = cfg.COLOR_VOICE
                    elif voice_state == VoiceState.RECOGNIZING:
                        v_text = "[MIC] RECOGNIZING..."
                        v_color = cfg.COLOR_VOICE
                    elif voice_state == VoiceState.TYPING:
                        v_text = f"[MIC] TYPING: {voice_result_text[:30]}"
                        v_color = cfg.COLOR_SUCCESS
                    else:
                        v_text = f"[MIC] {voice_state}"
                        v_color = cfg.COLOR_VOICE
                    cv2.putText(frame, v_text,
                                (10, cfg.CAMERA_HEIGHT - 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, v_color, 2)
                elif voice_state == VoiceState.ERROR:
                    cv2.putText(frame, f"[MIC] Error ({cfg.VOICE_HOTKEY.upper()} to retry)",
                                (10, cfg.CAMERA_HEIGHT - 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, cfg.COLOR_DANGER, 1)
                elif voice_state == VoiceState.DONE and voice_result_text:
                    cv2.putText(frame, f"[MIC] Done: {voice_result_text[:35]}",
                                (10, cfg.CAMERA_HEIGHT - 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, cfg.COLOR_SUCCESS, 1)

            # --- Hien thi ---
            cv2.imshow(cfg.WINDOW_NAME, frame)

            # --- Phim dieu khien ---
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("\n[INFO] Exiting...")
                break
            elif key == ord('s') or key == ord('S'):
                # Luon toggle coordinator.system_active — nguon state doc nhat
                coordinator.system_active = not coordinator.system_active
                state = "ON" if coordinator.system_active else "OFF"
                print(f"[KEY] System {state}")
                if state == "OFF" and controller.is_dragging:
                    controller.drag_end()
            elif key == ord('d') or key == ord('D'):
                cfg.DEMO_MODE = not cfg.DEMO_MODE
                print(f"[KEY] DEMO_MODE {'ON' if cfg.DEMO_MODE else 'OFF'}")

            # (Voice duoc xu ly qua global hotkey, khong can cv2 key handler o day)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted (Ctrl+C)")

    except Exception as e:
        print(f"\n[ERROR] Runtime exception: {e}")
        traceback.print_exc()

    finally:
        if controller.is_dragging:
            controller.drag_end()
        if gesture_logger is not None:
            try:
                gesture_logger.close()
            except Exception:
                pass
        if cfg.ENABLE_VOICE_INPUT:
            keyboard.unhook_all_hotkeys()   # Giai phong global hotkey khi thoat
        cap.release()
        detector.release()
        cv2.destroyAllWindows()

        # --- Session Stats ---
        print("\n" + "=" * 50)
        print("  SESSION STATISTICS")
        print("=" * 50)
        avg_fps = (fps_sum / fps_count) if fps_count > 0 else 0
        print(f"  Average FPS:    {avg_fps:.1f}")
        print(f"  Total Frames:   {fps_count}")
        print(f"  Total Gestures: {total_gestures}")
        print(f"  DEMO_MODE:      {'ON' if cfg.DEMO_MODE else 'OFF'}")
        print("=" * 50)
        print("[INFO] Resources released. Goodbye!")


if __name__ == "__main__":
    main()

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
import config as cfg
from hand_tracking import HandDetector
from gesture_recognition import (
    GestureRecognizer,
    GESTURE_NONE, GESTURE_MOVE,
    GESTURE_LEFT_CLICK, GESTURE_DOUBLE_CLICK, GESTURE_RIGHT_CLICK,
    GESTURE_DRAG_START, GESTURE_DRAGGING, GESTURE_DRAG_END,
    GESTURE_SCROLL_UP, GESTURE_SCROLL_DOWN,
    GESTURE_SWIPE_LEFT, GESTURE_SWIPE_RIGHT,
    GESTURE_ZOOM_IN, GESTURE_ZOOM_OUT,
    GESTURE_SYSTEM_TOGGLE, GESTURE_OPEN_PALM
)
from mouse_controller import MouseController


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


def main():
    """Hàm chính — khởi tạo modules, chạy vòng lặp real-time."""
    print("=" * 50)
    print("  AI Mouse Controller - Starting...")
    print("=" * 50)

    # Webcam
    cap = cv2.VideoCapture(cfg.CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_HEIGHT)

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam!")
        return

    # Modules
    detector = HandDetector()
    recognizer = GestureRecognizer()
    controller = MouseController()

    # FPS
    prev_time = 0
    fps = 0

    # Banner linger
    linger_gesture = None
    linger_counter = 0

    screen_w, screen_h = controller.get_screen_size()
    print(f"  Webcam: {cfg.CAMERA_WIDTH}x{cfg.CAMERA_HEIGHT}")
    print(f"  Screen: {screen_w}x{screen_h}")
    print(f"  Smoothing: {cfg.SMOOTHING_FACTOR}")
    print(f"  System: {'ON' if recognizer.system_active else 'OFF (hold 5 fingers 3s to enable)'}")
    print("=" * 50)
    print("  Press 'q' to quit | 's' to toggle control")
    print("=" * 50)

    try:
        while True:
            # --- Đọc frame ---
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Cannot read frame!")
                break

            frame = cv2.flip(frame, 1)

            # --- Detect bàn tay ---
            frame = detector.find_hands(frame, draw=False)
            landmark_list, bbox = detector.find_position(frame)

            # --- Xử lý gesture ---
            gesture_result = None

            if detector.is_hand_detected() and landmark_list:
                fingers = detector.fingers_up()
                palm_size = detector.get_palm_size()
                hand_center = detector.get_hand_center()

                gesture_result = recognizer.recognize(
                    landmark_list, fingers, palm_size, hand_center
                )

                # Thuc thi action (chi khi system ON)
                if gesture_result["system_active"]:
                    controller.process_gesture(gesture_result)
                else:
                    # Safety: release drag khi system vua OFF
                    if controller.is_dragging:
                        controller.drag_end()

                # Vẽ custom landmarks
                detector.draw_custom_landmarks(frame)

                # Visual feedback cho gesture trên tay
                draw_gesture_feedback(
                    frame, gesture_result["gesture"], landmark_list, recognizer
                )

                # Bounding box (xanh = ON, đỏ = OFF)
                if bbox:
                    x1, y1, x2, y2 = bbox
                    bb_color = cfg.COLOR_SUCCESS if gesture_result["system_active"] else cfg.COLOR_DANGER
                    cv2.rectangle(frame, (x1, y1), (x2, y2), bb_color, 2)

            else:
                # Mất tracking → reset states
                gesture_result = recognizer.recognize([], [], 0, None)
                # An toàn: thả chuột nếu đang drag
                if controller.is_dragging:
                    controller.drag_end()

            # --- Cập nhật linger ---
            current_gesture = gesture_result["gesture"] if gesture_result else GESTURE_NONE
            system_active = gesture_result["system_active"] if gesture_result else False

            if current_gesture in EVENT_GESTURES:
                linger_gesture = current_gesture
                linger_counter = cfg.BANNER_LINGER_FRAMES

            # --- Vẽ Banner ---
            if linger_counter > 0 and current_gesture in (GESTURE_NONE, GESTURE_MOVE):
                # Event vừa xảy ra → hiển thị linger
                draw_linger_banner(frame, linger_gesture, linger_counter)
                linger_counter -= 1
            else:
                # Hiển thị banner bình thường
                banner_result = draw_gesture_banner(
                    frame, current_gesture, system_active, linger_counter
                )
                if banner_result is None and linger_counter > 0:
                    draw_linger_banner(frame, linger_gesture, linger_counter)
                    linger_counter -= 1

            # --- ROI ---
            detector.draw_roi(frame)

            # --- Toggle progress bar ---
            draw_toggle_progress(frame, recognizer.get_toggle_progress())

            # --- FPS ---
            current_time = time.time()
            if current_time - prev_time > 0:
                fps = 1 / (current_time - prev_time)
            prev_time = current_time

            # --- HUD (FPS + Gesture + Status ở góc trái) ---
            detector.draw_info(frame, fps, current_gesture, system_active)

            # --- Mode indicator ---
            draw_mode_indicator(frame, recognizer)

            # --- Hotkey help ---
            draw_hotkey_help(frame, system_active)

            # --- Hiển thị ---
            cv2.imshow(cfg.WINDOW_NAME, frame)

            # --- Phím điều khiển ---
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("\n[INFO] Exiting...")
                break
            elif key == ord('s') or key == ord('S'):
                recognizer.system_active = not recognizer.system_active
                state = "ON" if recognizer.system_active else "OFF"
                print(f"[KEY] System {state}")
                # Safety: release drag when system OFF
                if not recognizer.system_active and controller.is_dragging:
                    controller.drag_end()

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted (Ctrl+C)")

    finally:
        if controller.is_dragging:
            controller.drag_end()
        cap.release()
        detector.release()
        cv2.destroyAllWindows()
        print("[INFO] Resources released. Goodbye!")


if __name__ == "__main__":
    main()

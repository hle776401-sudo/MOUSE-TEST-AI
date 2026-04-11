"""
hand_tracking.py - Module phát hiện và theo dõi bàn tay
======================================================
Sử dụng MediaPipe Hands để detect bàn tay real-time qua webcam.
Cung cấp class HandDetector với các phương thức:
  - find_hands(): Phát hiện bàn tay trong frame
  - find_position(): Trả về danh sách tọa độ landmarks
  - fingers_up(): Xác định ngón tay nào đang giơ lên
  - draw_landmarks(): Vẽ landmarks tùy chỉnh lên frame
"""

import cv2
import mediapipe as mp
import numpy as np
import config as cfg


class HandDetector:
    """
    Class phát hiện và theo dõi bàn tay sử dụng MediaPipe.

    Attributes:
        mp_hands: MediaPipe Hands solution
        hands: Đối tượng Hands đã cấu hình
        mp_draw: MediaPipe Drawing utilities
        results: Kết quả detection mới nhất
        landmark_list: Danh sách tọa độ (id, x, y) của 21 landmarks
    """

    def __init__(self,
                 max_hands=cfg.MAX_NUM_HANDS,
                 detection_confidence=cfg.MIN_DETECTION_CONFIDENCE,
                 tracking_confidence=cfg.MIN_TRACKING_CONFIDENCE,
                 model_complexity=cfg.MODEL_COMPLEXITY):
        """
        Khởi tạo HandDetector.

        Args:
            max_hands: Số bàn tay tối đa cần phát hiện
            detection_confidence: Ngưỡng tin cậy phát hiện (0.0 - 1.0)
            tracking_confidence: Ngưỡng tin cậy theo dõi (0.0 - 1.0)
            model_complexity: Độ phức tạp model (0 hoặc 1)
        """
        # Khởi tạo MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,        # Video mode (không phải ảnh tĩnh)
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
            model_complexity=model_complexity
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_draw_styles = mp.solutions.drawing_styles

        # Kết quả và dữ liệu
        self.results = None
        self.landmark_list = []             # Danh sách [(id, x, y), ...]
        self.landmark_list_normalized = []  # Danh sách tọa độ chuẩn hóa [0,1]

        # Cấu hình custom drawing
        self._landmark_drawing_spec = self.mp_draw.DrawingSpec(
            color=cfg.COLOR_PRIMARY,
            thickness=cfg.LANDMARK_THICKNESS,
            circle_radius=cfg.LANDMARK_RADIUS
        )
        self._connection_drawing_spec = self.mp_draw.DrawingSpec(
            color=cfg.COLOR_SECONDARY,
            thickness=cfg.CONNECTION_THICKNESS
        )

    def find_hands(self, frame, draw=True):
        """
        Phát hiện bàn tay trong frame.

        Quy trình:
        1. Chuyển BGR -> RGB (MediaPipe yêu cầu RGB)
        2. Đặt flag writeable=False để tăng performance
        3. Xử lý qua MediaPipe
        4. Khôi phục flag writeable=True

        Args:
            frame: Frame ảnh BGR từ OpenCV (numpy array)
            draw: Có vẽ landmarks mặc định của MediaPipe không

        Returns:
            frame: Frame đã xử lý (có/không có landmarks)
        """
        # Chuyển đổi màu BGR -> RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Tối ưu: đặt writeable=False trước khi xử lý
        frame_rgb.flags.writeable = False
        self.results = self.hands.process(frame_rgb)
        frame_rgb.flags.writeable = True

        # Vẽ landmarks mặc định nếu được yêu cầu
        if draw and self.results.multi_hand_landmarks:
            for hand_landmarks in self.results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    image=frame,
                    landmark_list=hand_landmarks,
                    connections=self.mp_hands.HAND_CONNECTIONS,
                    landmark_drawing_spec=self._landmark_drawing_spec,
                    connection_drawing_spec=self._connection_drawing_spec
                )

        return frame

    def find_position(self, frame, hand_index=0):
        """
        Tìm tọa độ pixel của 21 landmarks trên bàn tay.

        Args:
            frame: Frame ảnh (cần kích thước để chuyển đổi tọa độ)
            hand_index: Index bàn tay cần lấy (0 = bàn tay đầu tiên)

        Returns:
            landmark_list: List các tuple (id, x_pixel, y_pixel)
                          Rỗng nếu không phát hiện bàn tay
            bounding_box: Tuple (x_min, y_min, x_max, y_max) bao quanh bàn tay
                         None nếu không phát hiện bàn tay
        """
        self.landmark_list = []
        self.landmark_list_normalized = []
        bounding_box = None

        if self.results and self.results.multi_hand_landmarks:
            if hand_index < len(self.results.multi_hand_landmarks):
                hand = self.results.multi_hand_landmarks[hand_index]
                h, w, _ = frame.shape

                x_coords = []
                y_coords = []

                for lm_id, lm in enumerate(hand.landmark):
                    # Chuyển tọa độ chuẩn hóa [0,1] sang pixel
                    px = int(lm.x * w)
                    py = int(lm.y * h)

                    self.landmark_list.append((lm_id, px, py))
                    self.landmark_list_normalized.append((lm_id, lm.x, lm.y))

                    x_coords.append(px)
                    y_coords.append(py)

                # Tính bounding box
                if x_coords and y_coords:
                    padding = 20  # Padding cho bounding box
                    bounding_box = (
                        max(0, min(x_coords) - padding),
                        max(0, min(y_coords) - padding),
                        min(w, max(x_coords) + padding),
                        min(h, max(y_coords) + padding)
                    )

        return self.landmark_list, bounding_box

    def fingers_up(self):
        """
        Xác định ngón tay nào đang giơ lên (mở).

        Logic:
        - Ngón cái: So sánh theo trục X (do ngón cái mở ngang)
          + Tay phải: TIP.x > IP.x => giơ lên
          + Tay trái: TIP.x < IP.x => giơ lên
        - 4 ngón còn lại: So sánh theo trục Y
          + TIP.y < PIP.y => giơ lên (vì trục Y ngược trong ảnh)

        Returns:
            fingers: List 5 phần tử [thumb, index, middle, ring, pinky]
                    1 = giơ lên, 0 = cụp xuống
                    Rỗng nếu không phát hiện landmarks
        """
        fingers = []

        if len(self.landmark_list) < 21:
            return fingers

        # --- Xác định tay trái hay tay phải ---
        # Dựa vào handedness từ MediaPipe
        is_right_hand = True  # Mặc định
        if self.results and self.results.multi_handedness:
            handedness = self.results.multi_handedness[0]
            label = handedness.classification[0].label
            # MediaPipe trả về "Right"/"Left" theo góc nhìn của camera (mirror)
            # Trong hệ tọa độ camera: "Right" thực ra là tay trái người dùng
            is_right_hand = (label == "Right")

        # --- Ngón cái (Thumb) ---
        # So sánh TIP (4) với IP (3) theo trục X
        thumb_tip_x = self.landmark_list[cfg.THUMB_TIP][1]
        thumb_ip_x = self.landmark_list[cfg.THUMB_IP][1]

        if is_right_hand:
            # Tay "Right" trong camera => ngón cái giơ khi TIP.x < IP.x
            fingers.append(1 if thumb_tip_x < thumb_ip_x else 0)
        else:
            # Tay "Left" trong camera => ngón cái giơ khi TIP.x > IP.x
            fingers.append(1 if thumb_tip_x > thumb_ip_x else 0)

        # --- 4 ngón còn lại (Index, Middle, Ring, Pinky) ---
        # So sánh TIP với PIP theo trục Y
        # Trong OpenCV, trục Y hướng xuống => TIP.y < PIP.y => ngón giơ lên
        finger_tips = [cfg.INDEX_TIP, cfg.MIDDLE_TIP, cfg.RING_TIP, cfg.PINKY_TIP]
        finger_pips = [cfg.INDEX_PIP, cfg.MIDDLE_PIP, cfg.RING_PIP, cfg.PINKY_PIP]

        for tip, pip in zip(finger_tips, finger_pips):
            tip_y = self.landmark_list[tip][2]    # Tọa độ Y của TIP
            pip_y = self.landmark_list[pip][2]     # Tọa độ Y của PIP
            fingers.append(1 if tip_y < pip_y else 0)

        return fingers

    def get_landmark(self, landmark_id):
        """
        Lấy tọa độ pixel của một landmark cụ thể.

        Args:
            landmark_id: ID landmark (0-20), dùng hằng số từ config.py

        Returns:
            (x, y): Tuple tọa độ pixel, hoặc None nếu không tìm thấy
        """
        if landmark_id < len(self.landmark_list):
            _, x, y = self.landmark_list[landmark_id]
            return (x, y)
        return None

    def get_hand_center(self):
        """
        Tính tâm bàn tay (trung bình tọa độ tất cả landmarks).

        Returns:
            (cx, cy): Tuple tọa độ tâm bàn tay, hoặc None nếu không có
        """
        if not self.landmark_list:
            return None

        x_sum = sum(lm[1] for lm in self.landmark_list)
        y_sum = sum(lm[2] for lm in self.landmark_list)
        n = len(self.landmark_list)

        return (x_sum // n, y_sum // n)

    def get_palm_size(self):
        """
        Ước lượng kích thước bàn tay dựa trên khoảng cách WRIST -> MIDDLE_MCP.
        Dùng để chuẩn hóa ngưỡng khoảng cách (adaptive threshold).

        Returns:
            float: Khoảng cách pixel từ cổ tay đến gốc ngón giữa, hoặc 0
        """
        wrist = self.get_landmark(cfg.WRIST)
        middle_mcp = self.get_landmark(cfg.MIDDLE_MCP)

        if wrist and middle_mcp:
            return np.sqrt(
                (wrist[0] - middle_mcp[0]) ** 2 +
                (wrist[1] - middle_mcp[1]) ** 2
            )
        return 0

    def draw_custom_landmarks(self, frame, highlight_fingers=None):
        """
        Vẽ landmarks tùy chỉnh lên frame với các hiệu ứng visual.

        Args:
            frame: Frame ảnh để vẽ
            highlight_fingers: List ID các ngón tay cần highlight (có thể None)

        Returns:
            frame: Frame đã vẽ landmarks
        """
        if not self.landmark_list:
            return frame

        # Vẽ tất cả landmarks
        for lm_id, x, y in self.landmark_list:
            color = cfg.COLOR_PRIMARY

            # Highlight các đầu ngón tay
            if lm_id in cfg.FINGER_TIPS:
                color = cfg.COLOR_SUCCESS
                radius = cfg.LANDMARK_RADIUS + 2
            else:
                radius = cfg.LANDMARK_RADIUS

            # Highlight ngón tay được chỉ định
            if highlight_fingers and lm_id in highlight_fingers:
                color = cfg.COLOR_DANGER
                radius = cfg.LANDMARK_RADIUS + 4

            cv2.circle(frame, (x, y), radius, color, cfg.LANDMARK_THICKNESS)

        # Vẽ các đường nối chính (connections)
        connections = [
            # Ngón cái
            (cfg.WRIST, cfg.THUMB_CMC), (cfg.THUMB_CMC, cfg.THUMB_MCP),
            (cfg.THUMB_MCP, cfg.THUMB_IP), (cfg.THUMB_IP, cfg.THUMB_TIP),
            # Ngón trỏ
            (cfg.WRIST, cfg.INDEX_MCP), (cfg.INDEX_MCP, cfg.INDEX_PIP),
            (cfg.INDEX_PIP, cfg.INDEX_DIP), (cfg.INDEX_DIP, cfg.INDEX_TIP),
            # Ngón giữa
            (cfg.WRIST, cfg.MIDDLE_MCP), (cfg.MIDDLE_MCP, cfg.MIDDLE_PIP),
            (cfg.MIDDLE_PIP, cfg.MIDDLE_DIP), (cfg.MIDDLE_DIP, cfg.MIDDLE_TIP),
            # Ngón áp út
            (cfg.WRIST, cfg.RING_MCP), (cfg.RING_MCP, cfg.RING_PIP),
            (cfg.RING_PIP, cfg.RING_DIP), (cfg.RING_DIP, cfg.RING_TIP),
            # Ngón út
            (cfg.WRIST, cfg.PINKY_MCP), (cfg.PINKY_MCP, cfg.PINKY_PIP),
            (cfg.PINKY_PIP, cfg.PINKY_DIP), (cfg.PINKY_DIP, cfg.PINKY_TIP),
            # Lòng bàn tay
            (cfg.INDEX_MCP, cfg.MIDDLE_MCP), (cfg.MIDDLE_MCP, cfg.RING_MCP),
            (cfg.RING_MCP, cfg.PINKY_MCP), (cfg.THUMB_CMC, cfg.INDEX_MCP),
        ]

        for start_id, end_id in connections:
            start_point = self.get_landmark(start_id)
            end_point = self.get_landmark(end_id)
            if start_point and end_point:
                cv2.line(frame, start_point, end_point,
                        cfg.COLOR_SECONDARY, cfg.CONNECTION_THICKNESS)

        return frame

    def draw_roi(self, frame):
        """
        Vẽ vùng hoạt động (Region of Interest) lên frame.
        Chỉ cử chỉ trong vùng này mới được mapping sang tọa độ màn hình.

        Args:
            frame: Frame ảnh để vẽ

        Returns:
            frame: Frame đã vẽ ROI
        """
        cv2.rectangle(
            frame,
            (cfg.ROI_X_MIN, cfg.ROI_Y_MIN),
            (cfg.ROI_X_MAX, cfg.ROI_Y_MAX),
            cfg.COLOR_ROI_BORDER,
            2
        )
        return frame

    def draw_info(self, frame, fps=0, gesture_name="None", system_active=False):
        """
        Vẽ thông tin HUD (Heads-Up Display) lên frame.

        Args:
            frame: Frame ảnh để vẽ
            fps: Số frame per second hiện tại
            gesture_name: Tên cử chỉ đang được nhận diện
            system_active: Trạng thái hệ thống (True=ON, False=OFF)

        Returns:
            frame: Frame đã vẽ thông tin
        """
        font = cv2.FONT_HERSHEY_SIMPLEX

        # --- FPS ---
        fps_text = f"FPS: {int(fps)}"
        cv2.putText(frame, fps_text, cfg.FPS_POSITION, font,
                   cfg.FONT_SCALE, cfg.COLOR_SUCCESS, cfg.FONT_THICKNESS)

        # --- Cử chỉ hiện tại ---
        gesture_text = f"Gesture: {gesture_name}"
        cv2.putText(frame, gesture_text, cfg.GESTURE_POSITION, font,
                   cfg.FONT_SCALE, cfg.COLOR_INFO, cfg.FONT_THICKNESS)

        # --- Trạng thái hệ thống ---
        if system_active:
            status_text = "System: ON"
            status_color = cfg.COLOR_SUCCESS
        else:
            status_text = "System: OFF"
            status_color = cfg.COLOR_DANGER

        cv2.putText(frame, status_text, cfg.STATUS_POSITION, font,
                   cfg.FONT_SCALE, status_color, cfg.FONT_THICKNESS)

        return frame

    def is_hand_detected(self):
        """
        Kiểm tra xem có bàn tay nào được phát hiện không.

        Returns:
            bool: True nếu phát hiện ít nhất 1 bàn tay
        """
        return (self.results is not None and
                self.results.multi_hand_landmarks is not None and
                len(self.results.multi_hand_landmarks) > 0)

    def release(self):
        """
        Giải phóng tài nguyên MediaPipe.
        Nên gọi khi kết thúc chương trình.
        """
        self.hands.close()

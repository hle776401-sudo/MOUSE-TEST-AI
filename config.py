"""
config.py - Cấu hình hệ thống điều khiển máy tính bằng cử chỉ tay
=================================================================
Chứa tất cả hằng số, ngưỡng và tham số cấu hình cho toàn bộ hệ thống.
"""

# ==============================================================================
# 1. CÀI ĐẶT CAMERA & FRAME
# ==============================================================================
CAMERA_ID = 0                       # ID webcam (0 = webcam mặc định)
CAMERA_WIDTH = 640                  # Chiều rộng frame webcam (pixels)
CAMERA_HEIGHT = 480                 # Chiều cao frame webcam (pixels)

# Vùng hoạt động (Region of Interest) - giới hạn vùng di chuyển chuột
# Tạo padding để tránh ngón tay phải chạm mép khung hình
ROI_PADDING_X = 100                 # Padding trái/phải (pixels)
ROI_PADDING_Y = 120                 # Padding trên/dưới (pixels)
ROI_X_MIN = ROI_PADDING_X
ROI_Y_MIN = ROI_PADDING_Y
ROI_X_MAX = CAMERA_WIDTH - ROI_PADDING_X
ROI_Y_MAX = CAMERA_HEIGHT - ROI_PADDING_Y

# ==============================================================================
# 2. CÀI ĐẶT MEDIAPIPE HANDS
# ==============================================================================
MAX_NUM_HANDS = 1                   # Số lượng bàn tay tối đa detect
MIN_DETECTION_CONFIDENCE = 0.7      # Ngưỡng tin cậy khi phát hiện bàn tay
MIN_TRACKING_CONFIDENCE = 0.7       # Ngưỡng tin cậy khi theo dõi bàn tay
MODEL_COMPLEXITY = 1                # Độ phức tạp model (0 = nhẹ, 1 = đầy đủ)

# ==============================================================================
# 3. NGƯỠNG CỬ CHỈ (GESTURE THRESHOLDS)
# ==============================================================================

# --- MVP: Click ---
CLICK_DISTANCE_THRESHOLD = 35       # Fallback pixel khi không có palm_size (pixels)
CLICK_COOLDOWN = 0.3                # Cooldown giữa các lần click (giây)

# --- MVP: Pinch (Dùng chung cho Click + Drag) ---
PINCH_HOLD_THRESHOLD = 0.25         # Giữ pinch > 250ms = drag, < 250ms = click (giây)
PINCH_THRESHOLD_NORMALIZED = 0.25   # Ngưỡng pinch chuẩn hóa theo palm_size (~25% kích thước tay)

# --- MVP: Scroll ---
SCROLL_SPEED = 5                    # Tốc độ cuộn (đơn vị scroll/frame)
SCROLL_SENSITIVITY = 15             # Ngưỡng di chuyển tối thiểu theo trục Y để kích hoạt scroll (pixels)

# --- MVP: System Toggle (Bật/Tắt hệ thống) ---
SYSTEM_TOGGLE_FINGERS = 5           # Số ngón tay giơ lên để kích hoạt toggle
SYSTEM_TOGGLE_HOLD_TIME = 3.0       # Thời gian giữ (giây) để kích hoạt/tắt hệ thống
SYSTEM_TOGGLE_COOLDOWN = 2.0        # Cooldown sau khi toggle (giây) để tránh toggle liên tục

# --- Phase 2: Double Click (chưa dùng trong MVP) ---
# DOUBLE_CLICK_TIME_WINDOW = 0.5    # Thời gian tối đa giữa 2 click để thành double click

# --- Phase 2: Zoom (chưa dùng trong MVP) ---
# ZOOM_SENSITIVITY = 5              # Ngưỡng thay đổi khoảng cách tối thiểu để kích hoạt zoom
# ZOOM_SPEED = 3                    # Số lần nhấn Ctrl +/- mỗi lần zoom
# ZOOM_COOLDOWN = 0.15              # Cooldown giữa các lần zoom

# ==============================================================================
# 4. SMOOTHING (LÀM MƯỢT CHUỘT)
# ==============================================================================
SMOOTHING_FACTOR = 5                # Hệ số làm mượt (càng cao = càng mượt nhưng phản hồi chậm hơn)
                                    # Công thức: current = previous + (target - previous) / factor

# ==============================================================================
# 5. MÀU SẮC (BGR Format cho OpenCV)
# ==============================================================================
COLOR_PRIMARY = (255, 165, 0)       # Cam - màu chính cho landmarks
COLOR_SECONDARY = (0, 255, 255)     # Vàng - màu phụ
COLOR_SUCCESS = (0, 255, 0)         # Xanh lá - trạng thái thành công / hệ thống ON
COLOR_DANGER = (0, 0, 255)          # Đỏ - trạng thái lỗi / hệ thống OFF
COLOR_INFO = (255, 255, 0)          # Cyan - thông tin
COLOR_WHITE = (255, 255, 255)       # Trắng
COLOR_BLACK = (0, 0, 0)             # Đen
COLOR_PURPLE = (255, 0, 128)        # Tím - drag indicator
COLOR_CLICK = (0, 200, 255)         # Cam nhạt - click indicator
COLOR_ROI_BORDER = (100, 100, 100)  # Xám - viền ROI

# --- Landmarks ---
LANDMARK_RADIUS = 5                 # Bán kính điểm landmark
LANDMARK_THICKNESS = -1             # Độ dày vẽ landmark (-1 = tô đặc)
CONNECTION_THICKNESS = 2            # Độ dày đường nối giữa các landmarks

# ==============================================================================
# 6. HIỂN THỊ (DISPLAY / UI)
# ==============================================================================
WINDOW_NAME = "AI Mouse Controller"
FONT = None                         # Sẽ dùng cv2.FONT_HERSHEY_SIMPLEX (gán trong code)
FONT_SCALE = 0.7                    # Kích thước font chữ
FONT_THICKNESS = 2                  # Độ dày font chữ
FPS_POSITION = (10, 30)             # Vị trí hiển thị FPS
GESTURE_POSITION = (10, 70)         # Vị trí hiển thị cử chỉ hiện tại
STATUS_POSITION = (10, 110)         # Vị trí hiển thị trạng thái hệ thống

# ==============================================================================
# 7. LANDMARK IDS (Tham chiếu MediaPipe Hand Landmarks)
# ==============================================================================
# Mỗi bàn tay có 21 landmarks (0-20)
#
#        8   12  16  20         <- Đầu ngón tay (TIP)
#        |   |   |   |
#        7   11  15  19         <- DIP
#        |   |   |   |
#        6   10  14  18         <- PIP
#        |   |   |   |
#        5   9   13  17         <- MCP
#         \  |   |  /
#           \|   |/
#      4     \   /
#      |      \ /
#      3       0                <- WRIST
#      |
#      2
#      |
#      1                        <- Ngón cái (THUMB)
#
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# Danh sách các đầu ngón tay (TIP) để dễ dàng truy cập
FINGER_TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
# Danh sách các khớp PIP (dùng để so sánh ngón giơ/cụp)
FINGER_PIPS = [THUMB_IP, INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]

# ==============================================================================
# 8. TRẠNG THÁI HỆ THỐNG
# ==============================================================================
SYSTEM_ACTIVE_DEFAULT = False       # Hệ thống mặc định TẮT khi khởi động (cần cử chỉ để bật)

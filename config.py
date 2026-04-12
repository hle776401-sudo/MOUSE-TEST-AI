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

# --- Pinch (Dùng chung cho Click + Drag) ---
CLICK_DISTANCE_THRESHOLD = 40       # Fallback pixel khi không có palm_size (pixels)
CLICK_COOLDOWN = 0.2                # Cooldown giữa các lần click (giây)
PINCH_HOLD_THRESHOLD = 0.30         # Giữ pinch > 300ms = drag, < 300ms = click (giây)
PINCH_THRESHOLD_NORMALIZED = 0.28   # Ngưỡng pinch ENTER (~28% kích thước tay)
PINCH_EXIT_MULTIPLIER = 1.3         # Hysteresis: exit = enter * 1.3 (tránh flickering ở biên)

# --- Double Click ---
DOUBLE_CLICK_TIME_WINDOW = 0.5      # Thời gian tối đa giữa 2 left click để thành double click (giây)
DOUBLE_CLICK_COOLDOWN = 0.5         # Cooldown sau double click (giây)

# --- Scroll ---
SCROLL_SPEED = 12                   # Tốc độ cuộn (đơn vị scroll/frame)
SCROLL_SENSITIVITY = 10             # Ngưỡng di chuyển tối thiểu theo trục Y (pixels)

# --- Swipe ---
SWIPE_MIN_FINGERS = 4               # Số ngón tối thiểu phải giơ để nhận swipe
SWIPE_THRESHOLD_X = 80              # Di chuyển ngang tối thiểu để trigger swipe (pixels)
SWIPE_TIME_WINDOW = 0.5             # Thời gian tối đa cho 1 lần swipe (giây)
SWIPE_COOLDOWN = 0.8                # Cooldown giữa các lần swipe (giây)

# --- System Toggle (Bật/Tắt hệ thống) ---
SYSTEM_TOGGLE_FINGERS = 5           # Số ngón tay giơ lên để kích hoạt toggle
SYSTEM_TOGGLE_HOLD_TIME = 3.0       # Thời gian giữ (giây) để kích hoạt/tắt hệ thống
SYSTEM_TOGGLE_COOLDOWN = 2.0        # Cooldown sau khi toggle (giây)

# --- Stability (Ổn định gesture) ---
POST_ACTION_COOLDOWN = 0.15         # Neutral gap sau event gestures (click, swipe) (giây)

# --- Phase 2: Zoom (chưa dùng) ---
# ZOOM_SENSITIVITY = 5
# ZOOM_SPEED = 3
# ZOOM_COOLDOWN = 0.15

# ==============================================================================
# 4. SMOOTHING (LÀM MƯỢT CHUỘT)
# ==============================================================================
SMOOTHING_FACTOR = 4                # Hệ số làm mượt (càng cao = càng mượt nhưng phản hồi chậm hơn)
                                    # Công thức: current = previous + (target - previous) / factor

# ==============================================================================
# 5. MÀU SẮC (BGR Format cho OpenCV)
# ==============================================================================
COLOR_PRIMARY = (255, 165, 0)       # Cam - màu chính cho landmarks
COLOR_SECONDARY = (0, 255, 255)     # Vàng - màu phụ
COLOR_SUCCESS = (0, 255, 0)         # Xanh lá - hệ thống ON / thành công
COLOR_DANGER = (0, 0, 255)          # Đỏ - hệ thống OFF / lỗi
COLOR_INFO = (255, 255, 0)          # Cyan - thông tin
COLOR_WHITE = (255, 255, 255)       # Trắng
COLOR_BLACK = (0, 0, 0)             # Đen
COLOR_PURPLE = (255, 0, 128)        # Tím - drag indicator
COLOR_CLICK = (0, 200, 255)         # Cam nhạt - click indicator
COLOR_DOUBLE_CLICK = (0, 255, 255)  # Vàng - double click indicator
COLOR_SWIPE = (255, 100, 50)        # Xanh dương nhạt - swipe indicator
COLOR_ROI_BORDER = (100, 100, 100)  # Xám - viền ROI

# --- Landmarks ---
LANDMARK_RADIUS = 5                 # Bán kính điểm landmark
LANDMARK_THICKNESS = -1             # Độ dày vẽ landmark (-1 = tô đặc)
CONNECTION_THICKNESS = 2            # Độ dày đường nối giữa các landmarks

# ==============================================================================
# 6. HIỂN THỊ (DISPLAY / UI)
# ==============================================================================
WINDOW_NAME = "AI Mouse Controller"
FONT_SCALE = 0.7                    # Kích thước font chữ HUD nhỏ
FONT_THICKNESS = 2                  # Độ dày font chữ HUD
FPS_POSITION = (10, 30)             # Vị trí hiển thị FPS
GESTURE_POSITION = (10, 70)         # Vị trí hiển thị cử chỉ hiện tại
STATUS_POSITION = (10, 110)         # Vị trí hiển thị trạng thái hệ thống

# --- Demo Banner (text gesture lớn ở trung tâm-trên) ---
BANNER_FONT_SCALE = 1.2             # Font to cho banner gesture
BANNER_FONT_THICKNESS = 3           # Font dày cho banner
BANNER_Y = 55                       # Vị trí Y của banner (từ trên xuống)
BANNER_LINGER_FRAMES = 12           # Event gesture (click/swipe) giữ banner bao nhiêu frame

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
SYSTEM_ACTIVE_DEFAULT = False       # Hệ thống mặc định TẮT khi khởi động

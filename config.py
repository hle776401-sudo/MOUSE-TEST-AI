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
# 2. CAI DAT MEDIAPIPE HANDS
# ==============================================================================
MAX_NUM_HANDS = 2                   # So luong ban tay toi da detect
MIN_DETECTION_CONFIDENCE = 0.7      # Nguong tin cay khi phat hien ban tay
MIN_TRACKING_CONFIDENCE = 0.7       # Nguong tin cay khi theo doi ban tay
MODEL_COMPLEXITY = 1                # Do phuc tap model (0 = nhe, 1 = day du)

# --- Che do 2 tay phan vai ---
ENABLE_TWO_HAND_MODE = True         # Bat che do 2 tay (True = 2 tay, False = fallback 1 tay)
DOMINANT_HAND = "Right"             # Tay thuan cua nguoi dung (Right/Left)
                                    # Tay thuan = Primary (dieu khien cursor)
                                    # Tay con lai = Secondary (lenh he thong)

# ===== HANDEDNESS MAPPING =====
# Ket qua test thuc te (test_handedness.py):
#   Tay PHAI nguoi dung -> MediaPipe tra ve "Right"
#   Tay TRAI nguoi dung -> MediaPipe tra ve "Left"
PRIMARY_HAND_LABEL = "Right"        # MP label cua tay PHAI = Primary
SECONDARY_HAND_LABEL = "Left"       # MP label cua tay TRAI = Secondary

# --- Debug handedness ---
SHOW_HANDEDNESS_DEBUG = True        # Hien thi raw MediaPipe label tren overlay de verify

# --- Mode switching hysteresis ---
# Tranh nhay mode lien tuc khi MediaPipe hut tay 1-2 frame
MODE_ENTER_TWO_HAND_FRAMES = 5     # Phai thay 2 tay lien tuc 5 frame moi vao 2-hand mode
MODE_EXIT_TWO_HAND_FRAMES = 30     # Phai mat 1 tay lien tuc 30 frame (~1 giay) moi roi ve fallback

# --- Mau label 2 tay ---
COLOR_PRIMARY_HAND = (0, 255, 0)    # Xanh la - Primary hand bbox
COLOR_SECONDARY_HAND = (255, 165, 0) # Cam - Secondary hand bbox

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

# --- Scroll ---
SCROLL_SPEED = 12                   # Tốc độ cuộn (đơn vị scroll/frame)
SCROLL_SENSITIVITY = 10             # Ngưỡng di chuyển tối thiểu theo trục Y (pixels)

# --- Swipe (trình chiếu: next/prev slide) ---
SWIPE_MIN_FINGERS = 4               # Số ngón tối thiểu phải giơ để nhận swipe
SWIPE_THRESHOLD_X = 80              # Di chuyển ngang tối thiểu để trigger swipe (pixels)
SWIPE_TIME_WINDOW = 0.5             # Thời gian tối đa cho 1 lần swipe (giây)
SWIPE_COOLDOWN = 0.8                # Cooldown giữa các lần swipe (giây)
SWIPE_STABLE_FRAMES = 2             # Số frame liên tục thỏa điều kiện mới bắt đầu tracking
SWIPE_MODE = "browser"              # Chon che do swipe:
                                    #   "arrow"   = right/left (PowerPoint, Google Slides)
                                    #   "page"    = pagedown/pageup (PDF viewer)
                                    #   "browser" = Alt+Left / Alt+Right (trinh duyet web)

# --- System Toggle (Bật/Tắt hệ thống) ---
SYSTEM_TOGGLE_FINGERS = 5           # Số ngón tay giơ lên để kích hoạt toggle
SYSTEM_TOGGLE_HOLD_TIME = 3.0       # Thời gian giữ (giây) để kích hoạt/tắt hệ thống
SYSTEM_TOGGLE_COOLDOWN = 2.0        # Cooldown sau khi toggle (giây)
OPEN_PALM_GRACE_PERIOD = 0.4        # Grace period: 5 ngón phải giữ yên 0.4s trước khi
                                    # bắt đầu đếm toggle (cho swipe có cơ hội chạy trước)

# --- Stability (Ổn định gesture) ---
POST_ACTION_COOLDOWN = 0.15         # Neutral gap sau event gestures (click, swipe) (giây)
CLICK_FREEZE_TIME = 0.10            # Freeze cursor sau click/right click (giây)
                                    # Chống rung: cursor không move trong khoảng này
MOVE_DEADZONE = 3                   # Deadzone di chuyển chuột (pixels trên màn hình)
                                    # Nếu target gần current hơn deadzone → không move
                                    # Giảm rung khi tay đứng yên

# --- Zoom (1 tay: index + middle guard, thumb-index distance delta) ---
ZOOM_DELTA_THRESHOLD = 20           # Delta tích lũy tối thiểu để trigger zoom (pixels)
                                    # Accumulator gom nhiều frame nhỏ → 1 trigger ổn định
                                    # Tăng từ 15 → 20 để bớt trigger nhạy
ZOOM_COOLDOWN = 0.25                # Cooldown giữa các lần zoom (giây)
ZOOM_STABLE_FRAMES = 4              # Số frame liên tục ở zoom mode mới bắt đầu tracking delta
                                    # Tăng từ 3 → 4 để chắc mode hơn

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
COLOR_ZOOM = (0, 220, 0)            # Xanh lá sáng - zoom indicator
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

# ==============================================================================
# 9. VOICE INPUT (nhập liệu bằng giọng nói)
# ==============================================================================
# Flow: nhấn hotkey → mic nghe → STT → gõ text vào ô đang focus
#
# State flow:
#   VOICE_IDLE → VOICE_LISTENING → VOICE_RECOGNIZING → VOICE_TYPING → VOICE_DONE
#                     ↓                    ↓
#                VOICE_ERROR          VOICE_ERROR
#
ENABLE_VOICE_INPUT = True           # Bật/tắt chức năng voice input
VOICE_HOTKEY = "ctrl+shift+v"       # Global hotkey bat voice (khong can focus cua so webcam)
                                    # Nguoi dung click vao o nhap tren browser, giu focus o do
                                    # roi nhan Ctrl+Shift+V -> browser van co focus -> paste dung cho
VOICE_LANGUAGE = "vi-VN"            # Ngôn ngữ nhận diện giọng nói (vi-VN / en-US / ja-JP ...)
VOICE_LISTEN_TIMEOUT = 5            # Thời gian chờ tối đa để bắt đầu nghe được giọng (giây)
                                    # Nếu im lặng quá lâu → VOICE_ERROR
VOICE_PHRASE_TIME_LIMIT = 10        # Thời gian tối đa cho 1 câu nói (giây)
                                    # Sau thời gian này tự cắt và gửi STT
VOICE_AUTO_ENTER = False            # True = tự nhấn Enter sau khi gõ xong text
VOICE_TYPING_SPEED = 0.02          # Delay giữa mỗi ký tự khi gõ (giây), 0 = gõ tức thời
VOICE_STATUS_DISPLAY = True         # Hiển thị trạng thái voice trên UI overlay
COLOR_VOICE = (255, 200, 0)         # Màu banner voice (cyan-vàng)

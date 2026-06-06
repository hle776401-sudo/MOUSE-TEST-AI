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
MODEL_COMPLEXITY = 0                # Do phuc tap model (0 = nhe/nhanh, 1 = day du)
                                    # 0 uu tien FPS cho demo, 1 tracking chinh xac hon

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

# --- Duplicate hand filter ---
# MediaPipe doi khi tra ve 2 detection cho cung 1 ban tay (label "Right" + "Left")
# Filter loai duplicate truoc khi assign PRIMARY/SECONDARY
DUPLICATE_HAND_IOU_THRESHOLD    = 0.35   # IoU bbox > 0.35 = duplicate ro rang
DUPLICATE_HAND_CENTER_DISTANCE  = 80     # px — chi dung kem dieu kien size_ratio + overlap
MIN_PALM_SIZE                   = 30     # px — palm_size < 30 coi la detection loi, bo qua

# --- Mau label 2 tay ---
COLOR_PRIMARY_HAND = (0, 255, 0)    # Xanh la - Primary hand bbox
COLOR_SECONDARY_HAND = (255, 165, 0) # Cam - Secondary hand bbox

# ==============================================================================
# 3. NGƯỠNG CỬ CHỈ (GESTURE THRESHOLDS)
# ==============================================================================

# --- Pinch (Dùng chung cho Click + Drag) ---
CLICK_DISTANCE_THRESHOLD = 40       # Fallback pixel khi không có palm_size (pixels)
CLICK_COOLDOWN = 0.2                # Cooldown giữa các lần click (giây)
PINCH_HOLD_THRESHOLD = 0.85         # Giu pinch > 850ms = drag, < 850ms = click (giay)
                                    # Tang tu 0.60 -> 0.85 de tranh drag nham
PINCH_THRESHOLD_NORMALIZED = 0.28   # Ngưỡng pinch ENTER (~28% kích thước tay)
PINCH_EXIT_MULTIPLIER = 1.3         # Hysteresis: exit = enter * 1.3 (tránh flickering ở biên)

# --- Double Click ---
DOUBLE_CLICK_TIME_WINDOW = 0.5      # Thời gian tối đa giữa 2 left click để thành double click (giây)

# --- Scroll ---
SCROLL_SPEED = 12                   # Tốc độ cuộn (đơn vị scroll/frame)
SCROLL_SENSITIVITY = 10             # Ngưỡng di chuyển tối thiểu theo trục Y (pixels)

# --- Swipe (trình chiếu: next/prev slide) ---
SWIPE_MIN_FINGERS = 4               # Số ngón tối thiểu phải giơ để nhận swipe
SWIPE_THRESHOLD_X = 110              # Di chuyển ngang tối thiểu để trigger swipe (pixels)
                                     # Tang 80 -> 110 de can vuot ro rang hon
SWIPE_TIME_WINDOW = 0.5             # Thời gian tối đa cho 1 lần swipe (giây)
SWIPE_COOLDOWN = 1.2                # Cooldown giữa các lần swipe (giây)
                                     # Tang 0.8 -> 1.2 de tay co du thoi gian thu ve
SWIPE_STABLE_FRAMES = 3             # Số frame liên tục thỏa điều kiện mới bắt đầu tracking
                                     # Tang 2 -> 3 de chong re-trigger
SWIPE_MODE = "auto"                 # Chon che do swipe:
                                    #   "auto"    = tu dong detect theo cua so dang active
                                    #   "slide"   = ep che do slide (PowerPoint, Slides)
                                    #   "pdf"     = ep che do PDF viewer
                                    #   "browser" = ep che do trinh duyet web
                                    #   "image"   = ep che do xem anh

# --- Context-Aware Swipe: keyword detect (chi dung khi SWIPE_MODE = "auto") ---
# Thu tu uu tien: slide > pdf > image > browser > default
# (Google Slides chay trong Chrome nen slide phai uu tien hon browser)
SWIPE_SLIDE_KEYWORDS   = ["powerpoint", "google slides", ".pptx", ".ppt", "slide"]
SWIPE_PDF_KEYWORDS     = [".pdf", "acrobat", "pdf viewer", "foxit", "sumatra"]
SWIPE_IMAGE_KEYWORDS   = ["photos", "image viewer", "photo viewer",
                          ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]
SWIPE_BROWSER_KEYWORDS = ["chrome", "edge", "firefox", "opera", "brave", "vivaldi"]

# --- System Toggle (Bật/Tắt hệ thống) ---
SYSTEM_TOGGLE_FINGERS = 5           # Số ngón tay giơ lên để kích hoạt toggle
SYSTEM_TOGGLE_HOLD_TIME = 3.0       # Thời gian giữ (giây) để kích hoạt/tắt hệ thống
SYSTEM_TOGGLE_COOLDOWN = 2.0        # Cooldown sau khi toggle (giây)
OPEN_PALM_GRACE_PERIOD = 0.4        # Grace period: 5 ngón phải giữ yên 0.4s trước khi
                                    # bắt đầu đếm toggle (cho swipe có cơ hội chạy trước)

# --- Stability (Ổn định gesture) ---
POST_ACTION_COOLDOWN = 0.15         # Neutral gap sau event gestures (click, swipe) (giây)
CLICK_FREEZE_TIME = 0.20            # Freeze cursor sau click/right click (giây)
                                    # Chống rung: cursor không move trong khoảng này
MOVE_DEADZONE = 5                   # Deadzone di chuyển chuột (pixels trên màn hình)
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
SMOOTHING_FACTOR = 6                # Hệ số làm mượt (càng cao = càng mượt nhưng phản hồi chậm hơn)
                                    # Công thức: current = previous + (target - previous) / factor
                                    # Tang tu 4 -> 6 de giam jitter cursor

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
# 2 chế độ voice riêng biệt:
#   Voice Search Mode: nghe → gõ → auto Enter (dùng cho Google Search, YouTube...)
#   Voice Text Mode:   nghe → gõ → dừng       (dùng cho chat, comment, form...)
#
# State flow:
#   VOICE_IDLE → VOICE_LISTENING → VOICE_RECOGNIZING → VOICE_TYPING → VOICE_DONE
#                     ↓                    ↓
#                VOICE_ERROR          VOICE_ERROR
#
ENABLE_VOICE_INPUT = True           # Bật/tắt chức năng voice input

# --- Hotkey cho 2 chế độ (global, không cần focus cửa sổ webcam) ---
VOICE_HOTKEY = "ctrl+alt+v"         # Global hotkey bat voice (V = Voice, khong trung voi app nao)
VOICE_AUTO_ENTER = False            # True = tu nhan Enter sau khi go xong text

# --- Cấu hình STT chung (dùng cho cả 2 mode) ---
VOICE_LANGUAGE = "vi-VN"            # Ngôn ngữ nhận diện giọng nói (vi-VN / en-US / ja-JP ...)
VOICE_LISTEN_TIMEOUT = 7            # Thời gian chờ tối đa để bắt đầu nghe được giọng (giây)
                                    # Nếu im lặng quá lâu → VOICE_ERROR
VOICE_PHRASE_TIME_LIMIT = 30        # Thời gian tối đa cho 1 câu nói (giây)
                                    # Sau thời gian này tự cắt và gửi STT
VOICE_TYPING_SPEED = 0.02          # Delay trước khi paste (giây)
VOICE_STATUS_DISPLAY = True         # Hiển thị trạng thái voice trên UI overlay
COLOR_VOICE = (255, 200, 0)         # Màu banner voice (cyan-vàng)
VOICE_TEXT_APPEND_SPACE = True      # True = them 1 dau cach sau text khi nhap bang giong noi


# ==============================================================================
# 10. CONTEXT-AWARE GESTURES
# ==============================================================================
# Phat hien cua so dang active de map gesture vao hanh dong phu hop theo context.
# Vi du: swipe = next/prev slide (presentation), play/pause (media), v.v.
#
# Context chuan:
#   browser      = trinh duyet web (Chrome, Edge, Firefox, Brave, Opera, Coc Coc)
#   presentation = trinh chieu (PowerPoint, Google Slides)
#   document     = van ban/PDF (Word, PDF viewer, Notepad, Google Docs...)
#   media        = nhac/video (Spotify, VLC, Windows Media Player...)
#   default      = mac dinh (khong khop context nao)
#
# Luu y:
#   - YouTube trong Chrome CHUA dua vao media o dot 1.
#   - Excel/Spreadsheet CHUA lam o dot 1.
#   - Thu tu uu tien detect: presentation > document > media > browser > default.
# ==============================================================================

ENABLE_CONTEXT_AWARE   = True   # Bat/tat toan bo co che Context-Aware Gestures
CONTEXT_CACHE_INTERVAL = 0.5    # Chu ky cap nhat context (giay) - lay ten cua so active
CONTEXT_MODE           = "auto" # Che do context:
                                #   "auto" = tu dong detect theo cua so dang active
                                #   (cac gia tri khac se mo rong o dot sau)
SHOW_CONTEXT_HUD       = True   # Hien thi context hien tai tren UI overlay (HUD)
CONTEXT_STICKY_SECONDS = 2.0    # Giu context cu khi cua so tam ve default (giay)
                                # Vi du: Swipe trong khi camera window active van
                                # dung context cua app truoc trong 2 giay

# --- Swipe V2: State Machine + Movement Buffer ---
# Nếu ENABLE_SWIPE_V2 = False thì dùng logic Swipe cũ (legacy)
ENABLE_SWIPE_V2              = True   # Bat Swipe V2 State Machine
SWIPE_V2_POSE_STABLE_FRAMES  = 4      # So frame gio pose on dinh truoc khi ARMED
                                       # Tang 2 -> 4: can 160ms moi ARM lai, chong re-trigger
SWIPE_V2_MIN_DISTANCE_X      = 80     # Khoang cach ngang toi thieu de trigger (pixels)
                                       # Tang 60 -> 80: can vuot ro rang hon
SWIPE_V2_MAX_TIME            = 0.9    # Thoi gian toi da cho 1 swipe (giay)
SWIPE_V2_MIN_TIME            = 0.12   # Thoi gian toi thieu (loai bo chuyen dong giat)
SWIPE_V2_MIN_VELOCITY_X      = 120    # Toc do ngang toi thieu (pixels/giay)
SWIPE_V2_LOST_GRACE_FRAMES   = 4      # Frame cho phep mat pose truoc khi reset
SWIPE_V2_COOLDOWN            = 1.2    # Cooldown giua cac lan swipe (giay)
                                       # Tang 0.5 -> 1.2: du thoi gian thu tay ve
SWIPE_V2_INVERT_DIRECTION    = False  # True = dao huong (dung khi cam bi nguoc)
SWIPE_V2_DEBUG               = False  # Luu debug info (tat de giam dict allocation per-frame)



# --- Keyword groups de detect context theo ten cua so (title / process name) ---
# So sanh case-insensitive, kiem tra xem keyword co xuat hien trong tieu de cua so khong.

CONTEXT_BROWSER_KEYWORDS = [
    "chrome",
    "edge",
    "firefox",
    "brave",
    "opera",
    "cốc cốc",
    "coc coc",
]

CONTEXT_PRESENTATION_KEYWORDS = [
    "powerpoint",
    "slide show",
    "google slides",
    "presentation",
    ".pptx",                    # WPS Office / bất kỳ app mở file .pptx
    ".ppt",                     # File .ppt cũ
    "wps presentation",         # WPS Office - chế độ Presentation
    "kingsoft presentation",    # Tên cũ của WPS Presentation
]

CONTEXT_DOCUMENT_KEYWORDS = [
    "word",
    "pdf",
    "adobe",
    "acrobat",
    "foxit",
    "sumatra",
    "notepad",
    "notepad++",
    "google docs",
    "libreoffice writer",
    "wordpad",
]

CONTEXT_MEDIA_KEYWORDS = [
    "spotify",
    "vlc",
    "windows media player",
    "groove music",
    "musicbee",
    "foobar",
    "itunes",
    "media player",                     # Generic: Windows Media Player rut gon
    "trình phát đa phương tiện",        # Windows Media Player - tieng Viet (Unicode)
    "trinh phat da phuong tien",        # Windows Media Player - tieng Viet (khong dau)
]

# ==============================================================================
# Section 11: Gesture Logging (phuc vu chuong thuc nghiem bao cao)
# ==============================================================================
ENABLE_GESTURE_LOGGING = True   # True = ghi log ra CSV; False = tat hoan toan
GESTURE_LOG_DIR        = "logs" # Thu muc chua file log (tu tao neu chua co)

# ==============================================================================
# Section 12: Voice Command Mode (MVP)
# ==============================================================================
ENABLE_VOICE_COMMANDS      = True  # True = kich hoat Voice Command Mode
VOICE_COMMAND_DRY_RUN      = False # True = chi print, khong mo app/URL that
VOICE_COMMAND_PRINT_RESULT = True  # True = in ket qua parse/execute ra console

# ==============================================================================
# Section 13: Gesture Voice Trigger (kich hoat Voice Input bang cu chi tay)
# ==============================================================================
ENABLE_GESTURE_VOICE_TRIGGER = True         # True = bat tinh nang nay
VOICE_TRIGGER_POSE           = [0, 1, 1, 1, 0]  # cai cụp, tro/giua/ap-ut duoi, ut cụp
VOICE_TRIGGER_HOLD_SECS      = 1.5          # Giay phai giu pose de trigger (tang de tranh fire nham)
VOICE_TRIGGER_COOLDOWN       = 3.0          # Giay khong trigger lai sau khi fired

# ==============================================================================
# Section 14: DEMO MODE — Che do demo an toan truoc hoi dong
# ==============================================================================
# Khi DEMO_MODE = False: dung nhom ENABLE_* de bat/tat tung gesture.
# Khi DEMO_MODE = True:  dung nhom DEMO_ENABLE_* thay the, tang cooldown, tang stable frames.
# DEMO_MODE khong lam mat chuc nang o che do thuong.

DEMO_MODE = False                   # False = che do thuong, True = che do demo an toan

# --- Che do thuong (DEMO_MODE = False) ---
ENABLE_DOUBLE_CLICK    = True       # Bat/tat Double Click
ENABLE_DRAG            = True       # Bat/tat Drag and Drop
ENABLE_RIGHT_CLICK     = True       # Bat/tat Right Click
ENABLE_ZOOM            = True       # Bat/tat Zoom In/Out
ENABLE_VOICE_TRIGGER_G = True       # Bat/tat Gesture Voice Trigger (khac ENABLE_GESTURE_VOICE_TRIGGER)
ENABLE_SWIPE           = True       # Bat/tat Swipe Left/Right
ENABLE_SCROLL          = True       # Bat/tat Scroll Up/Down
ENABLE_SYSTEM_TOGGLE   = True       # Bat/tat System Toggle (5 ngon)

# --- Che do demo (DEMO_MODE = True) ---
DEMO_ENABLE_DOUBLE_CLICK    = False  # Demo: tat double click de tranh nham
DEMO_ENABLE_DRAG            = False  # Demo: tat drag de tranh loi
DEMO_ENABLE_RIGHT_CLICK     = False  # Demo: tat right click de tranh mo menu
DEMO_ENABLE_ZOOM            = False  # Demo: tat zoom de tranh tu kich hoat
DEMO_ENABLE_VOICE_TRIGGER_G = True   # Demo: bat voice trigger gesture (de demo cu chi + giong noi)
DEMO_ENABLE_SWIPE           = True   # Demo: giu swipe (on dinh)
DEMO_ENABLE_SCROLL          = True   # Demo: giu scroll (on dinh)
DEMO_ENABLE_SYSTEM_TOGGLE   = True   # Demo: giu system toggle

# --- Demo mode multipliers (nhan voi gia tri goc) ---
DEMO_COOLDOWN_MULTIPLIER      = 1.5  # Tang cooldown x1.5 khi demo
DEMO_POST_ACTION_MULTIPLIER   = 2.0  # Tang post-action cooldown x2 khi demo
DEMO_PINCH_HOLD_THRESHOLD     = 1.20 # Pinch hold lau hon khi demo (1.2s, ko bao gio drag)

# --- Voice Demo Safe Mode ---
# Khi True: chi cho phep cac voice command trong safe whitelist
# Command ngoai whitelist bi block, khong execute
VOICE_DEMO_SAFE_MODE = True
# Khi True: neu cau noi khong phai command thi van go text vao o dang focus
# Khi False: chan ca typing, chi cho phep command trong whitelist
VOICE_SAFE_ALLOW_TEXT_FALLBACK = True

# ==============================================================================
# Section 15: CURSOR STABILITY — Tham so on dinh con tro
# ==============================================================================
CURSOR_SMOOTHING       = 6          # EMA factor cho con tro (dung thay SMOOTHING_FACTOR)
CURSOR_DEADZONE        = 5          # Pixels tren man hinh, tuong duong MOVE_DEADZONE
MAX_CURSOR_JUMP        = 200        # Pixels/frame toi da. Vuot thi clamp thay vi skip
                                    # Tranh con tro nhay dot ngot khi landmark loi
LOST_HAND_GRACE_FRAMES = 5          # Frame mat tay truoc khi reset gesture state
                                    # Trong grace: khong action moi, khong reset
                                    # Qua grace: reset state, release drag neu dang drag
PINCH_STABLE_FRAMES    = 3          # Frame lien tuc pinch moi vao PREPARING
                                    # Tang tu 2 -> 3 de giam click/drag nham

# --- Right Click stability ---
RIGHT_CLICK_STABLE_FRAMES = 4       # Frame lien tuc o right-click pose moi bat dau tracking
RIGHT_CLICK_COOLDOWN      = 1.0     # Cooldown rieng cho right click (giay) — tang tu 0.2
                                    # Tranh ban lien tuc khi giu pose

# BÁO CÁO LÝ THUYẾT HỆ THỐNG
# AI Gesture Mouse Controller + Voice Input

---

## PHẦN 1: GIỚI THIỆU

### 1.1 Mục tiêu

Xây dựng hệ thống cho phép người dùng **điều khiển máy tính hoàn toàn bằng tay** thông qua webcam thường, kết hợp **nhập liệu bằng giọng nói**. Không yêu cầu phần cứng đặc biệt — chỉ cần laptop có webcam và microphone.

### 1.2 Bài toán cần giải quyết

| Bài toán | Mô tả |
|---|---|
| Nhận diện bàn tay | Phát hiện vị trí, hình dạng, ngón tay trong video real-time |
| Nhận diện cử chỉ | Phân loại tư thế tay thành các lệnh: click, drag, scroll, swipe, zoom |
| Điều khiển chuột | Ánh xạ tọa độ tay trong camera sang tọa độ con trỏ trên màn hình |
| Phân vai 2 tay | Tay phải điều khiển chuột, tay trái điều khiển hệ thống — không xung đột |
| Nhập liệu giọng nói | Chuyển giọng nói thành text, gõ vào ô đang focus trên trình duyệt |

### 1.3 Công nghệ sử dụng

| Công nghệ | Vai trò | Lý do chọn |
|---|---|---|
| **MediaPipe Hands** | Detect 21 landmark bàn tay | Chạy real-time trên CPU, không cần GPU, độ chính xác cao |
| **OpenCV** | Đọc webcam + vẽ overlay | Thư viện xử lý ảnh chuẩn, nhẹ, nhanh |
| **PyAutoGUI** | Thực thi mouse/keyboard | API đơn giản, cross-platform, đủ cho mọi action |
| **SpeechRecognition** | Giao tiếp Google STT | Wrapper gọn cho nhiều engine STT |
| **keyboard** | Global hotkey | Bắt phím hệ thống không cần focus cửa sổ |
| Python 3.10 | Ngôn ngữ chính | Hệ sinh thái AI/CV mạnh, dễ prototype |

---

## PHẦN 2: LÝ THUYẾT NỀN TẢNG

### 2.1 MediaPipe Hands — Mô hình nhận diện bàn tay

MediaPipe Hands của Google sử dụng **2 mô hình deep learning nối tiếp**:

**Mô hình 1 — Palm Detector**: Phát hiện vùng chứa bàn tay trong frame. Dùng kỹ thuật Single Shot Detector (SSD) trên toàn bộ ảnh. Chỉ chạy khi chưa detect được tay hoặc mất tracking.

**Mô hình 2 — Hand Landmark Model**: Nhận vùng ảnh bàn tay từ Palm Detector, trả về **21 điểm landmark** 3D (x, y, z) với tọa độ chuẩn hóa [0, 1].

```
21 điểm landmark trên bàn tay:

        8   12  16  20      ← TIP (đầu ngón)
        |   |   |   |
        7   11  15  19      ← DIP
        |   |   |   |
        6   10  14  18      ← PIP
        |   |   |   |
        5   9   13  17      ← MCP (gốc ngón)
         \  |   |  /
    4     \ |   |/
    |      \|  /
    3       0               ← WRIST (cổ tay)
    |
    2
    |
    1                       ← THUMB (ngón cái)
```

**Handedness**: MediaPipe cũng trả về label "Left" hoặc "Right" cho mỗi tay. Trong hệ thống này, sau `cv2.flip(frame, 1)` (mirror), label vẫn giữ nguyên — đã xác nhận bằng test thực tế.

### 2.2 Xác định ngón tay giơ/cụp

**4 ngón chính** (trỏ, giữa, áp út, út): So sánh trục Y.

```
Nếu TIP.y < PIP.y → ngón giơ (TIP cao hơn PIP)
Nếu TIP.y >= PIP.y → ngón cụp
```

(Lưu ý: OpenCV trục Y hướng xuống, nên y nhỏ = cao hơn)

**Ngón cái**: So sánh trục X (vì ngón cái nằm ngang).

```
Tay phải: TIP.x > IP.x → ngón cái mở
Tay trái: TIP.x < IP.x → ngón cái mở
```

Kết quả: mảng 5 phần tử `[thumb, index, middle, ring, pinky]`, mỗi phần tử = 0 (cụp) hoặc 1 (giơ). Ví dụ: `[0, 1, 0, 0, 0]` = chỉ ngón trỏ.

### 2.3 Khoảng cách chuẩn hóa (Normalized Distance)

**Vấn đề**: Cùng 1 cử chỉ pinch, khi tay gần camera → khoảng cách pixel lớn (60px), khi tay xa → khoảng cách nhỏ (25px). Nếu dùng ngưỡng cố định (px) → gesture không nhất quán.

**Giải pháp**: Chuẩn hóa theo kích thước bàn tay.

```
palm_size = distance(WRIST, MIDDLE_MCP)
normalized = distance(THUMB_TIP, INDEX_TIP) / palm_size
```

Ngưỡng chuẩn hóa **28% palm_size** hoạt động ổn định bất kể khoảng cách tay tới camera.

### 2.4 Ánh xạ tọa độ Camera → Màn hình

Camera 640×480 nhưng con trỏ chuột cần di trên màn hình 1920×1080. Ánh xạ tuyến tính qua `np.interp()`:

```
screen_x = interp(cam_x, [ROI_X_MIN, ROI_X_MAX], [0, screen_width])
screen_y = interp(cam_y, [ROI_Y_MIN, ROI_Y_MAX], [0, screen_height])
```

**ROI (Region of Interest)**: Không map toàn bộ 640×480 mà chỉ vùng giữa (100-540, 120-360). Lý do: ngón tay ở mép frame khó giữ ổn định, padding tạo vùng thoải mái hơn cho người dùng.

### 2.5 Làm mượt con trỏ (Smoothing)

**Vấn đề**: Tay người run tự nhiên 1-3px mỗi frame → con trỏ jitter liên tục.

**Giải pháp**: Nội suy tuyến tính (Linear Interpolation).

```
new_position = current + (target - current) / factor
```

Với `factor = 4`: mỗi frame, con trỏ chỉ di 25% khoảng cách còn lại đến vị trí đích. Kết quả: chuyển động mượt, không giật, nhưng vẫn phản hồi kịp thời.

**Deadzone (3px)**: Nếu vị trí mới cách vị trí cũ < 3px → không di chuyển. Loại bỏ micro-jitter khi tay đứng yên.

---

## PHẦN 3: KIẾN TRÚC HỆ THỐNG

### 3.1 Cấu trúc file

```
MOUSE TEST AI/
├── config.py                ← Tất cả hằng số & tham số
├── utils.py                 ← Hàm tiện ích (distance, smooth, map)
├── hand_tracking.py         ← MediaPipe wrapper
├── gesture_recognition.py   ← 4 class nhận diện gesture (Swipe V2)
├── mouse_controller.py      ← Thực thi PyAutoGUI action + execute_action()
├── context_manager.py       ← [MỚI] Detect active window, classify context
├── action_router.py         ← [MỚI] Route (gesture, context) → action_name
├── voice_input.py           ← Speech-to-Text module
├── main.py                  ← Vòng lặp chính + Context HUD + UI overlay
├── test_handedness.py       ← Script test xác nhận tay phải/trái
└── requirements.txt         ← Dependencies
```

### 3.2 Luồng dữ liệu (mỗi frame ~33ms)

```
Webcam → cv2.flip() → MediaPipe detect → 21 landmarks × N tay
    → Hand Assignment (gán role theo handedness)
    → Mode Switching (TWO_HAND / ONE_HAND)
    → Gesture Recognition (PinchState, Swipe, Zoom, Toggle, Scroll)
    → Mouse/Keyboard Action (PyAutoGUI)
    → Draw UI Overlay → cv2.imshow()
```

### 3.3 Nguyên tắc thiết kế

1. **Tách biệt hoàn toàn**: Mỗi file 1 trách nhiệm. Không có dependency vòng tròn.
2. **Config tập trung**: Tất cả ngưỡng/tham số nằm trong `config.py`. Thay đổi hành vi không cần sửa code.
3. **Role enforcement cứng**: Gesture được phân chia bằng class riêng biệt, không trộn lẫn.
4. **Fail-safe**: Mọi lỗi được bắt, không crash chương trình chính.

---

## PHẦN 4: HỆ THỐNG PHÂN VAI 2 TAY

### 4.1 Vấn đề của hệ thống 1 tay

Khi chỉ có 1 tay phải làm tất cả (10+ gesture), các xung đột xảy ra:

| Xung đột | Mô tả |
|---|---|
| Zoom vs Right Click | Cùng cần ngón giữa giơ |
| Swipe vs Toggle | 4 ngón vs 5 ngón — dễ trigger sai |
| Move bị khóa | Khi zoom/swipe đang active, cursor không di được |

### 4.2 Thiết kế 2 tay phân vai

| Tay | Vai trò | Gestures |
|---|---|---|
| Phải (Primary) | Điều khiển con trỏ | Move, Click, DblClick, RClick, Drag, Scroll |
| Trái (Secondary) | Lệnh hệ thống | Swipe, Zoom, System Toggle |

**Ưu điểm**: Mỗi tay chỉ 5-6 gesture → xung đột giảm gần như bằng 0.

### 4.3 Enforcement 2 tầng

**Tầng 1 — Code level**: `PrimaryHandRecognizer` không chứa method swipe/zoom/toggle. `SecondaryHandRecognizer` không chứa method move/click/drag/scroll. Không thể gọi nhầm.

**Tầng 2 — Runtime level**: `main.py` có 5 nhánh xử lý, mỗi nhánh chỉ gọi đúng recognizer cho đúng tay.

### 4.4 Hysteresis chuyển chế độ

```
Vào TWO_HAND: cần 5 frame liên tục thấy 2 tay   (~0.17s)
Rời TWO_HAND: cần 30 frame mất 1 tay             (~1.0s)
```

**Lý do exit chậm hơn enter**: MediaPipe thường hụt tay 1-2 frame khi tay che nhau hoặc di nhanh. Exit chậm (30 frame = 1 giây) cho tay thời gian quay lại mà không nhảy mode.

### 4.5 Grace Period

Khi ở TWO_HAND MODE mà tạm mất 1 tay (< 30 frame), hệ thống vào Grace Period: giữ nguyên mode, tay còn lại vẫn xử lý đúng vai trò.

---

## PHẦN 5: CHI TIẾT CÁC GESTURE

### 5.1 PinchState Machine — Click & Drag

Bài toán phân biệt Click vs Drag dựa trên **thời gian giữ pinch**:

```
IDLE ──[pinch vào]──► PREPARING
                          │
                    [< 300ms, thả]──► LEFT_CLICK
                          │
                    [≥ 300ms]──► HOLDING ──► DRAGGING ──[thả]──► DRAG_END
```

**Double Click**: 2 lần LEFT_CLICK trong 0.5 giây.

**Hysteresis ngưỡng pinch**: Enter = 28% palm_size, Exit = 28% × 1.3 = 36.4%. Vùng đệm 8.4% ngăn flicker khi tay run ở biên.

### 5.2 Scroll

```
Điều kiện: fingers = [x, 0, 0, 0, 0] (nắm tay)
Tracking: Chênh lệch center.y giữa 2 frame
Ngưỡng: |delta_y| ≥ 10px
Action: pyautogui.scroll(±12)
```

### 5.3 Swipe V2 — State Machine

Phase Context-Aware Gestures đã thiết kế lại Swipe bằng **State Machine 4 trạng thái** trong `SecondaryHandRecognizer`:

```
IDLE ──[pose OK × 3 frame]──► ARMED ──[dx > 15px]──► TRACKING
  ▲                              │                      │
  │  pose lost > grace          │ timeout              │ timeout
  └────────────────────────────────────────────────┘
                                               │
                               dx≥60 & vel≥120 & t≥0.12s
                                               ▼
                                     COOLDOWN (0.7s) ──► IDLE
                                     return Swipe Left/Right
```

**Pose Swipe V2**: `fingers = [0,1,1,1,1]` (ngón cái cụp, 4 ngón giơ) ≠ Toggle `[1,1,1,1,1]` (5 ngón). Không bao giờ xung đột.

**Diều kiện trigger**:
```
elapsed  ≥ 0.12s   (không quá nhanh — loại giật)
abs(dx)  ≥ 60px    (quãng đường tối thiểu)
vel_x    ≥ 120px/s (tốc độ tối thiểu)
elapsed  ≤ 0.9s    (không quá chậm)
```

**Context-Aware action**: sau khi trigger, `ActionRouter.resolve()` tra bảng:

| Context | Swipe Left ← | Swipe Right → |
|---|---|---|
| browser | `Alt+Left` | `Alt+Right` |
| presentation | `←` (prev slide) | `→` (next slide) |
| document | `PageUp` | `PageDown` |
| media | `prevtrack` | `nexttrack` |
| default | `←` | `→` |

### 5.4 Zoom

```
Guard gesture: Index + Middle giơ, Ring + Pinky cụp
Tracking: Khoảng cách thumb_tip — index_tip thay đổi
Accumulator: Gom delta nhiều frame, trigger khi |tổng| ≥ 20px

Tăng → Zoom In  → Ctrl+=
Giảm → Zoom Out → Ctrl+-

Frame stability: 4 frame liên tục ở zoom pose mới bắt đầu track
Cooldown: 0.25s giữa các lần trigger
Lock: Tay phải đang drag → block zoom
```

**Tại sao dùng Accumulator?** — Delta mỗi frame rất nhỏ (1-3px). Nếu trigger ngay → zoom quá nhạy, loạn. Accumulator gom nhiều frame nhỏ thành 1 trigger có chủ đích.

### 5.5 System Toggle

```
Cử chỉ: Giơ cả 5 ngón tay trái, giữ yên ≥ 3 giây
Grace period: 0.4s đầu không đếm (cho swipe chạy trước)
Cooldown: 2s sau mỗi lần toggle
UI: Progress bar 0→100%
Action: Bật/Tắt toàn bộ hệ thống
```

**Grace period 0.4s**: Khi vuốt ngang, tay mở 5 ngón → dễ trigger toggle nhầm. Đợi 0.4s không có swipe mới bắt đầu đếm toggle.

---

## PHẦN 6: KỸ THUẬT CHỐNG NHIỄU

| # | Kỹ thuật | Áp dụng | Mục đích |
|---|---|---|---|
| 1 | Pinch Hysteresis | Click/Drag | Enter 28%, exit 36.4% — chống flicker biên |
| 2 | PinchState Machine | Click/Drag | Phân biệt click vs drag theo thời gian |
| 3 | Post-action Cooldown | Mọi event | 0.15s nghỉ sau mỗi gesture event |
| 4 | Click Freeze | Cursor | 100ms không move sau click — chống rung |
| 5 | Deadzone | Cursor | 5px — bỏ qua micro-movement |
| 6 | Smoothing | Cursor | factor=4, nội suy tuyến tính |
| 7 | Frame Stability | Zoom/Swipe | N frame liên tục mới bắt đầu tracking |
| 8 | Delta Accumulator | Zoom | Gom delta nhỏ thành 1 trigger lớn |
| 9 | Grace Period | Toggle | 0.4s chờ swipe trước khi đếm toggle |
| 10 | Mode Hysteresis | 2-hand/1-hand | Enter 5f, Exit 30f |
| 11 | Drag Lock | Coordinator | Đang drag → block swipe/zoom |
| 12 | Guard Gesture | Zoom vs Click | Ngón giữa giơ → skip pinch, nhường zoom |

---

## PHẦN 7: VOICE INPUT

### 7.1 Luồng xử lý

```
1. User click vào ô tìm kiếm trên browser (giữ focus)
2. Nhấn Ctrl+Alt+V (global hotkey — không cần focus webcam)
3. VOICE_LISTENING: Microphone mở, chờ giọng nói (timeout 5s)
4. VOICE_RECOGNIZING: Gửi audio lên Google Speech-to-Text
5. VOICE_TYPING: Paste text vào ô đang focus (Windows Clipboard API)
6. VOICE_DONE hoặc VOICE_ERROR
```

### 7.2 State Machine

```
VOICE_IDLE
  │
  ├─[Ctrl+Alt+V]──► VOICE_LISTENING
  │                        │
  │                   [im lặng > 5s]──► VOICE_ERROR
  │                        │
  │                   [có giọng nói]
  │                        │
  │                   VOICE_RECOGNIZING
  │                        │
  │                   [lỗi STT/mạng]──► VOICE_ERROR
  │                        │
  │                   [thành công]
  │                        │
  │                   VOICE_TYPING ──► VOICE_DONE
  │
  └─[đang listen]──► "Already listening" (bỏ qua)
```

### 7.3 Ba vấn đề kỹ thuật đã giải quyết

**Vấn đề 1 — Blocking I/O**: `listen_and_recognize()` chờ mic 5-10 giây. Nếu chạy trong main loop → UI đóng băng.

→ **Giải pháp**: Thread riêng (daemon). Main loop tiếp tục chạy, voice xử lý song song.

**Vấn đề 2 — Focus bị mất**: Cách cũ dùng `cv2.waitKey()` bắt phím V chỉ khi webcam window focus → user phải click webcam → browser mất focus.

→ **Giải pháp**: `keyboard.add_hotkey("ctrl+alt+v")` — global hotkey ở OS level. User nhấn từ browser, browser giữ focus.

**Vấn đề 3 — Tkinter steal focus khi paste**: `tkinter.Tk()` tạo window ẩn nhưng vẫn steal focus → `Ctrl+V` paste vào tkinter thay vì browser.

→ **Giải pháp**: Windows Clipboard API qua `ctypes` (built-in). Gọi trực tiếp `GlobalAlloc → GlobalLock → SetClipboardData`, không tạo window → browser giữ focus → paste đúng ô tìm kiếm.

### 7.4 Hỗ trợ Unicode (tiếng Việt)

`pyautogui.typewrite()` chỉ hỗ trợ ASCII → không gõ được tiếng Việt. Giải pháp clipboard:

```
Text "thời tiết" → encode UTF-16-LE → copy vào clipboard → Ctrl+V paste
```

---

## PHẦN 8: CẤU HÌNH QUAN TRỌNG

| Nhóm | Tham số | Giá trị | Ý nghĩa |
|---|---|---|---|
| Camera | CAMERA_WIDTH × HEIGHT | 640 × 480 | Độ phân giải webcam |
| ROI | ROI_PADDING_X / Y | 100 / 120 | Padding vùng di chuột |
| MediaPipe | MIN_DETECTION_CONFIDENCE | 0.7 | Ngưỡng phát hiện tay |
| Hand | PRIMARY_HAND_LABEL | "Right" | Tay phải = Primary |
| Mode | MODE_ENTER / EXIT | 5 / 30 frame | Hysteresis chuyển mode |
| Pinch | PINCH_THRESHOLD_NORMALIZED | 0.28 | Ngưỡng pinch 28% palm |
| Pinch | PINCH_HOLD_THRESHOLD | 0.30s | Click < 300ms, Drag ≥ 300ms |
| Scroll | SCROLL_SPEED | 12 | Đơn vị scroll mỗi frame |
| Swipe | SWIPE_THRESHOLD_X | 80px | Di ngang tối thiểu |
| Swipe | SWIPE_MODE | "auto" | Tự động route theo context; override: slide/pdf/browser/image |
| Zoom | ZOOM_DELTA_THRESHOLD | 20px | Accumulator trigger |
| Toggle | SYSTEM_TOGGLE_HOLD_TIME | 3.0s | Giữ 5 ngón bao lâu |
| Smoothing | SMOOTHING_FACTOR | 4 | Hệ số làm mượt cursor |
| Voice | VOICE_HOTKEY | "ctrl+alt+v" | Global hotkey |
| Voice | VOICE_LANGUAGE | "vi-VN" | Ngôn ngữ STT |

---

## PHẦN 9: SƠ ĐỒ CLASS

```
gesture_recognition.py
├── PinchState (enum)
│     IDLE / PREPARING / HOLDING / DRAGGING
│
├── GestureRecognizer            ← Legacy (không dùng trong runtime)
│
├── PrimaryHandRecognizer        ← Tay phải
│     recognize(landmarks, fingers, palm_size)
│     → Move, Click, DblClick, RClick, Drag, Scroll
│
├── SecondaryHandRecognizer      ← Tay trái
│     recognize(landmarks, fingers, palm_size, center)
│     → Toggle, Swipe V2, Zoom
│     _check_swipe()              ← Swipe V2 State Machine
│     _check_swipe_legacy()       ← Fallback khi ENABLE_SWIPE_V2=False
│     get_swipe_debug_info()      ← {state, dx, vel, elapsed, ...}
│
└── GestureCoordinator           ← Điều phối
      process(primary_hand, secondary_hand)
      → {primary_result, secondary_result, system_active}

context_manager.py  [MỚI]
└── ContextManager
      update()                    ← gọi mỗi frame (có cache 0.5s)
      get_current_context()       ← browser/presentation/document/media/default
      classify_window(title)      ← keyword matching, priority order
      get_context_display()       ← "CTX: Browser"
      Sticky mechanism: giữ context cũ 2s khi tạm về default

action_router.py  [MỚI]
└── ActionRouter(context_manager)
      resolve(gesture_name)       ← action_name (ví dụ: "next_slide")
      ACTION_TABLE: (gesture, context) → action_name

mouse_controller.py
└── MouseController(action_router=None)
      process_gesture(result_dict)
      execute_action(action_name) ← [MỚI] thực thi bằng pyautogui
      type_text(text)             ← ctypes clipboard
      press_enter()

voice_input.py
└── VoiceInputManager
      listen_and_recognize()      ← Blocking, chạy trong thread
      → {"state", "text", "error"}
```

---

## PHẦN 10: YÊU CẦU HỆ THỐNG

| Yêu cầu | Chi tiết |
|---|---|
| OS | Windows 10/11 |
| Python | 3.10+ |
| Hardware | Webcam + Microphone |
| Internet | Cần cho Google STT (voice input) |
| Cài đặt | `pip install -r requirements.txt` |
| Chạy | `python main.py` |

### Phím tắt

| Phím | Chức năng |
|---|---|
| Q | Thoát chương trình |
| S | Toggle System ON/OFF nhanh |
| Ctrl+Shift+V | Bật Voice Input (global, không cần focus webcam) |

---

## PHẦN 11: PHASE CONTEXT-AWARE GESTURES + SWIPE V2

### 11.1 Mục tiêu phase

Thêm khả năng **nhận biết ứng dụng đang active** và **tự động điều chỉnh hành vi Swipe/Zoom** mà không cần cấu hình thủ công. Đồng thời cải thiện độ ổn định của Swipe bằng State Machine.

### 11.2 Kiến trúc Context Pipeline

```
Active Window Title (Windows API qua ctypes)
    │
    ▼
 ContextManager.classify_window(title)
    │  keyword matching theo priority order:
    │  presentation > document > media > browser > default
    │  + sticky 2s (giữ context cũ khi tạm về default)
    ▼
  context: "browser" | "presentation" | "document" | "media" | "default"
    │
    ▼
 ActionRouter.resolve(gesture_name, context)
    │  ACTION_TABLE[(gesture, context)] → action_name
    │  Ví dụ: ("swipe_left", "presentation") → "previous_slide"
    ▼
 MouseController.execute_action(action_name)
    │  pyautogui.press() / hotkey()
    │  Anti-spam: warning mỗi action chỉ in 1 lần
    ▼
  Hành vi thực tế trên màn hình
```

### 11.3 Kiến trúc Swipe V2

**Vấn đề cũ**: Swipe V1 dựa trên delta x và time window đơn giản — không có vận tốc, dễ trigger nhầm hoặc bỏ sót.

**Giải pháp**: State Machine 4 trạng thái với kiểm tra đa điều kiện:

| Tham số | Giá trị | Mục đích |
|---|---|---|
| `SWIPE_V2_POSE_STABLE_FRAMES` | 3 | Cần 3 frame pose ổn định → ARMED |
| `SWIPE_V2_MIN_DISTANCE_X` | 60px | Quãng đường ngang tối thiểu |
| `SWIPE_V2_MIN_VELOCITY_X` | 120px/s | Tốc độ tối thiểu (lọc chầm chạp) |
| `SWIPE_V2_MIN_TIME` | 0.12s | Loại cử động giật tay |
| `SWIPE_V2_MAX_TIME` | 0.9s | Timeout tuyến tính |
| `SWIPE_V2_LOST_GRACE_FRAMES` | 4 | Dung sai mất pose (giữ state) |
| `SWIPE_V2_COOLDOWN` | 0.7s | Chống re-trigger ngay sau swipe |

**Fallback an toàn**: `ENABLE_SWIPE_V2 = False` → gọi `_check_swipe_legacy()` giữ nguyên hành vi cũ.

### 11.4 Context Sticky Mechanism

**Vấn đề**: Khi camera window đang active (nhìn vào tay), active window là "AI Mouse Controller" → context = default → Swipe bị route sai.

**Giải pháp**: `_last_non_default_time` + `CONTEXT_STICKY_SECONDS = 2.0s`:
```
Cử chỉ Swipe trong PowerPoint → để tay hướng vào camera
  → Active window: "AI Mouse Controller" (default)
  → Elapsed: 0.3s < 2.0s
  → ⇒ Vẫn dùng context "presentation" (sticky)
  → Swipe route đúng: previous_slide / next_slide
```

### 11.5 Kết quả validation

| Kiểm tra | Kết quả |
|---|---|
| App khởing động không crash | ✅ PASS |
| Context HUD đúng màu (vàng/xanh lá/xanh dương/tím/xám) | ✅ PASS |
| Browser → CTX: Browser | ✅ PASS |
| WPS/PowerPoint .pptx → CTX: Presentation | ✅ PASS |
| PDF viewer → CTX: Document | ✅ PASS |
| Trình phát Đa phương tiện → CTX: Media | ✅ PASS |
| Sticky context 2s | ✅ PASS |
| Swipe Left = back/prev/pageup/prevtrack | ✅ PASS |
| Swipe Right = forward/next/pagedown/nexttrack | ✅ PASS |
| Zoom media → volume_up/volume_down | ✅ PASS |
| Toggle 5 ngón không xung đột Swipe V2 | ✅ PASS |
| Zoom 2 ngón không xung đột Swipe V2 | ✅ PASS |
| Move/click/drag/scroll không bị ảnh hưởng | ✅ PASS |
| Voice Ctrl+Alt+V | ✅ PASS |
| Gemini Pro High review | ✅ PASS (no critical/high/medium bug) |

---

*Tài liệu phản ánh trạng thái hệ thống tính đến tháng 5/2026.*

---

## PHẦN 12: ĐÁNH GIÁ THỰC NGHIỆM

### 12.1 Mục tiêu đánh giá

Phần này trình bày kết quả đánh giá thực nghiệm hệ thống AI Gesture Mouse Controller trong kịch bản điều khiển trình chiếu PowerPoint bằng cử chỉ tay. Mục tiêu bao gồm:

- Xác nhận cơ chế Context-Aware Gestures định tuyến đúng hành động theo ứng dụng đang hoạt động.
- Đánh giá tính ổn định của Swipe V2 State Machine và Zoom In/Out trong điều kiện sử dụng thực tế.
- Ghi nhận tỉ lệ thực thi thành công của các cử chỉ thông qua module GestureLogger.
- Phân tích phân phối context, gesture, action và chế độ hoạt động (TWO_HAND / ONE_HAND).

> **Lưu ý:** Kết quả dưới đây phản ánh **một phiên thử nghiệm mẫu** thực hiện ngày 08/05/2026. Đây không phải đánh giá tuyệt đối cho toàn bộ hệ thống trong mọi điều kiện sử dụng.

---

### 12.2 Môi trường thử nghiệm

| Thành phần | Chi tiết |
|---|---|
| Hệ điều hành | Windows 11 |
| Python | 3.10 |
| Webcam | Webcam tích hợp laptop |
| Độ phân giải camera | 640 × 480 |
| Ứng dụng kiểm thử | Microsoft PowerPoint (file .pptx) |
| Ánh sáng | Trong phòng, ánh sáng tự nhiên ban ngày |
| Khoảng cách tay–camera | ~50–70 cm |
| FPS trung bình | 16.1 FPS |
| Công cụ ghi log | `gesture_logger.py` + `analyze_logs.py` |

---

### 12.3 Kịch bản thử nghiệm

Người thử nghiệm thực hiện các thao tác sau **bằng tay trái (Secondary Hand)**:

1. **Swipe Right** → chuyển slide tiếp theo (`next_slide`)
2. **Swipe Left** → quay lại slide trước (`previous_slide`)
3. **Zoom In / Zoom Out** → phóng to / thu nhỏ slide trong PowerPoint (`presentation_zoom_in` / `presentation_zoom_out`)

Trong suốt quá trình, cửa sổ active được duy trì ở PowerPoint. Một số event ghi nhận context `default` xảy ra khi cửa sổ active tạm thời chuyển sang `AI Mouse Controller` (cửa sổ webcam) — đây là hành vi bình thường và được ghi nhận đúng.

Thử nghiệm bao gồm cả 2 chế độ:
- **ONE_HAND**: chỉ dùng tay trái đơn (chế độ fallback)
- **TWO_HAND**: dùng cả hai tay đồng thời

---

### 12.4 Công cụ ghi log

Hệ thống sử dụng module `gesture_logger.py` (Bước 6.1–6.4) để ghi sự kiện ra file CSV theo thời gian thực. Mỗi sự kiện bao gồm:

```
timestamp, mode, system_active, context, window_title,
gesture, action, executed, fps, note
```

File log được đặt tên theo ngày/giờ: `logs/gesture_events_YYYYMMDD_HHMMSS.csv`.

Phân tích kết quả thực hiện bằng `analyze_logs.py` (built-in Python, không có dependency ngoài).

---

### 12.5 Kết quả thống kê từ log

**Tổng quan phiên thử nghiệm:**

| Chỉ số | Giá trị |
|---|---|
| Tổng số sự kiện ghi nhận | 58 |
| Thực thi thành công | 58 |
| Thực thi thất bại | 0 |
| Tỉ lệ thành công (phiên test mẫu) | **100.0%** |
| FPS trung bình | **16.1 FPS** |
| Khoảng thời gian | 10:47:14 → 10:48:38 (≈ 84 giây) |

**Phân phối theo gesture:**

| Gesture | Số lần | Tỉ lệ |
|---|---|---|
| Swipe Left | 18 | 31.0% |
| Zoom In | 16 | 27.6% |
| Swipe Right | 13 | 22.4% |
| Zoom Out | 11 | 19.0% |
| **Tổng** | **58** | **100%** |

**Phân phối theo context:**

| Context | Số lần | Tỉ lệ |
|---|---|---|
| presentation | 53 | 91.4% |
| default | 5 | 8.6% |
| **Tổng** | **58** | **100%** |

**Phân phối theo action:**

| Action | Số lần | Tỉ lệ |
|---|---|---|
| previous_slide | 18 | 31.0% |
| presentation_zoom_in | 13 | 22.4% |
| next_slide | 13 | 22.4% |
| presentation_zoom_out | 9 | 15.5% |
| default_zoom_in | 3 | 5.2% |
| default_zoom_out | 2 | 3.4% |
| **Tổng** | **58** | **100%** |

**Phân phối theo chế độ hoạt động:**

| Chế độ | Số lần | Tỉ lệ |
|---|---|---|
| ONE_HAND (tay trái đơn) | 46 | 79.3% |
| TWO_HAND (hai tay) | 12 | 20.7% |

**Cửa sổ được ghi nhận (2 unique):**
- `Slide 1 - Software testing overview.pptx - PowerPoint`
- `AI Mouse Controller`

---

### 12.6 Nhận xét kết quả

**Định tuyến context chính xác:**
Trong 53/58 sự kiện (91.4%), hệ thống xác định đúng context `presentation` và định tuyến Swipe/Zoom sang slide control. 5 sự kiện còn lại (8.6%) ghi nhận context `default` khi cửa sổ active tạm thời là `AI Mouse Controller` — đây là hành vi đúng của hệ thống vì không có context keyword phù hợp với tên cửa sổ webcam.

**Cơ chế Sticky Context hoạt động hiệu quả:**
Cơ chế giữ context 2 giây giúp phần lớn thao tác Swipe/Zoom ngay sau khi nhìn vào camera vẫn sử dụng đúng context `presentation`, giảm thiểu routing về `default`.

**Swipe V2 State Machine ổn định:**
Trong 31 sự kiện swipe được ghi nhận, tất cả đều được thực thi thành công (executed=1). Không có sự kiện nào bị kẹt hoặc nhận diện sai hướng trong phiên thử nghiệm này.

**Zoom In/Out định tuyến đúng:**
27 sự kiện zoom được ghi nhận. Context `presentation` sử dụng `Ctrl+` / `Ctrl-` để phóng to/thu nhỏ slide PowerPoint. Context `default` sử dụng zoom toàn cục.

**Chế độ ONE_HAND chiếm ưu thế:**
79.3% sự kiện xảy ra khi chỉ có tay trái (tay phải không vào frame). Hệ thống xử lý đúng theo nhánh ONE_HAND fallback mà không mất context hay gesture routing.

---

### 12.7 Hạn chế

1. **Phiên test hạn chế:** Kết quả dựa trên 1 phiên thử nghiệm (~84 giây, 1 người dùng). Chưa đủ để kết luận về hiệu năng trong mọi điều kiện ánh sáng, khoảng cách và góc máy.

2. **FPS thấp (16.1 FPS):** Thấp hơn target 30 FPS. Nguyên nhân có thể do tải xử lý MediaPipe + Context detection + Camera loop chạy đồng thời trên cùng một luồng. FPS thấp có thể ảnh hưởng đến độ nhạy của Swipe V2.

3. **5 sự kiện default không mong muốn:** Khi người dùng nhìn vào camera để kiểm tra frame, cửa sổ active thay đổi về `AI Mouse Controller`, dẫn đến context `default`. Sticky 2s giảm thiểu nhưng chưa loại bỏ hoàn toàn.

4. **Chỉ kiểm thử kịch bản PowerPoint:** Chưa thực hiện thử nghiệm ghi log đầy đủ trên các context khác (browser, document, media).

5. **Log chưa ghi Click/Drag/Scroll:** Ở giai đoạn hiện tại, chỉ Swipe và Zoom được ghi log. Click, Drag, Scroll của tay phải chưa được đưa vào CSV để phân tích.

---

### 12.8 Hướng cải tiến

| # | Hướng cải tiến | Mức độ ưu tiên |
|---|---|---|
| 1 | Mở rộng kiểm thử sang các context: browser, document, media | Cao |
| 2 | Tối ưu FPS: chạy context detection trong thread riêng | Cao |
| 3 | Bổ sung log cho Click, Double Click, Drag End, Scroll | Trung bình |
| 4 | Tích hợp Confidence Score từ MediaPipe vào CSV | Trung bình |
| 5 | Thực hiện nhiều phiên test (≥ 5 phiên, ≥ 3 người dùng) để đánh giá khách quan | Cao |
| 6 | Phân tích gesture latency (thời gian từ detect → execute) | Thấp |
| 7 | Xuất báo cáo Excel từ analyze_logs.py | Thấp |

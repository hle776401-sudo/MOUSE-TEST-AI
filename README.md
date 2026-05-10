# AI Gesture Mouse Controller

> Hệ thống điều khiển máy tính bằng **cử chỉ tay qua webcam** kết hợp **nhập liệu bằng giọng nói** — không cần chuột vật lý, không cần bàn phím.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc & các file](#2-kiến-trúc--các-file)
3. [Pipeline xử lý mỗi frame](#3-pipeline-xử-lý-mỗi-frame)
4. [Chế độ hoạt động](#4-chế-độ-hoạt-động)
5. [Phân vai tay (Role System)](#5-phân-vai-tay-role-system)
6. [Danh sách gesture đầy đủ](#6-danh-sách-gesture-đầy-đủ)
7. [Chức năng Voice Input](#7-chức-năng-voice-input)
8. [Kỹ thuật chống nhiễu](#8-kỹ-thuật-chống-nhiễu)
9. [UI Overlay](#9-ui-overlay)
10. [Cấu hình (config.py)](#10-cấu-hình-configpy)
11. [Cài đặt & Chạy](#11-cài-đặt--chạy)
12. [Desktop Control Panel GUI](#12-desktop-control-panel-gui)
13. [Phím tắt](#13-phím-tắt)
14. [Sơ đồ class](#14-sơ-đồ-class)
15. [Changelog Phase](#15-changelog-phase)

---

## 1. Tổng quan hệ thống

Hệ thống cho phép người dùng **điều khiển máy tính hoàn toàn bằng tay** thông qua webcam thông thường, không cần phần cứng đặc biệt. Kết hợp thêm **Voice Input** cho phép nhập liệu bằng giọng nói vào bất kỳ ô nhập nào đang được focus.

### Điều có thể làm được

| Nhóm | Chức năng |
|---|---|
| **Điều khiển chuột** | Move, Left Click, Double Click, Right Click, Drag & Drop, Scroll |
| **Điều khiển hệ thống** | Swipe Next/Prev (slide/PDF/web), Zoom In/Out, System Toggle ON/OFF |
| **Nhập liệu giọng nói** | Voice Text Mode → paste text vào ô focus |
| **Voice Command** | Voice Command Mode → thực thi lệnh từ whitelist (mở app, tìm kiếm...) |
| **Gesture Voice Trigger** | Giữ pose tay trái 1.2s → kích hoạt Voice Input (không cần bàn phím) |

### Công nghệ sử dụng

| Thư viện | Vai trò |
|---|---|
| `MediaPipe Hands` | Detect & track 21 landmarks bàn tay |
| `OpenCV` | Đọc webcam, flip frame, vẽ overlay |
| `PyAutoGUI` | Thực thi mouse/keyboard action |
| `SpeechRecognition` | Giao tiếp với Google Speech-to-Text |
| `PyAudio` | Driver microphone |
| `keyboard` | Global hotkey (không cần focus cửa sổ webcam) |
| `ctypes` | Windows Clipboard API (paste Unicode không mất focus) |

---

## 2. Kiến trúc & các file

```
MOUSE TEST AI/
├── main.py                     Main loop + UI overlay + mode switching
├── app_gui.py                  Desktop Control Panel (CustomTkinter) [MỚI]
├── config.py                   Tất cả hằng số và tham số cấu hình
├── hand_tracking.py            MediaPipe wrapper — detect & extract hand data
├── gesture_recognition.py      4 class nhận diện gesture (bao gồm Swipe V2 + Voice Trigger)
├── mouse_controller.py         Thực thi action qua PyAutoGUI + execute_action()
├── context_manager.py          Detect active window → classify context
├── action_router.py            Route (gesture, context) → action_name
├── voice_input.py              STT module — mic → audio → text
├── voice_intent.py             Rule-based parser — text → intent dict [MỚI]
├── voice_command_executor.py   Thực thi intent theo whitelist [MỚI]
├── gesture_logger.py           Ghi log gesture event ra CSV
├── analyze_logs.py             Phân tích file CSV log
├── utils.py                    Hàm tiện ích (distance, smooth, map, cooldown)
├── test_handedness.py          Script test xác nhận mapping tay phải/trái
└── requirements.txt            Danh sách dependencies
```

### Mối quan hệ giữa các file

```
main.py
  ├── hand_tracking.py        → get_all_hands_data() mỗi frame
  ├── gesture_recognition.py  → coordinator.process() hoặc recognizer.recognize()
  │     ├── PrimaryHandRecognizer    (tay phải: chuột)
  │     ├── SecondaryHandRecognizer  (tay trái: swipe V2/zoom/toggle/voice trigger)
  │     └── GestureCoordinator       (điều phối 2 tay)
  ├── context_manager.py      → update() + get_current_context()
  ├── action_router.py        → resolve(gesture) → action_name
  ├── mouse_controller.py     → process_gesture(), execute_action(), type_text()
  ├── voice_input.py          → listen_and_recognize() (trong thread riêng)
  ├── voice_intent.py         → VoiceIntentParser.parse(text) → intent dict [MỚI]
  ├── voice_command_executor.py → VoiceCommandExecutor.execute(intent) [MỚI]
  └── config.py               → import ở tất cả các file
```

---

## 3. Pipeline xử lý mỗi frame

```
┌─────────────────────────────────────────────────────────────┐
│                     MAIN LOOP (mỗi frame)                    │
│                                                               │
│  1. cap.read() → cv2.flip(frame, 1)     [Mirror webcam]      │
│                                                               │
│  2. context_manager.update()            [Context detect]     │
│     → classify active window → browser/presentation/...      │
│                                                               │
│  3. detector.find_hands(frame)          [MediaPipe detect]   │
│     → [{handedness, landmarks, fingers, palm_size, bbox}]    │
│                                                               │
│  4. Hand Assignment                     [Gán vai tay]        │
│     "Right" → primary_hand (tay phải)                        │
│     "Left"  → secondary_hand (tay trái)                      │
│                                                               │
│  5. Mode Switching (hysteresis)         [Chọn chế độ]        │
│     2 tay ≥ 5 frame → TWO_HAND                               │
│     < 2 tay ≥ 30 frame → ONE_HAND FALLBACK                   │
│                                                               │
│  6. Gesture Recognition                 [Nhận diện]          │
│     TWO_HAND → coordinator.process()                         │
│     ONE_HAND → primary/secondary recognizer riêng lẻ        │
│                                                               │
│  7. MouseController.process_gesture()   [Thực thi]           │
│     Swipe/Zoom → action_router.resolve() → execute_action()  │
│                                                               │
│  8. Draw Overlay → draw_context_hud()→ cv2.imshow()          │
│                                                               │
│  9. cv2.waitKey() + keyboard hook       [Phím điều khiển]    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Chế độ hoạt động

Hệ thống có **2 chế độ chính** tự động chuyển đổi dựa trên số tay detect được:

### 4.1 TWO-HAND MODE

**Kích hoạt**: Detect liên tục 2 tay trong ≥ 5 frame (~0.17 giây)

**Thoát**: Mất 1 tay liên tục ≥ 30 frame (~1 giây) — hysteresis để tránh nhảy mode

Khi đang ở TWO-HAND MODE mà tạm mất 1 tay (< 30 frame), hệ thống vào **Grace Period**: vẫn giữ mode, chỉ xử lý tay còn lại đúng vai trò của nó.

### 4.2 ONE-HAND FALLBACK MODE

**Kích hoạt**: Không đủ điều kiện vào TWO-HAND MODE

- Chỉ có tay phải → full cursor control
- Chỉ có tay trái → chỉ system gestures (swipe/zoom/toggle)

### Sơ đồ chuyển đổi

```
INIT
  │
  ├─[thấy 2 tay liên tục 5 frame]──► TWO-HAND MODE
  │                                        │
  │                                  [mất 1 tay < 30 frame]
  │                                        │
  │                                  GRACE PERIOD (giữ mode)
  │                                        │
  │                                  [mất 1 tay ≥ 30 frame]
  │                                        │
  └────────────────────────────────► ONE-HAND FALLBACK
```

---

## 5. Phân vai tay (Role System)

### Mapping handedness

```
MediaPipe label "Right" → Tay PHẢI người dùng → PRIMARY
MediaPipe label "Left"  → Tay TRÁI người dùng → SECONDARY
```
*(Đã xác nhận bằng test thực tế với `test_handedness.py` — camera flip không đảo label)*

### Ma trận gesture × role — CỨNG không thể vi phạm

| Gesture | Tay phải (PRI) | Tay trái (SEC) |
|---|---|---|
| Move Cursor | ✅ | ❌ |
| Left Click | ✅ | ❌ |
| Double Click | ✅ | ❌ |
| Right Click | ✅ | ❌ |
| Drag & Drop | ✅ | ❌ |
| Scroll Up/Down | ✅ | ❌ |
| Swipe Left/Right | ❌ | ✅ |
| Zoom In/Out | ❌ | ✅ |
| System Toggle | ❌ | ✅ |
| Voice Trigger (hold pose) | ❌ | ✅ |

### Cơ chế enforcement (2 tầng)

**Tầng 1 — Recognizer class:**
- `PrimaryHandRecognizer` không chứa code swipe/zoom/toggle
- `SecondaryHandRecognizer` không chứa code move/click/drag/scroll
- Không có đường nào trigger gesture sai nhóm

**Tầng 2 — main.py runtime:**
- Mỗi nhánh code chỉ gọi đúng recognizer cho đúng tay
- `coordinator.system_active` là nguồn state duy nhất

### GestureCoordinator (điều phối 2 tay)

```python
coordinator.process(primary_hand, secondary_hand)
  → Gọi SecondaryHandRecognizer TRƯỚC (Toggle ảnh hưởng system_active)
  → Gọi PrimaryHandRecognizer (chỉ khi system ON)
  → Lock: primary đang DRAG → block secondary swipe/zoom
```

---

## 6. Danh sách gesture đầy đủ

### 6.1 System Toggle (tay trái)

| | |
|---|---|
| **Cử chỉ** | Giơ cả 5 ngón tay, giữ yên ≥ 3 giây |
| **Grace period** | 0.4s đầu không đếm (cho swipe có cơ hội) |
| **Cooldown** | 2s sau khi toggle |
| **Action** | Bật/Tắt toàn bộ hệ thống |
| **UI** | Progress bar 0→100% trên overlay |

> Khi system **OFF**: tay phải không điều khiển chuột. Khi **ON**: toàn bộ chức năng hoạt động.

---

### 6.2 Move Cursor (tay phải)

| | |
|---|---|
| **Cử chỉ** | Chỉ ngón trỏ giơ lên `[x,1,0,0,0]` |
| **ROI** | Camera 640×480 với padding 100px ngang, 120px dọc |
| **Smoothing** | Nội suy tuyến tính, factor = 4 |
| **Deadzone** | 5px — không move nếu tay đứng yên |
| **Action** | `pyautogui.moveTo(x, y)` |

**Pipeline tọa độ:**
```
camera (x,y) → clamp(ROI) → map(screen) → smooth() → deadzone check → moveTo()
```

---

### 6.3 Left Click (tay phải)

| | |
|---|---|
| **Cử chỉ** | Ngón cái + Ngón trỏ chạm nhau (pinch) — ngón giữa PHẢI cụp |
| **Ngưỡng** | Khoảng cách chuẩn hóa < 28% palm_size |
| **Thời gian** | Giữ pinch < 300ms |
| **Guard** | Ngón giữa giơ → skip (nhường Zoom) |
| **Anchor** | Click tại đúng vị trí bắt đầu pinch |
| **Freeze** | Cursor không move 100ms sau click |
| **Action** | `pyautogui.click()` |

---

### 6.4 Double Click (tay phải)

| | |
|---|---|
| **Cử chỉ** | 2 lần Left Click trong vòng 0.5 giây |
| **Action** | `pyautogui.doubleClick()` |

---

### 6.5 Right Click (tay phải)

| | |
|---|---|
| **Cử chỉ** | Ngón cái + Ngón giữa chạm nhau (thumb-middle pinch) |
| **Guard** | Zoom mode đang active → vô hiệu hóa hoàn toàn |
| **Action** | `pyautogui.rightClick()` |

---

### 6.6 Drag & Drop (tay phải)

| | |
|---|---|
| **Cử chỉ** | Ngón cái + Ngón trỏ pinch và GIỮ ≥ 300ms → di chuyển → thả |
| **State machine** | `IDLE → PREPARING → HOLDING → DRAGGING → IDLE` |
| **Action** | `mouseDown()` → `moveTo()` → `mouseUp()` |

---

### 6.7 Scroll (tay phải)

| | |
|---|---|
| **Cử chỉ** | Nắm tay `[x,0,0,0,0]` + di chuyển dọc |
| **Ngưỡng** | Di dọc ≥ 10px |
| **Tốc độ** | ±12 đơn vị scroll/frame |
| **Action** | `pyautogui.scroll(±12)` |

---

### 6.8 Swipe Left / Right (tay trái) — Swipe V2

| | |
|---|---|
| **Cử chỉ** | 4 ngón giơ, ngón cái cụp `[0,1,1,1,1]` |
| **Thuật toán** | State Machine V2: `IDLE → ARMED → TRACKING → COOLDOWN` |
| **Khoảng cách** | ≥ 60px ngang |
| **Tốc độ** | ≥ 120 px/s |
| **Thời gian** | 0.12s → 0.9s |
| **Cooldown** | 0.7s giữa các lần swipe |
| **Grace frames** | 4 frame mất pose vẫn giữ state (tránh reset sớm) |
| **Swipe Left** ← | Lùi / previous / back |
| **Swipe Right** → | Tiến / next / forward |

**Context-Aware routing** (tự động theo ứng dụng đang mở):

| Context | Swipe Left ← | Swipe Right → |
|---|---|---|
| Browser | `Alt+Left` (back) | `Alt+Right` (forward) |
| Presentation | `←` (previous slide) | `→` (next slide) |
| Document/PDF | `PageUp` | `PageDown` |
| Media | Previous track | Next track |
| Default | `←` | `→` |

**Phân biệt với Toggle**: Swipe pose `[0,1,1,1,1]` (ngón cái cụp) ≠ Toggle pose `[1,1,1,1,1]` (5 ngón). Không xung đột.

---

### 6.9 Zoom In / Out (tay trái)

| | |
|---|---|
| **Cử chỉ** | Ngón trỏ + Ngón giữa giơ, ngón áp út + ngón út cụp (guard gesture) |
| **Tracking** | Khoảng cách ngón cái — ngón trỏ thay đổi |
| **Frame stability** | 4 frame liên tục ở zoom mode mới bắt đầu tracking |
| **Accumulator** | Gom delta nhiều frame, trigger khi tích lũy ≥ 20px |
| **Cooldown** | 0.25s giữa các lần zoom |
| **Zoom In** | Thumb-index tăng → `Ctrl+=` |
| **Zoom Out** | Thumb-index giảm → `Ctrl+-` |
| **Lock** | Tay phải đang drag → block zoom |

---

## 7. Chức năng Voice Input

Hệ thống hỗ trợ **2 mode Voice Input** hoạt động tự động theo nội dung giọng nói:

### 7.1 Voice Text Mode

Nếu câu nói **không khớp** bất kỳ command nào trong whitelist → paste text bình thường vào ô đang focus.

```
Ví dụ: "xin chào thầy cô" → paste "xin chào thầy cô" vào ô tìm kiếm/Google Docs...
```

### 7.2 Voice Command Mode

Nếu câu nói **khớp** command trong whitelist → thực thi lệnh (mở app, tìm kiếm, điều khiển hệ thống).

**Whitelist command:**

| Câu nói (tiếng Việt có dấu/không dấu) | Intent | Hành động |
|---|---|---|
| "mở youtube" / "mo youtube" | `open_youtube` | Mở https://www.youtube.com |
| "mở nhạc `<query>`" / "mo nhac" | `open_music` | Mở YouTube search |
| "mở bài hát `<query>`" | `open_music` | Mở YouTube search |
| "tìm kiếm `<query>`" / "tim kiem" | `web_search` | Mở Google search |
| "tra cứu `<query>`" / "tra cuu" | `web_search` | Mở Google search |
| "mở word" / "mo word" | `open_word` | Mở Microsoft Word |
| "mở chrome" / "mo chrome" | `open_chrome` | Mở Google Chrome |
| "mở cốc cốc" / "mo coc coc" | `open_coccoc` | Mở Cốc Cốc (nếu cài) |
| "bật hệ thống" / "bat he thong" | `system_on` | System ON |
| "tắt hệ thống" / "tat he thong" | `system_off` | System OFF |
| "bật điều khiển" / "bat dieu khien" | `system_on` | System ON |
| "tắt điều khiển" / "tat dieu khien" | `system_off` | System OFF |

> **Lưu ý an toàn:**
> - Chỉ thực thi đúng command trong whitelist. Không chạy shell tự do.
> - `open_music` / `web_search` bắt buộc phải có query — nếu không có → fallback text.
> - Không tự click video đầu tiên YouTube. Không mở file tùy ý.

**Kiến trúc Voice Command:**

```
voice_input.py  →  mic → audio → text (STT)
     ↓
voice_intent.py →  VoiceIntentParser.parse(text) → intent dict
     ↓                (rule-based, không LLM/API, hỗ trợ có dấu/không dấu)
 voice_command_executor.py → VoiceCommandExecutor.execute(intent)
     ↓                       (whitelist dispatch, dry_run mode, safe callbacks)
main.py         →  type_text() nếu text | execute_action nếu command
```

### 7.3 Gesture Voice Trigger

Ngoài `Ctrl+Alt+V`, có thể kích hoạt Voice Input bằng **cử chỉ tay trái**:

| | |
|---|---|
| **Pose** | `[0, 1, 1, 1, 0]` — cái cụp, trỏ+giữa+áp út duỗi, út cụp |
| **Hold time** | 1.2 giây |
| **Cooldown** | 3.0 giây sau khi trigger |
| **Điều kiện** | Chỉ hoạt động khi **System ON** |
| **Xung đột** | Không trùng Swipe `[0,1,1,1,1]`, Zoom `[0,1,1,0,0]`, Toggle `[1,1,1,1,1]` |
| **Fallback** | `Ctrl+Alt+V` vẫn hoạt động bất kể System ON/OFF |

**Quy tắc System ON/OFF an toàn:**

```
System OFF:
  ✅ System Toggle (5 ngón giữ 3s)    ← cách duy nhất thoát System OFF
  ✅ Ctrl+Alt+V                        ← hotkey dự phòng luôn hoạt động
  ❌ Move / Click / Drag / Scroll
  ❌ Swipe / Zoom
  ❌ Gesture Voice Trigger

System ON:
  ✅ Tất cả gesture đều hoạt động
  ✅ Gesture Voice Trigger (pose 1.2s)
  ✅ Ctrl+Alt+V
```

### 7.4 Flow tổng thể

```
User muốn dùng voice:
  Cách 1: Nhấn Ctrl+Alt+V (mọi lúc)
  Cách 2: Tay trái giữ pose [0,1,1,1,0] 1.2s (khi System ON)
     ↓
Mic mở → LISTENING (timeout 5s)
     ↓
Google STT → text
     ↓
VoiceIntentParser.parse(text)
     ├── type = "command" → VoiceCommandExecutor.execute()
     └── type = "text"   → controller.type_text() [paste vào ô focus]
```

### 7.5 State machine

```
VOICE_IDLE ──[Ctrl+Alt+V hoặc Gesture]──► VOICE_LISTENING ──[im lặng > 5s]──► VOICE_ERROR
                                                   │
                                             [có giọng nói]
                                                   │
                                           VOICE_RECOGNIZING ──[lỗi STT]──► VOICE_ERROR
                                                   │
                                             [có text]
                                                   │
                                     ┌─────────────┴─────────────┐
                               [command match]             [không match]
                                     │                           │
                              execute_action()           type_text() + paste
                                     │                           │
                               VOICE_DONE                  VOICE_DONE
```

### 7.6 Cấu hình Voice Input

| Config | Giá trị mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_VOICE_INPUT` | `True` | Bật/tắt Voice Input |
| `VOICE_HOTKEY` | `"ctrl+alt+v"` | Global hotkey kích hoạt |
| `VOICE_LANGUAGE` | `"vi-VN"` | Ngôn ngữ STT |
| `VOICE_LISTEN_TIMEOUT` | `5` | Chờ tối đa 5s bắt đầu nghe |
| `VOICE_PHRASE_TIME_LIMIT` | `30` | Tối đa 30s cho 1 câu nói |
| `VOICE_AUTO_ENTER` | `False` | Tự Enter sau khi gõ (chỉ text mode) |
| `ENABLE_VOICE_COMMANDS` | `True` | Bật Voice Command Mode |
| `VOICE_COMMAND_DRY_RUN` | `False` | Test không mở app thật |
| `ENABLE_GESTURE_VOICE_TRIGGER` | `True` | Bật Gesture Voice Trigger |
| `VOICE_TRIGGER_POSE` | `[0,1,1,1,0]` | Pose tay kích hoạt |
| `VOICE_TRIGGER_HOLD_SECS` | `1.2` | Thời gian giữ pose (giây) |
| `VOICE_TRIGGER_COOLDOWN` | `3.0` | Cooldown sau khi trigger (giây) |

### 7.7 Xử lý lỗi

| Lỗi | Trạng thái | Thông báo |
|---|---|---|
| Không có mic | `VOICE_ERROR` | "Không tìm thấy microphone" |
| Im lặng quá lâu | `VOICE_ERROR` | "Timeout: không nghe được giọng nói" |
| Không nhận ra | `VOICE_ERROR` | "Không nhận ra giọng nói" |
| Mất kết nối | `VOICE_ERROR` | "Lỗi kết nối STT" |
| Command không mở được app | warning print | App không crash |

> **Lưu ý**: Mọi lỗi đều được bắt — không crash chương trình chính. Gesture/cursor tiếp tục hoạt động bình thường.

---

## 8. Kỹ thuật chống nhiễu

| Kỹ thuật | Áp dụng ở | Mục đích |
|---|---|---|
| **Pinch Hysteresis** | Click/Drag | Enter threshold 28% palm_size, exit = 28% × 1.3 → tránh flicker |
| **PinchState Machine** | Click/Drag | `IDLE→PREPARING→HOLDING→DRAGGING` — unified flow tránh xung đột |
| **Post-action Cooldown** | Tất cả event | 0.15s neutral gap sau mỗi gesture event |
| **Click Freeze** | Cursor move | 100ms không di chuột sau click — chống run chuột sau click |
| **Deadzone** | Cursor move | 5px — không moveTo() nếu tay gần như đứng yên |
| **Smoothing** | Cursor move | Nội suy tuyến tính factor 4 — mượt, không jitter |
| **Frame Stability** | Zoom, Swipe | Phải liên tục N frame mới bắt đầu tracking |
| **Delta Accumulator** | Zoom | Gom delta nhỏ nhiều frame thành 1 trigger ổn định |
| **Grace Period** | Toggle | 0.4s đầu không đếm thời gian toggle |
| **Mode Hysteresis** | 2-hand/1-hand | Enter 5f, Exit 30f — tránh nhảy mode liên tục |
| **Drag Lock** | Coordinator | Đang drag → block secondary swipe/zoom |
| **Guard Gesture** | Zoom vs Click | Ngón giữa giơ → skip Pinch, nhường Zoom |
| **Single Thread Guard** | Voice Input | Chỉ 1 voice thread tại 1 thời điểm |

---

## 9. UI Overlay

Cửa sổ webcam hiển thị real-time:

```
┌──────────────────────────────────────────────────────┐
│  FPS: 28    Gesture: Move Cursor    System: ON        │  ← HUD
│                                    ┌───────────────┐ │
│                                    │CTX: Browser   │ │  ← Context HUD
│              [ SWIPE LEFT ]        │ACT: browser.. │ │  ← (góc trên-phải)
│                                    │WIN: Chrome... │ │
│   [ZOOM MODE] hoặc [SWIPE TRACKING]└───────────────┘ │  ← Mode indicator
│                                                       │
│        ┌──────────────┐                               │
│        │  ROI border  │  ← Vùng di chuyển chuột       │
│        └──────────────┘                               │
│                                                       │
│  PRIMARY: Move Cursor [ON]    SECONDARY: Swipe Right  │  ← Hand labels
│                                                       │
│  ████████░░ Toggle Progress                           │  ← Progress bar
│                                                       │
│  [MIC] LISTENING... (say something)                   │  ← Voice status
│                                                       │
│              TWO-HAND MODE ACTIVE                     │  ← Mode display
│                                          Q: Quit      │
│                                          S: Toggle    │
└──────────────────────────────────────────────────────┘
```

**Context HUD** (góc trên-phải): Viền màu theo context (vàng=Browser, xanh lá=Presentation, xanh dương=Document, tím=Media, xám=Default). Dòng ACT hiện xanh khi có action, xám khi idle.

**Debug overlay** (mỗi tay): `MP:Right=PRI` / `MP:Left=SEC` — xác nhận role assignment đúng.

---

## 10. Cấu hình (config.py)

File `config.py` chứa toàn bộ hằng số. Các tham số quan trọng nhất:

### Camera & ROI

```python
CAMERA_WIDTH = 640          # Độ rộng frame webcam
CAMERA_HEIGHT = 480         # Chiều cao frame webcam
ROI_PADDING_X = 100         # Padding trái/phải (tạo vùng an toàn cho ngón tay)
ROI_PADDING_Y = 120         # Padding trên/dưới
```

### Handedness

```python
PRIMARY_HAND_LABEL = "Right"    # MediaPipe label cho tay phải → Primary
SECONDARY_HAND_LABEL = "Left"   # MediaPipe label cho tay trái → Secondary
```

### Mode switching

```python
MODE_ENTER_TWO_HAND_FRAMES = 5    # Cần 5 frame liên tục thấy 2 tay
MODE_EXIT_TWO_HAND_FRAMES = 30    # Cần 30 frame mất 1 tay mới về fallback
```

### Context-Aware Gestures

```python
ENABLE_CONTEXT_AWARE    = True   # Bật/tắt toàn bộ Context-Aware
CONTEXT_CACHE_INTERVAL  = 0.5    # Chu kỳ query active window (giây)
SHOW_CONTEXT_HUD        = True   # Hiện Context HUD góc trên-phải
CONTEXT_STICKY_SECONDS  = 2.0    # Giữ context cũ khi tạm về default
```

### Swipe V2

```python
ENABLE_SWIPE_V2             = True   # Bật State Machine V2
SWIPE_V2_MIN_DISTANCE_X     = 60     # Khoảng cách ngang tối thiểu (px)
SWIPE_V2_MIN_VELOCITY_X     = 120    # Tốc độ tối thiểu (px/s)
SWIPE_V2_COOLDOWN           = 0.7    # Cooldown giữa các lần swipe
SWIPE_V2_LOST_GRACE_FRAMES  = 4      # Frame cho phép mất pose
```

### Voice Input

```python
ENABLE_VOICE_INPUT = True
VOICE_HOTKEY = "ctrl+alt+v"
VOICE_LANGUAGE = "vi-VN"
VOICE_AUTO_ENTER = False
```

### Voice Command Mode

```python
ENABLE_VOICE_COMMANDS      = True   # Bật Voice Command Mode
VOICE_COMMAND_DRY_RUN      = False  # True = chi print, khong mo app that
VOICE_COMMAND_PRINT_RESULT = True   # In ket qua parse/execute ra console
```

### Gesture Voice Trigger

```python
ENABLE_GESTURE_VOICE_TRIGGER = True         # Bat tinh nang trigger bang cu chi
VOICE_TRIGGER_POSE           = [0, 1, 1, 1, 0]  # Pose kich hoat
VOICE_TRIGGER_HOLD_SECS      = 1.2          # Thoi gian giu pose (giay)
VOICE_TRIGGER_COOLDOWN       = 3.0          # Cooldown sau trigger (giay)
```

---

## 11. Cài đặt & Chạy

### Yêu cầu

- Python 3.10+
- Windows 10/11
- Webcam
- Microphone (cho Voice Input)
- Internet (Google STT)

### Cài đặt

```bash
pip install -r requirements.txt
```

Nếu `PyAudio` lỗi trên Windows:
```bash
pip install pipwin
pipwin install pyaudio
```

### Chạy trực tiếp (terminal)

```bash
python main.py
```

### Chạy qua GUI (khái niệm sản phẩm)

```bash
python app_gui.py
```

> GUI là **Desktop Control Panel** — khởi động/dừng hệ thống, mở log, phân tích log, xem tài liệu. Xem mục 12 để biết thêm.

### Lần đầu sử dụng

1. Chương trình khởi động, hệ thống mặc định **OFF**
2. Giơ **tay trái** với cả 5 ngón, giữ yên **3 giây** → System **ON**
3. Dùng **tay phải** di chuyển chuột, click, scroll
4. Dùng **tay trái** để swipe slide, zoom trang
5. Nhấn **Ctrl+Alt+V** hoặc giữ pose `[0,1,1,1,0]` 1.2s để dùng voice

---

## 12. Desktop Control Panel GUI

### Vai trò

`app_gui.py` là **launcher độc lập** chạy `main.py` bằng `subprocess`. GUI không nhúng camera loop, không xử lý gesture, không can thiệp pipeline OpenCV/MediaPipe.

```
app_gui.py  (CustomTkinter window)
    │
    ├── subprocess.Popen([python, main.py])
    │       └── main.py chạy độc lập trong process riêng
    │               └── Camera loop + Gesture + Voice (không bị nhúng bởi GUI)
    │
    ├── poll timer (500ms) → tự cập nhật status khi process tắt
    └── _on_close() → terminate + wait + kill → giải phóng sạch
```

### Danh sách chức năng GUI

| Tính năng | Mô tả |
|---|---|
| **Start Controller** | Spawn `main.py` bằng subprocess; guard chống multi-spawn |
| **Stop Controller** | `terminate()` → wait 3s → `kill()` fallback; không block GUI |
| **Controller Status** | Nhãn trực quan: STOPPED / STARTING / RUNNING |
| **Open Logs Folder** | Mở thư mục `logs/` bằng Windows Explorer |
| **Analyze Logs** | Chạy `analyze_logs.py` trong background thread; hiện kết quả trong textbox |
| **Open README** | Mở `README.md` bằng trình xem mặc định của Windows |
| **Open Report** | Mở `BAO_CAO_HE_THONG.md` bằng trình xem mặc định |
| **System Configuration** | Hiện các giá trị cấu hình đọc từ `config.py` (safe import) |
| **Gesture Reference** | Bảng hướng dẫn nhanh cho cử chỉ tay phải/tay trái |
| **Analyze Output** | Scrollable textbox hiện kết quả phân tích log |

### Quy trình demo nhanh

```
1. Mở Control Panel:
      python app_gui.py

2. Bấm  [START CONTROLLER]
      → Status chuyển RUNNING
      → Cửa sổ camera OpenCV hiện ra riêng

3. Dùng cử chỉ tay điều khiển hệ thống:
      • 5 ngón tay trái giữ 3s  → System ON
      • Tay phải di chuyển     → Move cursor
      • Pinch ngắn              → Left Click
      • 4 ngón swipe            → Next / Prev slide
      • Ctrl+Alt+V              → Voice Input

4. Bấm  [STOP] khi xong
      → main.py dừng sạch, camera giải phóng

5. Bấm  [Analyze Logs]
      → Thống kê gesture/action từ phiên vừa chạy
```

### Lưu ý kỹ thuật

- GUI **không redirect stdout** của `main.py` — tránh deadlock buffer.
- `config.py` được import với `try/except` — GUI không crash nếu config lỗi.
- `analyze_logs.py` chạy trong `threading.Thread(daemon=True)`, kết quả post về UI qua `self.after()`.
- Poll timer 500ms tự cập nhật STOPPED khi người dùng nhấn `Q` trong cửa sổ camera.
- Đóng GUI khi đang RUNNING → `_on_close()` gọi `terminate` → `wait(3s)` → `kill()` fallback.

---

## 13. Phím tắt

| Phím / Tổ hợp | Chức năng |
|---|---|
| `Q` | Thoát chương trình |
| `S` | Toggle System ON/OFF nhanh (không cần cử chỉ) |
| `Ctrl+Alt+V` | Bật Voice Input (global, không cần focus webcam) |

---

## 14. Sơ đồ class

```
gesture_recognition.py
│
├── PinchState (enum)
│     IDLE / PREPARING / HOLDING / DRAGGING
│
├── GestureRecognizer           ← Legacy fallback (không dùng trong runtime)
│     recognize(landmarks, fingers, palm_size, hand_center)
│     → ALL gestures (toggle, pinch, move, scroll, zoom, swipe)
│
├── PrimaryHandRecognizer       ← Tay phải (cursor only)
│     recognize(landmarks, fingers, palm_size)
│     → Move, Click, DblClick, RClick, Drag, Scroll
│
├── SecondaryHandRecognizer     ← Tay trái (system only)
│     recognize(landmarks, fingers, palm_size, hand_center)
│     → Toggle, Swipe, Zoom
│
└── GestureCoordinator          ← Điều phối 2 recognizer
      process(primary_hand, secondary_hand)
      → {primary_result, secondary_result, system_active}

hand_tracking.py
└── HandDetector
      find_hands(frame)
      get_all_hands_data(frame)
      → [{handedness, landmarks, fingers, palm_size, center, bbox}]

context_manager.py  [MỚI]
└── ContextManager
      update()                       ← gọi mỗi frame (có cache 0.5s)
      get_current_context() → str    ← browser/presentation/document/media/default
      get_current_window_title() → str
      classify_window(title) → str
      get_context_display() → str    ← "CTX: Browser"
      get_last_non_default_context() ← sticky context

action_router.py  [MỚI]
└── ActionRouter(context_manager)
      resolve(gesture_name) → action_name
      get_last_action() → str
      get_last_context() → str

mouse_controller.py
└── MouseController(action_router=None)
      process_gesture(result_dict)   ← entry point chính
      execute_action(action_name)    ← [MỚI] thực thi action từ router
      move_cursor / click / drag / scroll / zoom_in / zoom_out
      swipe_action(gesture_name)     ← context-aware nếu router có mặt
      type_text(text)                ← ctypes clipboard, không steal focus
      press_enter()

voice_input.py
└── VoiceInputManager
      listen_and_recognize()  ← BLOCKING, gọi trong thread riêng
      → {"state": VoiceState, "text": str, "error": str}

main.py
└── main()
      ├── HandDetector, GestureCoordinator
      ├── ContextManager + ActionRouter (safe init, fallback None)
      ├── MouseController(action_router=action_router)
      ├── keyboard.add_hotkey(VOICE_HOTKEY, callback)
      ├── Main loop (context.update → detect → assign → mode → recognize → action → draw)
      ├── draw_context_hud()         ← [MỚI] HUD góc trên-phải
      └── cv2.waitKey() → Q/S keys
```

---

## Dependencies đầy đủ

```
numpy==2.2.6
opencv-python==4.12.0.88
mediapipe==0.10.9
protobuf==3.20.3
PyAutoGUI==0.9.54
SpeechRecognition==3.14.5
PyAudio==0.2.14
keyboard
```

---

## 15. Changelog Phase

### Phase: Context-Aware Gestures + Swipe V2 — **COMPLETED** ✅
*Tháng 5/2026 · Review: Gemini Pro High PASS*

| File | Thay đổi |
|---|---|
| `config.py` | Append Section 10: Context-Aware constants + Swipe V2 constants |
| `context_manager.py` | [MỚI] Detect active window, classify context, sticky mechanism |
| `action_router.py` | [MỚI] Route (gesture, context) → action_name |
| `mouse_controller.py` | Thêm `execute_action()`, tích hợp ActionRouter, anti-spam warning |
| `main.py` | Safe init ContextManager/ActionRouter, `draw_context_hud()`, `context_manager.update()` mỗi frame |
| `gesture_recognition.py` | Swipe V2 State Machine trong `SecondaryHandRecognizer` |

**Validation PASS:**
- ✅ App chạy, không crash import/init
- ✅ Context HUD đúng màu (Browser=vàng, Presentation=xanh lá, Document=xanh dương, Media=tím)
- ✅ Sticky context 2s khi tạm về default
- ✅ Swipe Left/Right route đúng context
- ✅ Zoom media → volume_up/volume_down
- ✅ Toggle 5 ngón không xung đột Swipe V2
- ✅ Zoom 2 ngón không xung đột Swipe V2
- ✅ Move/click/drag/scroll/voice không bị ảnh hưởng

---

### Phase: Voice Command Mode + Gesture Voice Trigger — **COMPLETED** ✅
*Tháng 5/2026*

| File | Thay đổi |
|---|---|
| `config.py` | Append Section 12: Voice Command constants; Section 13: Gesture Voice Trigger constants |
| `voice_intent.py` | [MỚI] VoiceIntentParser — rule-based, hỗ trợ tiếng Việt có/không dấu |
| `voice_command_executor.py` | [MỚI] VoiceCommandExecutor — whitelist dispatch, dry_run, system callbacks |
| `main.py` | Safe import, init parser/executor, nâng cấp `_voice_worker()`, `_check_gesture_voice_trigger()` |
| `gesture_recognition.py` | Thêm `_check_voice_trigger()` vào `SecondaryHandRecognizer` |

**Validation PASS:**
- ✅ Ctrl+Alt+V vẫn hoạt động (hotkey dự phòng)
- ✅ "mở youtube" → open_youtube
- ✅ "mở nhạc Sơn Tùng MTP" → YouTube search giữ dấu
- ✅ "tìm kiếm trí tuệ nhân tạo" → Google search
- ✅ "mở word" → Microsoft Word hoặc warning nếu không tìm thấy
- ✅ "xin chào thầy cô" → paste text (fallback text)
- ✅ "mở word bài báo cáo" → paste text (không mở Word — exact-only)
- ✅ Gesture Voice Trigger: giữ [0,1,1,1,0] 1.2s → voice bật
- ✅ Gesture Voice Trigger KHÔNG hoạt động khi System OFF
- ✅ Zoom / Swipe / Toggle không bị ảnh hưởng
- ✅ Camera loop không crash

---

---

### Phase: Desktop Control Panel GUI-1 — **COMPLETED** ✅
*Tháng 5/2026*

| File | Thay đổi |
|---|---|
| `app_gui.py` | [MỚI] CustomTkinter GUI — Launcher, Status, Quick Access, Gesture Reference |
| `requirements.txt` | Thêm `customtkinter` |

**Validation PASS:**
- ✅ GUI mở không crash, hiện Status STOPPED
- ✅ START → spawn `main.py`, Status RUNNING, cự̉a sổ̉ OpenCV hiện riêng
- ✅ Guard chống multi-spawn (bấm START 2 lần không spawn thêm process)
- ✅ STOP → `terminate()` → wait 3s → `kill()` fallback — camera giải phóng sạch
- ✅ Nhấn Q trong OpenCV → GUI tự về STOPPED trong ≤1s (poll 500ms)
- ✅ Đóng GUI khi RUNNING → `_on_close()` terminate + wait + kill an toàn
- ✅ Analyze Logs chạy trong background thread, không treo GUI
- ✅ Config import lỗi → fallback defaults, không crash
- ✅ Open Logs / README / Report → mở đúng bằng Windows default app
- ✅ `main.py` và tất cả file core **không bị sửa**

---

*Tài liệu này phản ánh trạng thái hệ thống tính đến tháng 5/2026.*

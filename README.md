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
12. [Phím tắt](#12-phím-tắt)
13. [Sơ đồ class](#13-sơ-đồ-class)

---

## 1. Tổng quan hệ thống

Hệ thống cho phép người dùng **điều khiển máy tính hoàn toàn bằng tay** thông qua webcam thông thường, không cần phần cứng đặc biệt. Kết hợp thêm **Voice Input** cho phép nhập liệu bằng giọng nói vào bất kỳ ô nhập nào đang được focus.

### Điều có thể làm được

| Nhóm | Chức năng |
|---|---|
| **Điều khiển chuột** | Move, Left Click, Double Click, Right Click, Drag & Drop, Scroll |
| **Điều khiển hệ thống** | Swipe Next/Prev (slide/PDF/web), Zoom In/Out, System Toggle ON/OFF |
| **Nhập liệu** | Voice Input → nhận diện giọng nói → gõ text vào ô đang focus |

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
├── main.py                 Main loop + UI overlay + mode switching
├── config.py               Tất cả hằng số và tham số cấu hình
├── hand_tracking.py        MediaPipe wrapper — detect & extract hand data
├── gesture_recognition.py  4 class nhận diện gesture
├── mouse_controller.py     Thực thi action qua PyAutoGUI
├── voice_input.py          STT module — mic → audio → text
├── utils.py                Hàm tiện ích (distance, smooth, map, cooldown)
├── test_handedness.py      Script test xác nhận mapping tay phải/trái
└── requirements.txt        Danh sách dependencies
```

### Mối quan hệ giữa các file

```
main.py
  ├── hand_tracking.py        → get_all_hands_data() mỗi frame
  ├── gesture_recognition.py  → coordinator.process() hoặc recognizer.recognize()
  │     ├── PrimaryHandRecognizer    (tay phải: chuột)
  │     ├── SecondaryHandRecognizer  (tay trái: system)
  │     └── GestureCoordinator       (điều phối 2 tay)
  ├── mouse_controller.py     → process_gesture(), type_text(), press_enter()
  ├── voice_input.py          → listen_and_recognize() (trong thread riêng)
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
│  2. detector.find_hands(frame)          [MediaPipe detect]   │
│     detector.get_all_hands_data()                            │
│     → [{handedness, landmarks, fingers, palm_size, bbox}]    │
│                                                               │
│  3. Hand Assignment                     [Gán vai tay]        │
│     "Right" → primary_hand                                   │
│     "Left"  → secondary_hand                                 │
│                                                               │
│  4. Mode Switching (hysteresis)         [Chọn chế độ]        │
│     2 tay ≥ 5 frame → TWO_HAND                               │
│     < 2 tay ≥ 30 frame → ONE_HAND FALLBACK                   │
│                                                               │
│  5. Gesture Recognition                 [Nhận diện]          │
│     TWO_HAND → coordinator.process()                         │
│     ONE_HAND → primary/secondary recognizer riêng lẻ        │
│                                                               │
│  6. MouseController.process_gesture()   [Thực thi]           │
│                                                               │
│  7. Draw Overlay → cv2.imshow()         [Hiển thị]           │
│                                                               │
│  8. cv2.waitKey() + keyboard hook       [Phím điều khiển]    │
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
| **Deadzone** | 3px — không move nếu tay đứng yên |
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

### 6.8 Swipe Left / Right (tay trái)

| | |
|---|---|
| **Cử chỉ** | ≥ 4 ngón giơ, vuốt ngang ≥ 80px trong < 0.5s |
| **Frame stability** | 2 frame liên tục thỏa điều kiện mới bắt đầu tracking |
| **Cooldown** | 0.8s giữa các lần swipe |
| **Swipe Left** | Nội dung tiếp theo |
| **Swipe Right** | Nội dung trước |

**3 chế độ swipe** (cấu hình bằng `SWIPE_MODE` trong config.py):

| Mode | Swipe Left | Swipe Right | Dùng cho |
|---|---|---|---|
| `"arrow"` | `→` (right arrow) | `←` (left arrow) | PowerPoint, Google Slides |
| `"page"` | `PageDown` | `PageUp` | PDF Viewer |
| `"browser"` | `Alt+Right` | `Alt+Left` | **Trình duyệt web** (mặc định) |

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

### Flow tổng thể

```
User click vào ô nhập (browser giữ focus)
  ↓
Nhấn Ctrl+Shift+V (global hotkey — không cần focus webcam)
  ↓
VOICE_LISTENING: Mic mở, chờ giọng nói (timeout 5s)
  ↓
VOICE_RECOGNIZING: Gửi audio lên Google Speech-to-Text
  ↓
VOICE_TYPING: Paste text vào ô đang focus bằng Windows Clipboard API
  ↓
VOICE_DONE: Hoàn thành (hoặc VOICE_ERROR nếu có lỗi)
```

### State machine

```
VOICE_IDLE ──[Ctrl+Shift+V]──► VOICE_LISTENING ──[im lặng > 5s]──► VOICE_ERROR
                                      │
                               [có giọng nói]
                                      │
                               VOICE_RECOGNIZING ──[lỗi mạng/STT]──► VOICE_ERROR
                                      │
                               [có text]
                                      │
                               VOICE_TYPING ──► VOICE_DONE
```

### Tại sao không mất focus ô nhập?

Vấn đề gốc: Cách cũ dùng `tkinter.Tk()` để copy clipboard → window tkinter ẩn vẫn **steal focus** khỏi browser → `Ctrl+V` paste vào sai chỗ.

**Giải pháp**: Dùng **Windows Clipboard API qua `ctypes`** (built-in Python):
```
GlobalAlloc → GlobalLock → memmove → GlobalUnlock
OpenClipboard → SetClipboardData → CloseClipboard
```
Không tạo window → **browser giữ nguyên focus** → Ctrl+V paste đúng ô tìm kiếm.

### Cấu hình Voice Input

| Config | Giá trị mặc định | Ý nghĩa |
|---|---|---|
| `ENABLE_VOICE_INPUT` | `True` | Bật/tắt chức năng |
| `VOICE_HOTKEY` | `"ctrl+shift+v"` | Global hotkey kích hoạt |
| `VOICE_LANGUAGE` | `"vi-VN"` | Ngôn ngữ STT (đổi `"en-US"` cho tiếng Anh) |
| `VOICE_LISTEN_TIMEOUT` | `5` | Chờ tối đa 5s để bắt đầu nghe |
| `VOICE_PHRASE_TIME_LIMIT` | `10` | Tối đa 10s cho 1 câu nói |
| `VOICE_AUTO_ENTER` | `False` | Tự nhấn Enter sau khi gõ xong |
| `VOICE_TYPING_SPEED` | `0.02` | Delay 20ms trước khi paste |

### Xử lý lỗi

| Lỗi | Trạng thái | Thông báo |
|---|---|---|
| Không có mic | `VOICE_ERROR` | "Không tìm thấy microphone" |
| Im lặng quá lâu | `VOICE_ERROR` | "Timeout: không nghe được giọng nói" |
| Không nhận ra | `VOICE_ERROR` | "Không nhận ra giọng nói" |
| Mất kết nối | `VOICE_ERROR` | "Lỗi kết nối STT" |

> **Lưu ý**: Mọi lỗi đều được bắt — không crash chương trình chính. Gesture/cursor tiếp tục hoạt động bình thường.

---

## 8. Kỹ thuật chống nhiễu

| Kỹ thuật | Áp dụng ở | Mục đích |
|---|---|---|
| **Pinch Hysteresis** | Click/Drag | Enter threshold 28% palm_size, exit = 28% × 1.3 → tránh flicker |
| **PinchState Machine** | Click/Drag | `IDLE→PREPARING→HOLDING→DRAGGING` — unified flow tránh xung đột |
| **Post-action Cooldown** | Tất cả event | 0.15s neutral gap sau mỗi gesture event |
| **Click Freeze** | Cursor move | 100ms không di chuột sau click — chống run chuột sau click |
| **Deadzone** | Cursor move | 3px — không moveTo() nếu tay gần như đứng yên |
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
│                                                       │
│              [ SWIPE LEFT ]                           │  ← Banner gesture lớn (linger 12f)
│                                                       │
│   [ZOOM MODE] hoặc [SWIPE TRACKING]                   │  ← Mode indicator
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

### Swipe mode

```python
SWIPE_MODE = "browser"    # "arrow" | "page" | "browser"
```

### Voice Input

```python
ENABLE_VOICE_INPUT = True
VOICE_HOTKEY = "ctrl+shift+v"
VOICE_LANGUAGE = "vi-VN"
VOICE_AUTO_ENTER = False
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

### Chạy

```bash
python main.py
```

### Lần đầu sử dụng

1. Chương trình khởi động, hệ thống mặc định **OFF**
2. Giơ **tay trái** với cả 5 ngón, giữ yên **3 giây** → System **ON**
3. Dùng **tay phải** di chuyển chuột, click, scroll
4. Dùng **tay trái** để swipe slide, zoom trang
5. Nhấn **Ctrl+Shift+V** để dùng voice input

---

## 12. Phím tắt

| Phím / Tổ hợp | Chức năng |
|---|---|
| `Q` | Thoát chương trình |
| `S` | Toggle System ON/OFF nhanh (không cần cử chỉ) |
| `Ctrl+Shift+V` | Bật Voice Input (global, không cần focus webcam) |

---

## 13. Sơ đồ class

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

mouse_controller.py
└── MouseController
      process_gesture(result_dict)   ← entry point chính
      move_cursor(cam_pos)
      left_click / double_click / right_click(anchor)
      drag_start / drag_move / drag_end
      scroll(amount)
      swipe_action(gesture_name)     ← 3 mode: arrow/page/browser
      zoom_in / zoom_out
      type_text(text)                ← ctypes clipboard, không steal focus
      press_enter()

voice_input.py
└── VoiceInputManager
      listen_and_recognize()  ← BLOCKING, gọi trong thread riêng
      reset()
      → {"state": VoiceState, "text": str, "error": str}

main.py
└── main()
      ├── HandDetector, GestureCoordinator, MouseController, VoiceInputManager
      ├── keyboard.add_hotkey(VOICE_HOTKEY, callback)
      ├── Main loop (frame → detect → assign → mode → recognize → action → draw)
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

*Tài liệu này phản ánh trạng thái hệ thống tính đến tháng 4/2026.*

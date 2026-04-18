# AI Gesture Mouse Controller

Hệ thống điều khiển máy tính bằng cử chỉ tay qua webcam (1 tay, rule-based).

## Kịch bản Demo (10 bước)

| # | Cử chỉ | Hành động | Ghi chú |
|---|--------|-----------|---------|
| 1 | Giơ 5 ngón giữ 4s | **System ON** | Progress bar hiện 0→100% |
| 2 | Chỉ ngón trỏ | **Move Cursor** | Di chuyển con trỏ theo tay |
| 3 | Thumb + Index pinch nhanh | **Left Click** | Cụp ngón giữa, pinch < 300ms |
| 4 | Pinch 2 lần liên tiếp | **Double Click** | 2 click trong 0.5s |
| 5 | Thumb + Middle pinch | **Right Click** | Ngón giữa giơ + ngón trỏ cụp |
| 6 | Thumb + Index giữ lâu | **Drag and Drop** | Pinch >= 300ms rồi di chuyển |
| 7 | Nắm tay + di dọc | **Scroll Up/Down** | 4 ngón chính cụp |
| 8 | Mở tay + vuốt ngang nhanh | **Swipe Left/Right** | Next/Prev slide (Right/Left arrow) |
| 9 | Index+Middle giơ + thumb xa/gần | **Zoom In/Out** | Ctrl+= / Ctrl+- |
| 10 | Giơ 5 ngón giữ 4s | **System OFF** | Tắt điều khiển |

**Tip demo**: Mở PowerPoint/PDF/trình duyệt để test Swipe và Zoom trực tiếp.

---

## Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Q` | Thoát chương trình |
| `S` | Toggle System ON/OFF nhanh (không cần giơ tay) |

---

## Pipeline xử lý (mỗi frame)

```
Webcam → flip → HandDetector → landmarks, fingers, palm_size
  → GestureRecognizer.recognize() → gesture result dict
  → MouseController.process_gesture() → PyAutoGUI action
  → Draw overlay → cv2.imshow()
```

### Priority pipeline trong recognize()

```
1. System Toggle    (luôn check, cả khi system OFF)
2. Post-action cooldown check
3. Pinch            (Click / Drag / Double Click — unified flow)
4. Zoom             (Index+Middle guard, thumb-index delta)
5. Right Click      (Thumb + Middle pinch — bị lock khi zoom mode)
6. Swipe            (Open palm + vuốt ngang nhanh)
7. Scroll           (Nắm tay + di dọc)
8. Move Cursor      (Chỉ ngón trỏ)
```

---

## Chi tiết Gesture

### System Toggle
- **Rule**: 5 ngón giữ yên >= 3.0s (+ 0.4s grace period cho swipe)
- **Action**: Toggle `system_active` flag

### Move Cursor
- **Rule**: `fingers = [x, 1, 0, 0, 0]` — chỉ ngón trỏ
- **Action**: `pyautogui.moveTo()` với ROI mapping + smoothing

### Left Click
- **Rule**: Thumb + Index pinch < 300ms (ngón giữa CỤP)
- **Guard**: `fingers[2] == 1` → skip (nhường Zoom)
- **Action**: `pyautogui.click()`

### Double Click
- **Rule**: 2x Left Click trong 0.5s
- **Action**: `pyautogui.doubleClick()`

### Right Click
- **Rule**: Thumb + Middle pinch (chạm rồi thả)
- **Guard**: Zoom mode active → vô hiệu hoàn toàn
- **Action**: `pyautogui.rightClick()`

### Drag and Drop
- **Rule**: Thumb + Index pinch >= 300ms → drag → thả pinch → drop
- **Action**: `mouseDown()` → `moveTo()` → `mouseUp()`

### Scroll
- **Rule**: Nắm tay `[x, 0, 0, 0, 0]` + di dọc
- **Action**: `pyautogui.scroll(±12)`

### Swipe Left / Right (Trình chiếu)
- **Rule**: >= 4 ngón giơ + vuốt ngang >= 80px trong < 0.5s
- **Frame stability**: 2 frame liên tục thỏa điều kiện mới bắt đầu tracking
- **Action**:
  - Swipe Left → `press('right')` — Next slide/page
  - Swipe Right → `press('left')` — Prev slide/page
  - Fallback: `press('pagedown')` / `press('pageup')`

### Zoom In / Out (1 tay)
- **Rule**: Index + Middle giơ, Ring + Pinky cụp (guard gesture)
  - Thumb-index distance tăng → Zoom In
  - Thumb-index distance giảm → Zoom Out
- **Frame stability**: 3 frame liên tục ở zoom mode mới bắt đầu tracking
- **Accumulator**: Gom delta nhiều frame, chỉ trigger khi >= 15px
- **Action**:
  - Zoom In → `Ctrl+=` (ổn định hơn `Ctrl++` trên Windows)
  - Zoom Out → `Ctrl+-`

---

## Kỹ thuật chống loạn

| Kỹ thuật | Mục đích |
|----------|----------|
| **Hysteresis** | Enter/exit threshold riêng cho pinch (1.3x) |
| **Unified Pinch Flow** | Click + Drag + Double Click chung state machine |
| **Post-action Cooldown** | 0.15s neutral gap sau event gestures |
| **Grace Period** | 0.4s cho toggle, nhường swipe chạy trước |
| **Frame Stability** | Zoom 3 frame, Swipe 2 frame liên tục mới bắt đầu |
| **Delta Accumulator** | Zoom gom nhiều frame nhỏ thành 1 trigger |
| **Click Anchor** | Lưu vị trí pinch bắt đầu cho visual feedback ổn định |
| **Guard Gesture** | Ngón giữa giơ → skip Pinch, lock Right Click → Zoom xử lý |

---

## Tham số Config

| Nhóm | Tham số | Giá trị |
|------|---------|---------|
| Camera | `CAMERA_WIDTH × HEIGHT` | 640 × 480 |
| MediaPipe | `MIN_DETECTION_CONFIDENCE` | 0.7 |
| Pinch | `PINCH_THRESHOLD_NORMALIZED` | 0.28 |
| | `PINCH_EXIT_MULTIPLIER` | 1.3 |
| | `PINCH_HOLD_THRESHOLD` | 0.30s |
| Double Click | `DOUBLE_CLICK_TIME_WINDOW` | 0.5s |
| Scroll | `SCROLL_SPEED / SENSITIVITY` | 12 / 10px |
| Swipe | `SWIPE_THRESHOLD_X` | 80px |
| | `SWIPE_STABLE_FRAMES` | 2 |
| | `SWIPE_COOLDOWN` | 0.8s |
| Zoom | `ZOOM_DELTA_THRESHOLD` | 15px |
| | `ZOOM_STABLE_FRAMES` | 3 |
| | `ZOOM_COOLDOWN` | 0.25s |
| Toggle | `SYSTEM_TOGGLE_HOLD_TIME` | 3.0s |
| | `OPEN_PALM_GRACE_PERIOD` | 0.4s |
| Stability | `POST_ACTION_COOLDOWN` | 0.15s |
| Smoothing | `SMOOTHING_FACTOR` | 4 |

---

## Chạy

```bash
python main.py
```

## Yêu cầu

- Python 3.8+
- `opencv-python`, `mediapipe`, `pyautogui`, `numpy`

## Phase 2 (chưa triển khai)

| Chức năng | Mô tả |
|-----------|-------|
| Zoom 2 tay | Khoảng cách 2 bàn tay thay đổi |
| Multi-hand | `MAX_NUM_HANDS = 2` |
| Custom gesture mapping | Config file cho user tự map gesture → action |

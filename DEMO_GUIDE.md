# DEMO GUIDE — AI Gesture Mouse Controller

**Đề tài:** ỨNG DỤNG THỊ GIÁC MÁY TÍNH XÂY DỰNG CHƯƠNG TRÌNH NHẬN DẠNG CỬ CHỈ TAY ĐỂ ĐIỀU KHIỂN MÁY TÍNH

---

## 1. Mục tiêu demo

Demo này minh họa hệ thống điều khiển máy tính hoàn toàn bằng cử chỉ tay thông qua webcam thường, không cần phần cứng đặc biệt.

**Các nhóm chức năng sẽ demo:**

| Nhóm | Nội dung |
|---|---|
| **GUI Control Panel** | Launcher, Start/Stop, Quick Access |
| **Gesture cơ bản** | Move, Click, Drag, Scroll (tay phải) |
| **Gesture hệ thống** | Toggle, Swipe, Zoom (tay trái) |
| **Context-Aware** | Swipe tự động next/prev slide trong PowerPoint |
| **Voice Input** | Text Mode + Command Mode (mở app, tìm kiếm) |
| **Gesture Logger** | Ghi log CSV, phân tích thống kê |

**Bản chất kỹ thuật cần nắm:**
- Không tự huấn luyện model AI mới.
- Dùng **MediaPipe Hands** (pretrained) để phát hiện 21 hand landmarks.
- Nhận dạng cử chỉ bằng **rule-based recognition**: normalized distance, finger state, threshold và state machine.
- **PyAutoGUI** ánh xạ gesture thành thao tác chuột/bàn phím.

---

## 2. Chuẩn bị trước khi demo

### Yêu cầu phần cứng/phần mềm

- Windows 10/11
- Python 3.10+
- Webcam hoạt động (không bị chiếm bởi Zoom, Teams, v.v.)
- Microphone hoạt động (đã cấp quyền trong Windows Settings)
- Internet ổn định (Google STT cần kết nối)
- Có sẵn PowerPoint hoặc file trình chiếu mẫu để demo Context-Aware
- Có sẵn browser (Chrome/Edge/CocCoc)

### Cài đặt môi trường

```powershell
cd "C:\MOUSE TEST AI"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu PowerShell báo lỗi policy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Nếu `PyAudio` lỗi:
```powershell
pip install pipwin
pipwin install pyaudio
```

### Kiểm tra nhanh trước demo

```powershell
# Syntax check
python -m py_compile app_gui.py main.py

# Kiểm tra import
python -c "import cv2, mediapipe, pyautogui, speech_recognition, customtkinter; print('OK')"
```

---

## 3. Cách chạy hệ thống

### Cách 1 — Ưu tiên (qua GUI Desktop Control Panel)

```powershell
python app_gui.py
```

Sau đó:
1. Cửa sổ Control Panel hiện ra, Status: **STOPPED**
2. Bấm **[START CONTROLLER]** → Status: RUNNING, cửa sổ camera OpenCV hiện ra
3. Sử dụng gesture/voice như bình thường
4. Bấm **[STOP]** để dừng

### Cách 2 — Trực tiếp (nếu cần)

```powershell
python main.py
```

Nhấn `Q` trong cửa sổ camera để thoát.

---

## 4. Kịch bản demo chính

> **Lưu ý:** Thực hiện theo thứ tự. Mỗi mục có thể demo độc lập nếu thời gian bị giới hạn.

---

### 4.1 Demo GUI Desktop Control Panel

**Thời gian ước tính: ~2 phút**

```
[ ] Mở terminal, chạy: python app_gui.py
[ ] Giải thích: GUI là launcher/control panel — không thay thế pipeline xử lý
[ ] Chỉ vào phần System Configuration → đọc từ config.py
[ ] Chỉ vào Gesture Reference → bảng hướng dẫn nhanh cho tay phải/trái
[ ] Bấm [START CONTROLLER] → cửa sổ OpenCV hiện ra
[ ] Quan sát Status chuyển RUNNING
[ ] Bấm [STOP] → camera dừng, Status về STOPPED
[ ] Nếu có log: bấm [Analyze Logs] để xem thống kê
```

---

### 4.2 Demo System Toggle (tay trái)

**Thời gian ước tính: ~1 phút**

```
[ ] Bật lại controller (START)
[ ] Hệ thống mặc định OFF khi khởi động
[ ] Giơ tay TRÁI — xòe đủ 5 ngón, hướng vào camera
[ ] Giữ yên ~3 giây → progress bar trên overlay đầy
[ ] System chuyển ON — overlay đổi màu
[ ] Giải thích: khi OFF, chỉ nhận toggle 5 ngón và Ctrl+Alt+V
[ ] Toggle lại để tắt → hệ thống về OFF
[ ] Toggle lần nữa để bật lại cho các demo tiếp theo
```

---

### 4.3 Demo tay phải (Primary Hand — Cursor Control)

**Thời gian ước tính: ~3 phút**

```
[ ] Đảm bảo System ON

Move Cursor:
[ ] Giơ tay PHẢI, chỉ duỗi ngón trỏ
[ ] Di chuyển tay → con trỏ chuột di chuyển theo

Left Click:
[ ] Chụm ngón cái + ngón trỏ (pinch) nhanh
[ ] Thả ra — thực hiện Left Click

Double Click:
[ ] Pinch 2 lần liên tiếp nhanh

Right Click:
[ ] Chụm ngón cái + ngón giữa
[ ] Menu chuột phải hiện ra

Drag & Drop:
[ ] Pinch và giữ trong thời gian ngắn cho đến khi hệ thống chuyển sang trạng thái drag, sau đó di chuyển tay để kéo thả
[ ] Di chuyển tay → kéo object
[ ] Thả ra → drop

Scroll:
[ ] Nắm tay (các ngón cụp)
[ ] Di chuyển tay lên/xuống → cuộn trang
```

---

### 4.4 Demo tay trái (Secondary Hand — System Control)

**Thời gian ước tính: ~2 phút**

```
[ ] Đảm bảo System ON

Swipe:
[ ] Duỗi 4 ngón [0,1,1,1,1] — ngón cái cụp
[ ] Quét nhanh sang TRÁI hoặc PHẢI
[ ] Gesture SWIPE được nhận diện (thấy trên overlay)

Zoom In / Zoom Out:
[ ] Duỗi ngón trỏ + ngón giữa [0,1,1,0,0]
[ ] Dang rộng 2 ngón → Zoom In (Ctrl + =)
[ ] Chụm lại 2 ngón → Zoom Out (Ctrl + -)

Gesture Voice Trigger:
[ ] Pose tay trái: [0,1,1,1,0] — cái cụp, trỏ/giữa/áp út duỗi, út cụp
[ ] Giữ yên 1.2 giây → Voice Input tự kích hoạt
[ ] Giải thích: trigger từ gesture, không cần nhấn phím
[ ] Chỉ hoạt động khi System ON
```

---

### 4.5 Demo Context-Aware Gestures

**Thời gian ước tính: ~3 phút**

**Kịch bản PowerPoint (context = presentation):**

```
[ ] Mở PowerPoint, chuẩn bị slideshow
[ ] Bắt đầu trình chiếu (F5 hoặc Slideshow mode)
[ ] Focus vào cửa sổ PowerPoint
[ ] Swipe LEFT (tay trái) → Previous Slide (←)
[ ] Swipe RIGHT (tay trái) → Next Slide (→)
[ ] Giải thích: ContextManager detect "PowerPoint" trong window title
               → ActionRouter route swipe → previous/next slide
               → Không cần cấu hình thủ công
```

**Kịch bản Browser (context = browser) — nếu có thêm thời gian:**

```
[ ] Mở Chrome/Edge, duyệt vài trang
[ ] Swipe RIGHT → Browser Forward
[ ] Swipe LEFT  → Browser Back
[ ] Giải thích: cùng gesture, khác context → khác hành động
```

---

### 4.6 Demo Voice Input

**Thời gian ước tính: ~3 phút**

**Voice Text Mode:**

```
[ ] Click vào ô tìm kiếm Google hoặc mở Notepad
[ ] Nhấn Ctrl+Alt+V (hoặc dùng Gesture Voice Trigger)
[ ] Nói một câu tiếng Việt, ví dụ: "xin chào thầy cô"
[ ] Hệ thống nhận diện → paste text vào ô đang focus
[ ] Giải thích: Google STT → text → Windows Clipboard API (ctypes) → paste vào ô đang focus
```

**Voice Command Mode:**

```
[ ] Nhấn Ctrl+Alt+V
[ ] Nói: "mở youtube"
[ ] Trình duyệt mở YouTube homepage

[ ] Nhấn Ctrl+Alt+V
[ ] Nói: "tìm kiếm trí tuệ nhân tạo"
[ ] Trình duyệt mở Google search với query

[ ] (Nếu máy có Word) Nhấn Ctrl+Alt+V → "mở word"
```

**Điểm nhấn khi thuyết trình:**
- Voice Command dùng **whitelist cứng** — không chạy shell tự do.
- Parser rule-based, không dùng LLM/API.
- Câu không khớp whitelist → fallback paste text (an toàn).

---

### 4.7 Demo Gesture Logger + Analyze Logs

**Thời gian ước tính: ~2 phút**

```
[ ] Thực hiện vài gesture (swipe, zoom, click) trong 1-2 phút
[ ] Dừng controller (STOP hoặc Q)
[ ] Trong GUI: bấm [Analyze Logs]
[ ] Kết quả hiện ra trong Analyze Output:
    - Total events, Success rate
    - Events by gesture (Swipe Left, Zoom In, ...)
    - Events by context (presentation, default, ...)
    - Events by action
    - FPS trung bình
[ ] Giải thích: GestureLogger ghi CSV, analyze_logs.py xử lý bằng built-in Python
[ ] Bấm [Open Logs Folder] để xem file CSV thô nếu cần
```

---

## 5. Checklist trước khi bảo vệ

Chạy checklist này **tối thiểu 30 phút trước khi demo**:

```
PHẦN CỨNG & MÔI TRƯỜNG
[ ] Webcam hoạt động, không bị app khác chiếm
[ ] Microphone hoạt động, đã cấp quyền Windows
[ ] Internet ổn định (Google STT)
[ ] .venv activate được
[ ] pip install -r requirements.txt không lỗi

KIỂM TRA KHỞi ĐỘNG
[ ] python app_gui.py chạy được, không crash
[ ] [START CONTROLLER] mở được cửa sổ camera
[ ] [STOP] tắt được camera sạch

KIỂM TRA GESTURE
[ ] System Toggle (5 ngón trái, 3s) ON/OFF
[ ] Move cursor tay phải hoạt động
[ ] Left Click (pinch ngắn) hoạt động
[ ] Swipe Left/Right (tay trái) hoạt động
[ ] Zoom In/Out (2 ngón trái) hoạt động

KIỂM TRA CONTEXT-AWARE
[ ] PowerPoint đã sẵn sàng, test swipe → next/prev slide
[ ] Browser đã mở, test swipe → back/forward

KIỂM TRA VOICE
[ ] Ctrl+Alt+V → mic bật → paste text
[ ] "mở youtube" → YouTube mở

KIỂM TRA LOGGER
[ ] Analyze Logs có output (cần chạy ít nhất 1 phiên trước)
[ ] Open Logs Folder mở được

VẬT LIỆU DỰ PHÒNG
[ ] Có sẵn PowerPoint demo (5–10 slide)
[ ] Có sẵn browser tab đã mở vài trang
[ ] Có ảnh screenshot kết quả analyze_logs nếu demo lỗi
[ ] Biết cách mở Task Manager để kill process nếu camera kẹt
```

---

## 6. Lỗi thường gặp và cách xử lý

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| **Không mở được camera** | App khác đang dùng camera (Zoom, Teams, Camera app) | Tắt toàn bộ app dùng camera, chạy lại |
| **MediaPipe không detect tay** | Ánh sáng yếu, tay quá gần/xa, background lộn xộn | Tăng sáng phòng, đặt tay cách camera 50–70cm, dùng background đơn giản |
| **Voice không nghe** | Mic chưa cấp quyền, không có internet, mic nhầm device | Kiểm tra Settings > Privacy > Microphone; test `ping google.com` |
| **PyAudio lỗi khi cài** | Wheel không tương thích | `pip install pipwin` rồi `pipwin install pyaudio`; hoặc tải wheel từ [lfd.uci.edu](https://www.lfd.uci.edu/~gohlke/pythonlibs/) |
| **GUI không chạy (ImportError)** | Thiếu `customtkinter` | `pip install customtkinter` hoặc `pip install -r requirements.txt` |
| **Stop không tắt camera** | Process bị treo | Nhấn `Q` trong cửa sổ OpenCV trực tiếp; nếu vẫn treo → kill python.exe trong Task Manager |
| **Gesture nhận sai/liên tục** | Ánh sáng ngược, tay rung, pose không chuẩn | Di chuyển tay chậm hơn, giữ đúng pose, tránh ánh sáng từ phía sau tay |
| **Swipe không chuyển slide** | PowerPoint chưa ở chế độ Slideshow / focus sai cửa sổ | F5 để vào Slideshow, click vào cửa sổ PPT, thử lại |
| **Voice command không execute** | Câu nói không khớp whitelist | Nói đúng cú pháp: "mở youtube", "tìm kiếm [query]" — kiểm tra console log |
| **Status mãi STARTING** | main.py crash ngay khi khởi động | Xem terminal, thường do thiếu webcam hoặc import lỗi |

---

## 7. Lệnh kiểm tra cuối

```powershell
# Kiểm tra working tree sạch
git status

# Syntax check các file quan trọng
python -m py_compile app_gui.py main.py voice_intent.py voice_command_executor.py

# Chạy GUI
python app_gui.py
```

---

## 8. Ghi chú an toàn khi thuyết trình

Nếu hội đồng hỏi về tính an toàn, trả lời theo các điểm sau:

| Câu hỏi thường gặp | Trả lời chuẩn |
|---|---|
| "GUI có thay thế OpenCV window không?" | Không. GUI chỉ là launcher/control panel. `main.py` vẫn là core xử lý, chạy riêng trong process độc lập. |
| "Có tự train model AI không?" | Không. Dùng **MediaPipe Hands** pretrained model — bộ 21 landmark đã được Google huấn luyện sẵn. |
| "Gesture recognition dùng gì?" | **Rule-based**: normalized distance, finger state, threshold và state machine — không phải neural network riêng. |
| "Voice Command có nguy hiểm không?" | Không. Dùng **whitelist cứng** — chỉ execute các intent định nghĩa sẵn. Câu lạ fallback thành text. Không chạy shell tự do. |
| "Tắt nguồn bằng lệnh voice được không?" | Không nằm trong whitelist. System ON/OFF chỉ toggle trạng thái phần mềm. |
| "System OFF an toàn không?" | System OFF chỉ nhận gesture 5 ngón (toggle) và hotkey Ctrl+Alt+V. Không nhận gesture di chuột, click, voice trigger. |
| "Hiệu năng camera loop bị ảnh hưởng bởi GUI không?" | GUI chạy process riêng và không can thiệp trực tiếp vào camera loop trong `main.py`. FPS thực tế phụ thuộc thiết bị, ánh sáng và tải xử lý; trong phiên test mẫu hệ thống đạt khoảng 16.1 FPS. |

---

## 9. Kịch bản nói nhanh khi bảo vệ

> Đoạn dưới có thể dùng để thuyết minh trong khi demo (~90 giây đến 2 phút).

---

*"Đây là hệ thống điều khiển máy tính bằng cử chỉ tay, được xây dựng bằng Python, OpenCV và MediaPipe Hands.*

*Tôi bắt đầu bằng cách mở Desktop Control Panel — đây là launcher GUI viết bằng CustomTkinter. Bấm **START CONTROLLER**, hệ thống spawn `main.py` dưới dạng subprocess, cửa sổ camera OpenCV hiện ra độc lập.*

*Pipeline mỗi frame: webcam → MediaPipe phát hiện 21 hand landmarks → rule-based recognizer phân loại gesture → PyAutoGUI thực thi thao tác chuột.*

*Hệ thống dùng hai tay với vai trò khác nhau: **tay phải** điều khiển con trỏ — move, click, drag, scroll; **tay trái** điều khiển hệ thống — toggle ON/OFF, swipe, zoom.*

*[Demo gesture tay phải và tay trái]*

*Điểm nổi bật là **Context-Aware Gestures**: cùng một động tác swipe, nhưng khi focus vào PowerPoint thì chuyển slide — khi ở browser thì back/forward. Hệ thống tự phát hiện ứng dụng đang active qua Windows API.*

*[Demo swipe trong PowerPoint]*

*Hệ thống còn tích hợp **Voice Input**: nhấn Ctrl+Alt+V hoặc dùng Gesture Voice Trigger — nói câu thường thì paste text, nói lệnh trong whitelist thì execute command như mở YouTube hay tìm kiếm Google.*

*Cuối cùng, mọi gesture đều được **ghi log CSV** qua GestureLogger. Bấm Analyze Logs để xem thống kê success rate, gesture distribution và FPS.*

*Hệ thống đã pass Final Safety Review — không có bug Critical hay High. Sẵn sàng demo."*

---

## Phụ lục: Whitelist Voice Command

| Câu nói | Lệnh thực thi |
|---|---|
| "mở youtube" | Mở youtube.com |
| "mở nhạc [tên bài]" | YouTube search |
| "mở bài hát [tên bài]" | YouTube search |
| "tìm kiếm [query]" | Google search |
| "mở word" | Mở Microsoft Word |
| "mở chrome" | Mở Google Chrome |
| "mở cốc cốc" | Mở CocCoc |
| "bật hệ thống" / "bật điều khiển" | System ON |
| "tắt hệ thống" / "tắt điều khiển" | System OFF |

> Câu không khớp whitelist → fallback paste text an toàn.

---

*DEMO_GUIDE.md — Tháng 5/2026 · AI Gesture Mouse Controller · Phase GUI-1 COMPLETED*

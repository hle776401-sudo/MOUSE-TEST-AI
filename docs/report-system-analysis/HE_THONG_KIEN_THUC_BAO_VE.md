# TÓM TẮT CHO BÁO CÁO VÀ BẢO VỆ

## 1. Tóm tắt hệ thống (1 trang)

**Đề tài:** Ứng dụng thị giác máy tính xây dựng chương trình nhận dạng cử chỉ tay để điều khiển máy tính.

Hệ thống cho phép người dùng hỗ trợ điều khiển máy tính bằng cử chỉ tay thông qua webcam thông thường, kết hợp nhập liệu bằng giọng nói. Chương trình sử dụng mô hình MediaPipe Hands (pretrained, Google) để phát hiện bàn tay và trích xuất 21 điểm landmark trong mỗi frame video thời gian thực. Phần nhận dạng cử chỉ được xây dựng bằng bộ luật (rule-based) dựa trên trạng thái ngón tay, khoảng cách chuẩn hóa, ngưỡng, hướng chuyển động, thời gian giữ, và state machine.

Hệ thống hỗ trợ 12 loại cử chỉ chia thành 2 nhóm: tay phải điều khiển con trỏ (move, click, double click, right click, drag, scroll) và tay trái điều khiển hệ thống (bật/tắt, swipe, zoom, kích hoạt giọng nói). Cơ chế context-aware cho phép cùng một cử chỉ swipe/zoom tự động thay đổi hành vi theo ứng dụng đang active. Hệ thống giọng nói hỗ trợ gõ text tiếng Việt và thực thi 8 lệnh thoại theo whitelist, đảm bảo an toàn.

Chương trình được viết bằng Python, chạy trên Windows, với giao diện GUI bằng CustomTkinter. GUI và hệ thống core chạy trên 2 process riêng biệt, đảm bảo ổn định.

---

## 2. 10 câu giải thích quan trọng khi bảo vệ

1. **Hệ thống không tự train AI.** MediaPipe Hands là model pretrained của Google. Phần nhận dạng cử chỉ do em tự xây dựng bằng rule-based.

2. **Rule-based phù hợp vì cử chỉ có cấu trúc rõ ràng.** 21 landmark cho ra thông tin trạng thái ngón tay, khoảng cách — đủ để phân loại bằng luật mà không cần dataset lớn.

3. **State machine là cốt lõi.** Pinch State Machine (3 trạng thái) phân biệt click ngắn và drag giữ lâu. Swipe V2 State Machine (4 trạng thái) đảm bảo chỉ nhận swipe khi pose ổn định.

4. **Hai tay không xung đột** nhờ phân vai: tay phải = Primary (cursor), tay trái = Secondary (system). Handedness do MediaPipe trả về.

5. **Context-aware tự động.** Hệ thống dùng Windows API lấy tiêu đề cửa sổ → phân loại context → cùng cử chỉ swipe nhưng hành vi khác nhau trên Chrome, PowerPoint, media player.

6. **Voice command an toàn.** Chỉ 8 lệnh trong whitelist, không chạy shell command tự do. Text tiếng Việt dùng Clipboard API, không steal focus.

7. **Smoothing + Deadzone loại bỏ rung.** Nội suy tuyến tính làm mượt, deadzone bỏ micro-movement, hysteresis tránh flickering.

8. **GUI và core là 2 process riêng.** app_gui.py chạy main.py bằng subprocess.Popen(). Crash GUI không ảnh hưởng core.

9. **Gesture Logger phục vụ thực nghiệm.** Mỗi swipe/zoom event ghi vào CSV → analyze_logs.py tính success rate, FPS trung bình.

10. **Hệ thống mặc định OFF.** Phải xòe 5 ngón 3 giây để bật — tránh kích hoạt nhầm.

---

## 3. Câu hỏi giảng viên có thể hỏi

### Q1: Em có tự train AI không?

> **Trả lời:** Dạ không. Em sử dụng MediaPipe Hands — một mô hình đã được Google huấn luyện sẵn — để phát hiện bàn tay và trích xuất 21 điểm landmark. Phần nhận dạng cử chỉ từ landmark em tự xây dựng bằng bộ luật (rule-based), không train model mới.

### Q2: MediaPipe Hands làm gì trong hệ thống?

> **Trả lời:** MediaPipe Hands nhận đầu vào là frame ảnh RGB và trả về 2 thông tin cho mỗi bàn tay: (1) tọa độ 21 điểm landmark trên bàn tay, và (2) nhãn handedness (tay trái/tay phải). Hệ thống em sử dụng 21 điểm này làm đầu vào cho bộ luật nhận dạng cử chỉ.

### Q3: OpenCV làm gì?

> **Trả lời:** OpenCV có 3 vai trò chính: (1) Đọc video thời gian thực từ webcam (`VideoCapture`), (2) Tiền xử lý ảnh (lật mirror, chuyển BGR→RGB), (3) Hiển thị demo overlay (vẽ landmark, banner cử chỉ, ROI, HUD lên frame). OpenCV không thực hiện nhận dạng cử chỉ — phần đó do module gesture_recognition.py đảm nhận.

### Q4: Vì sao dùng rule-based mà không dùng machine learning?

> **Trả lời:** Có 3 lý do chính:
> 1. **Dữ liệu có cấu trúc rõ ràng:** 21 landmark cho thông tin vị trí chính xác — có thể xác định ngón tay giơ/cụp, khoảng cách pinch bằng phép so sánh đơn giản.
> 2. **Số lượng cử chỉ hữu hạn:** 12 cử chỉ với điều kiện phân biệt rõ ràng — không cần mạng phân loại phức tạp.
> 3. **Dễ debug và điều chỉnh:** Khi cử chỉ bị nhận sai, chỉ cần điều chỉnh ngưỡng hoặc thêm điều kiện vào luật, không cần train lại model.
>
> Tuy nhiên, nếu số lượng cử chỉ tăng lên (>20) hoặc cần nhận dạng cử chỉ phức tạp hơn, ML sẽ phù hợp hơn. Đây là một hướng phát triển.

### Q5: Vì sao chia tay phải / tay trái?

> **Trả lời:** Để tránh xung đột chức năng. Nếu 1 tay vừa điều khiển con trỏ vừa toggle hệ thống, việc xòe 5 ngón để bật hệ thống sẽ gây con trỏ di chuyển loạn. Phân vai cho phép tay phải chuyên trỏ/click, tay trái chuyên toggle/swipe/zoom — hoạt động song song, không ảnh hưởng nhau.

### Q6: Vì sao cần state machine?

> **Trả lời:** State machine giải quyết vấn đề **phân biệt cử chỉ có thời gian**. Ví dụ:
> - **Pinch ngắn (<0.6s) = click, pinch dài (≥0.6s) = drag.** Nếu không có state machine, hệ thống không biết nên click hay drag ngay khi phát hiện pinch.
> - **Swipe = pose ổn định + di chuyển đủ lớn.** State machine (ARMED → TRACKING → COOLDOWN) đảm bảo chỉ nhận swipe khi đủ điều kiện, tránh kích hoạt nhầm khi tay vô tình di chuyển.

### Q7: Voice Input có phải trọng tâm của đề tài không?

> **Trả lời:** Voice input là **tính năng bổ sung**, không phải trọng tâm. Trọng tâm đề tài là nhận dạng cử chỉ tay để điều khiển chuột. Voice input hỗ trợ cho những tình huống mà cử chỉ tay không tiện — ví dụ gõ text tiếng Việt hoặc mở ứng dụng bằng lời nói.

### Q8: GUI có ảnh hưởng đến core không?

> **Trả lời:** Không. GUI (`app_gui.py`) và core (`main.py`) chạy trên 2 process riêng biệt. GUI chỉ khởi động core bằng `subprocess.Popen()` và kiểm tra trạng thái mỗi 500ms. Nếu GUI crash, camera loop vẫn chạy bình thường. Nếu core crash, GUI tự detect và hiển thị trạng thái "Đã dừng".

### Q9: Hạn chế của hệ thống là gì?

> **Trả lời:** Hệ thống có một số hạn chế:
> 1. **Phụ thuộc ánh sáng:** MediaPipe hoạt động kém trong ánh sáng yếu hoặc ngược sáng.
> 2. **Chỉ hỗ trợ Windows:** Do sử dụng Windows API cho clipboard và context detection.
> 3. **Voice cần internet:** Google STT API yêu cầu kết nối mạng.
> 4. **Không thay thế hoàn toàn chuột:** Trong tình huống cần thao tác chính xác cao (thiết kế đồ họa, viết code), chuột truyền thống vẫn tiện lợi hơn.
> 5. **Rule-based giới hạn số lượng cử chỉ:** Khi cần hỗ trợ nhiều cử chỉ hơn, rule-based sẽ khó mở rộng.

### Q10: Hướng phát triển là gì?

> **Trả lời:**
> 1. **Hỗ trợ đa nền tảng:** Linux, macOS — thay ctypes bằng thư viện cross-platform.
> 2. **Voice offline:** Dùng Vosk hoặc OpenAI Whisper để không cần internet.
> 3. **ML gesture recognition:** Train model phân loại cử chỉ từ dữ liệu landmark, cho phép thêm cử chỉ mới mà không cần viết luật.
> 4. **Đo performance chi tiết hơn:** Log latency mỗi gesture, so sánh với thao tác chuột truyền thống.
> 5. **Cấu hình qua GUI:** Cho phép người dùng thay đổi ngưỡng, smoothing, hotkey trực tiếp trên giao diện.

---

## 4. Các thuật ngữ cần nắm khi bảo vệ

| Thuật ngữ | Giải thích ngắn |
|---|---|
| MediaPipe Hands | Mô hình ML pretrained của Google, phát hiện bàn tay và 21 landmark |
| Landmark | Điểm đặc trưng trên bàn tay (21 điểm: cổ tay, đốt ngón, đầu ngón) |
| Handedness | Nhãn tay trái/tay phải do MediaPipe trả về |
| Rule-based | Nhận dạng dựa trên bộ luật if/else + ngưỡng, không train model |
| State machine | Máy trạng thái — quản lý chu trình có nhiều giai đoạn (IDLE → PREPARING → ...) |
| Hysteresis | Dùng 2 ngưỡng riêng (enter/exit) để tránh flickering |
| Deadzone | Vùng "chết" — bỏ qua di chuyển nhỏ để tránh rung |
| Smoothing | Làm mượt bằng nội suy tuyến tính (linear interpolation) |
| Cooldown | Thời gian chờ giữa 2 lần kích hoạt cùng hành động |
| Context-aware | Tự động thay đổi hành vi theo ứng dụng đang active |
| ROI | Region of Interest — vùng hoạt động trên camera |
| Palm size | Kích thước bàn tay dùng để chuẩn hóa khoảng cách |
| Whitelist | Danh sách lệnh cho phép — chỉ thực thi intent nằm trong danh sách |
| Subprocess | Process con — GUI chạy core bằng process riêng biệt |
| STT | Speech-to-Text — chuyển giọng nói thành văn bản |

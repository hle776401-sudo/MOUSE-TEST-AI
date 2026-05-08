"""
gesture_logger.py - Ghi log gesture/action/context ra file CSV
===============================================================
Phục vụ chương thực nghiệm trong báo cáo tốt nghiệp.

Mỗi lần chạy tạo 1 file CSV mới đặt tên theo ngày/giờ:
    logs/gesture_events_YYYYMMDD_HHMMSS.csv

CSV Header:
    timestamp, mode, system_active, context, window_title,
    gesture, action, executed, fps, note

Thiết kế:
- Không dependency ngoài (csv + datetime + os + pathlib).
- Flush sau mỗi event → không mất log khi app tắt đột ngột.
- enabled=False → bỏ qua hoàn toàn, không ghi gì.
- Mọi lỗi được catch nội bộ → không crash app chính.
"""

import csv
import os
from datetime import datetime
from pathlib import Path


# CSV column order (cố định, không được thay đổi nếu đã có dữ liệu)
_CSV_FIELDS = [
    "timestamp",
    "mode",
    "system_active",
    "context",
    "window_title",
    "gesture",
    "action",
    "executed",
    "fps",
    "note",
]


class GestureLogger:
    """Ghi log gesture/action/context ra file CSV.

    Mỗi instance tương ứng 1 file CSV (1 phiên chạy app).
    Gọi close() khi kết thúc để đảm bảo file được đóng sạch.

    Attributes:
        enabled:    Bật/tắt logging. Nếu False thì không ghi gì.
        log_dir:    Thư mục chứa file log (tự tạo nếu chưa có).
        _log_path:  Đường dẫn đầy đủ tới file CSV hiện tại.
        _file:      File handle đang mở.
        _writer:    csv.DictWriter instance.
        _event_count: Số event đã ghi trong phiên này.
    """

    def __init__(self, enabled: bool = True, log_dir: str = "logs") -> None:
        """Khởi tạo GestureLogger.

        Args:
            enabled:  True = ghi log; False = bỏ qua mọi event.
            log_dir:  Thư mục chứa file log. Tự tạo nếu chưa tồn tại.
        """
        self.enabled = enabled
        self.log_dir = log_dir
        self._log_path: str = ""
        self._file = None
        self._writer = None
        self._event_count: int = 0

        if not self.enabled:
            return

        try:
            # Tạo thư mục logs/ nếu chưa có
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)

            # Tên file theo ngày/giờ
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gesture_events_{timestamp_str}.csv"
            self._log_path = os.path.join(self.log_dir, filename)

            # Mở file và ghi header
            self._file = open(self._log_path, "w", newline="", encoding="utf-8-sig")
            self._writer = csv.DictWriter(self._file, fieldnames=_CSV_FIELDS)
            self._writer.writeheader()
            self._file.flush()

            print(f"[GestureLogger] Log file: {self._log_path}")

        except Exception as e:
            print(f"[GestureLogger] Init error: {e} — logging disabled.")
            self.enabled = False
            self._file = None
            self._writer = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_event(
        self,
        mode: str = "",
        system_active: bool = False,
        context: str = "default",
        window_title: str = "",
        gesture: str = "",
        action: str = "",
        executed: bool = False,
        fps: float = 0.0,
        note: str = "",
    ) -> None:
        """Ghi 1 dòng log vào CSV.

        Args:
            mode:           Chế độ hiện tại ("TWO_HAND" / "ONE_HAND" / …).
            system_active:  Hệ thống đang ON (True) hay OFF (False).
            context:        Context hiện tại (browser/presentation/…/default).
            window_title:   Tiêu đề cửa sổ active (rút gọn nếu cần).
            gesture:        Tên gesture ("Swipe Left", "Left Click", …).
            action:         action_name từ ActionRouter ("previous_slide", …).
            executed:       True nếu execute_action() thành công.
            fps:            FPS hiện tại của camera loop.
            note:           Ghi chú tự do (để trống nếu không cần).
        """
        if not self.enabled or self._writer is None:
            return

        try:
            row = {
                "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "mode":          mode,
                "system_active": int(system_active),   # 1 / 0
                "context":       context,
                "window_title":  window_title[:80],     # Giới hạn 80 ký tự
                "gesture":       gesture,
                "action":        action,
                "executed":      int(executed),         # 1 / 0
                "fps":           f"{fps:.1f}",
                "note":          note,
            }
            self._writer.writerow(row)
            self._file.flush()                         # Flush ngay để không mất log
            self._event_count += 1

        except Exception as e:
            # Không crash app — chỉ báo lỗi 1 lần
            if self._event_count == 0:
                print(f"[GestureLogger] Write error: {e}")

    def close(self) -> None:
        """Đóng file log. Gọi khi app kết thúc.

        An toàn khi gọi nhiều lần hoặc khi enabled=False.
        """
        if self._file is not None:
            try:
                self._file.flush()
                self._file.close()
                print(
                    f"[GestureLogger] Closed. "
                    f"{self._event_count} events -> {self._log_path}"
                )
            except Exception as e:
                print(f"[GestureLogger] Close error: {e}")
            finally:
                self._file = None
                self._writer = None

    def get_log_path(self) -> str:
        """Trả về đường dẫn đầy đủ tới file CSV hiện tại.

        Returns:
            Path string, hoặc chuỗi rỗng nếu logging bị tắt / chưa init.
        """
        return self._log_path

    # ------------------------------------------------------------------
    # Context manager support (dùng với `with GestureLogger() as logger:`)
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False   # Không suppress exception


# ==============================================================================
# Quick test block
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GestureLogger - Quick Test")
    print("=" * 60)

    with GestureLogger(enabled=True, log_dir="logs") as logger:
        print(f"Log path: {logger.get_log_path()}\n")

        # Dòng 1: Swipe Left trên Presentation
        logger.log_event(
            mode="TWO_HAND",
            system_active=True,
            context="presentation",
            window_title="Slide 1 - Microsoft PowerPoint",
            gesture="Swipe Left",
            action="previous_slide",
            executed=True,
            fps=28.5,
            note="test event 1",
        )
        print("Event 1 logged: Swipe Left -> previous_slide [presentation]")

        # Dòng 2: Swipe Right trên Browser
        logger.log_event(
            mode="TWO_HAND",
            system_active=True,
            context="browser",
            window_title="Google - Chrome",
            gesture="Swipe Right",
            action="browser_forward",
            executed=True,
            fps=29.0,
            note="test event 2",
        )
        print("Event 2 logged: Swipe Right -> browser_forward [browser]")

        # Dòng 3: Zoom In trên Media
        logger.log_event(
            mode="ONE_HAND",
            system_active=True,
            context="media",
            window_title="Trình phát Đa phương tiện",
            gesture="Zoom In",
            action="volume_up",
            executed=True,
            fps=27.3,
            note="test event 3",
        )
        print("Event 3 logged: Zoom In -> volume_up [media]")

        # Dòng 4: Gesture không route được
        logger.log_event(
            mode="TWO_HAND",
            system_active=False,
            context="default",
            window_title="",
            gesture="",
            action="no_action",
            executed=False,
            fps=30.0,
            note="system OFF",
        )
        print("Event 4 logged: no_action [system OFF]")

    print(f"\nDone. Kiem tra file: logs/")

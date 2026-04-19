"""
voice_input.py - Module nhập liệu bằng giọng nói
==================================================
Trách nhiệm:
  - Mở microphone
  - Nghe giọng nói từ người dùng
  - Gửi audio lên Google Speech-to-Text
  - Trả text kết quả (hoặc trạng thái lỗi) về cho main.py

Không chứa logic chuột, không chứa UI, không crash chương trình chính.

Cách dùng từ main.py:
    from voice_input import VoiceInputManager, VoiceState

    vm = VoiceInputManager()
    result = vm.listen_and_recognize()
    if result["state"] == VoiceState.DONE:
        text = result["text"]   # dùng text để gõ vào ô input
    elif result["state"] == VoiceState.ERROR:
        reason = result["error"]  # hiển thị lý do lỗi
"""

import speech_recognition as sr
import config as cfg


# ==============================================================================
# STATE CONSTANTS
# ==============================================================================

class VoiceState:
    """Các trạng thái của Voice Input Manager."""
    IDLE         = "VOICE_IDLE"          # Đang chờ, chưa làm gì
    LISTENING    = "VOICE_LISTENING"     # Mic đang mở, đang chờ giọng nói
    RECOGNIZING  = "VOICE_RECOGNIZING"   # Đã có audio, đang gửi lên STT
    TYPING       = "VOICE_TYPING"        # main.py đang gõ text (state báo hiệu)
    DONE         = "VOICE_DONE"          # Thành công, có text
    ERROR        = "VOICE_ERROR"         # Có lỗi (timeout / không nghe được / mạng)


# ==============================================================================
# VOICE INPUT MANAGER
# ==============================================================================

class VoiceInputManager:
    """
    Quản lý toàn bộ chu trình voice input: mic → audio → text.

    Attributes:
        recognizer: SpeechRecognition Recognizer object
        state: Trạng thái hiện tại (VoiceState constant)
        last_result: Kết quả lần nhận diện gần nhất
    """

    def __init__(self):
        self.recognizer = sr.Recognizer()

        # Điều chỉnh độ nhạy ambient noise tự động khi khởi động
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300   # Ngưỡng mặc định, sẽ tự điều chỉnh

        self.state = VoiceState.IDLE
        self.last_result = self._make_result(VoiceState.IDLE)

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    def listen_and_recognize(self):
        """
        Mở mic → nghe → nhận diện → trả kết quả.

        Đây là hàm chính main.py gọi khi người dùng nhấn hotkey.
        Hàm này BLOCKING (chờ xong mới trả về), nên main.py cần gọi
        trong một thread riêng để không block UI.

        Returns:
            dict: {
                "state": VoiceState constant,
                "text":  str (text nhận được, rỗng nếu lỗi),
                "error": str (mô tả lỗi, rỗng nếu thành công)
            }
        """
        # Bước 1: Mở microphone
        try:
            mic = sr.Microphone()
        except OSError as e:
            # Không tìm thấy microphone
            return self._set_error(f"Không tìm thấy microphone: {e}")

        # Bước 2: Nghe audio
        self.state = VoiceState.LISTENING
        try:
            with mic as source:
                # Điều chỉnh noise ngắn trước khi nghe
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                audio = self.recognizer.listen(
                    source,
                    timeout=cfg.VOICE_LISTEN_TIMEOUT,        # Chờ bắt đầu nói
                    phrase_time_limit=cfg.VOICE_PHRASE_TIME_LIMIT  # Giới hạn độ dài câu
                )

        except sr.WaitTimeoutError:
            # Người dùng không nói trong thời gian VOICE_LISTEN_TIMEOUT
            return self._set_error("Timeout: không nghe được giọng nói")

        except Exception as e:
            # Lỗi microphone không xác định
            return self._set_error(f"Lỗi microphone: {e}")

        # Bước 3: Gửi lên Google STT
        self.state = VoiceState.RECOGNIZING
        try:
            text = self.recognizer.recognize_google(
                audio,
                language=cfg.VOICE_LANGUAGE
            )
            return self._set_done(text.strip())

        except sr.UnknownValueError:
            # Có audio nhưng STT không hiểu được
            return self._set_error("Không nhận ra giọng nói")

        except sr.RequestError as e:
            # Lỗi kết nối tới Google API
            return self._set_error(f"Lỗi kết nối STT: {e}")

        except Exception as e:
            return self._set_error(f"Lỗi không xác định: {e}")

    def reset(self):
        """
        Reset về trạng thái IDLE.
        Gọi khi main.py muốn xóa trạng thái cũ giữa 2 lần dùng.
        """
        self.state = VoiceState.IDLE
        self.last_result = self._make_result(VoiceState.IDLE)

    def get_state(self):
        """Trả về trạng thái hiện tại (string từ VoiceState)."""
        return self.state

    # --------------------------------------------------------------------------
    # PRIVATE HELPERS
    # --------------------------------------------------------------------------

    def _make_result(self, state, text="", error=""):
        """Tạo result dict chuẩn."""
        return {
            "state": state,
            "text":  text,
            "error": error,
        }

    def _set_done(self, text):
        """Cập nhật state DONE và trả result."""
        self.state = VoiceState.DONE
        self.last_result = self._make_result(VoiceState.DONE, text=text)
        print(f"[VOICE] Done: '{text}'")
        return self.last_result

    def _set_error(self, reason):
        """Cập nhật state ERROR và trả result."""
        self.state = VoiceState.ERROR
        self.last_result = self._make_result(VoiceState.ERROR, error=reason)
        print(f"[VOICE] Error: {reason}")
        return self.last_result

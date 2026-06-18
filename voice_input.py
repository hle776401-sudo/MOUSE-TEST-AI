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
import time
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

        # --- Energy threshold ---
        # dynamic_energy_threshold = False: dung gia tri co dinh, khong drift
        # Gia tri 300 phu hop voi mic laptop/USB thong thuong
        # Neu dung True, sau adjust_for_ambient_noise() threshold co the bi day
        # qua cao (nhat la khi beep xen vao) -> mic thanh "diec"
        self.recognizer.dynamic_energy_threshold = getattr(
            cfg, 'VOICE_DYNAMIC_ENERGY', False)
        self.recognizer.energy_threshold = getattr(
            cfg, 'VOICE_ENERGY_THRESHOLD', 300)

        # Pause threshold: thời gian im lặng trước khi coi là hết câu
        # Mặc định 0.8s quá ngắn cho tiếng Việt → tăng lên 1.0s
        self.recognizer.pause_threshold = getattr(cfg, 'VOICE_PAUSE_THRESHOLD', 1.0)
        self.recognizer.phrase_threshold = 0.3    # Min duration để coi là phrase

        self.state = VoiceState.IDLE
        self.last_result = self._make_result(VoiceState.IDLE)

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    def listen_and_recognize(self, mode="command"):
        """
        Mở mic → nghe → nhận diện → trả kết quả.

        Đây là hàm chính main.py gọi khi người dùng nhấn hotkey.
        Hàm này BLOCKING (chờ xong mới trả về), nên main.py cần gọi
        trong một thread riêng để không block UI.

        Args:
            mode: "command" (lenh ngan, phrase=3s, pause=0.6s)
                  "text"    (nhap van ban, phrase=10s, pause=1.0s)

        Returns:
            dict: {
                "state": VoiceState constant,
                "text":  str (text nhận được, rỗng nếu lỗi),
                "error": str (mô tả lỗi, rỗng nếu thành công)
            }
        """
        # --- Chon STT params theo mode ---
        if mode == "text":
            _lt  = getattr(cfg, 'VOICE_TEXT_LISTEN_TIMEOUT', 7)
            _ptl = getattr(cfg, 'VOICE_TEXT_PHRASE_TIME_LIMIT', 10)
            _pt  = getattr(cfg, 'VOICE_TEXT_PAUSE_THRESHOLD', 1.0)
        else:  # "command" hoac fallback
            _lt  = getattr(cfg, 'VOICE_CMD_LISTEN_TIMEOUT', 5)
            _ptl = getattr(cfg, 'VOICE_CMD_PHRASE_TIME_LIMIT', 3)
            _pt  = getattr(cfg, 'VOICE_CMD_PAUSE_THRESHOLD', 0.6)
        self.recognizer.pause_threshold = _pt
        print(f"[VOICE] Mode: {mode} (timeout={_lt}s, phrase={_ptl}s, pause={_pt}s)")
        # --- Bước 0: Chờ beep kết thúc trước khi mở mic ---
        # Beep chạy trên thread riêng (200ms). Nếu mở mic ngay lập tức,
        # adjust_for_ambient_noise() sẽ calibrate VÀO tiếng beep
        # → energy_threshold bị đẩy rất cao → mic "điếc" sau đó.
        _beep_dur_ms = getattr(cfg, 'VOICE_BEEP_DURATION_MS', 200)
        if getattr(cfg, 'VOICE_BEEP_ENABLED', False) and _beep_dur_ms > 0:
            _wait = (_beep_dur_ms / 1000.0) + 0.15   # beep + 150ms margin
            time.sleep(_wait)

        # --- Bước 1: Mở microphone ---
        _mic_idx = getattr(cfg, 'VOICE_MIC_DEVICE_INDEX', None)
        try:
            if _mic_idx is not None:
                mic = sr.Microphone(device_index=_mic_idx)
                print(f"[VOICE] Mic: device_index={_mic_idx} (manual)")
            else:
                mic = sr.Microphone()
                print(f"[VOICE] Mic: default device")
        except OSError as e:
            return self._set_error(f"Không tìm thấy microphone (idx={_mic_idx}): {e}")
        except Exception as e:
            return self._set_error(f"Lỗi khởi tạo microphone: {e}")

        # --- Bước 2: Nghe audio ---
        self.state = VoiceState.LISTENING
        _energy_before = self.recognizer.energy_threshold
        _skip_cal = getattr(cfg, 'VOICE_SKIP_AMBIENT_CALIBRATION', False)
        _max_energy = getattr(cfg, 'VOICE_MAX_ENERGY_THRESHOLD', 800)
        # _lt da duoc set tu mode o tren

        try:
            with mic as source:
                # Kiem tra stream co mo duoc khong
                if source.stream is None:
                    return self._set_error(
                        f"Mic stream None (idx={_mic_idx}) — device khong ho tro")

                print(f"[VOICE] Mic sample_rate={source.SAMPLE_RATE}, "
                      f"sample_width={source.SAMPLE_WIDTH}")

                # Calibration (co the skip)
                if _skip_cal:
                    print(f"[VOICE] Skip ambient calibration "
                          f"(VOICE_SKIP_AMBIENT_CALIBRATION=True)")
                else:
                    _noise_dur = getattr(cfg, 'VOICE_NOISE_ADJUST_DURATION', 0.3)
                    self.recognizer.adjust_for_ambient_noise(
                        source, duration=_noise_dur)

                    _energy_after = self.recognizer.energy_threshold
                    print(f"[VOICE] Energy: before={_energy_before:.0f} -> "
                          f"after={_energy_after:.0f} "
                          f"(noise_adj={_noise_dur}s)")

                    # CLAMP: neu calibration day threshold qua cao -> reset
                    if _energy_after > _max_energy:
                        _clamp_to = getattr(cfg, 'VOICE_ENERGY_THRESHOLD', 300)
                        print(f"[VOICE][WARN] Energy {_energy_after:.0f} > "
                              f"max {_max_energy} — clamped to {_clamp_to}")
                        self.recognizer.energy_threshold = _clamp_to

                # _ptl da duoc set tu mode o tren
                print(f"[VOICE] Listening: timeout={_lt}s, phrase_limit={_ptl}s, "
                      f"pause={self.recognizer.pause_threshold}s, "
                      f"energy={self.recognizer.energy_threshold:.0f}")

                _listen_start = time.time()
                audio = self.recognizer.listen(
                    source,
                    timeout=_lt,
                    phrase_time_limit=_ptl,
                )
                _listen_dur = time.time() - _listen_start

                # Kiểm tra audio có thực sự chứa data không
                _audio_bytes = len(audio.get_raw_data())
                print(f"[VOICE] Audio captured: {_audio_bytes} bytes "
                      f"({_listen_dur:.1f}s)")

                if _audio_bytes < 1000:
                    print(f"[VOICE] WARNING: Audio qua ngan ({_audio_bytes} bytes)")

        except sr.WaitTimeoutError:
            return self._set_error(
                f"{mode.upper()} STT failed: Timeout ({_lt}s) "
                f"— không nghe được giọng nói "
                f"(energy={self.recognizer.energy_threshold:.0f})")

        except AttributeError as e:
            # stream.close() on None — device khong mo duoc stream
            return self._set_error(
                f"Mic device không mở được stream (idx={_mic_idx}): {e}")

        except Exception as e:
            return self._set_error(f"Lỗi microphone: {e}")

        # --- Bước 3: Gửi lên Google STT ---
        self.state = VoiceState.RECOGNIZING
        print(f"[VOICE] Sending {_audio_bytes} bytes to Google STT "
              f"(lang={cfg.VOICE_LANGUAGE})...")
        try:
            text = self.recognizer.recognize_google(
                audio,
                language=cfg.VOICE_LANGUAGE
            )
            print(f"[VOICE] STT raw result: '{text}'")
            return self._set_done(text.strip())

        except sr.UnknownValueError:
            return self._set_error(
                f"{mode.upper()} STT failed: UnknownValue "
                f"— không nhận ra giọng nói "
                f"({_audio_bytes} bytes, {_listen_dur:.1f}s audio)")

        except sr.RequestError as e:
            return self._set_error(
                f"{mode.upper()} STT failed: RequestError — {e}")

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

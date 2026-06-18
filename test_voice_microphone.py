"""
test_voice_microphone.py — Cong cu chan doan mic va STT doc lap
================================================================
Khong phu thuoc GUI, camera, gesture. Chi test mic + Google STT.

Cach dung:
  python test_voice_microphone.py --list
  python test_voice_microphone.py --test
  python test_voice_microphone.py --test --device 10
  python test_voice_microphone.py --test --device 10 --no-calibrate --threshold 300
  python test_voice_microphone.py --energy --device 10
"""

import sys
import argparse
import time

# Reconfigure stdout UTF-8 cho Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ==============================================================================
# SAFE MIC OPEN — chong crash khi device stream bi None
# ==============================================================================

def _safe_open_mic(sr_module, device_index=None):
    """Mo mic an toan. Tra ve (mic_object, error_msg).

    Neu thanh cong: (mic, None)
    Neu loi:        (None, "error message")
    """
    try:
        if device_index is not None:
            mic = sr_module.Microphone(device_index=device_index)
        else:
            mic = sr_module.Microphone()
    except Exception as e:
        return None, f"Khong tao duoc Microphone object: {e}"

    # Thu __enter__ de kiem tra stream co mo duoc khong
    try:
        mic.__enter__()
    except Exception as e:
        # Cleanup an toan — mic.stream co the la None
        try:
            mic.__exit__(None, None, None)
        except Exception:
            pass
        return None, f"Khong mo duoc mic stream: {e}"

    # Kiem tra stream thuc su co data khong
    if mic.stream is None:
        try:
            mic.__exit__(None, None, None)
        except Exception:
            pass
        return None, "Mic stream la None — device khong ho tro hoac bi chiem"

    return mic, None


def _safe_close_mic(mic):
    """Dong mic an toan, khong crash neu stream la None."""
    if mic is None:
        return
    try:
        mic.__exit__(None, None, None)
    except Exception:
        pass


# ==============================================================================
# LIST
# ==============================================================================

def list_microphones():
    """Liet ke tat ca microphone devices qua PyAudio."""
    import speech_recognition as sr

    print("=" * 65)
    print("  DANH SACH MICROPHONE DEVICES")
    print("=" * 65)

    try:
        mic_names = sr.Microphone.list_microphone_names()
    except Exception as e:
        print(f"  [!] Loi khi liet ke mic: {e}")
        return

    if not mic_names:
        print("  [!] Khong tim thay microphone nao.")
        print("      Kiem tra: Windows Settings > Privacy > Microphone")
        return

    for i, name in enumerate(mic_names):
        marker = ""
        if i == 0:
            marker = " (default)"
        # Nhan biet device dang nghi van
        name_lower = name.lower()
        if any(kw in name_lower for kw in ["virtual", "deskin", "stereo mix", "cable"]):
            marker += " [VIRTUAL]"

        try:
            test_mic = sr.Microphone(device_index=i)
            status = "OK"
        except Exception:
            status = "ERR"

        print(f"  [{i:>2}] {name:<50} [{status}]{marker}")

    print()
    print("  TIP: Chon mic co 'Microphone', 'Mic Array', 'Headset'.")
    print("       Tranh 'Stereo Mix', 'CABLE Output', 'Virtual', 'DeskIn'.")
    print()
    print(f"  Test:  python {sys.argv[0]} --test --device <N>")
    print(f"  Nhanh: python {sys.argv[0]} --test --device <N> --no-calibrate --threshold 300")
    print("=" * 65)


# ==============================================================================
# ENERGY MEASUREMENT
# ==============================================================================

def measure_energy(device_index=None, duration=3.0):
    """Do energy threshold tu dong trong N giay."""
    import speech_recognition as sr

    print("=" * 65)
    print("  DO ENERGY THRESHOLD (ambient noise)")
    print("=" * 65)

    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    r.energy_threshold = 300

    idx_label = f"index={device_index}" if device_index is not None else "default"
    print(f"  Device: {idx_label}")

    mic, err = _safe_open_mic(sr, device_index)
    if err:
        print(f"  [ERROR] {err}")
        return

    print(f"  Sample rate: {mic.SAMPLE_RATE} Hz")
    print(f"  Sample width: {mic.SAMPLE_WIDTH} bytes")
    print(f"  Dang do nhieu nen trong {duration}s... (giu im lang)")

    try:
        r.adjust_for_ambient_noise(mic, duration=duration)
    except Exception as e:
        print(f"  [ERROR] Calibration failed: {e}")
        _safe_close_mic(mic)
        return

    _safe_close_mic(mic)

    print(f"\n  Energy threshold sau calibration: {r.energy_threshold:.0f}")
    if r.energy_threshold > 800:
        print(f"  [!] CANH BAO: threshold qua cao!")
        print(f"      Thu: --no-calibrate --threshold 300")
    else:
        print(f"  Khuyen nghi: VOICE_ENERGY_THRESHOLD = {int(r.energy_threshold)}")
    print("=" * 65)


# ==============================================================================
# TEST VOICE
# ==============================================================================

def test_voice(device_index=None, language="vi-VN",
               no_calibrate=False, threshold=None, mode="command"):
    """Test mic + Google STT. Cho phep noi 1 cau va in ket qua."""
    import speech_recognition as sr

    print("=" * 65)
    print("  TEST VOICE RECOGNITION")
    print("=" * 65)

    r = sr.Recognizer()
    r.dynamic_energy_threshold = False

    # STT params theo mode
    if mode == "text":
        r.pause_threshold = 1.0
        _phrase_limit = 10
    else:  # "command"
        r.pause_threshold = 0.8
        _phrase_limit = 4
    r.phrase_threshold = 0.3

    # Energy threshold: dung tu argument hoac default 300
    _threshold = threshold if threshold is not None else 300
    r.energy_threshold = _threshold

    idx_label = f"index={device_index}" if device_index is not None else "default"
    print(f"  Device:    {idx_label}")
    print(f"  Language:  {language}")
    print(f"  Mode:      {mode} (phrase={_phrase_limit}s, pause={r.pause_threshold}s)")
    print(f"  Threshold: {_threshold}")
    print(f"  Calibrate: {'NO (--no-calibrate)' if no_calibrate else 'YES'}")

    # --- Mo mic an toan ---
    mic, err = _safe_open_mic(sr, device_index)
    if err:
        print(f"\n  [ERROR] Cannot open microphone stream for device {device_index}")
        print(f"          {err}")
        print(f"          Thu device khac: --list")
        return False

    print(f"  Sample rate:  {mic.SAMPLE_RATE} Hz")
    print(f"  Sample width: {mic.SAMPLE_WIDTH} bytes")

    # --- Calibrate (optional) ---
    if not no_calibrate:
        print(f"  Dang calibrate nhieu nen (0.5s)...")
        _energy_before = r.energy_threshold
        try:
            r.adjust_for_ambient_noise(mic, duration=0.5)
        except Exception as e:
            print(f"  [ERROR] Calibration failed: {e}")
            _safe_close_mic(mic)
            return False

        print(f"  Energy: {_energy_before:.0f} -> {r.energy_threshold:.0f}")

        if r.energy_threshold > 800:
            print(f"  [!] CANH BAO: threshold {r.energy_threshold:.0f} qua cao!")
            print(f"      -> Clamp ve {_threshold}")
            r.energy_threshold = _threshold
    else:
        print(f"  Energy threshold (co dinh): {r.energy_threshold:.0f}")

    # --- Nghe ---
    print()
    print("  >> Hay noi mot cau tieng Viet (VD: 'trang sau')...")
    print(f"     Timeout: 7s. Energy: {r.energy_threshold:.0f}. Mic dang nghe...")
    print()

    audio = None
    listen_dur = 0
    audio_bytes = 0

    try:
        t0 = time.time()
        audio = r.listen(mic, timeout=7, phrase_time_limit=_phrase_limit)
        listen_dur = time.time() - t0

        audio_bytes = len(audio.get_raw_data())
        print(f"  [OK] Audio captured: {audio_bytes} bytes ({listen_dur:.1f}s)")
        print(f"       Sample rate: {audio.sample_rate}, "
              f"sample width: {audio.sample_width}")

        if audio_bytes < 1000:
            print(f"  [!] CANH BAO: Audio qua ngan ({audio_bytes} bytes)")

    except sr.WaitTimeoutError:
        print(f"  [!] TIMEOUT: Khong nghe duoc gi trong 7 giay.")
        print(f"      Energy threshold: {r.energy_threshold:.0f}")
        print(f"      Goi y:")
        print(f"        - Mic sai device? Thu: --list")
        print(f"        - Threshold qua cao? Thu: --no-calibrate --threshold 200")
        print(f"        - Noi gan mic hon")
        _safe_close_mic(mic)
        return False

    except Exception as e:
        print(f"  [!] LOI nghe: {e}")
        _safe_close_mic(mic)
        return False

    # Dong mic sau khi nghe xong
    _safe_close_mic(mic)

    if audio is None:
        print(f"  [!] Khong co audio data.")
        return False

    # --- STT ---
    print(f"  Dang gui {audio_bytes} bytes len Google STT (lang={language})...")
    try:
        text = r.recognize_google(audio, language=language)
        print()
        print(f"  ✅ KET QUA STT: \"{text}\"")
        print()

        # Test parser neu co
        try:
            from voice_intent import parse_intent
            intent = parse_intent(text)
            print(f"  Parser result:")
            print(f"    type:   {intent['type']}")
            print(f"    intent: {intent['intent']}")
            if intent['type'] == 'command':
                print(f"    query:  {intent.get('query', '')}")
            print(f"    norm:   {intent['normalized_text']}")
        except ImportError:
            print(f"  (voice_intent.py khong tim thay, bo qua parser test)")
        except Exception as e:
            print(f"  Parser error: {e}")

        print()
        return True

    except sr.UnknownValueError:
        print(f"  [!] Google STT khong nhan ra giong noi.")
        print(f"      Audio: {audio_bytes} bytes ({listen_dur:.1f}s)")
        print(f"      Goi y:")
        print(f"        - Noi to hon, ro hon")
        print(f"        - Thu --threshold <thap hon> (VD: 200)")
        print(f"        - Thu device khac")
        return False

    except sr.RequestError as e:
        print(f"  [!] LOI KET NOI Google STT: {e}")
        print(f"      Kiem tra ket noi internet.")
        return False

    except Exception as e:
        print(f"  [!] LOI: {e}")
        return False


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test voice microphone cho Mouse Test AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Vi du:
  python test_voice_microphone.py --list
  python test_voice_microphone.py --test --device 10
  python test_voice_microphone.py --test --device 10 --no-calibrate --threshold 300
  python test_voice_microphone.py --test --device 18 --no-calibrate --threshold 200
  python test_voice_microphone.py --energy --device 10
        """,
    )
    parser.add_argument("--list", action="store_true",
                        help="Liet ke tat ca microphone devices")
    parser.add_argument("--test", action="store_true",
                        help="Test nhan dien giong noi (noi 1 cau)")
    parser.add_argument("--energy", action="store_true",
                        help="Do energy threshold tu nhieu nen")
    parser.add_argument("--device", type=int, default=None,
                        help="Chon mic device index (xem --list)")
    parser.add_argument("--lang", type=str, default="vi-VN",
                        help="Ngon ngu STT (mac dinh: vi-VN)")
    parser.add_argument("--no-calibrate", action="store_true",
                        help="Bo qua adjust_for_ambient_noise (dung threshold co dinh)")
    parser.add_argument("--threshold", type=int, default=None,
                        help="Dat energy_threshold thu cong (VD: 300, 200, 500)")
    parser.add_argument("--mode", type=str, default="command",
                        choices=["command", "text"],
                        help="Voice mode: command (phrase=3s,pause=0.6s) "
                             "hoac text (phrase=10s,pause=1.0s)")

    args = parser.parse_args()

    if not (args.list or args.test or args.energy):
        # Mac dinh: list + test
        list_microphones()
        print()
        test_voice(device_index=args.device, language=args.lang,
                   no_calibrate=args.no_calibrate, threshold=args.threshold,
                   mode=args.mode)
        return

    if args.list:
        list_microphones()

    if args.energy:
        measure_energy(device_index=args.device)

    if args.test:
        test_voice(device_index=args.device, language=args.lang,
                   no_calibrate=args.no_calibrate, threshold=args.threshold,
                   mode=args.mode)


if __name__ == "__main__":
    main()

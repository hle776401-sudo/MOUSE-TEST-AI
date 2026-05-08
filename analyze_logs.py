"""
analyze_logs.py - Phan tich file CSV do GestureLogger tao ra
=============================================================
Phuc vu chuong thuc nghiem trong bao cao tot nghiep.

Su dung:
    python analyze_logs.py                        # Tu tim file CSV moi nhat trong logs/
    python analyze_logs.py logs/<file>.csv        # Phan tich file chi dinh

Chi dung thu vien built-in: csv, pathlib, sys, collections, statistics
"""

import csv
import sys
from collections import Counter
from pathlib import Path
from statistics import mean


# ==============================================================================
# HELPERS
# ==============================================================================

def find_latest_log(log_dir: str = "logs") -> "Path | None":
    """Tim file gesture_events_*.csv moi nhat trong thu muc log_dir.

    Returns:
        Path toi file moi nhat, hoac None neu khong tim thay.
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return None
    files = sorted(log_path.glob("gesture_events_*.csv"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def read_events(csv_path: "Path | str") -> "list[dict]":
    """Doc tat ca event rows tu file CSV (bo qua header).

    Args:
        csv_path: Duong dan toi file CSV.

    Returns:
        List cac dict, moi dict la 1 row CSV.

    Raises:
        FileNotFoundError: Neu file khong ton tai.
        ValueError: Neu file khong dung dinh dang CSV ky vong.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")

    events = []
    # Thu utf-8-sig truoc (BOM), fallback utf-8
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    return []
                events = [row for row in reader]
            break
        except UnicodeDecodeError:
            continue

    return events


def print_counter(title: str, counter: Counter, total: int = 0) -> None:
    """In 1 counter dang danh sach phan cap.

    Args:
        title:   Ten phan.
        counter: Counter can in.
        total:   Neu > 0, in them phan tram.
    """
    print(f"\n{title}:")
    if not counter:
        print("  (none)")
        return
    for name, count in counter.most_common():
        label = name if name else "(empty)"
        if total > 0:
            pct = count / total * 100
            print(f"  - {label}: {count}  ({pct:.1f}%)")
        else:
            print(f"  - {label}: {count}")


# ==============================================================================
# MAIN ANALYSIS
# ==============================================================================

def analyze(csv_path: "Path | str") -> None:
    """Doc va in thong ke day du tu 1 file CSV log.

    Args:
        csv_path: Duong dan toi file CSV can phan tich.
    """
    csv_path = Path(csv_path)

    # --- Doc data ---
    try:
        events = read_events(csv_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return
    except Exception as e:
        print(f"[ERROR] Cannot read file: {e}")
        return

    print("\n" + "=" * 55)
    print("  Gesture Log Analysis")
    print("=" * 55)
    print(f"File : {csv_path}")

    if not events:
        print("\n[WARN] No events found (file is empty or header only).")
        return

    # --- Tinh toan co ban ---
    total        = len(events)
    success_list = [e for e in events if str(e.get("executed", "0")).strip() == "1"]
    failed_list  = [e for e in events if str(e.get("executed", "0")).strip() != "1"]
    n_success    = len(success_list)
    n_failed     = len(failed_list)
    success_rate = n_success / total * 100 if total > 0 else 0.0

    print(f"\nTotal events : {total}")
    print(f"Success      : {n_success}")
    print(f"Failed       : {n_failed}")
    print(f"Success rate : {success_rate:.1f}%")

    # --- Time range ---
    timestamps = [e.get("timestamp", "").strip() for e in events if e.get("timestamp", "").strip()]
    if timestamps:
        print(f"\nTime range:")
        print(f"  {timestamps[0]}  ->  {timestamps[-1]}")

    # --- Counters ---
    gesture_counter = Counter(
        e.get("gesture", "").strip() for e in events if e.get("gesture", "").strip()
    )
    context_counter = Counter(
        e.get("context", "").strip() for e in events if e.get("context", "").strip()
    )
    action_counter = Counter(
        e.get("action", "").strip() for e in events if e.get("action", "").strip()
    )
    note_counter = Counter(
        e.get("note", "").strip() for e in events if e.get("note", "").strip()
    )
    mode_counter = Counter(
        e.get("mode", "").strip() for e in events if e.get("mode", "").strip()
    )

    print_counter("Events by gesture", gesture_counter, total)
    print_counter("Events by context", context_counter, total)
    print_counter("Events by action",  action_counter,  total)
    print_counter("Events by note",    note_counter)
    if len(mode_counter) > 0:
        print_counter("Events by mode",   mode_counter)

    # --- FPS ---
    fps_values = []
    for e in events:
        try:
            v = float(e.get("fps", "0") or "0")
            if v > 0:
                fps_values.append(v)
        except (ValueError, TypeError):
            pass
    if fps_values:
        print(f"\nAverage FPS  : {mean(fps_values):.1f}  (from {len(fps_values)} samples)")

    # --- Window titles (top 5 unique) ---
    titles = [
        e.get("window_title", "").strip()
        for e in events
        if e.get("window_title", "").strip()
    ]
    if titles:
        unique_titles = list(dict.fromkeys(titles))   # giu thu tu, loai trung
        print(f"\nWindow titles seen ({len(unique_titles)} unique):")
        for t in unique_titles[:5]:
            print(f"  - {t[:70]}")
        if len(unique_titles) > 5:
            print(f"  ... and {len(unique_titles) - 5} more")

    print("\n" + "=" * 55)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main() -> None:
    # --- Xac dinh file can phan tich ---
    if len(sys.argv) >= 2:
        # User truyen path
        target = Path(sys.argv[1])
        if not target.exists():
            print(f"[ERROR] File not found: {target}")
            sys.exit(1)
    else:
        # Tu tim file moi nhat trong logs/
        target = find_latest_log("logs")
        if target is None:
            log_dir = Path("logs")
            if not log_dir.exists():
                print("[INFO] Thu muc 'logs/' chua ton tai.")
                print("       Hay chay app truoc de tao file log.")
            else:
                print("[INFO] Khong tim thay file gesture_events_*.csv trong logs/")
                print("       Hay chay app va thuc hien Swipe/Zoom de tao log.")
            sys.exit(0)

    analyze(target)


if __name__ == "__main__":
    main()

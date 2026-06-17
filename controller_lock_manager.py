"""
controller_lock_manager.py - Controller Lock State Machine (Phase 1 Skeleton)
==============================================================================
Module huong phat trien: Single-controller lock using MediaPipe Pose.

Muc dich:
  - Quan ly state machine 3 trang thai: IDLE -> ARMING -> LOCKED.
  - Chon va khoa 1 nguoi lam controller khi ho gio tay giu du lau.
  - Quan ly lost grace period khi controller tam thoi mat khoi frame.
  - Luu ControllerSignature de Hand-Person Association doi chieu.

Luu y:
  - Module nay chi duoc goi khi MULTI_PERSON_CONTROLLER_LOCK_ENABLED = True.
  - Khi flag = False, module nay KHONG chay trong pipeline.
  - mp.solutions.pose chi detect 1 nguoi — day la single-controller lock,
    KHONG phai multi-person detection.

Trang thai: SKELETON — chua tich hop vao main loop.
"""

import time
import math
from dataclasses import dataclass
from typing import Optional

# Import cung module trong project
try:
    from pose_tracker import PersonPose
except ImportError:
    PersonPose = None


# ==============================================================================
# CONTROLLER SIGNATURE
# ==============================================================================

@dataclass
class ControllerSignature:
    """Thong tin controller da khoa de doi chieu giua cac frame.

    Luu tru toa do normalized cua nguoi da duoc xac thuc.
    Hand-Person Association se dung wrist positions de ghep ban tay.

    Attributes:
        body_center:     Tam co the (trung binh 2 vai), normalized.
        shoulder_width:  Khoang cach 2 vai, normalized.
        left_shoulder:   Vai trai, normalized (x, y).
        right_shoulder:  Vai phai, normalized (x, y).
        left_wrist:      Co tay trai Pose, normalized (x, y).
        right_wrist:     Co tay phai Pose, normalized (x, y).
        raised_side:     "left" / "right" / "both".
        last_seen_time:  time.time() lan cuoi thay controller.
        lock_time:       time.time() khi duoc lock.
    """
    body_center: tuple = (0.0, 0.0)
    shoulder_width: float = 0.0
    left_shoulder: tuple = (0.0, 0.0)
    right_shoulder: tuple = (0.0, 0.0)
    left_wrist: tuple = (0.0, 0.0)
    right_wrist: tuple = (0.0, 0.0)
    raised_side: str = "none"
    last_seen_time: float = 0.0
    lock_time: float = 0.0


# ==============================================================================
# STATE CONSTANTS
# ==============================================================================

STATE_IDLE = "IDLE"
STATE_ARMING = "ARMING"
STATE_LOCKED = "LOCKED"


# ==============================================================================
# CONTROLLER LOCK MANAGER
# ==============================================================================

class ControllerLockManager:
    """State machine quan ly viec khoa nguoi dieu khien.

    Pipeline:
        1. IDLE:   Chua co controller. Cho nguoi gio tay.
        2. ARMING: Phat hien nguoi gio tay, dang dem thoi gian giu.
        3. LOCKED: Da khoa controller. Chi xu ly tay thuoc nguoi nay.

    Cach dung:
        manager = ControllerLockManager(hold_secs=3.0, grace_secs=3.0)

        # Moi frame (hoac moi N frame khi LOCKED):
        manager.update(person_pose)

        # Kiem tra trang thai:
        if manager.state == STATE_LOCKED:
            sig = manager.controller_signature
            # Dung sig de filter hands

    An toan:
        - Neu PersonPose la None: coi nhu mat controller.
        - Neu loi bat ky: giu trang thai hien tai, khong crash.
    """

    def __init__(self,
                 hold_secs: float = 3.0,
                 grace_secs: float = 3.0,
                 stable_frames: int = 5,
                 match_threshold: float = 0.15):
        """Khoi tao ControllerLockManager.

        Args:
            hold_secs:       Thoi gian gio tay lien tuc de lock (giay).
            grace_secs:      Thoi gian grace khi mat controller (giay).
            stable_frames:   So frame on dinh truoc khi bat dau dem hold.
            match_threshold: Nguong Euclidean distance (normalized) de
                             coi 2 body_center la cung 1 nguoi.
        """
        self.state: str = STATE_IDLE
        self.controller_signature: Optional[ControllerSignature] = None

        # Config
        self._hold_secs = hold_secs
        self._grace_secs = grace_secs
        self._stable_frames = stable_frames
        self._match_threshold = match_threshold

        # Internal state
        self._arming_start_time: float = 0.0
        self._arming_stable_count: int = 0
        self._arming_body_center: tuple = (0.0, 0.0)
        self._last_seen_time: float = 0.0

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def update(self, person: Optional['PersonPose'] = None) -> str:
        """Cap nhat state machine voi PersonPose moi nhat.

        Goi moi frame (hoac moi N frame khi LOCKED).
        mp.solutions.pose chi tra 1 person nen tham so la Optional[PersonPose].

        Args:
            person: PersonPose tu PoseTracker.process(), None neu khong detect.

        Returns:
            str: Trang thai hien tai (STATE_IDLE / STATE_ARMING / STATE_LOCKED).
        """
        now = time.time()

        try:
            if self.state == STATE_IDLE:
                self._handle_idle(person, now)

            elif self.state == STATE_ARMING:
                self._handle_arming(person, now)

            elif self.state == STATE_LOCKED:
                self._handle_locked(person, now)

        except Exception as e:
            print(f"[LOCK_MANAGER] Error in update: {e}")
            # Giu trang thai hien tai, khong crash

        return self.state

    def force_unlock(self):
        """Bat buoc unlock (goi tu hotkey hoac System Toggle)."""
        if self.state != STATE_IDLE:
            print("[LOCK_MANAGER] Force unlock")
            self.state = STATE_IDLE
            self.controller_signature = None
            self._reset_arming()

    def get_lock_duration(self) -> float:
        """Tra ve thoi gian da lock (giay). 0 neu chua lock."""
        if self.state == STATE_LOCKED and self.controller_signature:
            return time.time() - self.controller_signature.lock_time
        return 0.0

    def get_arming_progress(self) -> float:
        """Tra ve tien trinh arming (0.0 - 1.0). 0 neu khong arming."""
        if self.state != STATE_ARMING:
            return 0.0
        elapsed = time.time() - self._arming_start_time
        return min(1.0, elapsed / self._hold_secs)

    # ------------------------------------------------------------------
    # STATE HANDLERS
    # ------------------------------------------------------------------

    def _handle_idle(self, person, now):
        """IDLE: cho nguoi gio tay."""
        if person is None or not person.is_raising_hand:
            return

        # Bat dau arming
        self._arming_body_center = person.body_center
        self._arming_stable_count = 1
        self._arming_start_time = now
        self.state = STATE_ARMING
        print(f"[LOCK_MANAGER] IDLE -> ARMING "
              f"(raised_side={person.raised_side})")

    def _handle_arming(self, person, now):
        """ARMING: dem stable frames + hold time."""
        if person is None or not person.is_raising_hand:
            # Mat tay hoac ha tay -> reset
            print("[LOCK_MANAGER] ARMING -> IDLE (lost/lowered hand)")
            self.state = STATE_IDLE
            self._reset_arming()
            return

        # Kiem tra co phai cung 1 nguoi (body center gan nhau)
        dist = math.hypot(
            person.body_center[0] - self._arming_body_center[0],
            person.body_center[1] - self._arming_body_center[1],
        )
        if dist > self._match_threshold:
            # Nguoi khac gio tay, reset
            print(f"[LOCK_MANAGER] ARMING -> IDLE "
                  f"(person changed, dist={dist:.3f})")
            self.state = STATE_IDLE
            self._reset_arming()
            return

        # Cap nhat body center (cho phep di chuyen nhe)
        self._arming_body_center = person.body_center
        self._arming_stable_count += 1

        # Chua du stable frames
        if self._arming_stable_count < self._stable_frames:
            return

        # Kiem tra hold time
        elapsed = now - self._arming_start_time
        if elapsed >= self._hold_secs:
            # LOCK!
            self.controller_signature = ControllerSignature(
                body_center=person.body_center,
                shoulder_width=person.shoulder_width,
                left_shoulder=person.left_shoulder,
                right_shoulder=person.right_shoulder,
                left_wrist=person.left_wrist,
                right_wrist=person.right_wrist,
                raised_side=person.raised_side,
                last_seen_time=now,
                lock_time=now,
            )
            self._last_seen_time = now
            self.state = STATE_LOCKED
            print(f"[LOCK_MANAGER] ARMING -> LOCKED "
                  f"(hold={elapsed:.1f}s, side={person.raised_side})")

    def _handle_locked(self, person, now):
        """LOCKED: theo doi controller, xu ly mat tam."""
        if person is not None:
            # Kiem tra co phai cung controller
            dist = math.hypot(
                person.body_center[0] - self.controller_signature.body_center[0],
                person.body_center[1] - self.controller_signature.body_center[1],
            )
            if dist < self._match_threshold:
                # Van la controller -> cap nhat signature
                self.controller_signature.body_center = person.body_center
                self.controller_signature.shoulder_width = person.shoulder_width
                self.controller_signature.left_shoulder = person.left_shoulder
                self.controller_signature.right_shoulder = person.right_shoulder
                self.controller_signature.left_wrist = person.left_wrist
                self.controller_signature.right_wrist = person.right_wrist
                self.controller_signature.last_seen_time = now
                self._last_seen_time = now
                return

        # Mat controller (person=None hoac nguoi khac)
        lost_duration = now - self._last_seen_time
        if lost_duration > self._grace_secs:
            print(f"[LOCK_MANAGER] LOCKED -> IDLE "
                  f"(lost for {lost_duration:.1f}s > grace {self._grace_secs}s)")
            self.state = STATE_IDLE
            self.controller_signature = None
            self._reset_arming()

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _reset_arming(self):
        """Reset internal arming state."""
        self._arming_start_time = 0.0
        self._arming_stable_count = 0
        self._arming_body_center = (0.0, 0.0)

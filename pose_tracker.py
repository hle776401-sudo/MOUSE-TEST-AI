"""
pose_tracker.py - MediaPipe Pose Wrapper (Phase 1 Skeleton)
============================================================
Module huong phat trien: Controller Lock bang Pose + Hand-Wrist Association.

Muc dich:
  - Wrapper MediaPipe Pose de phat hien co the nguoi trong khung hinh.
  - Trich xuat landmarks can thiet: shoulder, elbow, wrist, nose.
  - Tinh toan raised hand logic (co tay gio len hay khong).
  - Cung cap PersonPose dataclass cho ControllerLockManager.

Luu y:
  - mp.solutions.pose chi ho tro detect 1 nguoi chinh trong frame.
  - Day KHONG phai multi-person detection.
  - Module nay chi duoc goi khi MULTI_PERSON_CONTROLLER_LOCK_ENABLED = True.
  - Khi flag = False, module nay KHONG duoc import/chay trong pipeline.

Dependency:
  - mediapipe (da co san trong project)
  - opencv-python (da co san)

Trang thai: SKELETON — chua tich hop vao main loop.
"""

import time
import math
from dataclasses import dataclass, field
from typing import Optional

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class PersonPose:
    """Du lieu pose cua 1 nguoi duoc Pose detect.

    Tat ca toa do la normalized [0, 1] theo kich thuoc frame.
    y nho hon = cao hon trong frame (goc toa do top-left).

    Attributes:
        body_center:      Tam co the (trung binh 2 vai), normalized.
        shoulder_width:   Khoang cach 2 vai, normalized.
        left_shoulder:    Toa do vai trai, normalized (x, y).
        right_shoulder:   Toa do vai phai, normalized (x, y).
        left_elbow:       Toa do khuyu tay trai, normalized (x, y).
        right_elbow:      Toa do khuyu tay phai, normalized (x, y).
        left_wrist:       Toa do co tay trai, normalized (x, y).
        right_wrist:      Toa do co tay phai, normalized (x, y).
        nose:             Toa do mui, normalized (x, y).
        visibility:       Dict visibility score cho tung landmark.
        is_raising_hand:  True neu dang gio tay (it nhat 1 ben).
        raised_side:      "left" / "right" / "both" / "none".
        timestamp:        time.time() khi detect.
    """
    body_center: tuple = (0.0, 0.0)
    shoulder_width: float = 0.0
    left_shoulder: tuple = (0.0, 0.0)
    right_shoulder: tuple = (0.0, 0.0)
    left_elbow: tuple = (0.0, 0.0)
    right_elbow: tuple = (0.0, 0.0)
    left_wrist: tuple = (0.0, 0.0)
    right_wrist: tuple = (0.0, 0.0)
    nose: tuple = (0.0, 0.0)
    visibility: dict = field(default_factory=dict)
    is_raising_hand: bool = False
    raised_side: str = "none"
    timestamp: float = 0.0


# ==============================================================================
# POSE TRACKER
# ==============================================================================

class PoseTracker:
    """Wrapper MediaPipe Pose — phat hien co the va kiem tra tay gio.

    Chi ho tro 1 nguoi chinh trong frame (gioi han cua mp.solutions.pose).
    Thiet ke de phuc vu Controller Lock (Phase 1 skeleton).

    Cach dung:
        tracker = PoseTracker()
        person = tracker.process(frame)
        if person and person.is_raising_hand:
            ...

    An toan:
        - Neu mediapipe khong import duoc: process() tra None, khong crash.
        - Neu Pose init loi: _pose_ready = False, process() tra None.
    """

    def __init__(self,
                 model_complexity: int = 0,
                 min_detection_confidence: float = 0.6,
                 min_tracking_confidence: float = 0.5,
                 visibility_threshold: float = 0.7):
        """Khoi tao PoseTracker.

        Args:
            model_complexity: 0 = lite (nhanh), 1 = full (chinh xac hon).
            min_detection_confidence: Nguong detection (0.0 - 1.0).
            min_tracking_confidence: Nguong tracking (0.0 - 1.0).
            visibility_threshold: Nguong visibility toi thieu de coi
                                  landmark la hop le.
        """
        self._pose_ready = False
        self._pose = None
        self._visibility_threshold = visibility_threshold

        if not _MP_AVAILABLE:
            print("[POSE_TRACKER] WARNING: mediapipe not available, "
                  "PoseTracker disabled")
            return

        try:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=model_complexity,
                smooth_landmarks=True,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self._pose_ready = True
            print(f"[POSE_TRACKER] Initialized (complexity={model_complexity}, "
                  f"det={min_detection_confidence}, "
                  f"track={min_tracking_confidence})")
        except Exception as e:
            print(f"[POSE_TRACKER] ERROR: Failed to init Pose: {e}")
            self._pose_ready = False

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def process(self, frame) -> Optional[PersonPose]:
        """Xu ly 1 frame va tra ve PersonPose neu detect duoc.

        Args:
            frame: Frame BGR tu OpenCV (numpy array, da flip).

        Returns:
            PersonPose neu detect duoc nguoi, None neu khong.
        """
        if not self._pose_ready or not _NP_AVAILABLE:
            return None

        try:
            import cv2
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_rgb.flags.writeable = False
            results = self._pose.process(frame_rgb)
            frame_rgb.flags.writeable = True
        except Exception as e:
            print(f"[POSE_TRACKER] Process error: {e}")
            return None

        if not results.pose_landmarks:
            return None

        return self._extract_person(results.pose_landmarks)

    def release(self):
        """Giai phong tai nguyen MediaPipe Pose."""
        if self._pose is not None:
            try:
                self._pose.close()
            except Exception:
                pass
            self._pose = None
            self._pose_ready = False

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _extract_person(self, pose_landmarks) -> PersonPose:
        """Trich xuat PersonPose tu MediaPipe Pose landmarks.

        MediaPipe Pose landmark indices:
            0  = NOSE
            11 = LEFT_SHOULDER
            12 = RIGHT_SHOULDER
            13 = LEFT_ELBOW
            14 = RIGHT_ELBOW
            15 = LEFT_WRIST
            16 = RIGHT_WRIST
        """
        lm = pose_landmarks.landmark

        # Extract toa do va visibility
        nose = (lm[0].x, lm[0].y)
        l_shoulder = (lm[11].x, lm[11].y)
        r_shoulder = (lm[12].x, lm[12].y)
        l_elbow = (lm[13].x, lm[13].y)
        r_elbow = (lm[14].x, lm[14].y)
        l_wrist = (lm[15].x, lm[15].y)
        r_wrist = (lm[16].x, lm[16].y)

        vis = {
            "nose": lm[0].visibility,
            "left_shoulder": lm[11].visibility,
            "right_shoulder": lm[12].visibility,
            "left_elbow": lm[13].visibility,
            "right_elbow": lm[14].visibility,
            "left_wrist": lm[15].visibility,
            "right_wrist": lm[16].visibility,
        }

        # Body center = trung binh 2 vai
        body_center = (
            (l_shoulder[0] + r_shoulder[0]) / 2.0,
            (l_shoulder[1] + r_shoulder[1]) / 2.0,
        )

        # Shoulder width (Euclidean, normalized)
        shoulder_width = math.hypot(
            l_shoulder[0] - r_shoulder[0],
            l_shoulder[1] - r_shoulder[1],
        )

        # Raised hand detection
        left_raised = self._is_hand_raised(
            shoulder=lm[11], elbow=lm[13], wrist=lm[15])
        right_raised = self._is_hand_raised(
            shoulder=lm[12], elbow=lm[14], wrist=lm[16])

        if left_raised and right_raised:
            raised_side = "both"
        elif left_raised:
            raised_side = "left"
        elif right_raised:
            raised_side = "right"
        else:
            raised_side = "none"

        return PersonPose(
            body_center=body_center,
            shoulder_width=shoulder_width,
            left_shoulder=l_shoulder,
            right_shoulder=r_shoulder,
            left_elbow=l_elbow,
            right_elbow=r_elbow,
            left_wrist=l_wrist,
            right_wrist=r_wrist,
            nose=nose,
            visibility=vis,
            is_raising_hand=(raised_side != "none"),
            raised_side=raised_side,
            timestamp=time.time(),
        )

    def _is_hand_raised(self, shoulder, elbow, wrist) -> bool:
        """Kiem tra 1 ben tay co dang gio len khong.

        Dieu kien:
            1. Visibility cua ca 3 landmark >= threshold.
            2. wrist.y < shoulder.y (co tay cao hon vai).
            3. elbow.y < shoulder.y (khuyu tay cung phai nang,
               tranh nhan tay dat tren ban phia truoc).

        Trong image coords: y nho hon = cao hon.

        Args:
            shoulder: MediaPipe landmark (co .x, .y, .visibility).
            elbow:    MediaPipe landmark.
            wrist:    MediaPipe landmark.

        Returns:
            True neu tay dang gio len.
        """
        vt = self._visibility_threshold
        if (shoulder.visibility < vt or
                elbow.visibility < vt or
                wrist.visibility < vt):
            return False

        return (wrist.y < shoulder.y) and (elbow.y < shoulder.y)

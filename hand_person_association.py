"""
hand_person_association.py - Hand-Person Wrist Matching (Phase 1 Skeleton)
==========================================================================
Module huong phat trien: Ghep ban tay (MediaPipe Hands) voi nguoi da khoa
(MediaPipe Pose) bang khoang cach wrist.

Muc dich:
  - Nhan list all_hands tu get_all_hands_data().
  - Nhan ControllerSignature tu ControllerLockManager.
  - So khop wrist position cua tung ban tay voi wrist cua controller.
  - Chi giu lai ban tay co wrist gan controller (< threshold pixel).
  - Tra ve filtered_hands (max 2) de tiep tuc vao Hand Assignment binh thuong.

Luu y:
  - Module nay chi duoc goi khi MULTI_PERSON_CONTROLLER_LOCK_ENABLED = True
    VA ControllerLockManager.state == LOCKED.
  - Khi flag = False, module nay KHONG chay trong pipeline.
  - Khong sua doi all_hands, chi loc va tra ve list moi.
  - Khong anh huong primary/secondary hand assignment.

Trang thai: SKELETON — chua tich hop vao main loop.
"""

import math
from typing import Optional

try:
    from controller_lock_manager import ControllerSignature
except ImportError:
    ControllerSignature = None


# ==============================================================================
# HAND-PERSON ASSOCIATION
# ==============================================================================

class HandPersonAssociation:
    """Loc ban tay chi giu nhung tay thuoc controller da khoa.

    Nguyen ly:
        MediaPipe Hands tra hand_landmarks[0] = wrist (pixel coords).
        ControllerSignature luu left_wrist / right_wrist (normalized coords).
        Chuyen normalized -> pixel roi tinh Euclidean distance.
        Neu distance < threshold -> tay thuoc controller.
        Neu distance >= threshold -> tay nguoi khac, bo qua.

    Cach dung:
        assoc = HandPersonAssociation(threshold_px=80)
        filtered = assoc.filter(all_hands, controller_sig, frame_shape)
        # filtered chi chua tay thuoc controller (max 2)

    An toan:
        - Neu controller_sig la None: tra [].
        - Neu all_hands rong: tra [].
        - Neu loi: tra all_hands goc (fallback an toan).
    """

    def __init__(self, threshold_px: int = 80):
        """Khoi tao HandPersonAssociation.

        Args:
            threshold_px: Khoang cach toi da (pixel) giua hand wrist
                          va pose wrist de coi la cung 1 nguoi.
                          Default 80px (do voi 640x480 frame).
        """
        self._threshold = threshold_px

    def filter(self,
               all_hands: list,
               controller_sig: Optional['ControllerSignature'],
               frame_shape: tuple) -> list:
        """Loc all_hands chi giu tay thuoc controller.

        Args:
            all_hands:      List[dict] tu get_all_hands_data().
                            Moi dict co key "landmarks": [(id, x_px, y_px), ...].
            controller_sig: ControllerSignature tu ControllerLockManager.
                            None neu chua lock.
            frame_shape:    (height, width, channels) cua frame hien tai.

        Returns:
            List[dict]: Chi chua tay khop voi controller (max 2).
                        Rong neu controller_sig=None hoac khong match.
        """
        if controller_sig is None:
            return []

        if not all_hands:
            return []

        try:
            h, w = frame_shape[0], frame_shape[1]
            filtered = []

            # Controller wrist positions: normalized -> pixel
            ctrl_wrists_px = [
                (controller_sig.left_wrist[0] * w,
                 controller_sig.left_wrist[1] * h),
                (controller_sig.right_wrist[0] * w,
                 controller_sig.right_wrist[1] * h),
            ]

            for hand in all_hands:
                landmarks = hand.get("landmarks", [])
                if not landmarks or len(landmarks) < 1:
                    continue

                # hand_landmarks[0] = wrist = (id, x_pixel, y_pixel)
                hand_wrist_px = (landmarks[0][1], landmarks[0][2])

                # Check distance voi ca 2 wrist cua controller
                matched = False
                min_dist = float("inf")
                for ctrl_wrist in ctrl_wrists_px:
                    dist = math.hypot(
                        hand_wrist_px[0] - ctrl_wrist[0],
                        hand_wrist_px[1] - ctrl_wrist[1],
                    )
                    min_dist = min(min_dist, dist)
                    if dist < self._threshold:
                        matched = True
                        break

                if matched:
                    filtered.append(hand)
                # else: tay nguoi khac, bo qua (khong log de tranh spam)

            return filtered[:2]  # Max 2 tay (primary + secondary)

        except Exception as e:
            print(f"[HAND_ASSOC] Error in filter: {e}")
            # Fallback an toan: tra all_hands goc
            return all_hands

"""
Test nhanh: xac dinh MediaPipe tra handedness gi cho moi tay.
Huong dan:
  1. Chay script nay
  2. Giơ tay PHAI truoc camera -> doc dong "HAND 0: label=..."
  3. Giơ tay TRAI truoc camera -> doc dong "HAND 0: label=..."
  4. Giơ 2 tay -> doc ca 2 dong
  5. Nhan 'q' de thoat
  6. Bao ket qua cho toi
"""
import cv2
import mediapipe as mp

cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

hands = mp.solutions.hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

print("=" * 50)
print("HANDEDNESS TEST")
print("Giơ tay truoc camera, doc label tren console")
print("Nhan 'q' de thoat")
print("=" * 50)

while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks and results.multi_handedness:
        for i, (hand_lm, hand_cls) in enumerate(
            zip(results.multi_hand_landmarks, results.multi_handedness)
        ):
            label = hand_cls.classification[0].label
            score = hand_cls.classification[0].score

            # Ve text len frame
            h, w, _ = frame.shape
            cx = int(hand_lm.landmark[9].x * w)
            cy = int(hand_lm.landmark[9].y * h)

            text = f"HAND {i}: MP={label} ({score:.2f})"
            cv2.putText(frame, text, (cx - 80, cy - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            print(text)

    cv2.imshow("Handedness Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\nDone. Bao ket qua:")
print("  Tay PHAI cua ban -> MP tra label gi?")
print("  Tay TRAI cua ban -> MP tra label gi?")

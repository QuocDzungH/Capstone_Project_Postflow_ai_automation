from ultralytics import YOLO
import cv2
import numpy as np


class HandDetector:

    def __init__(self, model_path, conf=0.3):

        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, image):

        results = self.model.predict(
            source=image,
            conf=self.conf,
            verbose=False
        )

        result = results[0]

        hands = []

        if result.boxes is None:
            return hands

        for i, box in enumerate(result.boxes):

            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            hand = {
                "box": (
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2)
                ),
                "confidence": float(box.conf[0])
            }

            # Lấy keypoints nếu model có keypoints
            if result.keypoints is not None:

                keypoints = result.keypoints.xy[i].cpu().numpy()

                hand["keypoints"] = keypoints

            else:

                hand["keypoints"] = None

            hands.append(hand)

        return hands

    def draw(self, image, hands):

        result = image.copy()

        for hand in hands:

            x1, y1, x2, y2 = hand["box"]
            confidence = hand["confidence"]

            cv2.rectangle(
                result,
                (x1, y1),
                (x2, y2),
                (255, 0, 255),
                2
            )

            cv2.putText(
                result,
                f"hand {confidence:.2f}",
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 255),
                2
            )

            keypoints = hand["keypoints"]

            if keypoints is not None:

                for x, y in keypoints:

                    if x > 0 and y > 0:

                        cv2.circle(
                            result,
                            (int(x), int(y)),
                            4,
                            (0, 255, 0),
                            -1
                        )

        return result

    def remove_hands(self, image, hands):

        result = image.copy()

        mask = np.zeros(
            image.shape[:2],
            dtype=np.uint8
        )

        for hand in hands:

            x1, y1, x2, y2 = hand["box"]

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)

            mask[y1:y2, x1:x2] = 255

        result[mask == 255] = 0

        return result
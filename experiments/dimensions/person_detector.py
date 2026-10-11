from ultralytics import YOLO
import cv2
import numpy as np


class PersonDetector:

    def __init__(self, model_path, conf=0.4):

        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, image):

        results = self.model.predict(
            source=image,
            conf=self.conf,
            verbose=False
        )

        result = results[0]

        person_boxes = []

        if result.boxes is None:
            return person_boxes

        for box in result.boxes:

            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])

            class_name = self.model.names[cls_id]

            # Chỉ lấy class person
            if class_name != "person":
                continue

            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            person_boxes.append({
                "box": (
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2)
                ),
                "confidence": confidence
            })

        return person_boxes

    def remove_person(self, image, person_boxes):

        result = image.copy()

        mask = np.zeros(
            image.shape[:2],
            dtype=np.uint8
        )

        for person in person_boxes:

            x1, y1, x2, y2 = person["box"]

            # Giới hạn tọa độ trong ảnh
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)

            mask[y1:y2, x1:x2] = 255

        # Xóa vùng người bằng màu đen
        result[mask == 255] = 0

        return result

    def draw_boxes(self, image, person_boxes):

        result = image.copy()

        for person in person_boxes:

            x1, y1, x2, y2 = person["box"]
            confidence = person["confidence"]

            cv2.rectangle(
                result,
                (x1, y1),
                (x2, y2),
                (0, 255, 255),
                2
            )

            cv2.putText(
                result,
                f"person {confidence:.2f}",
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )

        return result
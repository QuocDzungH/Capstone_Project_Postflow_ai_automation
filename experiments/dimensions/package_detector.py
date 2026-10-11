from ultralytics import YOLO
import cv2


class PackageDetector:

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

        packages = []

        if result.boxes is None:
            return packages

        for box in result.boxes:

            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            packages.append({
                "box": (
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2)
                ),
                "confidence": float(box.conf[0])
            })

        return packages

    def draw(self, image, packages):

        result = image.copy()

        for package in packages:

            x1, y1, x2, y2 = package["box"]
            confidence = package["confidence"]

            cv2.rectangle(
                result,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                result,
                f"package {confidence:.2f}",
                (x1, max(25, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        return result

    def get_largest_package(self, packages):

        if not packages:
            return None

        return max(
            packages,
            key=lambda p:
                (p["box"][2] - p["box"][0])
                * (p["box"][3] - p["box"][1])
        )
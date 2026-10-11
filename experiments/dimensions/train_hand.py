from ultralytics import YOLO


def main():
    model = YOLO("yolo26n-pose.pt")

    model.train(
        data="hand-keypoints.yaml",
        epochs=100,
        imgsz=640,
        batch=16,
        device=0,
        workers=0
    )


if __name__ == "__main__":
    main()
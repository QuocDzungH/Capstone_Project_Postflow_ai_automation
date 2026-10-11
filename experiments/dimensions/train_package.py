from ultralytics import YOLO


def main():

    # YOLO26n pretrained
    model = YOLO("yolo26n.pt")

    # Fine-tune trên dataset Cardboard Box
    model.train(
        data=r"datasets\cardboard-box\data.yaml",

        epochs=100,
        imgsz=640,

        # RTX 3050 4 GB
        batch=16,
        device=0,

        # Windows
        workers=0,

        # Lưu kết quả
        project="runs\package",
        name="box_train",

        # Lưu checkpoint tốt nhất
        save=True,

        # Dừng sớm nếu validation không cải thiện
        patience=20
    )


if __name__ == "__main__":
    main()
from ultralytics import YOLO

if __name__ == "__main__":
    # Đường dẫn đến weights best.pt vừa train xong
    model_path = r"runs/detect/runs/detect/box_envelope_model/weights/best.pt"
    
    # Nạp mô hình
    model = YOLO(model_path)

    # Đánh giá trên tập test để tính precision, recall và mAP
    metrics = model.val(
        data="dataset/data.yaml",
        split="test",
        project="runs/detect",
        name="test_metrics",
        exist_ok=True
    )

    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall:    {metrics.box.mr:.4f}")
    print(f"mAP50:     {metrics.box.map50:.4f}")
    print(f"mAP50-95:  {metrics.box.map:.4f}")

    # Chạy dự đoán trên tập ảnh test
    results = model.predict(
        source="dataset/test/images",  # Đường dẫn thư mục ảnh test (hoặc đường dẫn 1 ảnh lẻ)
        conf=0.8,                      # Ngưỡng tin cậy (chỉ hiện ô vuông nếu conf >= 40%)
        save=True,                     # Tự động vẽ bounding box và lưu ảnh kết quả
        project="runs/predict",        # Thư mục chứa kết quả dự đoán
        name="test_results",           # Tên thư mục con
        exist_ok=True
    )

    print("--> Hoàn tất! Kết quả ảnh đã vẽ khung được lưu tại: runs/predict/test_results")
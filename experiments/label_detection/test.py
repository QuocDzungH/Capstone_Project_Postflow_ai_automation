from ultralytics import YOLO

def main():
    # 1. Load weights tốt nhất vừa train xong
    model = YOLO('runs/detect/yolo11_stage2_info-5/weights/best.pt')

    metrics = model.val(
        data='stage2_dataset/data_stage2.yaml',
        split='test',
        imgsz=640,
        conf=0.25,
        plots=True,
        workers=0
    )

    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall: {metrics.box.mr:.4f}")

    # Chạy predict để lưu ảnh minh họa và tọa độ detect
    # Có thể truyền đường dẫn 1 ảnh ('test.jpg') hoặc cả folder ('stage2_dataset/test/images')
    model.predict(
        source='stage2_dataset/test/images', # Thay bằng đường dẫn ảnh/folder bạn muốn test
        conf=0.8,                           # Ngưỡng độ tin cậy (Confidence threshold)
        save=True,                           # Tự động vẽ frame và lưu ảnh kết quả
        save_txt=True                        # Lưu tọa độ detect ra file txt (nếu cần)
    )

    print("🎉 Đã test xong! Ảnh kết quả nằm trong thư mục: runs/detect/predict/")


if __name__ == '__main__':
    main()
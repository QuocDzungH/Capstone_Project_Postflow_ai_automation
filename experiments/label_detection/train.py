from ultralytics import YOLO

if __name__ == '__main__':
    # Load weights gốc của YOLO11 (bản nano yolo11n.pt gọn nhẹ nhất)
    model = YOLO('yolo11n.pt') 

    # Tiến hành train
    results = model.train(
        data='stage2_dataset/data_stage2.yaml',
        epochs=50,                  # Số epoch (tùy chỉnh từ 30-100)
        imgsz=640,                  # Kích thước ảnh đầu vào
        batch=16,                   # Giảm xuống 8 hoặc 4 nếu bị tràn VRAM GPU
        name='yolo11_stage2_info',  # Tên folder lưu kết quả trong runs/detect/
        device='0',               # Đổi thành 0 khi máy đã cài PyTorch có CUDA
        workers=4
    )

    print("🎉 Hoàn tất huấn luyện!")
    print("Weight tốt nhất lưu tại: runs/detect/yolo11_stage2_info/weights/best.pt")
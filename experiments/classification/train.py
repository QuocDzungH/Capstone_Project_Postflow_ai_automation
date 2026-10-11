import os
from ultralytics import YOLO

if __name__ == "__main__":
    # 1. Tải trọng số pre-trained YOLO11 (bản nano)
    model = YOLO("yolo11n.pt")

    # 2. Bắt đầu huấn luyện
    model.train(
        data="dataset/data.yaml",     # Đường dẫn tới file config dữ liệu
        classes=[0, 1],
        epochs=50,                   # Cho mô hình đủ thời gian hội tụ
        patience=30,                  # Dừng sớm nếu validation không cải thiện
        imgsz=640,                    # Kích thước ảnh chuẩn hóa
        batch=16,                     # Kích thước batch (giảm xuống 8 hoặc 4 nếu thiếu VRAM)
        device=0,                     # Dùng GPU NVIDIA (id=0). Đổi thành 'cpu' nếu không có GPU
        workers=2,                    # Số luồng nạp dữ liệu
        project="runs/detect",        # Thư mục gốc lưu kết quả
        name="box_envelope_model",    # Tên thư mục lưu model lần train này
        exist_ok=True                 # Cho phép ghi đè nếu chạy lại
    )
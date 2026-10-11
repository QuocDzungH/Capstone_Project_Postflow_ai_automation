# Mã thử nghiệm gốc

Thư mục này giữ các script huấn luyện/suy luận của nhóm để đối chiếu phương pháp với báo cáo. Chúng không thuộc luồng demo nhẹ và chưa được chạy lại khi đóng gói.

| Thư mục | Nội dung | Phụ thuộc ngoài repository |
| --- | --- | --- |
| `classification/` | YOLO phân biệt bưu kiện/phong bì | Dataset gốc, weights; cấu hình GPU trong script |
| `label_detection/` | Crop vùng bưu kiện và YOLO vùng thông tin | Dataset gốc/stage2, weights; cấu hình GPU |
| `dimensions/` | Đo webcam, phát hiện tay/vật thể và xử lý cạnh | Camera, weights và YAML dataset huấn luyện tay/bưu kiện |
| `training-records/` | CSV kết quả và YAML tham số đã lưu | Dùng làm log thí nghiệm; không phải kết quả chạy lại |

Đọc script trước khi huấn luyện; đường dẫn và `device=0` phản ánh môi trường của đồ án. YAML dataset có thể cần điều chỉnh về thư mục local. Khôi phục ảnh và label từ bộ dữ liệu gốc của nhóm, rồi đặt đúng đường dẫn được khai báo trong từng script. Không có lệnh tái huấn luyện toàn bộ hệ thống trong bản portfolio này.

Hiệu chuẩn cảm biến là phần có dữ liệu đầy đủ để chạy lại riêng: [hardware/calibration](../hardware/calibration/README.md).

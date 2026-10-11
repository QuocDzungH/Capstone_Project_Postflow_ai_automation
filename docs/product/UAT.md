# Tiêu chí nghiệm thu và liên kết bằng chứng

Các ca dưới đây là đặc tả nghiệm thu được hệ thống hóa từ phạm vi MVP. Cột bằng chứng cho biết ca đã được kiểm tra trong bản portfolio hay còn cần môi trường bổ sung.

| ID | Yêu cầu | Given / When | Then | Bằng chứng |
| --- | --- | --- | --- | --- |
| AC-01 | FR-01, FR-05 | Có thông tin giả lập hợp lệ; nhân viên thực hiện luồng nhập tay | Có cước, mã đơn PAID và barcode | Kiểm tra Edge headless; screenshot trong `media/` |
| AC-02 | FR-04, BR-02 | ETN011, Hà Nội–Đà Nẵng, 2,2 kg, 50×20×20 cm | Dùng 2,2 kg; cước 72.000 VND theo JSON | `test_real_weight_when_all_sides_are_at_most_50cm` |
| AC-03 | FR-04, BR-03 | ETN011, Hà Nội–Đà Nẵng, 1 kg, 60×40×30 cm | Dùng 12 kg; cước 252.500 VND theo JSON | `test_volumetric_weight_when_any_side_is_over_50cm` |
| AC-04 | FR-06, BR-01 | Gửi số đo âm tới API tính cước | Trả lỗi 422, không báo cước | `test_invalid_measurement_and_unknown_order` |
| AC-05 | FR-04, BR-04 | Tỉnh/thành không có trong cấu hình | Từ chối tính cước và nêu lỗi | `test_unknown_province_is_rejected` |
| AC-06 | FR-05, BR-06 | Đơn đang WAITING_FOR_MEASUREMENT; gọi xác nhận mô phỏng | Trả 409, không lưu đơn PAID | `test_order_is_saved_after_simulated_payment` |
| AC-07 | FR-07 | Đơn đã có số đo; xác nhận mô phỏng | Lưu SQLite, tra được mã, trả ảnh barcode | `test_order_is_saved_after_simulated_payment` |
| AC-08 | FR-05 | Người xem mở QR demo | Nhận PNG chứa payload mô phỏng; không cần ảnh tài khoản riêng | `test_simulation_qr_can_be_generated_without_private_image` |
| AC-09 | FR-03 | ESP32 ở cùng mạng, ba sensor hợp lệ | Đọc được số đo cm và thể tích; đối chiếu thước chuẩn | Cần phần cứng; chưa chạy lại khi đóng gói |
| AC-10 | FR-03, FR-06 | ESP32 thiếu Echo/timeout/số đo ngoài miền | Thông báo lỗi, cho đo lại/nhập tay, không tự dùng số đo bất thường | Cần UAT; kiểm tra miền đo là backlog |
| AC-11 | FR-02 | OCR gợi ý sai tên/địa chỉ | Nhân viên sửa được trước khi lập đơn | Cần model/API và tập dữ liệu UAT |
| AC-12 | FR-07 | API khởi động lại khi đơn còn đang xử lý | Khôi phục đơn draft | Chưa hỗ trợ; backlog US-06 |

## Thực hiện demo UAT

1. Chạy ứng dụng theo [SETUP](../SETUP.md).
2. Điền thông tin giả lập; chọn ETN011, Hà Nội → Đà Nẵng.
3. Nhập 2,2 kg, 50×20×20 cm; kiểm tra mức 72.000 VND.
4. Chọn một phương thức thanh toán mô phỏng và xác nhận.
5. Kiểm tra mã vận đơn, barcode và khả năng tra đơn qua API.

Ảnh demo: [review cước](../../media/kiosk-quote.png), [QR](../../media/kiosk-qr.png), [hoàn tất](../../media/kiosk-complete.png). Kết quả kiểm thử và giới hạn môi trường nằm trong [VERIFICATION](../VERIFICATION.md).

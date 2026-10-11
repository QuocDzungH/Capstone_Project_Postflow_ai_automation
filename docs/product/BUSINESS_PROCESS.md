# Quy trình nghiệp vụ

Sơ đồ được hệ thống hóa từ chương 4 của báo cáo và luồng đang có trong ứng dụng.

## As-is: tiếp nhận thủ công

```mermaid
flowchart TD
    A[Khách cung cấp bưu gửi và thông tin] --> B[Nhân viên đọc và nhập thông tin]
    B --> C[Phân loại bưu gửi]
    C --> D[Cân và đo kích thước]
    D --> E[Tra tuyến và bảng cước]
    E --> F[Thông báo cước và xác nhận]
    F --> G[Cấp mã vận đơn]
```

Các điểm cần hỗ trợ là nhập lại thông tin, đo lặp và tra cước. Sai số đầu vào có thể truyền sang khối lượng quy đổi hoặc mức giá.

## To-be: tiếp nhận có hỗ trợ

```mermaid
flowchart TD
    A[Ảnh bưu gửi hoặc nhập tay] --> B[Phân loại và OCR nếu sẵn sàng]
    B --> C[Nhân viên xác nhận hoặc sửa thông tin]
    C --> D{Cần số đo hàng hóa?}
    D -->|Có| E[Camera hoặc cảm biến ESP32]
    E --> F{Số đo hợp lệ?}
    F -->|Không| G[Đo lại hoặc nhập tay]
    F -->|Có| H[Nhân viên xác nhận số đo và cân nặng]
    G --> H
    D -->|Thư theo cấu hình demo| I[Giá trị mặc định của luồng LETTER]
    H --> J[Tính tuyến và cước]
    I --> J
    J --> K[Xem cước và xác nhận mô phỏng]
    K --> L[Lưu đơn hoàn tất và tạo barcode]
```

Nhánh kiểm tra độ hợp lệ của phép đo là tiêu chí nghiệp vụ cho pilot. Demo nhập tay đã có kiểm tra số dương; khả năng chặn đầy đủ mọi số đo tự động cần UAT với phần cứng.

## Trạng thái đơn trong API

```mermaid
stateDiagram-v2
    [*] --> WAITING_FOR_MEASUREMENT: POST /orders
    WAITING_FOR_MEASUREMENT --> WAITING_FOR_PAYMENT: POST /orders/{code}/measurements
    WAITING_FOR_PAYMENT --> PAID: POST /orders/{code}/mock-payment
    PAID --> [*]: Lưu DB và sinh barcode
```

Giao diện thu thập thông tin và báo cước trước, rồi gọi ba API trên khi người dùng hoàn tất bước xác nhận. Đơn chưa thanh toán chỉ nằm trong bộ nhớ của tiến trình; đơn PAID được lưu trong DB. Khôi phục đơn dang dở là hạng mục backlog.

## Điểm xử lý ngoại lệ

| Sự kiện | Hành vi cần thiết | Tình trạng |
| --- | --- | --- |
| OCR sai hoặc không khả dụng | Nhân viên sửa/nhập tay | Form hỗ trợ; OCR cần môi trường đầy đủ |
| Cảm biến timeout hoặc thiếu Echo | Báo lỗi và cho đo lại/nhập tay | Có xử lý trong mã cảm biến; cần kiểm tra thiết bị |
| Không có tỉnh/thành hoặc dịch vụ trong cấu hình | Không báo cước; trả lỗi để sửa | Có kiểm tra |
| Thiếu số đo hoặc số đo âm/0 | Không tính cước | API nhập tay có kiểm tra |
| Xác nhận thanh toán trước có số đo/cước | Không chuyển đơn sang PAID | Kiểm thử trả 409 |
| API khởi động lại lúc đang xử lý | Có thể mất đơn chưa PAID | Hạn chế hiện tại; đề xuất lưu draft |

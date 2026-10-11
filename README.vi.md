# PostFlow — Hỗ trợ tự động hóa tiếp nhận bưu gửi

**Đồ án tốt nghiệp FPT University, 2026 · Portfolio ứng tuyển PO/PM**

PostFlow hỗ trợ quy trình nhập thông tin bưu gửi, đo kích thước, tính cước và tạo mã vận đơn. Dự án kết hợp giao diện kiosk, API Python, xử lý ảnh/OCR và cảm biến ESP32.

**Đóng góp cá nhân của chủ repository:** phân tích nghiệp vụ, xây dựng luồng tiếp nhận bưu gửi và phát triển phần cảm biến ESP32, bao gồm thu thập dữ liệu và hiệu chuẩn. Các mô hình AI và hệ thống tổng thể được giới thiệu là sản phẩm của nhóm.

## Lộ trình đọc cho nhà tuyển dụng

1. [Case study PO/PM](docs/product/CASE_STUDY.md): bài toán, người dùng, lựa chọn giải pháp và đánh giá kết quả.
2. [PRD](docs/product/PRD.md): phạm vi MVP, yêu cầu chức năng và quy tắc nghiệp vụ.
3. [Quy trình nghiệp vụ](docs/product/BUSINESS_PROCESS.md): As-is, To-be và trạng thái đơn.
4. [Backlog](docs/product/BACKLOG.md) và [UAT](docs/product/UAT.md): thứ tự ưu tiên đề xuất, tiêu chí nghiệm thu và liên kết đến mã nguồn.
5. [Phần cảm biến](hardware/README.md), [báo cáo](docs/reports/Final_Report.pdf) và [slide](docs/reports/Presentation_Final.pdf): bằng chứng kỹ thuật.

Các tài liệu sản phẩm được hệ thống hóa từ tài liệu và mã nguồn của đồ án khi chuẩn bị portfolio. Backlog và lộ trình là đề xuất hiện tại.

## Điểm nổi bật

- Demo chạy bằng SQLite, hỗ trợ nhập tay → tính cước → thanh toán mô phỏng → tạo mã vận đơn.
- Cảm biến đọc ba chiều của bưu kiện qua ESP32; có bù nhiệt độ, API HTTP và hiệu chuẩn bằng hồi quy tuyến tính.
- Trên 900 mẫu kiểm thử hiệu chuẩn, MAE của CB1 giảm từ **0,9372 xuống 0,2363 cm**, tương ứng khoảng **74,79%**. Xem [dữ liệu và cách chạy lại](hardware/calibration/README.md).
- README có ảnh demo dùng thông tin giả lập; mã nguồn, báo cáo và slide được chia thành các thư mục dễ xem.

## Chạy demo trên Windows

Trong thư mục repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Mở `http://127.0.0.1:8000`. Chọn nhập tay để thử luồng cơ bản. OCR và đo tự động cần model hoặc phần cứng; QR trong demo không chuyển tiền.

[Hướng dẫn đầy đủ](docs/SETUP.md) · [Nội dung dùng cho CV](docs/CV.md) · [Cách push GitHub](docs/PUBLISH.md) · [Đóng góp cá nhân](docs/CONTRIBUTIONS.md).

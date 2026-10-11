# Nội dung đưa vào CV và phỏng vấn

## Bản tiếng Việt

**PostFlow — Hệ thống hỗ trợ tiếp nhận bưu gửi tích hợp AI**  
Đồ án tốt nghiệp nhóm · FPT University · 2026  
Vai trò: **Phân tích nghiệp vụ, thiết kế luồng sản phẩm và phát triển cảm biến ESP32**

- Phân tích quy trình tiếp nhận bưu gửi và xác định luồng hỗ trợ từ nhập thông tin người gửi/nhận, đo kích thước đến tính cước và tạo mã vận đơn.
- Làm rõ yêu cầu nghiệp vụ và quy tắc tính cước; trình bày phạm vi MVP, luồng xử lý ngoại lệ và tiêu chí nghiệm thu trong portfolio sản phẩm.
- Phát triển hệ thống đo bằng ESP32 và ba cảm biến siêu âm, tích hợp bù nhiệt độ và cung cấp dữ liệu đo qua HTTP API.
- Hiệu chuẩn cảm biến bằng hồi quy tuyến tính; giảm MAE của CB1 từ **0,9372 xuống 0,2363 cm (~74,79%)** trên **900 mẫu kiểm thử** trong thí nghiệm hiệu chuẩn.

**Công nghệ:** ESP32, cảm biến siêu âm, Python, Linear Regression; hệ thống nhóm sử dụng FastAPI, YOLO, TrOCR/EasyOCR và giao diện HTML/JavaScript.

Khi đặt lên CV, gắn tên dự án với URL GitHub của repository sau khi push. Có thể rút còn ba bullet đầu nếu CV cần ưu tiên nghiệp vụ hơn kỹ thuật.

## English version

**PostFlow — AI-Assisted Postal Acceptance System**  
Team capstone project · FPT University · 2026  
Role: **Business Analysis, Product Workflow Design & ESP32 Development**

- Analyzed the postal acceptance workflow and defined an assisted flow covering sender/receiver information, parcel measurement, tariff calculation and tracking-code generation.
- Clarified business rules and documented MVP scope, exception flows and acceptance criteria in a product portfolio.
- Developed an ESP32 subsystem with three ultrasonic sensors, temperature compensation and an HTTP measurement API.
- Applied linear regression calibration, reducing CB1 distance MAE from **0.9372 to 0.2363 cm (~74.79%)** on **900 held-out test measurements**.

## Cách kể dự án khi phỏng vấn

1. **Vấn đề:** nhiều thao tác nhập liệu, đo và tra cước tại quầy; sai số đầu vào có thể ảnh hưởng cước.
2. **Vai trò cá nhân:** phân tích nghiệp vụ và phần cảm biến; giải thích ranh giới với các module AI của nhóm.
3. **Quyết định:** giữ bước xác nhận của nhân viên và khả năng nhập tay; cân nhắc camera với cụm cảm biến theo chi phí, điều kiện lắp đặt và sai số.
4. **Bằng chứng:** quy trình, quy tắc nghiệp vụ, demo và kết quả hiệu chuẩn có thể chạy lại.
5. **Bước tiếp theo:** thử nghiệm tại quầy, đo thời gian thao tác và tỷ lệ chỉnh sửa trước khi kết luận hiệu quả vận hành.

Mức giảm sai số cảm biến là kết quả thí nghiệm. Thời gian phục vụ, tỷ lệ lỗi nhập liệu và doanh thu chưa được đo trong pilot thực tế, nên không dùng làm thành tích định lượng trên CV.

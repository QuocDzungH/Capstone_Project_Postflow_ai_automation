# Backlog và roadmap đề xuất

Đây là backlog được sắp xếp khi chuẩn bị portfolio theo giá trị nghiệp vụ, rủi ro và phụ thuộc. Các mức P0/P1/P2 là ưu tiên đề xuất, không phải lịch sử sprint của nhóm. Chưa có story point hoặc thời gian ước lượng vì chưa có kế hoạch và nguồn lực pilot.

## Backlog

| ID | User story | Ưu tiên | Cơ sở/hiện trạng |
| --- | --- | --- | --- |
| US-01 | Là nhân viên, tôi muốn nhập và kiểm tra thông tin người gửi/nhận để tránh lập đơn sai | P0 | Form và luồng nhập tay đã kiểm tra |
| US-02 | Là nhân viên, tôi muốn thấy khối lượng tính cước, tuyến và tiền cước trước xác nhận | P0 | API tính cước và màn hình review đã kiểm tra |
| US-03 | Là nhân viên, tôi muốn có mã vận đơn và barcode sau xác nhận để gắn với bưu gửi | P0 | Luồng mô phỏng đã kiểm tra |
| US-04 | Là nhân viên, tôi muốn nhập tay khi AI/thiết bị không sẵn sàng để tiếp tục giao dịch | P0 | Đường nhập tay có sẵn; cần UAT với lỗi thiết bị |
| US-05 | Là nhân viên, tôi muốn đo lại khi cảm biến trả số bất thường để tránh báo sai cước | P0 trước pilot | Bổ sung kiểm tra miền đo, số dương và độ ổn định |
| US-06 | Là nhân viên, tôi muốn tiếp tục đơn dang dở sau sự cố để không nhập lại | P0 trước pilot | Đề xuất lưu draft; hiện ở bộ nhớ |
| US-07 | Là nhân viên, tôi muốn AI gợi ý thông tin và loại bưu gửi để giảm thao tác | P1 | Có module OCR/YOLO; cần cấu hình và đánh giá luồng |
| US-08 | Là người vận hành, tôi muốn có bảng cước được quản lý phiên bản để biết đơn dùng cấu hình nào | P1 | JSON hiện là snapshot; đề xuất phiên bản và quy trình cập nhật |
| US-09 | Là người quản lý, tôi muốn đo thời gian thao tác và tỷ lệ sửa dữ liệu để đánh giá lợi ích | P1 | Chưa có instrumentation/pilot |
| US-10 | Là nhân viên, tôi muốn trạng thái thanh toán đồng bộ với giao dịch thật | P2 sau pilot | Hiện là xác nhận mô phỏng |

Ưu tiên bảo đảm một giao dịch cơ bản có thể hoàn tất và sửa lỗi trước khi mở rộng mức tự động hóa. Các hạng mục US-05/06 là phụ thuộc của pilot, dù demo đã chạy được mà chưa có chúng.

## Milestone

| Giai đoạn | Đầu ra | Điều kiện chuyển tiếp |
| --- | --- | --- |
| M1 — Demo có thể xem và chạy | Tài liệu, screenshot, API nhẹ và dữ liệu hiệu chuẩn | Kiểm thử cơ bản và luồng trình duyệt đạt |
| M2 — UAT AI/phần cứng | Ca kiểm thử OCR, đo, timeout, số đo bất thường và thao tác sửa | Xử lý được các ngoại lệ đã xác định; xác nhận quy tắc cước |
| M3 — Pilot có đo lường | Baseline, log thao tác, tập giao dịch so sánh và phản hồi nhân viên | Có bằng chứng về thời gian, sai sót và độ ổn định |
| M4 — Tích hợp vận hành | Quản lý quyền, draft bền vững, cước có phiên bản và thanh toán thật | Đáp ứng yêu cầu vận hành được xác nhận sau pilot |

M1 được chuẩn bị trong repository này. M2–M4 là lộ trình đề xuất.

## Chỉ số cần đo

| Chỉ số | Định nghĩa đề xuất | Đã có dữ liệu? |
| --- | --- | --- |
| Thời gian tiếp nhận | Từ bắt đầu nhập/xác nhận thông tin đến tạo barcode; báo cả median và p90 | Chưa có pilot |
| Tỷ lệ sửa OCR | Số trường được sửa / số trường được AI gợi ý | Chưa có log sử dụng |
| Tỷ lệ đo lại | Số bưu gửi phải đo lại / số bưu gửi dùng đo tự động | Chưa có pilot |
| Tỷ lệ báo cước đúng | Số ca khớp cách tính chuẩn / tổng ca đối chiếu | Có kiểm thử giới hạn theo JSON |
| MAE cảm biến | Trung bình sai số tuyệt đối theo khoảng cách chuẩn, cm | Có workbook và thí nghiệm hiệu chuẩn |

Không gộp mAP/CER của mô hình vào KPI về thời gian giao dịch. Chọn mục tiêu định lượng cho pilot sau khi có baseline thay vì đặt một mức giảm thời gian chưa được chứng minh.

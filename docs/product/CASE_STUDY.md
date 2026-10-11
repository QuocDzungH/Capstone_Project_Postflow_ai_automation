# Case study: PostFlow dưới góc nhìn PO/PM

Đây là bản hệ thống hóa từ báo cáo và mã nguồn đồ án để trình bày năng lực phân tích sản phẩm. Các đề xuất ưu tiên và bước triển khai tiếp theo được ghi riêng với kết quả đã có.

## Bài toán và người dùng

Một lần tiếp nhận bưu gửi đòi hỏi nhập thông tin người gửi/nhận, xác định loại bưu gửi, cân, đo kích thước, tính cước và cấp mã. Nhiều bước nhập tay tạo cơ hội sai sót và làm tăng khối lượng thao tác tại quầy.

Báo cáo mô tả một giao dịch thường mất khoảng 6–8 phút trong phần bối cảnh. Đây chưa phải baseline của một thí nghiệm đối chứng trong dự án. Mục tiêu sản phẩm là hỗ trợ thao tác và chất lượng đầu vào; hiệu quả về thời gian cần được kiểm chứng trong pilot.

| Người dùng/bên liên quan | Công việc cần hoàn thành | Nhu cầu sản phẩm |
| --- | --- | --- |
| Khách gửi hàng | Cung cấp thông tin đúng và hiểu mức cước | Form rõ ràng, được xem thông tin và cước trước xác nhận |
| Nhân viên tiếp nhận | Kiểm tra thông tin, số đo và hoàn thành đơn | Có thể sửa dữ liệu AI, đo lại hoặc nhập tay |
| Người quản lý điểm phục vụ | Theo dõi chất lượng tiếp nhận | Chỉ số thời gian, tỷ lệ chỉnh sửa và số lần phải thao tác lại — đề xuất cho pilot |
| Nhóm kỹ thuật | Ghép các module AI/phần cứng với nghiệp vụ | Quy tắc dữ liệu, trạng thái đơn và tiêu chí nghiệm thu rõ ràng |

## Đóng góp cá nhân

Phân tích nghiệp vụ, xây dựng luồng hỗ trợ tiếp nhận và phát triển cụm cảm biến ESP32. [Phân định đóng góp](../CONTRIBUTIONS.md). Với vai trò này, phần kỹ thuật được đặt trong câu hỏi sản phẩm: số đo có đủ tin cậy để hỗ trợ tính cước, và nhân viên xử lý thế nào khi đo thất bại?

## Lựa chọn giải pháp và đánh đổi

| Quyết định | Cơ sở | Đánh đổi cần xử lý |
| --- | --- | --- |
| Giữ nhân viên xác nhận thông tin | OCR có sai số; thông tin nhận hàng cần chính xác | Chưa tự động hóa toàn bộ, nhưng có điểm kiểm tra trước tính cước |
| Giữ đường nhập tay | Camera, model hoặc mạng nội bộ có thể chưa sẵn sàng | Tốc độ phụ thuộc thao tác nhân viên trong các ca ngoại lệ |
| Dùng hai phương án đo: camera và cảm biến | Cho phép đánh giá phương án theo điều kiện quầy | Camera phụ thuộc bố trí/ánh sáng; cảm biến phụ thuộc bề mặt và vị trí lắp |
| Bù nhiệt độ và hiệu chuẩn cảm biến | Sai số khoảng cách là đầu vào trực tiếp của kích thước | Hệ số cần phù hợp từng cụm phần cứng; không mặc định áp dụng cho mọi thiết bị |
| Đánh giá tính cước độc lập với AI | Cần kiểm tra quy tắc giá ngay cả khi chưa có model | Chỉ chứng minh tính đúng theo dữ liệu cước đi kèm |

## Phạm vi MVP và kết quả

Luồng cơ bản đã chạy được: nhập tay → nhập số đo → tính cước → thanh toán mô phỏng → lưu đơn → sinh barcode. Bản portfolio có ảnh chụp từ luồng chạy thực tế và các kiểm thử API.

Phần cảm biến có firmware, dữ liệu và notebook hiệu chuẩn. Trên 900 mẫu kiểm thử, MAE sau hiệu chuẩn của ba cảm biến lần lượt là 0,2363; 0,4452; 0,5986 cm. [Chi tiết thí nghiệm](../../hardware/calibration/README.md).

Các kết quả phát hiện vật thể và OCR của nhóm được trích theo báo cáo, không đồng nghĩa với việc luồng nghiệp vụ đã được đánh giá tại bưu cục. [Báo cáo](../reports/Final_Report.pdf).

## Đề xuất đánh giá giá trị sản phẩm

Pilot cần so sánh quy trình hiện tại với quy trình có hỗ trợ trên nhóm bưu gửi tương đương. Ghi nhận thời gian thao tác thực tế, tỷ lệ trường OCR phải chỉnh, số lần đo lại và chênh lệch cước so với tính tay. Có thể ưu tiên hàng hóa dạng hộp, vì thí nghiệm cảm biến phù hợp bề mặt phẳng hơn các vật thể không đều.

Chỉ mở rộng sau khi có dữ liệu về độ ổn định, xử lý ngoại lệ và cách nhân viên sử dụng hệ thống. [Backlog và roadmap đề xuất](BACKLOG.md).

# Đóng góp cá nhân và phạm vi dự án nhóm

Chủ repository xác nhận phụ trách **phân tích nghiệp vụ/phần công việc theo hướng PO/PM** và **phần cảm biến ESP32**. Đây là cơ sở phân định đóng góp trong portfolio; tên người trong thư mục nguồn không được dùng để suy luận người thực hiện.

| Phạm vi cá nhân | Nội dung thể hiện | Bằng chứng trong repository |
| --- | --- | --- |
| Phân tích nghiệp vụ | Bài toán tiếp nhận bưu gửi, người dùng, luồng nhập thông tin–đo–tính cước–tạo mã | [Case study](product/CASE_STUDY.md), [quy trình](product/BUSINESS_PROCESS.md), chương 1 và 4 của báo cáo |
| Đặc tả và truyền đạt yêu cầu sản phẩm | Phạm vi MVP, quy tắc tính cước, xử lý ngoại lệ và tiêu chí nghiệm thu | [PRD](product/PRD.md), [UAT](product/UAT.md) được hệ thống hóa từ đồ án |
| Cảm biến ESP32 | Đọc ba cảm biến siêu âm, bù nhiệt độ, hiệu chuẩn và cung cấp dữ liệu qua HTTP | [Firmware](../hardware/esp32/SETUP_WIFI_ESP32/wifiConfig.h), [sensor client](../hardware/sensor_client.py) |
| Hiệu chuẩn và phân tích sai số | Hồi quy tuyến tính cho từng cảm biến; đánh giá trên các khoảng cách giữ lại để kiểm thử | [Notebook](../hardware/calibration/sensor_calibration.ipynb), [dữ liệu](../hardware/calibration/data.xlsx), [kết quả](../hardware/calibration/calibration_results.json) |

Mô hình phát hiện bưu kiện/phong bì, nhận dạng chữ viết, pipeline camera và ứng dụng tổng thể là phần của dự án nhóm. Các chỉ số mAP/CER/WER trong README là kết quả nhóm được ghi nhận trong báo cáo.

Tài liệu PO/PM trong `docs/product/` được biên tập lại khi chuẩn bị portfolio để giúp người đọc theo dõi quyết định và yêu cầu. Các tài liệu đó không được trình bày như biên bản họp, lịch sử Jira hay bằng chứng về một chức danh PO/PM chuyên nghiệp đã đảm nhiệm.

Báo cáo gốc ghi nhóm gồm Hoang Quoc Dung, Do Thanh Hung, Le Huy Anh và Bui Nhat Minh; giảng viên hướng dẫn Nguyen Thi Hoang Yen. Giữ các tài liệu gốc để đối chiếu nội dung học thuật.

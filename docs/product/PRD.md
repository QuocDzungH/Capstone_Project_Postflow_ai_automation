# PRD — Hỗ trợ tiếp nhận bưu gửi

Phiên bản portfolio, hệ thống hóa từ đồ án. Trạng thái dưới đây phân biệt phần đã kiểm tra trong demo với module cần model/phần cứng và yêu cầu cho pilot.

## Mục tiêu và phạm vi

Hỗ trợ nhân viên thu thập, xác nhận và sử dụng dữ liệu bưu gửi để tính cước và hoàn tất tiếp nhận. Người dùng chính là nhân viên quầy; khách hàng cung cấp thông tin và xác nhận các bước giao dịch.

**MVP:** thông tin người gửi/nhận, hỗ trợ phân loại/OCR, nhập hoặc đo kích thước, nhập khối lượng, tính cước và tạo mã. **Demo công khai:** dùng SQLite và thanh toán mô phỏng. **Phần mở rộng:** đo tự động và nhận dạng từ ảnh khi đủ model/phần cứng. Kết nối thanh toán thật, hệ thống vận hành bưu chính và chatbot không nằm trong luồng demo đã kiểm tra.

## Yêu cầu chức năng

| ID | Yêu cầu | Tiêu chí cốt lõi | Trạng thái |
| --- | --- | --- | --- |
| FR-01 | Thu thập thông tin người gửi/nhận | Cho nhập/sửa tên, điện thoại, tỉnh/thành, phường và địa chỉ | Nhập tay đã kiểm tra |
| FR-02 | Hỗ trợ phân loại và OCR | Kết quả nhận dạng dùng để điền gợi ý; nhân viên xác nhận | Có mã nguồn, cần model/API |
| FR-03 | Thu thập số đo | Ghi rõ kg/cm; có đường nhập tay khi đo tự động chưa sẵn sàng | Nhập tay đã kiểm tra; đo tự động cần thiết bị |
| FR-04 | Tính cước | Xác định tuyến, khối lượng tính cước và mức giá từ cấu hình | Đã kiểm tra theo bảng JSON đi kèm |
| FR-05 | Hoàn tất đơn | Tạo mã, ghi số đo, xác nhận mô phỏng và sinh barcode | Đã kiểm tra bằng API và trình duyệt |
| FR-06 | Thông báo ngoại lệ | Báo trường thiếu, giá trị không hợp lệ hoặc mã đơn không tồn tại | Kiểm tra API; ngoại lệ thiết bị cần UAT |
| FR-07 | Lưu và tra đơn hoàn tất | Đơn PAID lưu trong DB; có thể tra mã | SQLite đã kiểm tra; PostgreSQL cần cấu hình |

## Quy tắc nghiệp vụ

| ID | Quy tắc trong bản demo | Nguồn |
| --- | --- | --- |
| BR-01 | Khối lượng và ba kích thước phải lớn hơn 0 | Schema API và `backend/pricing.py` |
| BR-02 | Khi mọi cạnh ≤ 50 cm, dùng khối lượng thực | `chargeable_weight_kg` |
| BR-03 | Nếu có cạnh > 50 cm, tính L × W × H / 6000 và lấy lớn hơn giữa khối lượng thực và quy đổi | `chargeable_weight_kg` |
| BR-04 | Tỉnh/thành và dịch vụ phải có trong cấu hình; một số cách viết được chuẩn hóa | `regions.json`, `pricing.py` |
| BR-05 | Dùng bảng bậc giá và bước khối lượng tương ứng dịch vụ | `pricing.json` |
| BR-06 | Đơn chỉ lưu bền vững khi xác nhận thanh toán mô phỏng | `mock_payment` trong `app.py` |

Bảng cước và danh mục địa phương là snapshot trong mã nguồn đồ án, chưa được đối chiếu với chính sách hiện hành. Luồng LETTER trong giao diện hiện dùng số đo và khối lượng mặc định; cần xác nhận lại quy tắc này trước pilot.

## Yêu cầu cho pilot

- Có quyền truy cập phù hợp cho nhân viên và kiểm soát dữ liệu khách hàng.
- Ghi nhận thời gian từng bước, lần đo lại và trường dữ liệu được chỉnh sau OCR.
- Lưu đơn đang xử lý để khôi phục khi API khởi động lại; demo hiện giữ chúng trong bộ nhớ.
- Kiểm tra số đo dương, miền đo, timeout và tính ổn định trước khi tự điền cước.
- Đặt mục tiêu thời gian phản hồi và sai số chấp nhận được sau khi có baseline và mức cước nhạy cảm với sai số.

Các yêu cầu này là phạm vi đề xuất cho triển khai tiếp theo, không phải tính năng đã hoàn tất.

## Cách nghiệm thu

Dùng [UAT](UAT.md) để nối yêu cầu với thao tác, kết quả và bằng chứng. Luồng tạo đơn có thể chạy trước bằng dữ liệu giả lập; các ca OCR/cảm biến cần bổ sung thiết bị và dữ liệu đúng phạm vi.

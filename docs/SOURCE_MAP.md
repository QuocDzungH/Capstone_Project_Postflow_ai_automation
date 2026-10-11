# Nguồn tệp và cách đóng gói

Mã nguồn và tài liệu được sao chép vào repository; các thư mục gốc ở ngoài repository được giữ nguyên.

| Nguồn ban đầu | Vị trí trong repository | Xử lý |
| --- | --- | --- |
| `Huy ANh_Pricing_ Handwriting Recognition/graduation.zip` | `backend/`, giao diện root, `tests/`, `docs/technical/`, `legacy-ui/` | Giải nén chọn lọc mã nguồn; không lấy Git history, model, ảnh thanh toán, DB và knowledge base |
| ZIP phân biệt bưu kiện/phong bì | `experiments/classification/` và training records | Giữ script/config và số liệu huấn luyện; bỏ ảnh/label thô và weights |
| ZIP tìm vùng thông tin | `experiments/label_detection/` và training records | Giữ script/config và số liệu huấn luyện; bỏ ảnh/label thô và weights |
| ZIP đo bằng webcam | `experiments/dimensions/` | Giữ script gốc |
| `ESP32 STH30D HCSR04/` | `hardware/` | Đổi tên client/notebook cho dễ dùng; bỏ output notebook và dòng log mật khẩu Wi-Fi |
| `Final_Report.pdf`, `Presentation_Final.*` | `docs/reports/` | Giữ tài liệu cuối của dự án nhóm |
| `Capstone_Project_Overleaf.zip` | `docs/reports/latex/` | Giữ LaTeX và hình minh họa |
| Hình workflow/cảm biến trong báo cáo | `media/` | Chọn hình không có thông tin khách hàng để giới thiệu |

Không đưa các mẫu báo cáo môn học, báo cáo tham khảo của nhóm khác và bản tài liệu ngoài báo cáo cuối vào repository dự án.

## Điều chỉnh để demo có thể chạy

- Thêm SQLite làm mặc định; giữ adapter PostgreSQL gốc và chuyển tài khoản sang `DATABASE_URL`.
- Tách dependency demo, AI, PostgreSQL và hiệu chuẩn.
- Sinh QR mô phỏng; ảnh QR tài khoản riêng không được sao chép.
- Chặn việc đăng ký listener vào các control camera cũ không còn trong HTML hiện tại, giúp JavaScript tiếp tục gắn sự kiện cho form.
- Đồng bộ bài kiểm thử ETN001 với bậc giá vượt 2 kg đã có trong `pricing.json`; không thay đổi bảng cước.
- Chuyển model identifier của cloud OCR sang `ANTHROPIC_MODEL` để người chạy chọn cấu hình của họ.
- Thêm kiểm thử luồng API, script khôi phục weights/video có bước xem kế hoạch, và script tái chạy hiệu chuẩn từ notebook.

## Tài liệu và dữ liệu mới

`docs/product/`, CV, hướng dẫn chạy/publish, README và các tài liệu đóng góp được biên tập cho portfolio từ mã nguồn, báo cáo và xác nhận vai trò của chủ repository. Backlog/roadmap là đề xuất mới. Screenshot được chụp từ demo chạy với dữ liệu giả lập. JSON/CSV/biểu đồ hiệu chuẩn được tạo lại từ workbook gốc.

[source-manifest.json](source-manifest.json) ghi tệp được chọn, SHA-256 của bản nguồn và hash bản cuối. [archive-members.json](archive-members.json) ghi vị trí member trong archive để đối chiếu. Hash bản cuối có thể khác hash nguồn đối với tệp được làm sạch hoặc điều chỉnh runtime.

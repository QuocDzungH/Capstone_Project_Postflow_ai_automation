# Đưa portfolio lên GitHub

Thư mục này chứa nội dung repository. Push **các tệp trong thư mục Đồ án**, thay vì cả thư mục môn học chứa các ZIP và dữ liệu gốc.

Tên repository gợi ý: **postflow-ai-postal-automation**.

Description:

> PO/PM capstone portfolio for AI-assisted postal acceptance: business analysis, product workflow, ESP32 measurement and a runnable kiosk demo.

Topics gợi ý: `product-management`, `business-analysis`, `capstone-project`, `esp32`, `iot`, `fastapi`, `computer-vision`, `ocr`.

## Push bằng PowerShell

Tạo một repository GitHub trống để dùng cho dự án này. Mở terminal trong thư mục **Đồ án**, rồi chạy:

```powershell
git init -b main
git status --short
git add .
git commit -m "Prepare PostFlow PO-PM capstone portfolio"
$repoUrl = Read-Host "Dan URL repository GitHub cua ban"
git remote add origin $repoUrl
git push -u origin main
```

Git đã được khởi tạo trên nhánh `main` trong bản thư mục chuẩn bị; lệnh `git init` trên chỉ để hướng dẫn có thể dùng lại. Chưa có commit hoặc remote được tạo thay bạn. Nếu Git yêu cầu tên/email commit, cấu hình danh tính Git của bạn rồi chạy lại `git commit`.

Sau khi push, README sẽ hiện ở trang repository. Pin repository lên hồ sơ GitHub và dùng URL của nó trong CV. Có thể gửi trực tiếp đường dẫn đến `docs/product/CASE_STUDY.md` cho người tuyển dụng muốn đọc phần PO/PM.

## Tệp lớn và dữ liệu địa phương

`.gitignore` đã bỏ qua weights, video, archives, dataset ảnh, DB chạy thử và `.env`. Các model/dataset gốc vẫn ở thư mục nguồn của bạn. Dùng [script khôi phục](../model/README.md) để đưa model/video vào các vị trí local được bỏ qua bởi Git khi cần.

Ảnh demo trong README dùng thông tin giả lập. Video gốc không được đưa vào tập tệp push; nếu muốn thêm link video công khai, dùng một bản demo không chứa thông tin khách hàng hoặc tài khoản thật rồi cập nhật `media/README.md`.

Báo cáo, slide và mã nguồn là tài liệu của dự án nhóm; giữ credit trong tài liệu và mô tả đóng góp cá nhân theo [CONTRIBUTIONS](CONTRIBUTIONS.md). Repository chưa tự áp một giấy phép mã nguồn mở thay mặt các tác giả.

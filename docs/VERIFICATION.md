# Kết quả kiểm tra bản portfolio

Ngày kiểm tra: **11/10/2026**. Môi trường: Windows, Python 3.11; trình duyệt Microsoft Edge ở chế độ headless.

## Đã kiểm tra

| Phạm vi | Kết quả |
| --- | --- |
| `python -m unittest discover -s tests -v` | 11 bài kiểm thử đạt: quy tắc cước, input không hợp lệ, lifecycle đơn, SQLite, QR mô phỏng và barcode |
| Luồng trình duyệt | Nhập thông tin giả lập → nhập số đo → xem cước → QR mô phỏng → xác nhận → mã vận đơn/barcode; không có JavaScript page error |
| Hiệu chuẩn cảm biến | Chạy lại trên workbook gốc: 8.800 train / 900 test; kết quả MAE và hệ số khớp output notebook gốc sau làm tròn |
| JavaScript | `node --check app.js` đạt |
| Tập tệp public | Kiểm tra local Markdown links, cú pháp Python, file lớn và một số mẫu credential bằng `scripts/check_repository.py` |

Screenshot được tạo từ luồng demo thực tế và chỉ chứa thông tin giả lập. Kết quả hiệu chuẩn được lưu ở [CSV](../hardware/calibration/calibration_results.csv) và [JSON](../hardware/calibration/calibration_results.json).

## Giới hạn kiểm tra

- Chưa chạy lại PostgreSQL, nạp firmware trên board hoặc kiểm tra thiết bị ESP32 thật.
- Chưa tái huấn luyện YOLO/TrOCR hoặc gọi cloud OCR. Chỉ số mAP/CER/WER được trình bày theo báo cáo nhóm.
- Chưa chạy pilot tại bưu cục hoặc đo mức giảm thời gian tiếp nhận.
- GitHub Actions được cấu hình để kiểm tra demo khi push; chưa có lần chạy CI trên remote trong phiên chuẩn bị này.
- Kiểm tra credential bằng mẫu không thay thế việc đánh giá quyền công bố mọi dữ liệu trong báo cáo/slide gốc.

## Lệnh chạy lại

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

Thí nghiệm hiệu chuẩn chạy riêng theo [hướng dẫn](../hardware/calibration/README.md).

# Chạy demo và module mở rộng

Các lệnh bắt đầu từ thư mục repository. Python 3.11 là phiên bản đã kiểm tra khi đóng gói.

## Demo cơ bản trên Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Truy cập `http://127.0.0.1:8000`; tài liệu API tại `http://127.0.0.1:8000/docs`.

Không cần `.env` cho demo mặc định. Nếu muốn cấu hình, copy `.env.example` thành `.env`. Giữ `DATABASE_URL` rỗng để dùng SQLite; file DB mặc định được tạo tại `backend/data/postflow.db` và đã nằm trong `.gitignore`.

Chọn nhập tay thông tin giả lập, chọn ETN011 và nhập số đo. Ví dụ Hà Nội → Đà Nẵng, 2,2 kg, 50×20×20 cm có cước 72.000 VND theo bảng đi kèm. Xác nhận thanh toán mô phỏng để lưu đơn và xem barcode.

## Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.app:app --reload
```

## PostgreSQL

Đây là adapter của mã nguồn gốc, giữ lại cho môi trường có PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-postgres.txt
```

Đặt `DATABASE_URL` trong `.env` theo tài khoản/database của bạn, rồi chạy API. Không dùng thông tin tài khoản mẫu của máy cũ. API sẽ tạo bảng `orders`. PostgreSQL chưa được chạy lại trong lần đóng gói; luồng đã kiểm tra dùng SQLite.

## OCR và xử lý ảnh

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
```

Khôi phục weights theo [model/README](../model/README.md). TrOCR cần cả thư mục `model/trocr-vietnamese-final/`, không chỉ file weights. EasyOCR và một số model pretrained có thể tải thêm dữ liệu khi sử dụng lần đầu.

Các endpoint dùng cloud OCR cần `ANTHROPIC_API_KEY` và `ANTHROPIC_MODEL` trong `.env`; model identifier do người chạy cung cấp theo tài khoản của họ. Chỉ gọi endpoint đó khi muốn gửi ảnh đến dịch vụ OCR và dùng tài khoản của mình. Demo nhập tay không gọi dịch vụ này.

Nguồn có một nhánh OCR Vintern và các module camera/scale khác. Chúng được giữ làm phần mã nguồn dự án; không nằm trong luồng đã kiểm tra của demo nhẹ. Không có notebook huấn luyện TrOCR hoàn chỉnh trong bộ tệp đã chọn, nên repository không đưa ra lệnh huấn luyện lại TrOCR từ đầu.

## ESP32 và hiệu chuẩn

Xem [hardware/README](../hardware/README.md) để nạp firmware và đọc thiết bị. Endpoint backend `/detect-dimensions-esp32` hiện thuộc module đo có dependency xử lý ảnh; muốn dùng qua API, cài `requirements-ml.txt`. Có thể đọc độc lập bằng `hardware/sensor_client.py` chỉ với `requests`.

Hiệu chuẩn cần `hardware/requirements.txt`; chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r hardware/requirements.txt
.\.venv\Scripts\python.exe hardware/calibration/evaluate_calibration.py --plot
```

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_repository.py
```

## Giới hạn vận hành

Demo xác nhận thanh toán bằng thao tác mô phỏng, giữ đơn chưa hoàn tất trong bộ nhớ và chưa có phân quyền nhân viên. Bảng cước/địa phương là dữ liệu snapshot đi kèm. Các yêu cầu để tiến tới pilot được ghi trong [PRD](product/PRD.md) và [backlog](product/BACKLOG.md).

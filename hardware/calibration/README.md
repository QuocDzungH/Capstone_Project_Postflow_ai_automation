# Thí nghiệm hiệu chuẩn cảm biến

[data.xlsx](data.xlsx) là workbook trong thư mục cảm biến gốc. [Notebook](sensor_calibration.ipynb) được giữ mã xử lý và xóa output ảnh/metadata phiên chạy để dễ xem và tránh đưa trạng thái máy cá nhân lên Git.

## Thiết kế đánh giá

- Sheet `Calibration`: 9.700 dòng hợp lệ dùng cho hiệu chuẩn.
- Tập kiểm thử giữ riêng các khoảng cách thực **11, 21, 31, 41, 51, 61, 71, 81, 91 cm**: 900 mẫu.
- Các khoảng cách còn lại dùng huấn luyện: 8.800 mẫu.
- Fit một `LinearRegression` cho mỗi cảm biến theo `Actual_cm = coefficient × Measured_cm + intercept`.
- Đánh giá trước/sau trên cùng tập kiểm thử bằng MAE; báo thêm RMSE và MAPE sau hiệu chuẩn.

Việc giữ riêng các khoảng cách giúp đánh giá trên điểm tham chiếu chưa dùng fit. Kết quả vẫn thuộc cùng một bộ thu thập có kiểm soát; chưa chứng minh tính tổng quát trên thiết bị khác hoặc môi trường bưu cục.

## Kết quả tái chạy

| Sensor | MAE trước (cm) | MAE sau (cm) | RMSE sau (cm) | MAPE sau | Giảm MAE |
| --- | --- | --- | --- | --- | --- |
| CB1 | 0,9372 | 0,2363 | 0,2852 | 0,5267% | 74,7871% |
| CB2 | 1,8959 | 0,4452 | 0,5772 | 1,2643% | 76,5180% |
| CB3 | 2,1047 | 0,5986 | 0,6468 | 1,9374% | 71,5571% |

![MAE trước và sau hiệu chuẩn](../../media/sensor-calibration.png)

Kết quả chi tiết: [CSV](calibration_results.csv), [JSON](calibration_results.json). Hệ số được dùng trong firmware được làm tròn tới sáu chữ số thập phân.

## Chạy lại

Từ thư mục repository:

```powershell
python -m pip install -r hardware/requirements.txt
python hardware/calibration/evaluate_calibration.py --plot
```

Script dùng đúng cách tách dữ liệu và phép hồi quy trong notebook gốc, lưu JSON/CSV tại đây và biểu đồ vào `media/`. Muốn chạy notebook, mở JupyterLab rồi chọn thư mục `hardware/calibration/` để đường dẫn `data.xlsx` được resolve đúng.

Các sheet khác trong notebook khảo sát môi trường, chiều dài dây và hướng đo. Chỉ số MAE tổng thể 0,9016–1,7445 cm trong báo cáo dùng phạm vi 9.700 phép đo/cảm biến, khác với bảng trước/sau trên 900 mẫu kiểm thử ở trang này.

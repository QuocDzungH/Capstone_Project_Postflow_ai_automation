# Vùng cước

Nguồn dữ liệu: `DV_Cước_2026_updated.xlsx`, sheet `FLAT_TinhVung`.

| Vùng | Tỉnh/thành áp dụng |
| --- | --- |
| Vùng 1 | Điện Biên, Lai Châu, Sơn La, Lào Cai, Phú Thọ, Tuyên Quang, Cao Bằng, Thái Nguyên, Lạng Sơn, Bắc Ninh, Quảng Ninh, Hải Phòng, Hưng Yên, Ninh Bình, Hà Nội, Thanh Hoá, Nghệ An, Hà Tĩnh |
| Vùng 2 | An Giang, Bình Dương, Bình Phước, Bà Rịa - Vũng Tàu, Bạc Liêu, Bến Tre, Bình Thuận, Cà Mau, Cần Thơ, Đồng Nai, Đồng Tháp, TP. Hồ Chí Minh, Hậu Giang, Kiên Giang, Khánh Hoà, Long An, Lâm Đồng, Ninh Thuận, Sóc Trăng, Tây Ninh, Tiền Giang, Trà Vinh, Vĩnh Long, Đắk Lắk, Đắk Nông |
| Vùng 3 | Bình Định, Đà Nẵng, Gia Lai, Thừa Thiên Huế, Kon Tum, Phú Yên, Quảng Trị, Quảng Nam, Quảng Ngãi, Quảng Bình |

## Quy tắc tuyến

- Cùng tỉnh/thành: **Nội tỉnh**.
- Khác tỉnh/thành nhưng cùng vùng: **Nội vùng**.
- Với `CTN001`: Vùng 1 ↔ Vùng 3 hoặc Vùng 2 ↔ Vùng 3 là **Cận vùng**; Vùng 1 ↔ Vùng 2 là **Cách vùng**.
- Với nhóm `ETN`: Hà Nội ↔ TP. Hồ Chí Minh và Đà Nẵng ↔ (Hà Nội hoặc TP. Hồ Chí Minh) là tuyến đặc biệt; các tuyến khác vùng còn lại là **Liên vùng**.

> Danh sách Vùng 2 và Vùng 3 được giữ nguyên từ file nguồn, nơi có ghi chú cần đối chiếu khi thay đổi địa giới hành chính.

# Phong Thần — Tự lập tuyến và khảo sát map

## Khởi chạy

Nhấp đúp **CHAY_TOOL.bat**, sau đó bấm **TỰ LẬP TUYẾN VÀ KHẢO SÁT**.

Tool tự tìm nơi cài LDPlayer qua tiến trình đang chạy, thông tin cài đặt Windows, các ổ đĩa và PATH. Không cần sửa đường dẫn khi chuyển sang máy khác.

Khi mở tool, kết nối được dò tự động. Nếu chỉ có một LD phù hợp, tool tự chọn; nếu mở nhiều LD, tool ưu tiên bản đang chạy game. Khi có nhiều bản cùng phù hợp, chọn trong danh sách phía trên. Nút **Dò lại LD** dùng sau khi mở lại hoặc thêm giả lập. Khi đang khảo sát, phần chọn LD được khóa để giữ đúng nhân vật.

`config/settings.json` mặc định dùng `"adb_path": "auto"` và `"device_id": "auto"`. Có thể đặt đường dẫn hoặc serial cụ thể nếu cần chọn cố định. Các giá trị được dò chỉ dùng trên máy hiện tại, không ghi đè cấu hình thành đường dẫn của máy đó. Nếu LD chưa online, tool tự dò lại sau 10 giây; cần mở LDPlayer và cho phép kết nối ADB trong cài đặt giả lập.

Chạy từ dòng lệnh nếu Python đã được thiết lập:

```powershell
python -B main.py
python -B main.py --cli
```

## Các thư mục

```text
tool/
├── CHAY_TOOL.bat       Mở ứng dụng
├── main.py             Điểm khởi chạy GUI / CLI
├── README.md           Hướng dẫn này
├── config/             Cấu hình và danh sách map
├── core/               Điều khiển, quan sát, lập tuyến, ghi lỗi và tạo báo cáo
├── gui/                Giao diện ứng dụng
├── tests/              Kiểm tra tự động bằng dữ liệu mô phỏng
├── docs/               Kế hoạch, tình trạng triển khai và cấu hình Sheet
├── integrations/       Mã dịch vụ Google Apps Script
├── reports/            Kết quả và dữ liệu ứng dụng đang dùng
│   ├── evidence/       Ảnh bằng chứng lỗi
│   ├── routes/         Tuyến và tiến độ từng map, tự tạo khi chạy
│   └── dashboard.html  Báo cáo đã xuất
└── archive/            Ảnh, video và kết quả thử cũ, ứng dụng không đọc
    ├── screenshots/    Ảnh chụp tham khảo
    ├── videos/         Video gốc
    └── diagnostics/    Ảnh và dữ liệu khảo sát thử
```

Các tệp SQLite, JSON/CSV và ảnh có thể được ứng dụng tạo thêm trong `reports/`. Giữ `config/`, `core/`, `gui/`, `main.py` và dữ liệu trong `reports/` khi sử dụng. `archive/` chỉ chứa tư liệu cũ; có thể chuyển ra nơi lưu trữ khác nếu không cần để cạnh ứng dụng.

Máy mới cần Python và các thư viện trong `requirements.txt`; cài vào môi trường Python sẽ dùng để mở tool. Việc dò LD không thay thế việc cài các thư viện Python này.

## Quy trình tự động

1. Chờ nhân vật dừng, mở map và kéo xem các vùng để ghi nhớ địa hình.
2. Chọn mốc gốc gần vị trí thật, tạo các vòng thuận chiều kim đồng hồ từ nhỏ ra lớn; thêm mốc kiểm tra nhánh và biên còn thiếu.
3. Tự ghim từng đoạn; dùng tọa độ thực tế để kiểm tra đã tới đích.
4. Ghi nhớ vật cản tạm thời, thử lối vào khác có giới hạn. Điểm chưa tới vẫn được giữ là chưa hoàn tất.
5. Lưu tiến độ riêng theo LD/hồ sơ/phiên bản game và map vào SQLite để tiếp tục lần sau.
6. Lưu cảnh nghi ngờ có nhiều khung hình, tự lên lịch quay lại; đồng bộ lỗi đã xác nhận qua hàng chờ nền.

Khung lộ trình: xanh lá là đã đi, vàng là chưa đi, cam/đỏ là cần thử lại. Địa hình được ước lượng từ ảnh; dữ liệu `map-render-status.json` và `pos-trace-status.json` trong game phải đang cập nhật để xác minh vị trí. Cảnh nghi ngờ không chặn tuyến; có thể duyệt lại trên giao diện hoặc trong báo cáo.

Trong `config/settings.json` → `traversal`, `ring_spacing_pixels` điều chỉnh khoảng cách vòng và `arrival_tolerance` là sai số tới đích theo đơn vị tọa độ game. Phạm vi kiểm tra hình ảnh mặc định chưa được hiệu chỉnh (`inspection_radius=0`, `inspection_calibrated=false`), nên tool phân biệt đã đi hết mốc với đã kiểm tra hết diện tích.

Nút tạm dừng/dừng gửi hủy di chuyển và kiểm tra các mẫu đứng yên mới. Nếu chưa xác minh được, ứng dụng hiện cảnh báo, không báo đã dừng thành công. Khi đóng cửa sổ, ứng dụng chờ engine xử lý dừng và lưu dữ liệu.

## Google Sheet và tài liệu triển khai

Sheet đích đã đặt trong cấu hình. Cần triển khai dịch vụ Apps Script và cấu hình URL/token trước khi tự ghi; khi chưa cấu hình, công việc được giữ trong SQLite. Xem [hướng dẫn kết nối](docs/CAU_HINH_GOOGLE_SHEET.md).

- [Kế hoạch phát triển](docs/KE_HOACH_PHAT_TRIEN.md).
- [Tình trạng mã đã triển khai và phần cần nghiệm thu](docs/TRIEN_KHAI_VA_NGHIEM_THU.md).
- `integrations/google_apps_script/Code.gs`: mã dịch vụ ghi Sheet và tải ảnh Drive.
- `reports/runtime.sqlite3`: nguồn dữ liệu chính; JSON/CSV/HTML là bản xuất. Khi sao lưu lúc ứng dụng đang mở cần dùng cơ chế backup SQLite; không chỉ copy một file DB và bỏ file WAL đang hoạt động.

Chưa xác nhận chạy đủ 32 map hoặc đạt các chỉ tiêu chạy bền/độ chính xác của kế hoạch. Những map chưa có lối vào được ghi rõ trong báo cáo.

## Kiểm tra cho người phát triển

```powershell
python -B -m unittest discover -s tests -v
```

Các kiểm tra này dùng mô phỏng, không điều khiển nhân vật. Bộ khởi chạy đã tắt việc tạo cache `__pycache__` để giữ thư mục gọn.

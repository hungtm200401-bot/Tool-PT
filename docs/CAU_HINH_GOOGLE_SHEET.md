# Kết nối Google Sheet đích

Sheet đã được cấu hình: [bảng tính của dự án](https://docs.google.com/spreadsheets/d/1AvRcllKqX03WwwrE508vhJBnnWBUx2_hgpU8gHwZoqY/edit?gid=0#gid=0), tab `gid=0`.

Link này xác định đích ghi. Để ứng dụng desktop ghi được, triển khai dịch vụ Apps Script bên dưới bằng tài khoản có quyền sửa Sheet và ghi vào thư mục bằng chứng trên Drive. Mã dịch vụ đã chuẩn bị trong `integrations/google_apps_script/Code.gs`; chưa được triển khai vào tài khoản Google trong lần sửa mã này.

## 1. Chuẩn bị một lần

1. Tạo một thư mục Drive dành riêng cho bằng chứng. Lấy ID thư mục từ URL.
2. Chia sẻ thư mục cho những người cần đọc báo cáo. Dịch vụ giữ quyền kế thừa thư mục, không tự công khai ảnh cho mọi người.
3. Tạo dự án tại Apps Script, dùng tài khoản có quyền sửa bảng tính.
4. Copy nội dung `integrations/google_apps_script/Code.gs` vào `Code.gs`.
5. Trong **Project Settings → Script Properties**, thêm:

| Tên | Giá trị |
|---|---|
| `SPREADSHEET_ID` | `1AvRcllKqX03WwwrE508vhJBnnWBUx2_hgpU8gHwZoqY` |
| `SHEET_GID` | `0` |
| `EVIDENCE_FOLDER_ID` | ID thư mục đã tạo |
| `SYNC_TOKEN` | Chuỗi ngẫu nhiên riêng, ít nhất 32 ký tự; dùng cùng giá trị ở desktop |

Không đưa token vào mã nguồn, ảnh chụp, báo cáo hoặc tin nhắn công khai. Mỗi máy vận hành được cấp token qua cấu hình tại máy; token không nằm trong bản đóng gói.

## 2. Chuẩn bị cột dữ liệu

Mã hiện yêu cầu dòng 1 khớp các cột sau:

| Cột | Tiêu đề |
|---|---|
| A | STT |
| B | TÊN MAP |
| C | TỌA ĐỘ X |
| D | TỌA ĐỘ Y |
| E | ẢNH MINH CHỨNG |
| F | MÔ TẢ / GHI CHÚ |
| G | TRẠNG THÁI |
| H | incident_id |
| I | revision |
| J | observed_at |
| K | confidence |

Chạy hàm **setup** trong trình soạn thảo và cấp quyền Google khi được yêu cầu. Hàm kiểm tra tiêu đề hiện có trước khi điền những cột trống. Nếu cột đang có tiêu đề khác, hàm dừng để đối soát; không đổi tên hoặc ghi đè dữ liệu hiện có. Cần điều chỉnh ánh xạ sau khi kiểm tra Sheet thực tế nếu cấu trúc khác dự kiến.

Cột H–K có thể ẩn sau khi cấu hình. Không xóa ID/revision. Các dòng cũ không có ID được giữ nguyên, không tự suy đoán gộp với lỗi mới.

Cột G giữ trạng thái xử lý nghiệp vụ: lỗi mới là `Chưa fix`, cảnh bị bác bỏ là `Không phải lỗi`. Khi cập nhật lỗi đã có, client giữ trạng thái xử lý hiện có của nhóm trên Sheet. Phân loại `qa_confirmed`/`machine_confirmed` được ghi kèm độ tin cậy ở cột K và giữ riêng trong SQLite.

## 3. Triển khai Web App

1. Chọn **Deploy → New deployment → Web app**.
2. Chọn chạy với danh tính người triển khai đã được cấp quyền Sheet/Drive.
3. Desktop này dùng token trong nội dung POST, nên deployment phải cho phép truy cập không đòi phiên đăng nhập trình duyệt. Nếu chính sách Workspace không cho phép kiểu truy cập này, cần backend/OAuth riêng; cấu hình hiện tại chưa hỗ trợ vượt hạn chế đó.
4. Copy URL triển khai kết thúc bằng `/exec`.
5. Mở tool → **CẤU HÌNH ĐỒNG BỘ / THỬ LẠI** → nhập URL và token → lưu.

Token nhập ở giao diện chỉ được giữ trong tiến trình hiện tại. Để giữ qua những lần mở ứng dụng, đặt biến môi trường người dùng Windows `PHONG_THAN_SYNC_TOKEN` với cùng giá trị, rồi mở lại tool. URL được lưu vào `config/settings.json`. Có thể đặt URL qua biến `PHONG_THAN_SHEET_ENDPOINT` nếu để trường endpoint trong file trống.

Sau khi thay đổi mã Apps Script, cập nhật deployment sang phiên bản mới và kiểm tra lại URL đang dùng.

Tài liệu chính thức: [triển khai Apps Script Web App](https://developers.google.com/apps-script/guides/web), [khóa dùng chung giữa các lần gọi](https://developers.google.com/apps-script/reference/lock/lock-service).

## 4. Cách theo dõi

- **Chưa cấu hình:** công việc ở SQLite; chưa gửi dữ liệu ra mạng.
- **Chờ:** đã có sự kiện được xác nhận, đang chờ tải ảnh/ghi/đối soát.
- **Đã đối soát:** đọc lại đúng ID, revision và dữ liệu nghiệp vụ từ dịch vụ.
- **Cần xử lý:** thiếu quyền, ảnh không có, sai tab, sai cấu trúc hoặc xung đột phiên bản. Sửa nguyên nhân rồi lưu cấu hình/thử lại hàng chờ.

Mất mạng và lỗi tạm thời được thử lại với thời gian chờ tăng dần. Nếu ghi đã thành công nhưng desktop chưa nhận phản hồi, lần sau tìm lại ID trước khi upsert. Dịch vụ dùng khóa script cho đoạn kiểm tra ID và ghi hàng, rồi đọc lại dữ liệu. Mỗi ID có một hàng dưới giả định mọi writer tự động dùng cùng deployment và không sửa/xóa cột ID thủ công.

Ảnh PNG tối đa 5 MB mỗi lần tải trong phiên bản này. Video chưa được tải qua dịch vụ này. STT do dịch vụ cấp; STT trong CSV cục bộ có thể khác khi nhiều máy cùng ghi, ID là khóa đối soát.

## 5. Phạm vi xác nhận

Mặc định các vùng đen/texture tím lặp nhiều khung được lưu là `suspected`, giữ bằng chứng và đưa vào danh sách kiểm tra lại. Chỉ `qa_confirmed` hoặc quy tắc `machine_confirmed` được bật sau hiệu chỉnh mới vào hàng chờ Sheet. Bỏ qua một sự kiện đã đồng bộ sẽ đưa bản sửa `rejected` vào đúng ID trên Sheet.

Chưa có thao tác ghi thật, thử quyền truy cập hoặc đo tải trên Sheet đích trong lần sửa mã này. Cần nghiệm thu trên bản sao/thẻ thử trước khi bật dữ liệu nghiệp vụ. Chưa chứng minh chống trùng lỗi cùng vị trí giữa nhiều máy có ID quan sát khác nhau; cơ chế hiện bảo vệ việc thử lại cùng ID.

# Tình trạng triển khai theo kế hoạch

Cập nhật: 16/10/2026. Đây là nhật ký mã đã triển khai và phần còn cần dữ liệu/môi trường để nghiệm thu, không thay thế kết quả chạy thực tế.

## Đã triển khai trong mã

| Hạng mục | Hành vi mới |
|---|---|
| Tuyến chính | Các vòng quanh mốc gốc, theo chiều kim đồng hồ, mở rộng bán kính; thêm điểm khép biên/nhánh bị bỏ khỏi đường tròn lý tưởng |
| Điểm gốc | Lấy gần tọa độ thật trong nền đi được ước lượng; giữ qua checkpoint cùng hồ sơ |
| Đường nối | A* trên ảnh map; nối đoạn thẳng có kiểm tra vật cản/chi phí; giữ chặng còn thiếu khi không tìm được đường |
| Mục đích chặng | Lưu điểm đi–đến, vòng, mục đích, mã chặng và kết quả vào SQLite; hiển thị trên GUI |
| Xác nhận tới | Mẫu vị trí mới, đúng map, gần đích và đứng yên qua nhiều mẫu; phát hiện dịch chuyển lớn |
| Dừng/tạm dừng | Gửi thao tác hủy; chờ tọa độ mới và đứng yên. Không xác minh được thì hiện `stop_unverified` |
| Tiếp tục sau tạm dừng | Tính lại đường/ghim từ vị trí hiện tại; không coi lệnh bị hủy là đã tới |
| Tiến độ | Sổ đường đã đi, vùng quan sát, phần hình ảnh đã kiểm tra sau hiệu chỉnh, vùng chưa biết, điểm cần xử lý |
| Lưu bền vững | SQLite giao dịch, ảnh map theo dấu băm nội dung, checkpoint trỏ đúng tài sản; JSON/CSV/HTML là bản xuất |
| LD | Khóa ADB/serial/boot của phiên, kiểm tra trước input; dò độ phân giải ngang 16:9, scale vị trí UI |
| Hồ sơ | Tách theo LD/Android ID, danh tính nhân vật nếu có và phiên bản package; hỗ trợ `profile_id` khi game không cung cấp danh tính |
| Vật cản | Thử lối khác có giới hạn; vật cản từ kẹt chỉ né tạm 120 giây, không suy thành tường vĩnh viễn |
| Nhiều map | Đồng nhất danh mục 32 map; tận dụng bảng Link cũ, hỗ trợ cửa/slot đã hiệu chỉnh qua cấu hình, xác minh map đích |
| Phát hiện ảnh | Hai nhóm vùng đen/texture tím, yêu cầu nhiều mẫu mới, mask theo kích thước, gộp theo vùng/loại/bản game |
| Bằng chứng | UUID, tọa độ nhân vật thật, ảnh gốc/khoanh vùng và khung trước/sau nếu có; nén/ghi ở worker có hàng đợi giới hạn |
| Tái kiểm tra | Cảnh nghi ngờ vào danh sách quay lại có giới hạn; không chặn tuyến để đợi người dùng |
| Sheet | Outbox, client Apps Script, tải PNG, lookup/upsert/readback, backoff, sửa trạng thái cùng ID, cấu hình trên GUI |
| Báo cáo | Cùng đọc SQLite; có trạng thái từng map, từng lỗi và đồng bộ; loại bỏ phần trăm 100% cố định |
| Đo hiệu năng | Lưu số mẫu và p50/p95 cho telemetry, chụp ảnh, input và lập đường trong checkpoint `metrics:*` |
| Giao diện | Worker không gọi Tk trực tiếp; hàng đợi callback giới hạn, log giới hạn dòng; đóng ứng dụng chờ engine xử lý dừng |

## Những điểm phải hiệu chỉnh bằng game thực

1. **Hủy chạy:** tap trung tâm joystick là thao tác được gửi; cần xác minh tác dụng trên phiên bản game đang chạy. Chưa có bằng chứng đạt mục tiêu dừng ≤2 giây.
2. **Độ phân giải:** hiện scale bố cục tham chiếu 1920×1080 cho tỷ lệ 16:9; chưa có bộ nhận diện tự tìm lại vị trí UI khi game đổi bố cục. Tỷ lệ khác bị từ chối.
3. **Phạm vi kiểm tra hình:** mặc định `inspection_radius=0`, `inspection_calibrated=false`. Tool vẫn đi tuyến và theo dõi mốc/vệt thực tế, nhưng chưa tuyên bố kiểm tra hết diện tích. Cần đo bán kính quan sát mặt đất theo đơn vị tọa độ game và kiểm tra che khuất, rồi cập nhật cấu hình.
4. **Khoảng cách vòng:** hiện 96 pixel ảnh map; cần đo tốc độ/phạm vi quan sát thực để thay cho giá trị ban đầu này. Khoảng chồng 25% đang dùng cho mật độ điểm, chưa thay thế phép hiệu chỉnh camera.
5. **Map có hành lang phức tạp:** vòng hiện mở rộng theo khoảng cách hình học; A* tìm đường nối quanh vật cản và điểm nhánh bổ sung. Chưa triển khai đầy đủ vòng theo khoảng cách đường đi từ gốc hoặc tối ưu toàn cục thứ tự cung.
6. **Cửa chuyển map:** bảng Link cũ vẫn là giả định giao diện chưa kiểm tra trong lần sửa này. Những map thiếu lối vào được giữ `no_route`. Không tự coi tọa độ slot trong danh mục là lối vào đã được xác minh.
7. **Nhận dạng nhân vật:** nếu telemetry không có ID/tên, dùng `profile_id` riêng cho nhân vật trong settings; hiện chưa thể chứng minh không tiếp tục nhầm nhân vật trên cùng LD khi game không phát tín hiệu danh tính.
8. **Hồi sinh:** nhận diện nút dựa màu vẫn cần xác minh bằng mẫu thật; chưa có bộ template được gán nhãn cho popup.
9. **Ảnh map:** mặt nạ đi được là ước lượng; không thay thế dữ liệu va chạm. Không kết luận vùng không vào được là không cần kiểm tra.

## Cấu hình bổ sung

`config/settings.json → navigation.connections` nhận các cửa đã đo thực tế:

```json
{"from": 10, "to": 20, "exit": [150.0, 200.0], "cost": 1, "verified": false}
```

Đây chỉ là ví dụ cấu trúc, không phải cửa thật giữa hai map trên. Chỉ đổi `verified` sau khi xác minh map nguồn, tọa độ cửa và map đích. Tool ưu tiên cửa kế cận đã xác minh trước Link chuyển map.

`navigation.world_slot_overrides` nhận khóa map ID và giá trị `{"screen_xy": [x, y], "confirm_xy": [x, y], "verified": false}` theo bố cục tham chiếu 1920×1080. `confirm_xy` tùy chọn. Chưa có dữ liệu xác minh thì giữ trống.

Khi đổi nhân vật mà nguồn không có danh tính, đặt `profile_id` khác. `game_build` có thể đặt rõ nếu không đọc được versionName/versionCode của package. Tuyến cũ không xác định hồ sơ trong `reports/routes/` vẫn được giữ nguyên; không tự gán tiến độ cũ cho LD bất kỳ.

## Phần cần nghiệm thu tiếp

- Đăng nhập/triển khai dịch vụ Google, kiểm tra tiêu đề và quyền đọc/ghi đúng Sheet; mở ảnh bằng tài khoản người nhận báo cáo.
- Cập nhật bộ kiểm tra cũ vốn còn giả định quét ziczac/vật cản vĩnh viễn, và kiểm tra hành vi mới bằng mô phỏng.
- Thử pause/resume/stop, telemetry cũ, crash checkpoint, timeout sau khi ghi Sheet, khôi phục offline và nhiều writer.
- Tạo tập ảnh/video có nhãn độc lập; đo precision/recall. Mặc định chưa bật tự xác nhận lỗi texture; vùng đen vẫn là cảnh nghi ngờ.
- Bổ sung dữ liệu để phát hiện xé hình, xuyên tường/rơi map, xác nhận từ va chạm/game. Những loại này chưa có detector.
- So sánh vòng mở rộng với tuyến cũ trên cùng điều kiện; đo diện tích mới/phút, đường lặp và số lần mở map.
- Chạy bền 8/24 giờ, đo RAM/CPU/UI, xác minh toàn bộ lối vào map và thử trên máy LD khác.
- Chính sách giữ bằng chứng theo dung lượng, ghi video và tải video lớn chưa triển khai; chưa có tự cập nhật/installer độc lập Python.
- Khóa script chỉ điều phối writer cùng dịch vụ; không bảo vệ trước người sửa Sheet thủ công. Gộp một lỗi giữa nhiều máy chưa được nghiệm thu.

## Việc đã kiểm tra trong lượt sửa

Đã phân tích cú pháp 13 file Python và 2 file cấu hình JSON bằng Python 3.12, kiểm tra cú pháp JavaScript Apps Script bằng Node; không khởi động GUI/engine. Đã xuất lại `reports/dashboard.html` từ SQLite hiện có để bỏ báo cáo cũ ghi cố định 100%. Chưa chạy bộ kiểm tra tự động, chưa điều khiển LD/game và chưa ghi dữ liệu thật lên Sheet. Các ngưỡng trong kế hoạch vẫn là mục tiêu cần nghiệm thu.

# Kế hoạch khắc phục di chuyển và nhận diện bản đồ

Ngày: 20/10/2026 — Phạm vi: 5 vấn đề người dùng phản ánh. Trạng thái: đã khảo sát mã nguồn, dữ liệu lưu và kiểm thử mô phỏng; chưa triển khai sửa logic, chưa nghiệm thu trên LD đang chạy.

## 1. Mục tiêu và nguyên tắc nghiệm thu

Tool phải thực hiện được chu trình: xác định vị trí → đi quanh các góc theo biên an toàn → khép chu vi → đi các vòng bên trong → xử lý phần thiếu. Đường thực tế phải bám kế hoạch; khi kẹt phải lùi ra, ghi nhớ vùng lỗi và chọn lối khác. Không được tính nhìn thấy là đã đi tới.

“Các góc” được hiểu là vùng góc có thể tiếp cận của địa hình, có khoảng cách an toàn với vật cản. Tuyến nối các góc phải theo chu vi, không chạy tắt xuyên giữa map chỉ để đủ bốn điểm. Góc không thể tới phải có bằng chứng và trạng thái riêng; không được tự chuyển thành hoàn tất.

Vòng bên trong đi thuận chiều kim đồng hồ, từ nhỏ ra lớn quanh một tâm ổn định đã chọn trong vùng an toàn. Vòng phải tuân theo địa hình; tường, vực và hành lang có thể chia vòng thành các cung, có đường nối hợp lệ. Không ép nhân vật chạy một hình tròn xuyên vật cản.

Ưu tiên: đúng trạng thái và đúng hướng → thoát kẹt bền vững → đúng thứ tự tuyến → cải thiện nhận diện → đo và tối ưu độ trễ. Dừng do người dùng, mất vị trí hoặc lỗi thiết bị phải có lý do cụ thể. Mục tiêu chạy mượt không được làm mất khả năng dừng thật.

## 2. Bằng chứng đã kiểm tra

- Cấu hình hiện hành: `strategy=corners_first`, `joystick_only=true`, `arrival_tolerance=1.0`, `vision_radius=3.2`, `inspection_calibrated=false`.
- Đã chạy `unittest discover -s tests -v` bằng Python 3.12 tại đường dẫn cài trực tiếp: 138 kiểm thử, lệnh kết thúc thành công. Lệnh `python` qua PATH không chạy được; `py` không tìm thấy bản cài. Đây là vấn đề môi trường khởi chạy riêng, chưa phải bằng chứng gây dừng sau 3–4 giây.
- Tái hiện độc lập bằng dữ liệu giả: nhân vật ở `(5,6)`, mốc ở `(10.5,6)`, sai số tới đích `1.0`, tầm nhìn `3.2`, hướng nhìn `(1,0)` → mốc bị đổi thành `done` dù còn cách **5,5 đơn vị**.
- Xác nhận bằng chữ ký hàm: `_wait_stopped(max_seconds=2.0)` không hợp lệ vì hàm chỉ nhận `self`.
- JSON tuyến Bắc Hải trong `reports/routes/0c7f8412db49e052/map_6.json`: 143 mốc, 22 `done`, 11 `deferred`, 3 `retry`, 107 `pending`; **cả 4 góc đều `deferred`, mỗi góc đã thử 2 lần**. Đây là trạng thái file tại lúc đọc, không phải xác nhận nhân vật đã thực sự tới 22 mốc.
- SQLite ghi chặng `r1:104:41` bắt đầu lúc **17:16:44 ngày 19/10/2026**, kết thúc `stalled` lúc **17:16:47**, theo giờ Asia/Bangkok. Sau đó có `walking → stopping → stopped`; dữ liệu này không xác định ai hoặc điều kiện nào đã yêu cầu dừng toàn phiên.
- JSON tổng tiến độ ghi Bắc Hải 7/143, khác JSON tuyến 22/143. Cần đối soát snapshot/profile/checkpoint từ nguồn chính trước khi dùng số liệu để nghiệm thu; không cộng hoặc chọn số cao hơn.

Kết luận bằng chứng: đã tìm thấy lỗi logic có thể tái hiện và một chặng kẹt khoảng 3 giây. Chưa xác nhận mọi lần dừng 3–4 giây đều do cùng một lỗi hoặc do lỗi cảm ứng.

## 3. Chẩn đoán theo đúng 5 vấn đề

### 3.1. Đi 3–4 giây rồi ngưng

**Lỗi đã xác định:**

1. `CoveragePlan.observe_position()` dùng `max(tolerance, vision_radius)` để hoàn tất mốc; nón nhìn còn mở rộng thêm `1.85` lần. Với cấu hình hiện tại, mốc phía trước có thể được tính hoàn tất từ khoảng **5,92 đơn vị**. `_run_path_joystick_continuous()` nhận `target.state == done` rồi trả `arrived` và nhả joystick. Đây là đường kết thúc chặng sớm ngay trong logic, không cần có lỗi ADB. Nguồn: `core/coverage_planner.py:1041`, `core/map_traversal_engine.py:1449`.
2. Khi telemetry không hợp lệ ở đầu chặng, `_cover_map()` gọi `_wait_stopped(max_seconds=2.0)` sai chữ ký. Nếu nhánh này chạy, exception có thể kết thúc phiên. Nguồn: `core/map_traversal_engine.py:474`, `:1680`.
3. Mỗi chặng đều nhả joystick khi kết thúc, sau đó lưu tiến độ, xuất ảnh và lập đường chặng sau. Có sự gián đoạn giữa các chặng theo thiết kế hiện tại; thời lượng phải đo mới kết luận mức ảnh hưởng.

**Nguy cơ cần đo trên LD:**

- Cảm ứng trực tiếp cố định `/dev/input/event2`, chưa dò thiết bị và miền tọa độ ABS. Ghi thành công vào stdin không chứng minh Android đã nhận cảm ứng; stdout/stderr của shell đang bị bỏ. Nguồn: `core/ld_controller.py:180`, `:331`.
- Khi fallback, một swipe kéo dài 480 ms có thể được phát theo vòng điều khiển chờ 120 ms. Shell tuần tự có nguy cơ tích lũy lệnh cũ; tần số thực còn phụ thuộc xử lý mỗi vòng. Chưa đo độ dài hàng đợi thực tế.
- Nhánh `doing == walk` gọi `toggle_mount()` theo chu kỳ tối thiểu 3 giây, có thể can thiệp thao tác trong khi đang giữ joystick. Chưa có bằng chứng live chứng minh đây là nguồn khựng.

**Giải pháp:** tách xác nhận tới đích khỏi tầm nhìn; sửa lỗi exception; quản lý một chủ sở hữu cảm ứng; xác nhận backend đầu phiên; không xếp hàng hướng lái cũ; ghi lý do cho mọi lần release/stop. Chỉ nối liên tục sang chặng sau khi đường nối đã hợp lệ.

### 3.2. Không đi đúng các góc trước rồi đến vòng tròn

Chế độ `corners_first` đã tồn tại. Vấn đề nằm ở ý nghĩa và cách thực thi:

- Bốn góc được lấy bằng điểm nền gần bốn góc ảnh nhất, không áp dụng khoảng hở tối thiểu như một số mốc khác. Có thể chọn điểm sát mép/vật cản. Nguồn: `core/coverage_planner.py:465`.
- Bốn góc có thứ tự riêng, sau đó mới đến danh sách chu vi. A* giữa hai góc tối ưu đường tới đích, không bị ràng buộc bám biên; vì thế đủ thứ tự bốn góc vẫn không bảo đảm đi quanh map.
- Góc bị chuyển `deferred` không còn được chọn bởi `next_target()`. Các mốc sau có thể chạy tiếp dù nhiệm vụ góc chưa được giải quyết. Nguồn: `core/coverage_planner.py:749`.
- Điều kiện hoàn tất theo tầm nhìn có thể bỏ qua cả góc lẫn cung vòng mà chưa đi tới.
- Tâm vòng hiện lấy theo anchor gần vị trí ban đầu, dù nhãn gọi là “tâm bản đồ”; cần quy định tâm thực sự mong muốn, không dùng nhãn để suy ra hình học.

**Giải pháp:** xây một chu trình biên an toàn, đặt bốn vùng góc lên chính chu trình đó, đi từng cung liên tiếp. Khóa chuyển giai đoạn; góc chưa tới được phải có trạng thái giải quyết rõ ràng. Sau chu vi mới nối vào tâm vòng đã chọn và quét các vòng trong theo cùng chiều.

### 3.3. Có kế hoạch nhưng vẫn đi lung tung

**Lỗi hệ tọa độ đã xác định:** `game_to_joystick_angle()` biến vector tọa độ game thành góc màn hình. Ví dụ hướng game `+X` thành khoảng `36,27°`. Nhưng `cast_ray()` dùng `cos/sin(angle)` trực tiếp trên tọa độ game. Nhánh nhìn trước truyền góc joystick vào raycast game; `find_smart_exit()` lại so sánh góc raycast game với góc joystick rồi trả về làm góc điều khiển. Hai hệ không thể dùng thay nhau. Nguồn: `core/ld_controller.py:521`, `core/coverage_planner.py:345`, `core/map_traversal_engine.py:1612`, `core/obstacle_bypasser.py:21`.

Ngoài ra, hướng chạy lần lượt bị thay bởi nội suy bo cua, khóa góc kẹt, né theo raycast và giới hạn tốc độ đổi góc. Không có bước cuối kiểm tra hướng thực sự gửi xuống còn nằm trong hành lang cho phép. Nội suy tới mốc tiếp theo cũng chưa kiểm tra đoạn cắt góc có xuyên vật cản hay không.

Nhánh ghim cũ có phát hiện lệch tuyến/lặp vị trí; nhánh joystick liên tục đang bật không dùng đầy đủ các điều kiện đó. Chỉ kiểm tra dịch chuyển ròng có thể coi chạy vòng quanh là vẫn đang tiến bộ.

**Giải pháp:** mọi hình học, vật cản và lập đường dùng tọa độ game; chỉ chuyển sang tọa độ màn hình tại lớp điều khiển. Duy trì một chặng đang hoạt động và đo tiến bộ dọc tuyến, độ lệch hành lang, đường đi lặp. Mọi thay đổi tuyến phải có nguyên nhân, phiên bản và đường thay thế đã kiểm tra. Lọc an toàn thực hiện sau mọi bước làm mượt.

### 3.4. Thoát rồi 2–3 giây sau lại chui vào góc cũ

- `_perform_active_unstuck()` dùng `cos/sin` của góc joystick để đặt vật cản trên tọa độ game: vùng cấm có thể bị đặt lệch.
- Hàm này coi dịch chuyển xa điểm kẹt 1,5 đơn vị là thoát thành công; chưa chứng minh đã ở ngoài vùng nguy hiểm và có đường tiếp tục an toàn. Trong khi vùng cấm hướng có bán kính tới 4,5 đơn vị.
- Khi gặp kẹt ở nhánh joystick, `_cover_map()` lưu trạng thái rồi `continue`, bỏ qua phần `record_stall()` theo vùng ở cuối hàm. Vì vậy giới hạn số lần thất bại theo vùng không được tích lũy qua đúng đường xử lý này như nhánh ghim.
- Bộ khóa góc chạy trước raycast và làm mượt: hướng cuối có thể quay trở lại hướng cấm. Khóa hướng quanh một điểm cũng không thay thế được vùng cấm trong bản đồ đường đi.
- Cách chọn breadcrumb gần nhất rồi lái thẳng tới đó không bảo đảm lùi theo từng khúc đường đã đi. Có thể cắt qua chính góc tường.
- Khi nạp tuyến cũ không còn mốc hợp lệ, `_prepare_plan()` có thể dựng mới, làm mất lịch sử cản/thử lại nếu không chuyển dữ liệu sang. Nguồn: `core/map_traversal_engine.py:719`, `:1251`, `:1807`, `:1918`.

**Giải pháp:** dùng quy trình `phát hiện → nhả điều khiển cũ → lùi theo vệt xác minh → xác minh ra khỏi vùng kẹt → lập đường mới tránh vùng đó → tiếp tục`. Lưu kẹt theo khu vực và lối tiếp cận, độc lập target. Không được thử lại chỉ vì đã đổi mốc hoặc khởi động lại tool.

### 3.5. Nhìn map còn kém

`_ground_mask()` chủ yếu dựa trên độ sáng, độ bão hòa và biến thiên màu. Lưới đi được còn cho phép ô có tỷ lệ pixel sáng phù hợp chỉ từ 15%; vùng không chắc được tăng chi phí nhưng vẫn có thể đi xuyên. Vì vậy hình trang trí, cây hoặc vách có thể bị xem là hành lang. Nguồn: `core/coverage_planner.py:296`, `:397`.

“Radar” đang là raycast trên lưới suy ra từ atlas, không phải hệ nhận diện vật cản trực tiếp đáng tin cậy từ từng khung game. Quan sát hình ảnh nền chạy bất đồng bộ chưa tạo thành bản đồ va chạm cập nhật cho bộ lái. Bán kính quan sát còn có thể vượt kiểm tra calibration qua `radius_override`; không thể dùng số diện tích đó làm bằng chứng đã nhìn rõ.

**Giải pháp:** tách bản đồ thành đi được đã xác minh / vật cản / chưa biết / vùng nguy hiểm tạm thời; ghép ảnh có kiểm chứng tọa độ; che chữ, biểu tượng và UI; hiệu chỉnh khoảng hở theo kích thước nhân vật và sai số. Vùng chưa biết chỉ được thăm dò bằng hành vi có giới hạn. Kết hợp atlas, dữ liệu vị trí mới và phản hồi di chuyển thực; nếu sau này dùng mô hình phân đoạn, chỉ đưa vào sau khi có tập ảnh gán nhãn và số đo cải thiện.

## 4. Kế hoạch triển khai theo đợt

Không triển khai cả năm vấn đề thành một bản sửa lớn. Mỗi đợt có sản phẩm và điều kiện qua rõ ràng.

| Đợt | Phạm vi bắt buộc | Sản phẩm | Điều kiện qua |
|---|---|---|---|
| 0 — Ghi nhận và tái hiện | Ghi target, phase, tuổi/frame telemetry, vị trí, hướng game/màn hình, lý do release/stop, backend, thời gian vòng lặp; đồng bộ video với trace; đối soát checkpoint | Một gói tái hiện 5 triệu chứng, kiểm thử làm lộ lỗi trước khi sửa | Mỗi lần dừng phân loại được: tới đích / kẹt / mất dữ liệu / lỗi input / yêu cầu người dùng |
| 1 — Nền tảng điều khiển | Sửa chữ ký hàm, tách seen/reached/inspected; thống nhất tọa độ; dò và kiểm tra backend; một luồng sở hữu input; dữ liệu cũ không được dùng để lái tiếp | Điểm đến thật, góc thật, lệnh cảm ứng có vòng đời rõ | Không hoàn tất mốc từ xa; 8 hướng đúng; mất telemetry và dừng giữa chặng đều xử lý đúng |
| 2 — Bản đồ an toàn và thoát kẹt | Khoảng hở vật cản; vùng chưa biết; đường lùi theo vệt; bộ nhớ vùng kẹt bền vững; kiểm tra hướng cuối | Thoát góc rồi lập lại đường tránh cùng vùng | Bộ tình huống góc, hành lang, cây, ngõ cụt không tái nhập vùng cấm khi khóa còn hiệu lực |
| 3 — Tuyến góc/biên/vòng | Chu trình biên gắn bốn vùng góc; ràng buộc cung; tâm vòng ổn định; nối vòng hợp lệ; khóa giai đoạn; đo tiến bộ dọc tuyến | Một kế hoạch thống nhất với đường thực tế | Đi đủ cung biên trước vòng trong; không bỏ góc âm thầm, không chạy tắt qua giữa map |
| 4 — Độ mượt và chạy bền | Đưa render/ghi file/chụp ảnh nặng ra khỏi vòng lái; gộp snapshot; một worker telemetry; điều chỉnh tần số theo số đo | Báo cáo độ trễ, chạy bền, lỗi còn lại | Đạt các chỉ tiêu ở mục 6 trên ba loại map |

Đợt 1 phải qua trước khi đánh giá chất lượng né vật cản. Bản đồ an toàn tối thiểu ở đợt 2 phải có trước khi nghiệm thu bám biên ở đợt 3. Nhận diện có thể tiếp tục cải thiện sau đó bằng cùng bộ dữ liệu chuẩn.

Ước lượng ban đầu: 8–12 ngày công gồm tái hiện, sửa và chạy LD thực tế; cần điều chỉnh sau đợt 0 theo khả năng truy cập telemetry, độ ổn định input và số map đại diện. Đây là ước lượng lập kế hoạch, không phải cam kết đã kiểm chứng.

## 5. Thiết kế kỹ thuật cần giữ thống nhất

1. **Một nguồn vị trí:** một worker đọc telemetry, phát snapshot có map ID, frame ID, thời gian nguồn và thời gian nhận. Không tạo thêm lượt ADB đồng bộ chỉ vì cache hết hạn trong vòng lái. Chỉ dùng mẫu mới để đo kẹt, tốc độ và tiến bộ; tuổi quá hạn phải chuyển trạng thái chờ/hủy input rõ ràng.
2. **Một nguồn điều khiển:** quản lý press/steer/release dưới cùng khóa phiên và quyền chạy. Có xác nhận lỗi backend. Hàng đợi hướng lái chỉ giữ lệnh mới nhất; release/cancel được ưu tiên. Không tự tap mount giữa thao tác giữ joystick; xử lý mount ở trạng thái riêng sau khi hiệu chỉnh.
3. **Một nhiệm vụ đang chạy:** lưu `phase_id`, `segment_id`, `target_id`, đường, hành lang, phiên bản bản đồ, vị trí xuất phát và lý do replan. Resume phải khôi phục nhiệm vụ đúng phiên bản, không chạy lại vùng đã thất bại mà thiếu bằng chứng mới.
4. **Ba trạng thái tách biệt:** `seen` là ước lượng quan sát; `reached` là vị trí thực tới đúng vùng; `inspected` cần khung hình và hiệu chuẩn phù hợp. Mốc trung gian có thể được xác nhận khi đi xuyên qua đúng hành lang; không bắt dừng mỗi mốc. Chỉ xác nhận dừng ở nơi cần dừng.
5. **Thoát kẹt có điều kiện ra:** phải ra ngoài vùng cản có khoảng đệm, có nhiều mẫu mới chứng minh chuyển động hợp lệ, và có tuyến tiếp theo không cắt vùng khóa. Nếu không còn đường được xác minh, giữ phần việc chưa xong và báo lý do cụ thể.
6. **Tối ưu theo số đo:** vòng lái không render atlas, nén ảnh, ghi JSON đầy đủ hoặc chờ Sheet. UI nhận snapshot mới nhất theo tần số phù hợp; worker kiểm tra ảnh có giới hạn số việc đang chạy. Checkpoint bền vững tại chuyển trạng thái, ghi định kỳ có gộp; khi dừng phải flush được.
7. **Di trú dữ liệu cũ:** không tin toàn bộ `done` cũ vì có thể đến từ tầm nhìn. Giữ bản sao/checkpoint cũ, phân loại lại từ trace đủ tin cậy; mốc không có bằng chứng thành “cần xác minh lại”. Không xóa toàn bộ tiến độ để che lỗi.

## 6. Chỉ tiêu nghiệm thu đề xuất

Các con số dưới đây là mục tiêu, chưa phải kết quả đã đạt. Đợt 0 đo khả năng thực của LD để chốt ngân sách thời gian; không sửa chỉ tiêu sau chạy để biến kết quả thất bại thành đạt.

| Hạng mục | Tiêu chí |
|---|---|
| Đến đích thật | 0 lần đánh dấu reached khi ngoài sai số, sai map hoặc chỉ có dữ liệu cũ; riêng ca cách 5,5 đơn vị phải giữ chưa tới |
| Đi liên tục | 10 phút đường thoáng qua nhiều mốc: 0 lần dừng không có lý do; không nhả joystick ở mốc trung gian khi đường nối đã hợp lệ |
| Góc → biên → vòng | 100% mốc bắt buộc được reached hoặc có kết quả không thể tiếp cận kèm bằng chứng; không chuyển âm thầm sang vòng trong khi còn góc/biên chưa xử lý |
| Bám tuyến | Ít nhất 95% mẫu vị trí mới nằm trong hành lang đã định; lệch kéo dài phải phát hiện và ghi lý do trong 2 chu kỳ mẫu mới |
| Thoát kẹt | Ít nhất 30 tình huống góc/cây/ngõ cụt: mục tiêu ≥95% thoát trong 8 giây; 0 lần quay lại vùng bị khóa trong thời gian khóa; ca còn lại dừng có lý do |
| Nhận diện map | Ít nhất 60 vùng ảnh gán nhãn từ 3 loại map; đo riêng tỷ lệ vật cản bị nhận nhầm là lối đi, mục tiêu ≤2%; không che kết quả bằng độ chính xác tổng |
| Hình học đường | 0 đoạn đường xuyên vật cản đã biết trong bộ replay; lối hẹp chỉ được dùng khi đủ khoảng hở đã hiệu chỉnh |
| Độ trễ | Mục tiêu p95 xử lý vòng lái ≤150 ms khi dùng snapshot sẵn; báo riêng tuổi telemetry, độ trễ input và render. Không gọi đây là 60 FPS hoặc 0 ms |
| Dừng | Mục tiêu yêu cầu dừng → phát release/cancel p95 ≤200 ms; xác nhận đứng yên trong 2 mẫu mới cộng độ trễ truyền đã đo; không có lệnh di chuyển cũ chạy tiếp sau đó |
| Chạy bền | 3 map đại diện, tối thiểu 30 phút/map; thêm 1 phiên 2 giờ: không crash, không hàng đợi tăng mãi, không lặp một vùng mà không tăng tiến độ |
| Tiến độ | GUI, JSON và checkpoint cùng profile/phiên bản cho kết quả nhất quán; restart giữ vùng cấm, mốc chưa xong và chặng đang xử lý |

Ba loại map bắt buộc: vùng trống; vùng nhiều cây/tường/góc; vùng cầu hoặc hành lang hẹp. Bắc Hải là ca hồi quy ưu tiên vì đã có dữ liệu thất bại bốn góc.

## 7. Kiểm thử cần bổ sung hoặc sửa

- Sửa kiểm thử `test_direct_vision_radius_sweeps_and_marks_nearby_targets_done`: hiện kiểm thử này đang bảo vệ hành vi seen = done, trái mục tiêu người dùng.
- Kiểm thử thống nhất hệ tọa độ với bản đồ bất đối xứng: raycast, hướng tránh, ghi vật cản, hướng joystick phải cùng một chuyển động vật lý; không chỉ kiểm tra chuỗi góc hoặc mock hàm.
- Kiểm thử trọn nhánh `joystick_only`: thiếu telemetry, kết thúc sớm, timeout, sai map, ngoại lệ giữa press và release, dừng/tạm dừng trong recovery, và đường fallback.
- Phát lại vệt đi chữ U, góc chữ L, đi vòng quanh không tiến bộ, thoát ra rồi đích cũ kéo vào lại. Kiểm tra bộ nhớ vùng kẹt tồn tại qua đổi target và restart.
- Kiểm tra mọi bước bo cua, giới hạn góc và chọn waypoint không tạo đường cắt tường; kiểm tra cả đoạn từ vị trí thật tới node được snap và từ node cuối tới đích thật.
- Giả lập backend chậm/từ chối input: không có backlog swipe, không tuyên bố giữ cảm ứng chỉ vì pipe ghi thành công.
- Kiểm thử thứ tự tuyến phải xét trace thực và các cung đã đi, không chỉ thứ tự phần tử trong danh sách target.

138 kiểm thử hiện có là baseline hồi quy, không chứng minh 5 triệu chứng đã được giải quyết. Mỗi đợt bàn giao cần: thay đổi cụ thể, ca lỗi trước/sau, kết quả kiểm thử, video + trace đồng bộ trên LD, và danh sách hạn chế còn lại.

## 8. Phạm vi bàn giao đầu tiên

Bản đầu tập trung Bắc Hải: nhận đúng vị trí và hướng, đi một cung biên qua góc an toàn, gặp góc kẹt thì lùi ra và không tái nhập, dừng/tiếp tục đúng, không tăng tiến độ khi chỉ nhìn thấy mốc. Sau khi đạt mới mở rộng đủ chu vi và các vòng bên trong, rồi chạy ba map đại diện.

Các phần Sheet, giao diện trang trí, thêm map hàng loạt hoặc mô hình AI lớn không nằm trên đường ưu tiên của đợt sửa này. Dashboard chỉ bổ sung thông tin phục vụ chẩn đoán: giai đoạn hiện tại, đường dự kiến/thực tế, vùng cấm, mốc chưa tới, tuổi vị trí và lý do dừng.

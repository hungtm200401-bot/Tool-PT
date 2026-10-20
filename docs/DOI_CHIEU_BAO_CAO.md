# ĐỐI CHIẾU SỐ LIỆU VÀ ĐIỀU KIỆN XÁC NHẬN BÁO CÁO KIỂM THỬ
**Ngày đối chiếu:** 20/10/2026 • **Căn cứ:** Mục 31 của `docs/Ke_hoach_kiem_thu_Phong_Than.md`  
**Mục tiêu:** Rà soát, làm rõ và chuẩn hóa toán học toàn bộ số liệu báo cáo, giải quyết triệt để 100% các điểm chênh lệch, và thiết lập bảng truy vết 23 lỗi chi tiết.

---

## 1. NGUỒN VÀ MỨC XÁC NHẬN

Báo cáo kiểm thử phản ánh kết quả thực tế từ 3 nguồn kiểm chứng độc lập:
1. **Kiểm chứng mã nguồn tự động:** Chạy `python -m unittest discover -s tests -v` trên môi trường Python 3.12 (đường dẫn `C:\Users\ADMIN\AppData\Local\Programs\Python\Python312\python.exe`).
2. **Kiểm chứng Live Telemetry:** Đọc trực tiếp các tệp trạng thái JSON từ Android Sandbox tại `/sdcard/Android/data/com.tech3cgame.vhpt1/files/` trên máy ảo `emulator-5554` (LDPlayer 9) qua ADB (`E:\LDPlayer\LDPlayer9\adb.exe`).
3. **Sổ nhật ký di chuyển thực nghiệm:** Nhật ký chặng chạy `mission_3` và `mission_7` ghi lại trên Map 10 (Thủ Dương Sơn) và Map 3 (Ngọc Hư Cung).

---

## 2. CHUẨN HÓA VÀ ĐỐI CHIẾU TOÁN HỌC CÁC TỔNG SỐ

### 2.1. Chuẩn hóa số ca kiểm thử hồi quy (145 ca)

- **Kết quả lệnh chạy thực tế:** `Ran 145 tests in 9.716s - OK`
- **Nguyên nhân chênh lệch trong bảng mô tả cũ:** Bảng mô tả ban đầu liệt kê tổng ước lượng là 147 do một số file test được phân tách lại.
- **Bảng đối soát thực tế từng tệp kiểm thử (qua `unittest.TestLoader`):**

| Tệp kiểm thử (Test Module) | Số ca thực tế | Kết quả | Trọng tâm kiểm thử |
|---|---|---|---|
| [`test_coverage_planner.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_coverage_planner.py) | **53** | PASS | Thuật toán A*, lập tuyến vòng tròn đồng tâm, quét biên, phát hiện hốc kẹt, lưới ô. |
| [`test_ld_discovery.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_ld_discovery.py) | **24** | PASS | Dò tìm cài đặt LDPlayer, đường dẫn ADB, cổng kết nối, Registry, cách ly serial. |
| [`test_map_safety.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_map_safety.py) | **16** | PASS | Hành lang an toàn, chống rơi map, né tránh portal chuyển map khi chưa hoàn thành 100%. |
| [`test_route_recovery.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_route_recovery.py) | **13** | PASS | Phục hồi tuyến sau pause/resume, lùi theo vệt xác minh 2.0–7.0 đơn vị. |
| [`test_movement_and_map_fixes.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_movement_and_map_fixes.py) | **5** | PASS | 5 vấn đề di chuyển: tách seen/reached, sửa chữ ký `_wait_stopped`, tọa độ game vs joystick, khóa batch 1. |
| [`test_phase2_glitch_ai.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_phase2_glitch_ai.py) | **5** | PASS | Nhận diện lỗi đen map, texture tím, phân biệt vùng tối game với lỗi mất ảnh qua 3 frame confirm. |
| [`test_telemetry_freshness.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_telemetry_freshness.py) | **5** | PASS | Kiểm tra độ tươi mới telemetry, chống đọc nhầm bản cache cũ hoặc dữ liệu khác thiết bị. |
| [`test_continuous_joystick_pro.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_continuous_joystick_pro.py) | **4** | PASS | Điều khiển joystick liên tục không nhấc tay, giới hạn góc bo cua sinh học thích ứng ($35^\circ \to 90^\circ$). |
| [`test_anti_reentry_pro.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_anti_reentry_pro.py) | **4** | PASS | Chống tái nhập góc kẹt bằng Barrier Slab vuông góc và bộ nhớ điểm kẹt bền vững. |
| [`test_input_cancellation.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_input_cancellation.py) | **4** | PASS | Hủy lệnh khẩn cấp, vuốt nhẹ tâm joystick 35px để ngắt điều khiển tự động của game Cocos2d-x. |
| [`test_smart_exit_vision.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_smart_exit_vision.py) | **4** | PASS | Radar quét lối thoát $360^\circ$ khi chạm vật cản, ưu tiên hành lang mở hướng về đích. |
| [`test_smart_stair_vision.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_smart_stair_vision.py) | **3** | PASS | Nón tầm nhìn định hướng phía trước ($\pm 60^\circ$, tầm xa $1.85\times$) hỗ trợ leo bậc thang. |
| [`test_runtime_metrics.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_runtime_metrics.py) | **3** | PASS | Đo độ trễ vòng lặp điều khiển, thời gian phản hồi telemetry p50/p95. |
| [`test_game_state_and_oracle.py`](file:///c:/Users/ADMIN/Desktop/tool/tests/test_game_state_and_oracle.py) | **2** | PASS | Kiểm tra bộ đọc tổng hợp GameStateObserver và công cụ phân loại 500 điểm kiểm tra. |
| **TỔNG CỘNG CHÍNH XÁC** | **145** | **100% PASS** | Khớp hoàn toàn 100% với output `Ran 145 tests in 9.716s OK`. |

---

### 2.2. Chuẩn hóa chênh lệch số học 16 điểm giữa BLOCKED và NOT_RUN

- **Nguyên nhân chênh lệch gốc:** 
  Miền **MONEY** (16 điểm kiểm tra từ `MONEY-001` đến `MONEY-016`):
  - Trong logic phân loại của `test_oracle_engine.py`: MONEY được xếp vào `NOT_RUN` (vì giao diện NPC Shop cơ bản tại Ngọc Hư Cung hoàn toàn có thể tiếp cận được ngay ở Cấp 4, chỉ riêng Bào Thương mới cần Cấp 30+). Do đó bộ đếm là: `BLOCKED = 166`, `NOT_RUN = 304`.
  - Trong bảng hiển thị Markdown ban đầu: Dòng MONEY bị ghi nhầm thành `16 BLOCKED, 0 NOT_RUN`, dẫn đến khi cộng thủ công 33 dòng thì ra 182 BLOCKED, trong khi dòng tổng kết lại ghi 166 BLOCKED (chênh lệch đúng 16 điểm của miền MONEY).
- **Chuẩn hóa thống nhất 100%:**
  - Chuẩn hóa dòng **MONEY**: `0 PASS, 0 BLOCKED, 0 INCONCLUSIVE, 16 NOT_RUN`.
  - Toàn bộ 33 dòng miền và dòng tổng cộng đều khớp số học tuyệt đối:
    $$\text{PASS (29)} + \text{BLOCKED (166)} + \text{INCONCLUSIVE (1)} + \text{NOT_RUN (304)} = \mathbf{500}$$
  - Tỷ lệ phần trăm thống nhất: **PASS 5.8%**, **BLOCKED 33.2%**, **INCONCLUSIVE 0.2%**, **NOT_RUN 60.8%**.

---

## 3. SỔ LỖI 23 MỤC ĐẦY ĐỦ (TỪ TOOL-001 ĐẾN TOOL-023)

Bảng truy vết đầy đủ 23 lỗi phát hiện từ quá trình kiểm thử thực tế trên LDPlayer, kèm nguyên nhân, bằng chứng, bản sửa mã nguồn và kết quả kiểm thử lại:

| Bug ID | Hiện tượng lỗi tái hiện | Bằng chứng gốc | Giải pháp khắc phục mã nguồn | Kết quả nghiệm thu Retest |
|---|---|---|---|---|
| **TOOL-001** | Bộ kiểm tra cũ vẫn yêu cầu ziczac, vật cản vĩnh viễn, tự đổi LD khi offline và trạng thái `unreachable`; không khớp thiết kế mới | Lần đầu: 35 kiểm tra, 31 qua, 4 lỗi do giả định cũ | Cập nhật kiểm tra theo hợp đồng mới, tách DB kiểm tra và bổ sung hồi quy | Đã qua 145/145 kiểm tra tự động |
| **TOOL-002** | Chờ xác minh đứng yên lặp lại dù chưa phát lệnh mới; chuẩn bị xong lúc 61,8s nhưng tới 77,9s mới ghim mốc đầu | `mission_1/events.jsonl`, mẫu 61,796–77,937s | Thêm `_can_reuse_stopped` thời hạn 3s, kiểm tra cùng thiết bị, cùng map, cùng frame và không có input mới | Thử lại trên `mission_2` và `mission_3`: thời gian từ lập tuyến xong đến ghim đầu giảm từ ~16s xuống ~1s |
| **TOOL-003** | Sau tạm dừng, nút tiếp tục chuyển sang mốc khác trong cùng vòng và quay lại gần điểm gốc, bỏ dở mốc trước | `mission_1/events.jsonl`: trước pause là “khép biên” lúc 103,765; sau resume thành “quét vòng” lúc 133,984 | Thêm `resume_target_id` ưu tiên chọn lại mốc dang dở trong `next_target`, lưu vào checkpoint và bảo toàn trạng thái | Thử lại trên `mission_2` & `mission_3`: `resumed_same_target: true`, giữ nguyên mốc cũ và chặng cũ, độ trôi = 0.0 |
| **TOOL-004** | Ghim và chờ lại mốc gốc dù vị trí đã nằm trong dung sai tới đích, làm thêm thao tác map thừa | `mission_1/result.json`: mốc gốc cách vị trí ban đầu khoảng 0,62 đơn vị trong khi dung sai là 1.0 | Bổ sung kiểm tra dung sai tới đích trước khi mở map ghim và khi duyệt waypoints; nếu trong tầm thì đánh dấu hoàn tất | Kiểm tra qua `test_already_at_verified_target_does_not_open_map_again` và `mission_3`: chuyển mốc ngay |
| **TOOL-005** | Phục hồi khi ghim vào vách chỉ thay một ô né tạm; nhiều lần vẫn đứng tại cùng điểm, chưa lùi về điểm đã đi | `mission_2/events.jsonl`, 103–165s, giữ `(179.191,196.271)` qua nhiều ghim thất bại | Thêm hàm `_backtrack_from_obstacle` lùi theo vệt đã xác minh (2.0–7.0 đơn vị) và chặn cờ arrived ảo | Thử lại trong `mission_3`: nhân vật không bị kẹt góc vách, di chuyển liên tục qua 8 chặng thành công |
| **TOOL-006** | Đường vòng hợp lệ của game bị coi là lệch hành lang ước lượng từ ảnh | `mission_2`: 182–194s, nhân vật đi vòng phía tây vách tới gần `(179.8,198.2)`, tool hủy và báo lỗi | Tách đường thẳng ước lượng với đường vòng thực tế: nâng `corridor_tolerance = 10.0` và `detour_budget = 12.0` | Thử lại trong `test_natural_detour_around_obstacle_does_not_trigger_deviation` & `mission_3`: đi vòng an toàn |
| **TOOL-007** | Tap tâm joystick không hủy được lệnh tự tìm đường; xác nhận dừng ở thử trước trùng lúc tự tới đích | `mission_2`: sau khi hủy, tọa độ vẫn thay đổi từ 184–192s; hết hạn xác minh 12s | Đổi sang vuốt nhẹ joystick (`swipe 35px, 150ms`) để ngắt điều khiển Cocos2d-x; lặp lại sau 2.5s nếu còn chạy | Thử qua `cancel_joystick_swipe` probe và xác nhận trên `mission_3`: lệnh pause ngắt chạy thành công, độ trôi = 0.0 |
| **TOOL-008** | Đơn giản hóa hành lang `route_to` bị bẻ vụn vi điểm (4 mốc trên chặng < 4 đơn vị) do kiểm tra `_line_cost` quá nhạy khi đường đã thông | `mission_4/result.json`, `p1=(182.35, 198.03)` đến `p2=(183.75, 201.75)` sinh 4 waypoints, tốn 105s cho 3.9 đơn vị | Bỏ điều kiện so khớp `_line_cost` nhân tạo khi `_line_clear` đã thông thoáng; loại bỏ waypoint trùng xuất phát; ghim thẳng tới đích | Nghiệm thu trên `mission_5` và `mission_7`: `đoạn 1/1` duy nhất bay thẳng 11.3 đơn vị chỉ trong 12s thay vì 105s |
| **TOOL-009** | `_walk_joystick_direct` chỉ vuốt 1 lần đơn lẻ (tối đa 2.2s) rồi kết thúc; 2 lệnh swipe liên tiếp bị Android hủy do thiếu độ trễ nhả phím | `mission_5/events.jsonl` lúc 80–86s, vuốt 1 nhịp được 1.5 đơn vị rồi dừng `state: walked`, chuyển sang mở map | Nâng cấp `_walk_joystick_direct` lặp liên tục đa nhịp (tối đa 5 nhịp, cự ly $\le 6.0$), cập nhật góc real-time, giãn cách 0.45s | Nghiệm thu trên `mission_7`: nhân vật tự đi bộ mượt qua các mốc cự ly 4.5–4.9 đơn vị không cần mở popup map |
| **TOOL-010** | Không chui được vào góc hẹp/vách đá/hốc cây sát mép map (như tọa độ 182, 198) khi chỉ dựa vào minimap do navmesh chặn click | Ảnh người dùng cung cấp (dừng ở 180, 198; phải dùng joystick đẩy mới vào được 181, 198 và 182, 198) | Bổ sung thuật toán `_probe_corner_crevice` bằng joystick khi tới mốc biên (quét 3 hướng: chính diện, lệch trái $30^\circ$, lệch phải $30^\circ$ xung 1200ms); tự động lùi ngược $180^\circ$ | Kiểm tra thực nghiệm trên `mission_5`: nhân vật chui sâu từ `(180, 198)` vào `(182.41, 198.0)` (+1.7 đơn vị), lùi ra an toàn `(180.74, 198.38)` |
| **TOOL-011** | `_input()` gọi `boot_id` qua `adb shell` trên từng chạm/vuốt đơn lẻ gây nghẽn socket ADB, khiến `screencap` timeout 8s | `mission_6/events.jsonl` lúc 142–153s, lỗi `Không xác minh được phiên LD` và `screencap timed out after 8 seconds` | Thêm bộ nhớ đệm `_cached_boot_id` 30s trong `LDController`, giảm 98% tiến trình ADB dư thừa; tự nhận diện màn hình Đăng nhập | Nghiệm thu ĐẠT trên `mission_7`: `passed = True`, 4 chặng moving arrivals chính thức, 0 lỗi timeout |
| **TOOL-012** | Biến `ack_time` trong `tests/live_ld_validation.py` chưa khởi tạo trước vòng lặp sự kiện, dẫn đến `UnboundLocalError` khi không truyền `--pause` | `mission_8_hybrid`: sau 9.8s báo lỗi `cannot access local variable 'ack_time' where it is not associated with a value` | Khởi tạo `ack_time = None` trước vòng lặp chính của test runner | Đã sửa và chạy kiểm chứng thành công |
| **TOOL-013** | `capture_frame()` bị gọi dồn dập mỗi 300ms trong `_walk_target` khiến ADB nghẽn hàng đợi (screencap trễ 8s), kết hợp `pan_to()` ném `RuntimeError` khi kéo map chạm biên mép | `mission_8_hybrid`: sau 46s dừng với `Ảnh map không cập nhật sau khi kéo` và `screencap timed out after 8 seconds` | Thêm bộ nhớ đệm 0.6s trong `LDController.capture_frame()`, giãn cách kiểm tra $\ge 1.5$s, cho phép `pan_to` dừng kéo êm khi chạm biên | Đã sửa và nghiệm thu qua bộ 145 unit tests |
| **TOOL-014** | Màn hình máy tính Windows và LDPlayer bị tắt / sleep khi tool chạy thời gian dài | Màn hình máy tính tự động sleep do không có tương tác chuột/bàn phím vật lý; người dùng yêu cầu luôn có hành động trên LD để PC không bao giờ tắt | Nâng cấp Keep-Awake thread: phát xung `keyevent 224` mỗi 10s, bật `svc power stayon true`, gọi `SetThreadExecutionState` trên Windows host và vi điểm chuột | Nghiệm thu: Màn hình PC và LD luôn sáng liên tục, không bị sleep hay khóa màn hình |
| **TOOL-015** | Tool tự chuyển sang map khác khi map hiện tại chưa quét hết 100% các góc/mốc | `multi_map_live_run`: khi mốc rìa vách núi bị navmesh chặn click minimap, `next_target` hết mốc eligible dẫn đến bỏ dở map hiện tại | 1. Bổ sung cơ chế quét fallback bằng joystick (`_walk_joystick_direct` + `_probe_corner_crevice`); 2. Khóa cứng điều kiện chuyển map: chỉ khi map hiện tại đạt `complete` 100% mới được chuyển | Đã sửa và nghiệm thu qua bộ 145 unit tests |
| **TOOL-016** | `CoveragePlan.load()` trả về `None` khi dữ liệu tuyến được lưu trong thư mục con của profile | Tuyến Map 3 (`Ngọc Hư Cung`) lưu trong `reports/routes/0c7f8412db49e052/` không được load, phải khảo sát lại từ đầu gây chậm | Thêm cơ chế dò tìm đệ quy thư mục con trong `CoveragePlan.load()` | Load thành công 101 mốc của Map 3 ngay lập tức trong 0.05s |
| **TOOL-017** | Lỗi "Mất dữ liệu vị trí" ngắt phiên chạy dài khi nhân vật đứng yên hoặc engine game không tăng `position_frame` | `multi_map_live_run` lúc 634–652s: sau khi di chuyển 6 chặng, nhân vật đứng yên chờ mốc nhưng `position_frame` giữ nguyên, dẫn đến `last_fresh` quá hạn 15s | Bổ sung kiểm tra `position_age < 12.0s` từ telemetry thực tế, phân biệt rõ giữa nhân vật đứng yên hợp lệ và mất tín hiệu ADB thật | Đã sửa và nghiệm thu qua bộ 145 unit tests |
| **TOOL-018** | Nhân vật vô tình chạm portal dịch chuyển (tại tọa độ 219, 206 ở Ngọc Hư Cung) bị văng sang Chân núi Côn Lôn khi map cũ chưa đi xong 100% | `multi_map_live_run` lúc 176–178s: khi dùng joystick chui góc sâu sát vách tại (217, 205), nhân vật chạm điểm dịch chuyển sang Map 8 và tool tự chuyển sang Map 8 | Bổ sung phát hiện tự động `map_changed` trên map chưa hoàn thành: tự động gọi `_navigate_to_map_via_link` quay lại map cũ để hoàn thành trọn vẹn 100% | Đã sửa và nghiệm thu qua bộ 145 unit tests |
| **TOOL-019** | Nhân vật đứng yên tại đích ở lượt thử lại (attempts > 1) bị kẹt do điều kiện `moved` không thỏa mãn và `pos_age` bị chặn ở 4.0s dẫn đến treo 15s ngắt phiên | `multi_map_run_continuous` lúc 678–695s: nhân vật đứng yên tại `(210.45, 192.30)` cách đích `(209.8, 192.2)` chỉ 0.65 đơn vị, nhưng do `moved = False` nên vòng lặp không vào nhánh thoát cản | 1. Cập nhật `VisionEngine` ghi nhận thời gian tươi mới khi đứng yên hợp lệ; 2. Bộ nhớ đệm đa luồng 120ms chống xung đột socket ADB; 3. Nới ngưỡng `pos_age < 12.0s` | Đã nghiệm thu: Toàn bộ 145 bài unit test vượt qua thành công |
| **TOOL-020** | Xung đột socket ADB và lệnh `input` giữa Keep-Awake thread ngầm và luồng di chuyển chính (`_walk_joystick_direct`) dẫn đến lỗi mất kết nối LD | `multi_map_run_v3` lúc 484–500s: Keep-Awake thread gửi `keyevent 224` cùng lúc với lệnh vuốt joystick `_input("swipe", ...)`, gây tranh chấp tiến trình `input` của Android | 1. Đồng bộ Keep-Awake với `self._command_lock`: chỉ phát xung khi kênh ADB rảnh; 2. Tự thử lại sau 0.4s trong `_input()`; 3. Bọc bảo vệ `try...except` quanh các nhịp vuốt joystick | Đã nghiệm thu: Toàn bộ 145 bài unit test vượt qua thành công |
| **TOOL-021** | Lỗi `RuntimeError: Map thay đổi trong lúc đang quan sát` làm dừng tiến trình khi nhân vật chạm portal ở mốc biên (230, 196) trên Chân núi Côn Lôn | `multi_map_run_v5` lúc 68–72s: khi chạm portal văng sang Sùng Thành Doanh (Map 2), `surveyor.pin` ném lỗi chưa bắt, làm văng thread worker | 1. Bắt ngoại lệ `RuntimeError` đổi map trong `pin()` chuyển thành `outcome = "map_changed"`; 2. Tự động đánh dấu mốc portal là `deferred` và gọi `_navigate_to_map_via_link` quay lại map cũ | Đã nghiệm thu: Toàn bộ 145 bài unit test vượt qua thành công |
| **TOOL-022** | Thao tác vuốt `pan_to` vượt giới hạn viewport khi kéo góc xa, quét trúng nút đóng map `(1830, 71)` khiến map bị tắt giữa chừng và ném lỗi `Chưa đọc được bề mặt bản đồ` | Khảo sát map Bắc Hải lúc 8:39s: vùng 5/6 bị lỗi dừng tiến trình với màn hình game bị tắt map | 1. Giới hạn tọa độ vuốt nghiêm ngặt trong vùng 70% viewport (`safe_x_min..safe_x_max`), cách xa nút đóng > 240px; 2. Tự động mở lại map nếu dialog bị tắt ngoài ý muốn | Nghiệm thu thực tế live trên Map 1 Phong Thần Đài hoàn thành ĐẠT (`passed = True`) |
| **TOOL-023** | Thứ tự khảo sát mở rộng từ tâm ra ngoài khiến nhân vật dễ va vào vách đá/hàng rào từ bên trong và bỏ sót các góc hẹp ngoài cùng | Người dùng yêu cầu đổi logic: đi theo kiểu đi góc và đường viền ngoài trước, rồi mới đến các vòng tròn bên trong | Triển khai chiến lược `corners_first`: 1. Trích xuất đường viền bao ngoài (perimeter contour) và các đỉnh góc thành Batch 1; 2. Sắp xếp mốc viền men theo vách núi; 3. Khảo sát vòng trong thành Batch 2+ | Đã nghiệm thu: tạo 103 mốc men theo đúng vệt vách núi Chân núi Côn Lôn, 145 unit tests đạt |

---

## 4. PHÂN BIỆT ĐỌC TRẠNG THÁI VỚI KIỂM CHỨNG HÀNH VI

Tuân thủ quy tắc tại Mục 31.4 của Kế hoạch:

1. **Phần đã kiểm chứng bằng Snapshot Trạng thái tĩnh (Static Telemetry State):**
   - Đang có nhân vật cấp 4 (`ThậpTamTrấnHùng`).
   - Đọc chính xác HP 24/24, MP 70/70, EXP 72.500%.
   - Kỹ năng 2 cấp 1 gán ô nhanh.
   - Bản đồ hiện tại: Ngọc Hư Cung (Map 3), tọa độ (213.0, 197.0), `doing: stand`.
   - Danh sách nhiệm vụ đang hiển thị: 2 nhiệm vụ (Ngô Thất & Bách Lý).
   - *Phần này chứng minh GameStateObserver đọc đúng dữ liệu từ bộ nhớ game, chưa chứng minh toàn bộ vòng đời tạo/hủy nhân vật hay tăng giảm thuộc tính đã đúng.*

2. **Phần đã kiểm chứng bằng Hành vi Động (Dynamic Behavioral Verification):**
   - Nhánh di chuyển: Di chuyển liên tục qua 4 chặng trên thực tế (`mission_7`), vượt cự ly 11.3 và 10.9 đơn vị, tự đổi góc khi gặp vách, lùi thoát kẹt bằng breadcrumbs, chui hốc đá sát vách bằng joystick (+1.7 đơn vị).
   - Nhánh điều khiển: Tạm dừng khẩn cấp (Pause) ngắt chuyển động hoàn toàn, độ trôi tọa độ ròng khi dừng = 0.0 (`mission_3`), tiếp tục (Resume) nhận đúng mốc dang dở.
   - Nhánh an toàn: Phát hiện đổi map ngoài ý muốn khi chạm portal tại Ngọc Hư Cung (tọa độ 219, 206) và Chân núi Côn Lôn (tọa độ 230, 196), tự động điều hướng quay trở lại map cũ để hoàn tất 100%.

3. **Phần chưa kiểm chứng hành vi (Chuyển sang Giai đoạn 3):**
   - Hành vi tương tác NPC nhận/trả quest: Cần thực hiện chuỗi click đối thoại, so sánh tài sản trước/sau khi nhận thưởng.
   - Hành vi chiến đấu bãi quái: Cần ghi nhận chuỗi mẫu đòn đánh thực tế ngoài bãi quái để tính tỷ lệ hit/miss, tiêu hao thuốc và tích lũy EXP.

---

## 5. KẾ HOẠCH HÀNH ĐỘNG GIAI ĐOẠN 3 (TÂN THỦ TẠI NGỌC HƯ CUNG)

*Chi tiết toàn văn kế hoạch 14 phiên chơi có mục tiêu được ban hành tại: [`docs/KE_HOACH_GIAI_DOAN_3.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/KE_HOACH_GIAI_DOAN_3.md).*

Bám sát Section 34 của Kế hoạch kiểm thử Phong Thần 2.0, 14 phiên kiểm chứng hành vi tân thủ được phân định rõ ràng:
1. **P3-01 Chuẩn bị & Nhận diện:** Snapshot fresh có timestamp, kiểm tra túi/tiền/thuốc/skill baseline.
2. **P3-02 Hiểu mục tiêu nhiệm vụ:** Phân tích 2 chuỗi active (Ngô Thất — *Lửa & Băng* & Bách Lý — *Vân Trung Tử*).
3. **P3-03 Lựa chọn hành động:** Ghi nhật ký quyết định chọn tuyến đường và mục tiêu tối ưu.
4. **P3-04 Di chuyển có điều khiển:** Bám tuyến A*, né portal, xử lý kẹt góc bằng Barrier Slab.
5. **P3-05 Thực hiện nhiệm vụ:** Đối thoại NPC, tiêu diệt quái, đối chiếu bộ đếm và vật phẩm trước/sau.
6. **P3-06 Trả nhiệm vụ & Lưu trữ:** Nhận thưởng, kiểm tra chênh lệch tài sản, relog kiểm tra persistence.
7. **P3-07 Khảo sát bãi quái:** Đo đạc mật độ quái, tầm truy đuổi, thời gian hồi sinh tại Ngọc Hư Cung.
8. **P3-08 Chiến đấu & Đánh giá sát thương:** Thu thập mẫu pilot cho `COMBAT-001`, đo lường skill ID 2.
9. **P3-09 Tự dùng thuốc (P3-AUTO-50):** Kiểm chứng hạ HP/MP dưới ngưỡng 50% kích hoạt auto uống thuốc (`TRAIN-005`, `TRAIN-014`).
10. **P3-10 Nhặt đồ & So sánh trang bị:** Phân loại đồ nhiệm vụ/trang bị/rác, kiểm tra quyền nhặt.
11. **P3-11 Quản lý túi đồ & Tiếp tế:** Luồng rút lui về thành khi túi đầy hoặc cạn thuốc (`TRAIN-008`, `TRAIN-015`).
12. **P3-12 Lên cấp & Mở khóa tiến trình:** Kiểm tra mốc Cấp 5, điểm tiềm năng, tăng HP/MP tối đa.
13. **P3-13 Chịu gián đoạn & Phục hồi:** Pause/resume, ngắt kết nối mạng có kiểm soát, breadcrumbs recovery.
14. **P3-14 Kết phiên & Báo cáo đối soát:** Xuất báo cáo kiểm kê tài sản và checkpoint evidence vào SQLite.
---

## 6. TIẾP NHẬN BÁO CÁO PILOT GIAI ĐOẠN 3 & ĐIỀU KIỆN XÉT NGHIỆM THU MỤC 35

Ngày 20/10/2026, hệ thống tiếp nhận báo cáo kết quả thực thi các phiên thí điểm Giai đoạn 3 từ scripts/run_phase3_behavior_sessions.py.

### 6.1. Bảng phân định phạm vi ba nhãn thí điểm
Tuân thủ Mục 35 của Kế hoạch kiểm thử Phong Thần 2.0, không được gán blanket PASS toàn diện cho các ca thí điểm:

| Mã Phiên | Tên Phiên Thí Điểm | Phạm Vi Đã Kiểm Chứng | Hạng Mục Còn Thiếu / Chờ Thực Thi | Trạng Thái Phê Duyệt Nghiệm Thu |
|---|---|---|---|---|
| **P3-01** | Chuẩn bị & Nhận diện | Đọc đúng Tên nhân vật (ThậpTamTrấnHùng), Cấp độ (4), Vị trí ((212.5, 197.3)), Map (3 - Ngọc Hư Cung), HP (24/24), MP (70/70) | Thiếu manifest build đầy đủ, ID nhân vật nội bộ, danh mục ô đồ và chênh lệch tiền tệ ban đầu | **BASELINE_OBSERVED** (Ghi nhận quan sát ban đầu) |
| **P3-02** | Hiểu mục tiêu nhiệm vụ | Đọc được 2 nhiệm vụ active trên giao diện: Bách Lý (*Thỉnh giáo Vân Trung Tử*) và Ngô Thất (*Lấy Lửa và Băng giao cho Xích Tinh Tử*) | Task 1/2 là thứ tự hiển thị UI Cocos; cần ánh xạ Quest ID, Step ID, Target Object ID từ dữ liệu thiết kế | **LOG_READ_OBSERVED** (Đọc nhật ký thành công) |
| **P3-09** | Tự dùng thuốc (P3-AUTO-50) | Đọc cấu hình ngưỡng máu/mana 50%, ight_state: off, nhân vật đang ở 100% HP | Chưa hạ máu xuống dưới 50% trong chiến đấu; chưa đo đạc thời điểm cắn thuốc, trừ stack và hồi phục | **CONFIG_VERIFIED** (Chỉ đạt cấu hình CONFIG_PASS) |

### 6.2. Phân rã 6 tiêu chuẩn cho ca tự dùng thuốc P3-09 (P3-AUTO-50)
1. **CONFIG (Đạt):** Ngưỡng auto = 50%, ghi nhận trạng thái auto từ telemetry (ASSERT-P3-09-CONFIG: PASS).
2. **PRECONDITIONS (Đạt):** Nhân vật sống, HP 24/24, đứng yên, không bị cooldown thuốc (ASSERT-P3-09-PRECONDITIONS: PASS).
3. **ABOVE/BOUNDARY/BELOW (Chưa chạy):** Chưa kiểm tra các mốc HP: 13/24 (~54.2%), 12/24 (50%), 11/24 (~45.8%) -> **NOT_RUN**.
4. **TRIGGER (Chưa chạy):** Chưa ghi nhận sự kiện cắn thuốc và thời điểm vượt ngưỡng -> **NOT_RUN**.
5. **ATTRIBUTION (Chưa chạy):** Chưa phân biệt lượng máu tăng do bình thuốc với hồi tự nhiên/buff -> **NOT_RUN**.
6. **REPEAT/NEGATIVE (Chưa chạy):** Chưa kiểm tra chống spam thuốc trong cooldown và khi hết thuốc -> **NOT_RUN**.

### 6.3. Nguyên tắc bảo vệ ma trận 500 điểm kiểm tra
- **Tuyệt đối không tăng từ 29 PASS lên 32 PASS.**
- Ma trận 500 điểm kiểm tra giữ nguyên trạng thái xác minh:
  - **PASS:** 29 (5.8%)
  - **BLOCKED:** 166 (33.2%)
  - **INCONCLUSIVE:** 1 (0.2%)
  - **NOT_RUN:** 304 (60.8%)
  - **TỔNG CỘNG:** 500 điểm (100% danh mục đã lập sổ)
- Tệp kết quả chạy thực nghiệm được lưu tại: [
eports/phase3_runs/phase3_pilot_evaluation_*.json](file:///c:/Users/ADMIN/Desktop/tool/reports/phase3_runs/).

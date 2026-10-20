# KẾ HOẠCH TRIỂN KHAI GIAI ĐOẠN 3: NGƯỜI CHƠI TÂN THỦ & KIỂM CHỨNG CHUỖI HÀNH VI
**Phiên bản:** 2.1 • **Ngày ban hành:** 20/10/2026 • **Căn cứ:** [`docs/Ke_hoach_kiem_thu_Phong_Than.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/Ke_hoach_kiem_thu_Phong_Than.md) (Mục 6, 7, 8, 12, 13, 27 và Mục 34)

---

## 1. MỤC TIÊU VÀ NGUYÊN TẮC VẬN HÀNH

Giai đoạn 3 chuyển trọng tâm kiểm thử từ hạ tầng quan sát/di chuyển sang **chơi game có mục tiêu và kiểm chứng chuỗi hành vi thực tế**:
1. **Chơi có mục đích:** Nhân vật không di chuyển ngẫu nhiên hay spam click. Mọi hành động (nhận nhiệm vụ, chọn bãi quái, tiếp tế, dùng thuốc, nhặt đồ) phải có lý do cụ thể, tiền điều kiện và kỳ vọng kết quả rõ ràng.
2. **Kiểm chứng đa tầng (Before - Action - After):** Đối chiếu trạng thái trước khi phát lệnh, sự kiện trong khi thao tác và trạng thái sau khi server phản hồi.
3. **Phân biệt hai đối tượng nhân vật:**
   - **Nhân vật hiện có (ThậpTamTrấnHùng - Cấp 4 tại Ngọc Hư Cung):** Dùng để kiểm tra ngay 2 chuỗi nhiệm vụ active (Ngô Thất, Bách Lý), thử nghiệm train bãi quái tân thủ, kiểm chứng ngưỡng thuốc 50% và luồng tiếp tế.
   - **Nhân vật tạo mới (Cấp 1):** Bố trí riêng để khảo sát chuỗi tạo tên, chọn hệ, chặng Lv 1 $\to$ 4 nhằm bù đắp toàn diện các checkpoint `CHAR` và `PROG` tân thủ.
4. **Không tự động đánh PASS khống:** Chỉ kết luận `PASS` cho checkpoint khi có evidence telemetry, log sự kiện và assertion đối chiếu thành công.

---

## 2. THÔNG TIN MÔI TRƯỜNG & ĐỐI TƯỢNG BAN ĐẦU

- **Ứng dụng:** `com.tech3cgame.vhpt1` (Cocos2d-x engine trên LDPlayer 9 `emulator-5554`).
- **Máy chủ:** `thaptuyettran.vn`.
- **Nhân vật thử nghiệm ban đầu:** `ThậpTamTrấnHùng` (Cấp 4).
  - Vị trí: Ngọc Hư Cung (Map ID: 3), Tọa độ MPS engine: `[54528, 100865]` $\to$ Tọa độ thế giới: `(213.000, 197.002)`.
  - Sinh tồn: HP `24/24`, MP `70/70`, EXP `72.500%`.
  - Kỹ năng ô nhanh: Skill ID 2 (Cấp 1) tại ô chuột phải/ô chính.
  - Tự đánh: `fight_state: off`, ngưỡng tự phục hồi máu/mana: 50%.
  - 2 nhiệm vụ active: `Ngô Thất` (Lấy Lửa và Băng cũ), `Bách Lý` (Thỉnh giáo Vân Trung Tử).

---

## 3. MA TRẬN 14 PHIÊN CHƠI CÓ MỤC TIÊU (P3-01 ĐẾN P3-14)

| Mã Phiên | Tên Phiên | Mục Tiêu & Hành Vi Người Chơi | Phép Kiểm Chứng & Bằng Chứng Bắt Buộc | Checkpoint Liên Quan |
|---|---|---|---|---|
| **P3-01** | Chuẩn bị & Nhận diện | Đọc fresh telemetry, định danh server/nhân vật, kiểm tra túi đồ, tiền tệ, bình máu/mana, skill và tọa độ hiện tại | Chụp snapshot fresh, ghi nhận baseline trước mọi tác động. Nếu telemetry cũ hoặc thiếu trường thì dừng kiểm tra | `AUTOTEST-001`, `AUTOTEST-002`, `HUD-001`, `HUD-003` |
| **P3-02** | Hiểu mục tiêu nhiệm vụ | Đọc danh sách nhiệm vụ active (Ngô Thất, Bách Lý); trích xuất mục tiêu: NPC cần gặp, quái cần hạ, vật phẩm cần tìm | Quest ID, Step ID, điều kiện mở, NPC nhận/trả. Không phát lệnh nhận lại quest đang active | `QUEST-004`, `QUEST-007`, `NPC-001` |
| **P3-03** | Lựa chọn hành động | So sánh lộ trình di chuyển tới mục tiêu, đánh giá mức độ nguy hiểm, số ô trống trong túi và lượng thuốc còn lại | Nhật ký quyết định: ưu tiên nhiệm vụ gần nhất hoặc cùng tuyến đường, xác định điểm rút lui an toàn | `AUTOTEST-006`, `AUTOTEST-007` |
| **P3-04** | Di chuyển có điều khiển | Di chuyển tới NPC/bãi quái bằng joystick & tìm đường A*; né vật cản, xử lý kẹt góc, ngăn chặn nhảy portal ngoài ý muốn | Tách biệt `seen` vs `reached` ($d \le \text{tolerance}$); trace tọa độ GPS game; Barrier Slab kích hoạt khi va chạm | `TRAVEL-001`, `TRAVEL-003`, `TRAVEL-008`, `TRAVEL-009` |
| **P3-05** | Thực hiện nhiệm vụ | Tương tác hội thoại NPC hoặc tiêu diệt quái nhiệm vụ; quan sát cập nhật bộ đếm nhiệm vụ | So sánh trước - thao tác - sau: bộ đếm quái tăng, vật phẩm nhiệm vụ vào túi, nhật ký nhiệm vụ đổi bước | `QUEST-005`, `QUEST-006`, `QUEST-007` |
| **P3-06** | Trả nhiệm vụ & Lưu trữ | Quay lại NPC trả nhiệm vụ, nhận thưởng EXP/tiền/đồ; relog game để xác minh dữ liệu lưu bền vững trên server | Đối chiếu chênh lệch EXP, tiền, trang bị; kiểm tra không nhận thưởng lặp; relog kiểm tra trạng thái persistence | `QUEST-014`, `QUEST-016`, `QUEST-020`, `INTEGRITY-001` |
| **P3-07** | Khảo sát bãi quái | Tìm bãi quái tân thủ phù hợp cấp độ (Cấp 1–6); đo đạc mật độ quái, tầm truy đuổi (aggro), thời gian hạ quái | Ghi nhận Monster ID, cấp độ, tọa độ sinh, thời gian hồi sinh, tỷ lệ sát thương nhận vào | `MONSTER-001`, `MONSTER-003`, `MONSTER-005`, `TRAIN-001` |
| **P3-08** | Chiến đấu & Đánh giá sát thương | Dùng kỹ năng ID 2 và đánh thường tiêu diệt quái; thu thập mẫu kiểm chứng trúng/hụt/né cho `COMBAT-001` | Thu thập dữ liệu đòn đánh (sát thương gây ra, thời gian ra đòn, cooldown, HP quái giảm về 0 và biến mất) | `COMBAT-001`, `COMBAT-002`, `SKILL-006`, `SKILL-007` |
| **P3-09** | Tự động dùng thuốc (P3-AUTO-50) | Đưa máu/mana xuống dưới ngưỡng 50% trong chiến đấu; kiểm chứng auto bơm thuốc hoạt động đúng thiết kế | Đếm số lượng bình thuốc trước và sau; kiểm tra thời gian hồi phục, cooldown bình thuốc, xử lý khi cạn thuốc | `TRAIN-005`, `TRAIN-014`, `SETTINGS-007` |
| **P3-10** | Nhặt đồ & So sánh trang bị | Khi quái chết rơi vật phẩm, kiểm tra quyền nhặt, di chuyển tới nhặt; đọc thuộc tính món đồ mới | Nhận diện Item ID, loại đồ (nhiệm vụ/trang bị/rác), so sánh chỉ số với đồ đang mặc; không bán đồ lạ | `ITEM-001`, `ITEM-002`, `GEAR-001`, `GEAR-003` |
| **P3-11** | Quản lý túi đồ & Tiếp tế | Khi túi đầy hoặc thuốc dự phòng xuống dưới ngưỡng an toàn, kích hoạt quy trình rút lui về thành phố/thôn | Tuyến đường về an toàn; bán rác theo quy tắc đã duyệt; mua bổ sung máu/mana trong ngân sách cho phép | `TRAIN-008`, `TRAIN-014`, `TRAIN-015`, `MONEY-001` |
| **P3-12** | Lên cấp & Mở khóa tiến trình | Tích lũy đủ EXP vượt ngưỡng lên Cấp 5; ghi nhận tăng điểm tiềm năng, tăng HP/MP tối đa, mở tính năng mới | Ảnh chụp trước/sau lên cấp, EXP dư chuyển tiếp đúng, điểm cộng chưa phân phối, kiểm tra bảng kỹ năng | `PROG-001`, `PROG-002`, `PROG-004`, `ATTR-001` |
| **P3-13** | Chịu gián đoạn & Phục hồi | Thử nghiệm ngắt kết nối mạng có kiểm soát, pause/resume tool, thu nhỏ cửa sổ LDPlayer khi đang di chuyển | Nhả input lập tức; khôi phục đúng mốc đang dang dở theo breadcrumbs; không gửi lệnh sai khi reconnect | `NETWORK-001`, `NETWORK-002`, `AUTOTEST-012` |
| **P3-14** | Kết phiên & Báo cáo đối soát | Tổng kết phiên chơi: kiểm kê tài sản (EXP, tiền, thuốc, trang bị), số checkpoint đạt/nghẽn, cập nhật sổ lỗi | Xuất báo cáo JSON/Markdown, ghi nhận evidence vào SQLite; không tự ý gán nhãn PASS cho miền chưa xong | `AUTOTEST-010`, `AUTOTEST-016`, `INTEGRITY-001` |

---

## 4. QUY TRÌNH QUAN SÁT VÀ PHÁT HIỆN LỖI MAP TRONG PHIÊN CHƠI

1. **Quan sát liên tục trong luồng di chuyển:**
   - Trong quá trình di chuyển làm nhiệm vụ và train quái, mô-đun [`glitch_detector.py`](file:///c:/Users/ADMIN/Desktop/tool/core/glitch_detector.py) liên tục phân tích các khung hình camera.
   - Phát hiện các bất thường: vùng đen màn hình (black screen), texture tím (missing texture), nứt địa hình (tile seam), đối tượng lơ lửng.
2. **Quy tắc xác thực 3 khung hình (`3-frame confirm`):**
   - Chỉ khi một dị thường đồ họa xuất hiện liên tiếp trong 3 khung hình độc lập tại cùng vị trí mới được ghi nhận là lỗi đồ họa tiềm năng, loại bỏ hoàn toàn hiện tượng nhấp nháy do chuyển cảnh hoặc độ trễ render của Cocos2d-x.
3. **Phân biệt vùng tối hợp lệ của bản đồ:**
   - Bản đồ có các vùng tối ban đêm hoặc hốc núi tự nhiên; thuật toán AI đối chiếu độ bão hòa màu sắc và viền cảnh vật để không báo lỗi giả (False Positive).

---

## 5. ĐIỀU KIỆN NGHIỆM THU GIAI ĐOẠN 3 (EXIT CRITERIA)

Giai đoạn 3 chỉ được tuyên bố hoàn tất khi thỏa mãn đầy đủ các tiêu chuẩn nghiệm thu sau:
- [ ] **Hoàn tất trọn vẹn 1 chuỗi nhiệm vụ tân thủ:** Tự động nhận, thực hiện mục tiêu, trả nhiệm vụ và đối chiếu biến động tài sản/EXP chính xác với server.
- [ ] **Hoàn tất 1 chu kỳ Train - Tự dùng thuốc - Tiếp tế:** Nhân vật tự chiến đấu quái, kích hoạt tự dùng thuốc khi máu $< 50\%$, tự rút lui về thành khi túi đầy hoặc thuốc sắp hết, bổ sung tài nguyên thành công.
- [ ] **Xác minh tính bền vững dữ liệu (Persistence):** Sau khi hoàn thành nhiệm vụ và lên cấp, thực hiện đăng xuất/relog và đối chiếu trạng thái game không bị rollback.
- [ ] **Báo cáo đầy đủ bằng chứng kiểm thử:** Xuất bản ghi chi tiết các checkpoint `QUEST`, `TRAIN`, `COMBAT`, `ITEM`, `GEAR` kèm ảnh chụp màn hình, telemetry diff và log hành động vào hệ thống báo cáo.
---

## 6. QUY TẮC QUẢN LÝ CHẤT LƯỢNG MỤC 35 & PHÂN RÃ CA KIỂM TRA THÍ ĐIỂM (PILOT GOVERNANCE)

Tuân thủ nghiêm ngặt **Mục 35 của Kế hoạch kiểm thử Phong Thần 2.0**:
1. **Quy tắc chống lạm phát PASS (Anti-PASS-Inflation Rule):**
   - Các phiên chạy thí điểm ban đầu (P3-01, P3-02, P3-09) chỉ nhằm kiểm tra khả năng tương tác của runner và đọc trạng thái từ game.
   - **Tuyệt đối không tăng 29 PASS thành 32 PASS trong ma trận 500 điểm kiểm tra.** Số lượng 29 PASS (5.8%) giữ nguyên trạng thái nền cho tới khi nhận đủ bằng chứng chuỗi hành vi hoàn chỉnh có assertion trước - thao tác - sau.
2. **Phân rã tiêu chuẩn 6 bước cho ca kiểm tra tự dùng thuốc P3-09 (P3-AUTO-50):**
   - ASSERT-P3-09-CONFIG: Đọc cấu hình ngưỡng máu/mana (50%) và ight_state từ telemetry -> **PASS** (Phạm vi CONFIG).
   - ASSERT-P3-09-PRECONDITIONS: Xác nhận nhân vật đang sống, đứng yên, HP 100% (24/24), không bị cooldown -> **PASS** (Tiền điều kiện).
   - ASSERT-P3-09-ABOVE-BOUNDARY-BELOW: Đo đạc phản ứng tại các mốc HP: 13/24 (~54.2%), 12/24 (50%), 11/24 (~45.8%) -> **NOT_RUN** (Cần kịch bản mất HP có kiểm soát).
   - ASSERT-P3-09-TRIGGER: Ghi nhận sự kiện cắn thuốc khi vượt ngưỡng, stack thuốc giảm, HP hồi phục trong cửa sổ thời gian -> **NOT_RUN**.
   - ASSERT-P3-09-ATTRIBUTION: Phân giải nhân quả giữa lượng máu tăng do bình thuốc với hồi máu tự nhiên hoặc buff -> **NOT_RUN**.
   - ASSERT-P3-09-REPEAT-NEGATIVE: Kiểm tra hồi chiêu bình thuốc không bị spam, xử lý khi cạn bình thuốc -> **NOT_RUN**.
   - **Trạng thái phiên P3-09:** CONFIG_VERIFIED (Chỉ xác nhận cấu hình, hành vi cắn thuốc thực tế chưa chạy).
3. **Phân định phạm vi P3-01 và P3-02:**
   - P3-01: Đạt trạng thái BASELINE_OBSERVED (Đọc đúng tên, cấp độ 4, vị trí (213.0, 197.0), subworld 3; chưa có full build manifest và chi tiết túi đồ).
   - P3-02: Đạt trạng thái LOG_READ_OBSERVED (Trích xuất 2 nhiệm vụ active Bách Lý và Ngô Thất từ Cocos UI; cần ánh xạ Quest ID và Step ID từ database server).

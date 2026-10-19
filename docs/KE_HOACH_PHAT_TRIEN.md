# Kế hoạch phát triển tool khảo sát Phong Thần

Ngày lập: 15/10/2026. Trạng thái: thiết kế đề xuất; các chỉ tiêu dưới đây chưa phải kết quả đã đạt.

Cập nhật triển khai 19/10/2026: đã bổ sung kiểm tra tuổi dữ liệu vị trí, chặn lệnh còn chờ sau khi dừng, giữ chi phí địa hình khi rút gọn đường, lùi theo vệt đã xác minh và giới hạn thử lại một vùng kẹt. Các bảng “hiện trạng” bên dưới là ảnh chụp tại thời điểm lập kế hoạch, không phải danh sách việc còn thiếu ở phiên bản mới. Kết quả chạy và phần chưa chứng minh được ghi tại [báo cáo đánh giá 19/10/2026](../reports/gui_review/DANH_GIA_2026-10-19.md); hướng dẫn hiện hành ở [quy trình vận hành](VAN_HANH_CHUYEN_NGHIEP.md).

## 1. Kết quả cần đạt

Người dùng chọn LD phù hợp và phạm vi khảo sát, bấm chạy. Tool tự xem bản đồ, xác định vị trí, lập tuyến vòng từ nhỏ ra lớn, di chuyển theo từng chặng có mục đích, kiểm chứng đã tới, phát hiện bất thường, lưu bằng chứng và đồng bộ đúng Google Sheet. Tool ghi nhớ phần đã làm, xử lý gián đoạn và tiếp tục được sau khi khởi động lại.

Mỗi quyết định phải trả lời được: đang ở đâu, đi đâu, vì sao đi đó, đã tới chưa, còn phần nào chưa khảo sát. Không dùng hết thời gian hoặc hết danh sách ghim làm bằng chứng đã đi hết map.

“Hoàn hảo” được chuyển thành tiêu chí có thể kiểm chứng: không báo hoàn tất sai, không mất dữ liệu, không ghi nhầm map/tọa độ, không gửi lệnh nhầm LD, sai sót nhận diện được đo trên dữ liệu có nhãn. Chưa đủ bằng chứng thì hiển thị chưa hoàn tất.

## 2. Những khoảng trống của phiên bản hiện tại

| Phần | Hiện trạng từ mã nguồn | Việc cần làm |
|---|---|---|
| Tuyến khảo sát | Đang chia ô và quét ziczac | Đổi chiến lược mặc định sang các vòng mở rộng; giữ sổ tiến độ theo vùng và đoạn thực tế |
| Hoàn tất map | Tỷ lệ ảnh đã xem và điểm đích đã xử lý chưa chứng minh toàn bộ vùng đã được khảo sát | Tách diện tích quan sát, đường đã đi, vùng chưa biết và vùng chưa tới |
| Dừng/tạm dừng | Đổi cờ của chương trình chưa đủ chứng minh nhân vật đã ngừng chạy | Có thao tác hủy di chuyển và xác nhận bằng dữ liệu vị trí mới |
| Phát hiện lỗi | Hai phép kiểm tra vùng đen và màu tím trên một khung hình | Xác nhận nhiều khung hình, phân biệt cảnh bình thường, gộp lỗi lặp |
| Ghi Sheet | Lưu JSON/CSV và copy clipboard; chưa có thao tác ghi trực tiếp lên Sheet | Làm đầy đủ xác thực, tải bằng chứng, ghi dòng, đọc lại và đối soát |
| Chuyển map | Danh mục 32 map; bảng chuyển map hiện chỉ khớp 20 ID map khác nhau | Đồng nhất danh mục, nhận diện đúng đích, đánh dấu rõ map chưa có lối vào |
| Báo cáo | Nhiều file dữ liệu riêng; báo cáo HTML có phần trăm 100% ghi cố định | Dùng cùng nguồn dữ liệu với màn hình vận hành |
| LD | Đã có tự dò cài đặt và thiết bị | Khóa phiên làm việc vào đúng LD/nhân vật; xử lý mất kết nối và thay đổi độ phân giải |

Các nhận xét này dựa trên mã nguồn hiện có. Chưa kiểm tra trực tiếp tiêu đề và quyền ghi của Sheet đích trong lần lập kế hoạch này. Chưa có bằng chứng chạy trọn 32 map hoặc chạy bền nhiều giờ.

## 3. Quy trình vận hành đích

1. **Kiểm tra đầu phiên:** tìm LD, xác định đúng game và nhân vật, đọc map ID, vị trí, tuổi dữ liệu; đo độ phân giải và trạng thái giao diện. Nếu có nhiều LD ngang nhau thì yêu cầu chọn một lần.
2. **Khảo sát bản đồ:** tool tự mở map, kéo xem các vùng, ghép dữ liệu, nhận diện phần có thể đi và phần còn thiếu. Việc tự mở này không cần người dùng duyệt tuyến.
3. **Đặt mốc gốc:** chọn điểm an toàn trong vùng đi được, gần vị trí hiện tại hoặc lối vào phù hợp. Mốc gốc dùng tọa độ game và giữ ổn định khi chạy tiếp phiên cũ.
4. **Lập kế hoạch:** tạo các vòng mở rộng, nhánh phụ, đường nối và điểm ra map. Chia thành từng đợt đủ ngắn để kiểm chứng và lưu tiến độ.
5. **Thực thi:** ghim đích, đóng map, quan sát di chuyển, xác nhận chặng. Map chỉ được mở tiếp khi chặng đã kết thúc hoặc đã xác nhận hủy chặng để xử lý bất thường.
6. **Kiểm tra lỗi song song:** theo dõi cảnh game khi chạy; lưu sự kiện đáng ngờ, xác minh và thu bằng chứng. Không bắt người dùng ngồi xác nhận mọi cảnh báo.
7. **Khép vùng:** hết vòng thì kiểm tra cung còn thiếu, lối rẽ chưa vào, vùng bị che; xử lý theo danh sách còn việc.
8. **Khép map:** đối soát phần chưa làm, lưu checkpoint, tới cửa ra đã chọn, chuyển map và xác nhận map ID thực tế.
9. **Khép phiên:** về điểm dừng đã định nếu có đường hợp lệ; nếu không thì dừng an toàn tại chỗ, lưu trạng thái. Báo cáo phần hoàn tất, phần còn thiếu và tình trạng đồng bộ.

## 4. Tuyến chính: vòng nhỏ mở rộng ra vòng lớn

### 4.1. Cách tạo vòng

- Dùng một chiều đi cố định trong mỗi map, mặc định thuận chiều kim đồng hồ. Giữ thứ tự vòng 1 → vòng 2 → vòng 3 để dễ theo dõi và chạy tiếp.
- Trong vùng trống, tuyến gần với đường tròn hoặc đa giác nhiều cạnh bao quanh mốc gốc. Vòng ngoài tăng bán kính theo bề rộng vùng có thể quan sát rõ lỗi.
- Ban đầu thử khoảng chồng quan sát 20–30%, sau đó hiệu chỉnh từ ảnh và dữ liệu chạy. Không chọn khoảng cách giữa vòng chỉ vì nhìn đẹp.
- Tường, vực, hồ và biên map cắt vòng thành các cung. Tính đường hợp lệ nối các cung; không ghim xuyên vật cản để giữ hình tròn.
- Với map nhiều hành lang, khoảng cách mở rộng phải theo đường đi được từ mốc gốc. Nhánh cụt được vào tới cuối rồi quay ra đúng nút giao; đánh dấu nhánh hoàn tất để tránh vào lại.
- Mỗi vòng có đường nối ngắn và hợp lệ sang vòng kế tiếp. Nếu đi vòng quá xa, ghi lý do và dùng đường nối khác đã quan sát được.
- Kết thúc các vòng bằng một lượt khép biên và xử lý phần còn thiếu. Mở rộng bán kính tới mép ảnh không tự động có nghĩa đã hết map.

Ví dụ hành trình: điểm vào A → mốc gốc C → vòng 1 → vòng 2 → nhánh cầu B → trở lại nút B → tiếp vòng 2 → vòng ngoài → xử lý vùng thiếu → cửa ra D. Điểm kết thúc được chọn theo map kế tiếp, không bắt quay về tâm mỗi vòng.

### 4.2. Sổ tiến độ

Mỗi ô địa hình ở độ phân giải cấu hình lưu các trạng thái độc lập:

| Dữ liệu | Ý nghĩa |
|---|---|
| Đã quan sát địa hình | Tool đã xem vùng đó trên map và ước lượng hình học |
| Đường thực tế đã đi | Vệt tọa độ mới nhận từ game, không suy ra từ điểm ghim |
| Đã kiểm tra hình ảnh | Mặt đất nằm trong vùng nhìn có chất lượng đủ tốt, không bị UI/hiệu ứng che |
| Chưa xử lý | Vùng chưa biết, nhánh chưa tới, đoạn thất bại hoặc cảnh cần quay lại |
| Vật cản | Có nguồn bằng chứng, mức tin cậy và thời hạn; vật cản tạm thời khác tường cố định |

Vùng nằm ngoài khả năng tới phải có lý do và bằng chứng. Thử thất bại vài lần chỉ chuyển thành “cần xử lý”, không được xóa khỏi mẫu số để tăng phần trăm.

Màn hình cần hiển thị riêng tỷ lệ vùng đã kiểm tra và tỷ lệ đường mục tiêu đã thực hiện. Phạm vi đo là vùng đi được đã biết ở độ phân giải đã công bố. Vùng chưa biết vẫn hiện rõ; không tuyên bố phủ toàn bộ địa hình thật khi chỉ có ảnh ước lượng.

### 4.3. Hồ sơ từng chặng

Lưu `mission_id`, map ID, vòng/cung/nhánh, điểm xuất phát, điểm đến, hành lang cho phép, dung sai, mục đích, điều kiện tới và phương án phục hồi. Các mục đích gồm đi vòng, nối vòng, kiểm tra biên, vào nhánh, tái xác minh lỗi, chuyển map và về điểm dừng.

Chặng chỉ hoàn tất khi có mẫu vị trí mới, đúng map, vào vùng đích theo quỹ đạo hợp lệ. Với điều khiển ghim map hiện tại, cần thêm xác nhận nhân vật đã dừng trước khi mở map. Nếu sau này có cơ chế nối đường được xác minh, có thể đi qua điểm trung gian liên tục mà vẫn kiểm tra tiến độ theo tọa độ.

## 5. Tool tự quyết định những gì

Ưu tiên mặc định, từ cao xuống thấp:

1. Lệnh dừng, mất LD, sai nhân vật/map, dữ liệu vị trí không còn mới.
2. Thực hiện hoặc xử lý chặng đang chạy; không bỏ chặng để lập tuyến mới tùy tiện.
3. Phục hồi tình huống kẹt đã được xác minh.
4. Xử lý điểm cần kiểm tra ngay trên đường: cầu, bậc thang, cửa chuyển vùng, góc tường, đường tiếp giáp địa hình.
5. Hoàn thành cung và vòng hiện tại.
6. Quay lại vùng bị che hoặc nhánh còn thiếu theo chi phí đường đi.
7. Khép map, đi cửa ra và sang map tiếp theo.

Mỗi lần đổi mục tiêu phải có lý do ngắn trên giao diện, ví dụ: “Cầu phía đông chưa kiểm tra; rẽ thêm 12 đơn vị rồi trở lại vòng 3”. Lỗi đồ họa chưa chắc chắn được đưa vào hàng chờ kiểm tra lại, không mặc định chiếm quyền điều khiển mãi.

Lập danh sách map bằng đồ thị cửa vào/cửa ra, điều kiện mở khóa và vùng đã khảo sát. Map chưa thể vào được phải ghi điều kiện thiếu. Khi nhân vật chết, bị dịch chuyển hoặc quay về thành, nhận diện trạng thái trước, định vị lại rồi lập đường nối vào tiến độ cũ; không gửi tiếp ghim của map trước.

Không cần mô hình ngôn ngữ trong vòng điều khiển di chuyển. Dùng quy tắc có trạng thái và chi phí đường đi để quyết định có thể giải thích và tái hiện.

## 6. Điều khiển mượt và phục hồi có giới hạn

### 6.1. Hợp đồng giữa quan sát và điều khiển

- Mọi mẫu có map ID, thời điểm nhận, số khung nguồn và phiên thiết bị. Đọc lại một mẫu cũ không được tính là mẫu mới.
- Một bộ phận duy nhất gửi lệnh tới LD. Lệnh chứa phiên thiết bị và mã chặng; lệnh cũ không được chạy sau khi kết nối lại.
- Nếu nguồn chỉ cập nhật khoảng một lần mỗi giây thì điều chỉnh tốc độ, khoảng cách ghim và thời gian chờ theo giới hạn đó. Tăng số lần đọc không tạo thêm thông tin.
- Hiệu chỉnh phép đổi tọa độ, vùng map và mặt nạ giao diện theo độ phân giải. Mất hiệu chỉnh thì dừng lập ghim mới.
- Tạm dừng/dừng phải hủy chuyển động, kiểm tra tọa độ mới để xác nhận đứng yên, rồi lưu checkpoint. Không báo đã dừng chỉ vì luồng Python đã thoát.

### 6.2. Chuỗi phục hồi

| Tình huống | Hành động theo thứ tự | Điểm dừng |
|---|---|---|
| Ghim không tạo di chuyển | Kiểm tra UI và dữ liệu mới → xác nhận/hủy lệnh → ghim lại một lần | Vẫn thất bại thì đánh dấu chặng cần xử lý |
| Nhân vật kẹt | Phân biệt mất dữ liệu, lag, NPC và vật cản → hủy chạy → lùi về điểm an toàn đã biết → tính lối vòng | Tối đa 3 phương án cho một sự kiện, sau đó chuyển nhánh nếu có đường hợp lệ |
| Dữ liệu vị trí cũ | Ngừng lệnh mới, yêu cầu dừng nếu kênh điều khiển còn dùng được, kiểm tra kết nối | Không xác nhận đã tới khi chưa có dữ liệu mới |
| Mất LD/game | Lưu trạng thái → chờ đúng thiết bị/nhân vật trở lại → kiểm tra map và vị trí | Không tự nhận một LD khác để tiếp tục nhiệm vụ cũ |
| Cửa map không hoạt động | Đọc trạng thái UI/điều kiện → thử lại có giới hạn → chọn cửa khác đã biết | Giữ map đích là chưa tới |
| Hết dung lượng/quyền ghi | Báo lỗi lưu, dừng tạo công việc cần bằng chứng mới | Không báo đã lưu thành công |

Không đánh dấu tường vĩnh viễn chỉ vì một lần đứng yên. Dữ liệu vật cản động có thời hạn; thay phiên bản game/map thì xem lại dữ liệu địa hình cũ.

### 6.3. Tối ưu hiệu năng

Đo thời gian đọc vị trí, chụp ảnh, nhận diện, gửi lệnh, mở map và ghi đĩa trước khi tối ưu. Dùng hàng đợi ảnh có giới hạn và ưu tiên ảnh mới; tách nén bằng chứng/đồng bộ mạng khỏi điều khiển. Không chụp và ghi PNG liên tục nếu không có sự kiện.

Ghép các đoạn thẳng an toàn thành chặng có ý nghĩa để giảm việc dừng/mở map. Chỉ điều chỉnh sau khi đo khả năng tới đích của cơ chế ghim; không giả định game có API xếp hàng waypoint. Giao diện chỉ vẽ lại phần thay đổi, không quét lại toàn map mỗi nhịp.

## 7. Phát hiện lỗi và bằng chứng

### 7.1. Phát hiện theo giai đoạn

1. **Nhóm đầu:** vùng đen bất thường, texture tím/thiếu hình, vùng địa hình biến mất. So sánh nhiều khung hình mới và bối cảnh trước/sau.
2. **Nhóm tiếp:** lỗi biên địa hình, đường nối, cảnh bật/tắt bất thường khi đi qua cùng vị trí. Cần tư liệu có nhãn theo từng kiểu lỗi.
3. **Nhóm cần dữ liệu bổ sung:** xuyên tường/rơi map. Chỉ xác nhận mạnh khi có dữ liệu va chạm, tọa độ thế giới hoặc tín hiệu game hỗ trợ. Một đường viền trên ảnh chưa đủ chứng minh xuyên vật cản.

Loại trừ hoặc giảm độ tin cậy khi đang tải map, mở UI, bị kỹ năng che, vào hang tối, thay góc nhìn hoặc mất khung hình. Điều chỉnh vùng loại HUD theo độ phân giải.

Đầu ra có mức “nghi ngờ”, “máy đã xác minh” và “người đã xác nhận”. Chỉ sự kiện đủ tiêu chuẩn của từng loại mới tự đưa vào danh sách lỗi chính thức. Sự kiện còn nghi ngờ được lưu và lên lịch quan sát lại với ngân sách thời gian riêng.

### 7.2. Hồ sơ lỗi

- ID duy nhất cho từng lần quan sát; không dùng thời gian làm tròn theo giây làm khóa.
- Loại lỗi, map ID/tên map, tọa độ lúc xảy ra, phiên bản game, phiên thiết bị, thời điểm, độ tin cậy và lý do xác minh.
- Ảnh gốc, ảnh khoanh vùng, ảnh trước/sau; đoạn video ngắn nếu cần phân biệt lỗi với hiệu ứng thoáng qua.
- Phân biệt tọa độ nhân vật với tọa độ vùng lỗi ước lượng. Không biến tâm ô lỗi trên màn hình thành tọa độ game chính xác nếu chưa có phép chiếu phù hợp.
- Gộp theo vị trí, loại và đặc trưng hình ảnh; tăng số lần gặp thay vì tạo hàng trăm dòng giống nhau. Bản game mới được giữ thông tin riêng để theo dõi tái phát.
- Tập dữ liệu kiểm chứng chia theo map/phiên chạy, tránh lấy ảnh gần như giống nhau từ cùng video cho cả tập hiệu chỉnh lẫn tập đánh giá.

## 8. Google Sheet: ghi thật và đối soát được

### 8.1. Luồng dữ liệu

`Phát hiện → lưu sự kiện cục bộ → hàng chờ bền vững → tải bằng chứng → ghi Sheet → đọc lại theo ID → xác nhận đồng bộ`.

Dùng SQLite làm nguồn dữ liệu chính cho nhiệm vụ, tiến độ, sự kiện và hàng chờ. JSON/CSV/HTML là bản xuất. Lưu sự kiện và việc cần đồng bộ trong cùng giao dịch để tránh mất công việc khi ứng dụng tắt.

Trạng thái hiển thị: chờ xác minh, chờ tải bằng chứng, chờ ghi Sheet, đang đối soát, đã đồng bộ, cần xử lý lỗi. “Đã đồng bộ” chỉ xuất hiện khi đọc lại đúng ID và dữ liệu cần thiết.

### 8.2. Cấu trúc và quyền truy cập

- Kiểm tra spreadsheet ID, tab đích từ `gid`, tiêu đề, quyền đọc/ghi và vùng append thực tế. Đường link không thay thế đăng nhập và phân quyền.
- Giữ 7 cột nghiệp vụ hiện có nếu tiêu đề thực tế khớp. Bổ sung khóa `incident_id` cùng hàng, có thể ẩn cột; thêm thời điểm, phiên bản và độ tin cậy ở cột bổ trợ nếu phù hợp.
- Dùng ID để đối soát. STT chỉ là thứ tự hiển thị, không phải khóa duy nhất giữa nhiều máy.
- Ảnh minh chứng phải là liên kết mà người nhận báo cáo có quyền mở. Tên file hoặc đường dẫn ổ C không đáp ứng yêu cầu.
- Đăng nhập và lưu thông tin xác thực theo cơ chế desktop phù hợp; không đóng gói bí mật dùng chung vào bản phát hành.

### 8.3. Chống mất và trùng

- Mất mạng: giữ hàng chờ, tiếp tục khảo sát trong giới hạn lưu trữ; kết nối lại thì đồng bộ tiếp.
- Lỗi tạm thời: thử lại với thời gian chờ tăng dần. Lỗi quyền/cấu trúc cột: chuyển trạng thái cần xử lý thay vì lặp vô hạn.
- Timeout sau khi gửi: tìm `incident_id` trước khi ghi lại. Nếu dòng đã tồn tại thì đối soát nội dung, không append mù.
- Nhiều máy: mọi writer tự động đi qua một dịch vụ ghi trung tâm. Có thể dùng Apps Script với khóa script, kiểm tra ID và append trong cùng đoạn có khóa; ID phải nằm trong hàng dữ liệu để khôi phục chỉ mục sau sự cố. Thử tải và giới hạn dịch vụ trước khi chọn cho sản xuất.
- Không tuyên bố ghi đúng một lần chỉ nhờ gọi API append. Người sửa trực tiếp Sheet và writer ngoài dịch vụ có thể phá giả định; cần phát hiện dòng trùng hoặc ID bị xóa khi đối soát.

Tài liệu chính thức: [Sheets append](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append), [giới hạn và backoff](https://developers.google.com/workspace/sheets/api/limits), [Apps Script LockService](https://developers.google.com/apps-script/reference/lock/lock-service), [OAuth cho desktop](https://developers.google.com/identity/protocols/oauth2/native-app), [tải tệp Drive](https://developers.google.com/workspace/drive/api/guides/manage-uploads).

## 9. Tổ chức chương trình và giao diện

Giữ một ứng dụng desktop với các trách nhiệm rõ ràng:

| Thành phần | Trách nhiệm |
|---|---|
| Kết nối LD | Dò thiết bị, nhận dạng phiên, kiểm tra kết nối và hiệu chỉnh |
| Quan sát | Ảnh, vị trí, map, trạng thái UI và chất lượng/tính mới dữ liệu |
| Quản lý nhiệm vụ | Trạng thái đang chạy, mục tiêu và quyền phát lệnh |
| Lập tuyến | Vòng/cung/nhánh, đường nối, chi phí và phần còn thiếu |
| Thực thi chặng | Gửi lệnh, xác nhận tới, dừng và phục hồi |
| Kiểm tra lỗi | Phát hiện, xác minh, gộp sự kiện và thu bằng chứng |
| Kho dữ liệu/đồng bộ | Checkpoint, sự kiện, outbox, Drive/Sheet và đối soát |
| Giao diện/báo cáo | Cùng đọc dữ liệu thật từ kho; không tự đặt phần trăm hoàn tất |

Không cần chia thành nhiều dịch vụ cho vòng điều khiển cục bộ. Chỉ phần ghi Sheet nhiều máy cần đầu mối dùng chung.

Giao diện chính cần thấy ngay: LD/nhân vật, map, vòng đang đi, từ đâu tới đâu, mục đích, đường đã đi, phần chưa kiểm tra, lỗi mới và trạng thái Sheet. Nút dừng phải luôn dùng được. Thông tin chẩn đoán chi tiết nằm trong phần mở rộng.

Tổ chức file: `core/` mã nghiệp vụ, `gui/` giao diện, `config/` cấu hình có phiên bản, `tests/` kiểm chứng, `docs/` thiết kế/hướng dẫn, `reports/` dữ liệu chạy/bằng chứng/bản xuất, `archive/` tư liệu cũ. Có chính sách giữ bằng chứng theo dung lượng; không tự xóa lỗi chưa đồng bộ. Không dọn dữ liệu đang dùng chỉ để thư mục nhìn gọn.

## 10. Thứ tự triển khai và sản phẩm phải giao

| Mốc | Công việc | Sản phẩm xem được | Điều kiện qua mốc |
|---|---|---|---|
| 0 — Đo và chốt hợp đồng | Ghi đo hiện trạng; kiểm tra nguồn tọa độ, dừng, hệ tọa độ, danh mục map và cấu trúc Sheet | Bộ log có thời gian, danh sách map truy cập được, bảng tiêu chí và dữ liệu chuẩn | Biết giới hạn dữ liệu; không còn nhầm đã gửi lệnh với đã tới |
| 1 — Một map từ đầu tới cuối | Khóa đúng LD, dừng có xác nhận, lưu bền vững; vòng mở rộng trên map đơn giản; một lỗi mẫu và một dòng Sheet thử có ảnh mở được | Một phiên chạy tự động có phát lại tiến trình và đối soát Sheet | Chạy lại sau tắt ứng dụng tiếp tục đúng chặng; không báo thành công giả |
| 2 — Địa hình khó | Vòng bị cắt, hành lang, nhánh cụt, vật cản động, khép biên và vùng thiếu | Bản đồ tiến độ giải thích được trên ít nhất 3 dạng địa hình | Không bỏ vùng thiếu, không quay vòng vô hạn, không mở map giữa chặng chưa kết thúc |
| 3 — Tự vận hành nhiều map | Đồ thị cửa map, lịch chọn map, chết/dịch chuyển, mất LD; đối soát danh mục 32 map | Phiên nhiều map với điểm vào/ra và lý do từng lần chuyển | Tất cả map có trạng thái rõ: đã kiểm tra, đang làm, chưa vào được hoặc cần điều kiện |
| 4 — Chất lượng phát hiện và báo cáo | Dữ liệu có nhãn, xác minh nhiều khung, gộp lỗi, uploader bền vững, writer nhiều máy | Báo cáo độ chính xác, danh sách lỗi có bằng chứng, kiểm tra mất mạng/trùng dòng | Đạt ngưỡng từng loại lỗi; dữ liệu không mất/trùng trong bộ tình huống đã định |
| 5 — Chạy bền và phát hành | Tối ưu theo số đo, cấu hình máy khác, thay độ phân giải, đóng gói và hướng dẫn | Bản cài/chạy được trên máy mới và báo cáo chạy bền | Qua các cửa nghiệm thu bên dưới; không có lỗi nghiêm trọng còn mở |

Làm tích hợp Sheet thật ngay ở mốc 1 để phát hiện sớm vấn đề quyền và cấu trúc. Nâng chất lượng detector sau khi đã có đường thu dữ liệu đúng. Chốt thời lượng từng mốc sau phép đo mốc 0; chưa có cơ sở để hứa thời hạn cho toàn bộ map và mọi kiểu lỗi.

## 11. Bộ nghiệm thu đề xuất

Các con số là mục tiêu ban đầu để hiệu chỉnh sau đo, không phải cam kết đã đạt trên mọi máy.

| Nhóm | Điều kiện cần chứng minh |
|---|---|
| Đúng thiết bị | 0 lệnh vào sai LD/nhân vật trong kịch bản nhiều LD, rút kết nối và đổi serial |
| Đúng chặng | 0 chặng bị đánh dấu đã tới trong bộ thử tọa độ cũ, sai map, đi nửa đường, bị dịch chuyển và kẹt |
| Phủ map | Toàn bộ đoạn bắt buộc đã kiểm chứng; vùng đi được đã biết được kiểm tra hình ảnh đạt mục tiêu ban đầu ≥99%; phần còn lại hiển thị có lý do, không gọi 100% |
| Khôi phục | 100/100 điểm tắt ứng dụng có kiểm soát khôi phục nhất quán, không bỏ tiến độ hoặc gửi lại lệnh cũ |
| Phát hiện | Mục tiêu precision ≥98%, recall ≥95% cho từng loại đã hỗ trợ trên tập độc lập có nhãn; công bố số mẫu và sai số thống kê |
| Ghi Sheet | 1.000 sự kiện thử, bao gồm timeout sau ghi và ghi đồng thời: không mất ID, không tạo trùng ID, trường và ảnh đọc lại đúng dưới mô hình writer đã chọn |
| Ngoại tuyến | Mất mạng 60 phút vẫn giữ dữ liệu; mạng trở lại tự đồng bộ tiếp, khảo sát không bị chặn bởi yêu cầu mạng |
| Giao diện | Mục tiêu p95 phản hồi thao tác <100 ms; nhận lệnh dừng <150 ms; mục tiêu nhân vật dừng ≤2 giây được xác nhận trên cấu hình nguồn dữ liệu hỗ trợ |
| Tài nguyên | Trên máy tham chiếu công bố: mục tiêu RAM tool <600 MB; không tăng >10% từ giờ 1 tới giờ 8 với khối lượng ổn định; CPU tool đo riêng với LD |
| Chạy bền | 8 giờ trên ít nhất 3 cấu hình máy/cài LD, sau đó 24 giờ trên cấu hình phát hành; có nhật ký CPU/RAM, sự cố và mất dữ liệu |

Nếu dữ liệu chỉ cập nhật chậm hoặc game không hỗ trợ hủy chạy đủ nhanh, phải sửa thiết kế/nguồn quan sát hoặc điều chỉnh giới hạn vận hành có công bố. Không giảm yêu cầu an toàn bằng cách bỏ xác minh.

## 12. Chứng minh vòng mở rộng chạy hiệu quả

Vòng mở rộng là phương án mặc định theo yêu cầu. Hiệu quả cần so trên map thực tế vì địa hình hành lang và nhiều đảo có thể khiến đường tròn thuần túy phải đi lại nhiều.

So với tuyến hiện tại trên cùng map, điểm xuất phát, tốc độ, phiên bản và cấu hình phát hiện; ít nhất 5 lượt mỗi dạng map. Đo:

- Diện tích kiểm tra mới mỗi phút và thời gian khép map.
- Quãng đường lặp/tổng quãng đường, phần đi được còn bỏ sót.
- Số lần mở map trên cùng quãng đường thực tế.
- Thời gian phục hồi, số lần đổi tuyến và số lần cần người can thiệp.
- Chất lượng phát hiện với cùng ngân sách quan sát.

Ưu tiên vòng mở rộng có điều chỉnh theo địa hình. Chỉ thêm phương án khác tại đoạn cụ thể khi có bằng chứng giảm đường lặp hoặc khép được nhánh còn thiếu. Mọi so sánh phải dùng dữ liệu thực, không dùng hình tuyến đẹp làm kết luận tối ưu.

## 13. Những việc cần biết trước khi chốt phát hành

1. Có nguồn mặt nạ va chạm/địa hình chính xác hơn ảnh hay không? Nếu chưa có, giữ mức tin cậy và vùng chưa biết trong báo cáo.
2. Tần số cập nhật vị trí và tín hiệu đứng yên thực tế trên từng cấu hình LD là bao nhiêu?
3. Lệnh hủy di chuyển nào có thể xác nhận được? Đây là điều kiện trước khi cho chạy tự động lâu.
4. Những map nào cần nhiệm vụ, cấp độ hoặc cửa chuyển đặc biệt? 32 map trong danh mục chưa đồng nghĩa vào được cả 32.
5. Sheet có đúng tiêu đề, quyền, chính sách chia sẻ ảnh và chấp nhận cột ID hay không? Kiểm tra ở môi trường thử trước khi ghi dữ liệu nghiệp vụ.
6. Các loại lỗi có đủ ảnh/video chuẩn để đánh giá chưa? Không nhận là hỗ trợ tốt một loại lỗi chưa có dữ liệu kiểm chứng.

Ưu tiên bàn giao đầu tiên: một map chạy vòng nhỏ → vòng lớn, không bỏ chặng, dừng thật, tiếp tục sau gián đoạn, một lỗi có bằng chứng được ghi và đọc lại từ Sheet. Đây là nền tảng để mở rộng tự động hóa toàn bộ tool.

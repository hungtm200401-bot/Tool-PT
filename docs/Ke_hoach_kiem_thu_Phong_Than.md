# Kế hoạch kiểm thử Phong Thần theo hành vi người chơi

Phiên bản 2.0 • Ngày 20 tháng 10 năm 2026 • Phát triển từ tool khảo sát map hiện có

Hệ thống cần chơi được, hiểu mục đích của từng việc đang làm và kiểm tra kết quả của mọi việc đó. Một phiên chơi phải nối được việc nhận nhiệm vụ, chọn bãi, đánh quái, nhặt đồ, so trang bị, tiếp tế, giao tiếp, tham gia hoạt động và quay về phát triển nhân vật. Cùng lúc, hệ thống phát hiện nội dung chưa biết và tạo đầu việc kiểm thử mới.

Mục tiêu quản lý là mọi đối tượng và mọi hành vi có mặt trong bản game được đưa vào sổ, có quy tắc đúng sai, phép thử và bằng chứng. Các trường hợp còn thiếu phải có tên và lý do cụ thể. Chỉ ghi hoàn tất khi đã đối chiếu danh mục của build thực tế và giải quyết hết phần chưa biết trong phạm vi nghiệm thu.

| **Năng lực**     | **Hành vi cần thể hiện**                                              |
|------------------|-----------------------------------------------------------------------|
| Hiểu game        | Biết điều kiện, đường đi, chi phí, lợi ích, giới hạn và cách thất bại |
| Chơi có mục tiêu | Tự chọn bước hợp lý theo cấp, hệ, sức mạnh, ngân sách và lịch         |
| Kiểm đúng sai    | Đối chiếu thay đổi thật với quy tắc có nguồn và trạng thái trước      |
| Khám phá         | Gặp NPC, nút, đồ, quái hoặc map mới thì kiểm kê và khảo sát           |
| Chịu gián đoạn   | Biết xử lý chết, kẹt, đầy túi, hết thuốc, mất mạng và popup lạ        |
| Bao phủ chi tiết | Theo dõi từng đối tượng, trạng thái, nhánh, mức cấp và tương tác      |

Bộ bàn giao gồm kế hoạch này, sổ điểm kiểm chi tiết, hành trình chơi mẫu, đặc tả mở rộng tool, hợp đồng dữ liệu và 109 ca kiểm thử nền. Sổ điểm kiểm là các yêu cầu phải khảo sát, chưa phải bằng chứng đã có mặt hoặc đã chạy trên server.

## 1 Phạm vi kiểm soát đến từng chi tiết

Đơn vị kiểm thử nhỏ nhất là một hành vi trên một đối tượng trong một trạng thái xác định. Ví dụ kỹ năng không được kiểm bằng một dòng chung; cần từng skill ID, từng cấp kỹ năng, loại mục tiêu, đủ thiếu tài nguyên, hồi chiêu và ảnh hưởng của trang bị hoặc hiệu ứng liên quan.

| **Đối tượng** | **Cần tách thành**                                               |
|---------------|------------------------------------------------------------------|
| NPC           | Từng NPC và từng lựa chọn hội thoại theo trạng thái nhân vật     |
| Quái          | Từng loại, vùng sinh, hành vi truy đuổi, chiến đấu và thưởng     |
| Đồ            | Từng ID, nguồn nhận, loại khóa, stack, hạn, quyền dùng và chuyển |
| Map           | Từng ID, tầng, phiên bản cảnh, cửa vào và điều kiện kích hoạt    |
| Giao diện     | Từng màn, tab, ô, nút, menu, popup, tooltip và thông báo         |
| Tăng trưởng   | Mỗi mốc cấp, nhánh hệ, điểm, kỹ năng và chu kỳ sau trần          |
| Quan hệ       | Mỗi vai, trạng thái kết nối, quyền, thay đổi vai và lợi ích      |

Kiểm mỗi đối tượng qua tám câu hỏi: thấy đúng không; vào hoặc dùng được không; điều kiện kiểm đúng không; kết quả đúng không; giới hạn đúng không; thất bại có phục hồi được không; lưu lại đúng không; khi kết hợp hệ khác còn đúng không. Những câu không áp dụng phải có lý do theo thiết kế.

Không lấy tổng số nút đã bấm hoặc số giờ chơi làm bằng chứng đầy đủ. Chỉ số cần theo dõi là số đối tượng đã kiểm kê, số hành vi đã ràng buộc quy tắc, số ca đã thực hiện, các nhánh còn thiếu và nguồn dữ liệu chưa được đối chiếu. Nếu chưa có tổng danh mục của build thì báo đang xác lập phạm vi, chưa báo phần trăm toàn game.

## 2 Xác lập đúng bản Phong Thần

Tạo hồ sơ server gồm tên bản, nhà vận hành, package, client build, resource build, server, múi giờ, ngày nội dung hiệu lực, danh sách hệ và các lớp giới hạn cấp. Tool đang cấu hình package com.tech3cgame.vhpt1; không suy ra toàn bộ cơ chế của server này từ tên Phong Thần hoặc từ tài liệu VNG.

Đối chiếu năm nguồn: dữ liệu thiết kế được đội game cung cấp, danh mục client hoặc server được phép xuất, toàn bộ UI trong client, phiên chơi thật và tài liệu tham chiếu. Lập danh sách chênh lệch: có trong cấu hình nhưng không mở được, có trên UI nhưng thiếu danh mục, có trong tài liệu nhưng chưa thấy trong build.

| **Sổ dữ liệu gốc** | **Các thông tin cần nhập**                                         |
|--------------------|--------------------------------------------------------------------|
| Nhân vật           | Hệ, nơi sinh, lớp cấp, EXP, điểm và nhánh phát triển               |
| Nội dung           | NPC, quái, map tầng, quest, skill, item, công thức và hoạt động    |
| Giao diện          | Màn hình và mọi thao tác có thể tới theo từng quyền hoặc cấp       |
| Quy tắc            | Điều kiện, chi phí, kết quả, giới hạn, reset, quyền và persistence |
| Tài nguyên         | Asset liên quan đến hình, âm, hiệu ứng và map nếu có danh mục      |

Mỗi bản ghi có ID ổn định, build, nguồn, độ tin cậy, ngày xác minh, người duyệt và evidence. Tên hiển thị không thay ID vì các đối tượng có thể trùng tên. Cập nhật game phải tạo danh sách thêm, đổi và mất nội dung để kéo theo test tương ứng.

Người phụ trách cơ chế phải chơi và giải thích được luồng, đọc thiết kế, xử lý mâu thuẫn nguồn và chỉ ra phép kiểm. Trợ lý AI quản lý kiến thức và đề xuất phép thử; kết luận dựa trên oracle đã duyệt, nghĩa là quy tắc làm căn cứ so đúng sai.

## 3 Bộ quyết định của một người chơi

Mỗi vòng chơi bắt đầu bằng đọc tình huống: đang ở đâu, đang làm gì, sống hay chết, cấp và EXP, đồ và tiền còn bao nhiêu, mục tiêu gần nhất, lịch nào sắp đóng và có dấu hiệu bất thường nào. Hệ thống cần nhớ những gì đã thử, đường nào bị kẹt, bãi nào hiệu quả và nguyên nhân lần thất bại trước.

Thứ tự chọn mục tiêu mặc định là xử lý nguy cấp; hoàn tất hoặc ổn định thao tác đang dở; bảo đảm tài nguyên chơi; làm nội dung có thời hạn; mở khóa tiến trình; nâng sức mạnh; luyện cấp; khám phá phần chưa biết. Thứ tự được điều chỉnh theo persona và lịch, nhưng mọi quyết định phải ghi lý do.

| **Tình huống quan sát** | **Quyết định hợp lý**                          | **Cách kiểm**                       |
|-------------------------|------------------------------------------------|-------------------------------------|
| Train không tăng EXP    | Kiểm quái, trần cấp, bộ đếm và trạng thái auto | Xác định nguyên nhân bằng nguồn mới |
| Thuốc sắp cạn           | Ước lượng thời gian còn, về tiếp tế khi cần    | Kiểm tiền và thuốc trước sau        |
| Nhặt được đồ mới        | So điều kiện và hiệu quả, giữ bán hoặc mặc     | Kiểm chỉ số và quyền dùng           |
| Bãi quá nguy hiểm       | Lùi, đổi chiến thuật, thay đồ hoặc đổi bãi     | So tỷ lệ sống và EXP hữu ích        |
| Gặp NPC hoặc nút lạ     | Thêm vào sổ và khảo sát có giới hạn            | Ghi đủ lựa chọn và điều kiện        |
| Nghi lỗi map            | Lưu ngay bằng chứng, tạo lịch quay lại         | Không làm mất trạng thái phiên      |

Tool phải phân biệt chủ đích chơi và phép thử phá điều kiện. Phiên người chơi tự nhiên ưu tiên hoàn thành mục tiêu; phiên kiểm biên cố ý hết tiền, đầy túi hoặc rời đội. Hai phiên dùng cùng cơ chế nhưng ghi nhãn khác để không coi hành vi thử bất thường là cách chơi chuẩn.

## 4 Người chơi biết tự điều chỉnh

Không dùng một chuỗi click cố định cho mọi tình huống. Mỗi hành động có tiền điều kiện và kết quả phải quan sát. Đi tới NPC phải thấy đúng NPC và phạm vi tương tác; đánh quái phải thấy tiến triển hợp lệ; nhận thưởng phải đối chiếu nhiệm vụ và tài sản.

Ví dụ một phiên train bắt đầu bằng kiểm đồ, thuốc, ô trống và ngân sách về thành. Hệ thống chọn bãi đã xác minh, đi tới, đánh thử một cửa sổ mẫu rồi tính EXP hữu ích mỗi phút, thời gian hạ quái, thuốc tiêu hao và nguy cơ chết. Nếu bãi không phù hợp, hệ thống ghi lý do và chọn phương án khác.

Khi túi đầy, hệ thống phân biệt đồ nhiệm vụ, đồ nâng cấp, nguyên liệu, đồ dự phòng và rác đã xác định. Chỉ bán theo quy tắc giữ đồ đã duyệt; vật phẩm mới hoặc chưa hiểu được giữ lại và tạo công việc khảo sát. Sau tiếp tế, tool quay về đúng mục tiêu thay vì bắt đầu lại toàn bộ chuỗi.

| **Bộ nhớ cần có**      | **Ví dụ dữ liệu**                                                  |
|------------------------|--------------------------------------------------------------------|
| Mục tiêu dài hạn       | Mở nội dung tiếp theo, đạt mốc cấp, hoàn thành nghề hoặc bộ đồ     |
| Mục tiêu phiên         | Hoàn tất chuỗi, kiếm nguyên liệu, train hoặc khảo sát một vùng     |
| Kinh nghiệm tình huống | Chi phí tuyến, bãi nguy hiểm, NPC cần gặp, cách xử lý popup        |
| Ngân sách              | Tiền có thể tiêu, thuốc dự phòng, số lần chết và thời gian thử lại |
| Chưa biết              | Món đồ chưa rõ, câu thoại mới, cửa bị khóa, nguồn EXP lạ           |

Khi không tiến triển, chẩn đoán trước khi lặp: thao tác chưa gửi, game chưa nhận, điều kiện thiếu, đường bị chặn, nhận diện sai hay lỗi game. Quá ngân sách thì lưu trạng thái và chuyển blocked có lý do. Không spam thao tác để hy vọng tự qua.

## 5 Kiến thức đặc trưng Phong Thần

Danh mục khảo sát phải mang nội dung Phong Thần. Tư liệu chính thức VNG có các hệ Giáp Sĩ, Đạo Sĩ, Dị Nhân và Vũ Sĩ; cần xác nhận hệ nào đang mở trong bản Android này, chuỗi đầu mỗi hệ và các cơ chế khác nhau. Không dùng chung một nhân vật để thay kết quả cho mọi hệ. \[R1\]\[R5\]\[R6\]\[R7\]

| **Cụm nội dung tham chiếu** | **Câu hỏi cần trả lời trên server**                        |
|-----------------------------|------------------------------------------------------------|
| Các thôn và thành           | Nơi sinh, NPC dịch vụ, đường ra bãi và cách quay về        |
| Bào Thương                  | Thuê phương tiện, sức chở, hàng, nơi mua bán và lãi thực   |
| Khai khoáng                 | Điều kiện học nghề, dụng cụ, điểm tài nguyên và đầu ra     |
| Luyện đơn                   | Nguyên liệu, trạng thái online hoặc offline và cách nhận   |
| Sư đồ và kết hôn            | Điều kiện, quyền lợi, giới hạn và chấm dứt quan hệ         |
| Thần thú và thú cưỡi        | Nguồn nhận, nuôi, đổi, thuộc tính và tương tác             |
| Hậu kỳ                      | Độ kiếp, Tiên Ma, chuyển sinh hoặc cơ chế tương ứng nếu có |

Các tên trên tạo yêu cầu xác minh, không tự khẳng định mọi cơ chế đều có trên build. Cơ chế không có phải lưu nguồn xác nhận; cơ chế có tên khác cần ánh xạ tương đương, không xóa khỏi danh mục chỉ vì không tìm đúng từ khóa.

Một người am hiểu phải giải thích được vì sao đi bãi đó, lấy đồ ở đâu, thiếu điều kiện nào, cần NPC nào, khi nào nhận được thưởng và tại sao cùng thao tác lại khác kết quả ở trạng thái khác. Kho kiến thức phải lưu các giải thích này thành quy tắc có điều kiện, không chỉ sao chép hướng dẫn.

Tài liệu tham chiếu được đọc để tạo câu hỏi, rồi kiểm lại trên game thật. Nguồn VNG có thể thuộc giai đoạn phát hành khác; ngày, cấp, NPC và tọa độ chưa đối chiếu được giữ ở trạng thái chưa xác minh. \[R2\]\[R3\]\[R4\]\[R8\]\[R9\]\[R10\]

## 6 Hành trình từ nhân vật mới đến người chơi hậu kỳ

Mỗi hệ thực hiện ít nhất một hành trình tự nhiên từ cấp 1 đến các trần tiến trình của đúng build. Nhân vật thử ở cấp cao chỉ bổ sung kiểm biên, không thay hành trình này. Tách nhánh lựa chọn không thể đảo bằng nhân vật khác hoặc snapshot phù hợp.

| **Chặng**            | **Những việc phải thực sự làm**                                    |
|----------------------|--------------------------------------------------------------------|
| Bước vào game        | Tải, chọn server, tạo nhân vật, đọc hướng dẫn, thử điều khiển      |
| Tự sống được         | Tìm NPC, đánh quái, nhặt và mặc đồ, dùng thuốc, chết và hồi sinh   |
| Tự phát triển        | Chọn bãi, nâng điểm và skill, tiếp tế, nhận và trả các chuỗi       |
| Chơi cùng người khác | Chat, bạn, đội, trao đổi, quan hệ và tổ chức                       |
| Khai thác hệ thống   | Nghề, chế tạo, buôn bán, boss, phó bản và nội dung theo lịch       |
| Tiến tới trần        | Mở từng mốc, thử nội dung cấp cao, hoàn tất nhánh bắt buộc         |
| Sau trần             | Xây nhân vật, bộ đồ, bộ sưu tập, chu kỳ mới và nội dung cạnh tranh |
| Quay lại             | Nghỉ rồi đăng nhập, nhận phần offline, thay phiên bản và khôi phục |

Ở mỗi cấp lưu nguồn EXP, thay đổi chỉ số, kỹ năng, đồ mới, map đã vào và tính năng mở. Ở mỗi mốc mở kiểm trước, đúng và sau ngưỡng. Một lần nhảy qua nhiều cấp phải tạo đủ công việc mở khóa bị đi qua.

Hành trình phải có cả solo, tổ đội, ít tài nguyên và điều kiện bình thường. Dùng đồ vượt cấp hoặc cấp sẵn quá nhiều tài nguyên có thể che lỗi cân bằng và bế tắc; dữ liệu chuẩn của hành trình tự nhiên cần phản ánh người chơi mục tiêu.

Mỗi phiên có nhật ký quyết định và phần việc còn dở. Kết thúc ở Lmax chưa đủ: các nhánh, đối tượng và cơ chế đã mở nhưng chưa thử vẫn là phần còn thiếu.

## 7 Train quái và quản lý tài nguyên như người chơi

Xác minh từng bãi: đường đi, quái, mật độ, tầm truy đuổi, mức sát thương, EXP, rơi đồ, khoảng cách tới tiếp tế và nguy cơ tranh bãi. Chọn theo hệ, cấp, bộ đồ và mục tiêu; một bãi EXP danh nghĩa cao nhưng chết nhiều có thể kém hiệu quả.

Đo EXP hữu ích trên thời gian gồm cả chạy lại, hồi sinh, bán đồ và mua thuốc. Ghi tiền ròng, thuốc mỗi phút, số quái hợp lệ, quái bị tranh, số lần chết, ô túi sử dụng và thời gian đứng không. Không dùng số click hoặc số đòn làm bằng chứng đã train tốt.

| **Tình huống**            | **Cách chơi**                              | **Phép kiểm đi kèm**             |
|---------------------------|--------------------------------------------|----------------------------------|
| Quái không còn ở bãi      | Tìm vùng spawn đã biết hoặc đổi bãi        | Spawn và thời gian hồi đúng      |
| Bị tranh quái             | Chọn mục tiêu khác theo quyền và hiệu quả  | EXP, quyền hạ và quyền nhặt      |
| Máu thấp                  | Dùng thuốc hoặc rút về theo ngưỡng         | Hồi thực, tiêu hao và cooldown   |
| Hết tiền thuốc            | Chọn nguồn tiền hợp lệ hoặc hoạt động khác | Không tạo bế tắc tiến trình      |
| Đồ hỏng hoặc sức đánh yếu | Sửa, so đồ hoặc đổi chiến thuật            | Chi phí, chỉ số và tác dụng thật |
| Túi gần đầy               | Ưu tiên giữ đồ và chuẩn bị về thành        | Không bán nhầm đồ chưa phân loại |

Tạo cấu hình giữ đồ theo mục tiêu và nguồn chuẩn. Chọn số thuốc mua dựa thời gian dự kiến và dự phòng đã duyệt; không mặc định mua tối đa hoặc tiêu hết tiền. Nếu mua thất bại phải đọc nguyên nhân trước retry.

Sau vòng tiếp tế, so toàn bộ tài sản trước sau, quay lại bãi và xác nhận auto đúng trạng thái. Khảo sát map khi chiến đấu phải lưu hiệu ứng che khuất; một lượt quan sát yên tĩnh khác bù phần nền bị che.

## 8 Chiến đấu quái và cơ chế kỹ năng

Kiểm riêng đánh thường, chủ động, bị động, hỗ trợ, diện rộng và các dạng mục tiêu mà build có. Mỗi kỹ năng cần xác minh điều kiện học, tăng cấp, gán ô nhanh, chi phí, hồi chiêu, tầm, đường nhìn, thời gian ra đòn, ngắt chiêu và kết quả.

Đối với quái, kiểm spawn, truy đuổi, đổi mục tiêu, đi vòng, kéo về, hồi HP, chết, xác và hồi sinh. Cần tình huống quái ở mép map, sau vách, nhiều quái chồng nhau, quái nhiệm vụ trùng hình và người chơi khác tranh mục tiêu.

| **Nhóm**   | **Các biến phải đối chiếu**                                  |
|------------|--------------------------------------------------------------|
| Đòn        | Trúng, hụt, né, chí mạng, phản đòn và loại sát thương nếu có |
| Hiệu ứng   | Thời hạn, chồng, thay thế, miễn dịch và nguồn gây            |
| Tài nguyên | Thiếu, vừa đủ, dư, hồi tự nhiên và dùng khi đang bị đánh     |
| Mục tiêu   | Hợp lệ, ngoài tầm, đã chết, mất khỏi map, cùng đội hoặc phe  |
| Đồng bộ    | HP và log thực, animation, âm thanh và con số hiển thị       |
| Gián đoạn  | Di chuyển, choáng, chết, đổi map, mất mạng và đổi mục tiêu   |

Công thức sát thương chỉ được kết luận sai khi có đặc tả hoặc baseline được duyệt. Khi chưa có công thức, thực hiện phép thử kiểm soát một biến và ghi nghi vấn; không biến cảm giác mạnh yếu thành lỗi đã xác nhận. Hiệu ứng hoặc tỉ lệ ngẫu nhiên cần số mẫu và kế hoạch đánh giá riêng.

Người chơi tự động phải biết đòn nào phù hợp mục tiêu, khi nào giữ tài nguyên, khi nào tiếp cận và khi nào rút. Mỗi hệ cần chiến thuật riêng theo cơ chế xác minh; không giả lập hiểu mọi hệ bằng một nút auto.

## 9 Thuộc tính và cách xây nhân vật

Kiểm từng nguồn làm thay đổi sức mạnh: cấp, điểm phân phối, skill, trang bị, bộ đồ, thú, buff, quan hệ và công trình nếu có. Lưu ảnh chỉ số cùng giá trị quan sát thực trong chiến đấu. Tách chỉ số gốc, cộng cố định, phần trăm và hiệu ứng có điều kiện theo công thức thực tế.

Mỗi lần cộng điểm phải kiểm điểm còn lại, giới hạn, tác dụng lên HP, MP, công, thủ, kháng và các chỉ số liên quan. Thử cộng từng điểm, nhiều điểm, thiếu điểm và hoàn điểm nếu có. Sau relog phải giữ đúng; tháo nguồn tăng không để lại phần cộng sai.

| **Quyết định người chơi** | **Căn cứ cần biết**                           | **Phép kiểm**                               |
|---------------------------|-----------------------------------------------|---------------------------------------------|
| Chọn hướng xây            | Vai trò, điều kiện skill và loại đối thủ      | Nhánh có thể học và thực sự dùng            |
| Đổi trang bị              | Điều kiện, thuộc tính và lợi ích mục tiêu     | Chỉ số trước sau và hiệu quả                |
| Đổi skill                 | Tầm, chi phí, hồi chiêu và tình huống         | Ô nhanh, auto và thao tác tay               |
| Dùng buff                 | Có lợi, còn thời gian và không trùng lãng phí | Chồng, thay và hết hạn                      |
| Tẩy lại                   | Chi phí, hoàn điểm và phụ thuộc               | Không âm điểm hoặc giữ skill trái điều kiện |

So đồ không chỉ nhìn số lực chiến. Tool cần đọc điều kiện dùng, dòng thuộc tính, bộ đồ, độ bền, trạng thái khóa và mục tiêu đang chơi. Khi chưa hiểu món mới thì giữ và khảo sát, không bán theo màu hoặc giá mà chưa có rule.

Kiểm các tổ hợp nguồn tăng và thứ tự bật tắt để tìm cộng dồn sai: mặc rồi buff rồi đổi đồ; tháo đồ trong lúc buff; chết khi còn hiệu ứng; đổi map hoặc relog. Tăng sức mạnh phải đúng cả giá trị hiển thị và hành vi thực.

## 10 Di chuyển tìm đường và thế giới

Người chơi cần biết đường tới NPC, bãi quái, thành, cửa hang và nơi hoạt động; biết phương tiện hoặc vật phẩm nào có thể dùng, mất bao nhiêu và có điều kiện gì. Lập đồ thị map cùng tầng, cửa, điều kiện và chi phí. Mỗi cạnh phải được đi qua và xác nhận map đích.

Kiểm đi tám hướng, chạy giữ, đổi hướng, hủy đường tự tìm, dừng sát đích, vòng vách, cầu, bậc, nước và vùng an toàn. Tìm đường tới NPC phải kết thúc trong khoảng tương tác hợp lệ, không chỉ gần biểu tượng trên minimap.

| **Luồng đi lại**   | **Những gì cần kiểm**                             |
|--------------------|---------------------------------------------------|
| Đi tự do           | Va chạm, tốc độ, camera và điều khiển             |
| Tìm đường          | Đích thật, vật cản, đường vòng và hủy lệnh        |
| Qua cửa            | ID nguồn đích, tầng, spawn, hai chiều và loading  |
| Dịch chuyển        | Điều kiện, chi phí, vật phẩm, giới hạn và kết quả |
| Hồi thành          | Khi chiến đấu, khi chết, map đặc biệt và điểm về  |
| Cưỡi hoặc biến thể | Tốc độ, hình, va chạm, quyền dùng và xuống thú    |

Map bị khóa theo nhiệm vụ hoặc cấp phải được ghi đúng lý do. Một điểm đi không tới có thể do va chạm hợp lệ, pathfinding sai, tool điều khiển sai hoặc thiếu điều kiện. Chẩn đoán bằng quan sát và phép thử đối chiếu, không tự coi mọi điểm kẹt là bug map.

Mỗi tuyến lưu đường thực, hướng, thời gian, cửa đã qua và cách phục hồi. Khi sai map, đổi tầng hoặc bị dịch chuyển, hủy mục tiêu cũ trước khi lập đường mới. Không mang tọa độ của tầng trước áp vào cảnh mới.

## 11 Kiểm đen map và mọi sai lệch địa hình

Phạm vi gồm nền, texture, sprite, layer, vật thể, camera và va chạm. Danh mục 32 map hiện có chỉ là điểm xuất phát; bổ sung map tầng, nội dung khóa, phó bản riêng, map sự kiện và biến thể theo phase. Mỗi vùng cần được nhìn từ các hướng để bù phần bị UI, nhân vật hoặc cảnh vật che.

Tuyến kiểm gồm viền, góc, vùng giữa, cửa, cầu, hành lang, mép nước, quanh NPC và bãi quái. Thực hiện lúc yên tĩnh và khi có nhân vật, quái hoặc kỹ năng. Thử đổi chất lượng ảnh trong phạm vi được hỗ trợ, relog và đối chiếu client cùng build.

| **Dấu hiệu**         | **Cách phân biệt và xác minh**                       |
|----------------------|------------------------------------------------------|
| Đen map              | Phân biệt nền tối đúng, bóng, loading và mất ảnh     |
| Mất hoặc sai texture | So nguồn chuẩn, lặp cảnh và log tài nguyên nếu có    |
| Nứt hoặc lệch ảnh    | Kiểm đường nối, camera và độ phân giải               |
| Layer sai            | Đi trước sau công trình, cây, cầu và nhân vật        |
| Xuyên hoặc rơi map   | Ghi vị trí, đường vào, trạng thái và collision chuẩn |
| Vật thể biến mất     | Kiểm góc nhìn, phase, khoảng cách và điều kiện spawn |

Ảnh gốc giữ nguyên, ảnh khoanh là bản riêng. Tọa độ hiện tại của tool là tọa độ nhân vật đứng quan sát; không gọi đó là tọa độ tâm lỗ đen. Chỉ ghi vị trí lỗi theo tọa độ thế giới nếu phép chiếu đã được hiệu chuẩn.

Hiệu chuẩn vùng ảnh hợp lệ theo camera và độ phân giải, rồi kiểm chồng lấn bằng tuyến thật. Báo riêng map đã vào, tuyến đã đi, vùng nhìn thấy, vùng được kiểm và vùng chưa biết. Một map đủ mốc đi nhưng thiếu vùng ảnh vẫn chưa hoàn tất kiểm hình.

## 12 NPC hội thoại và nhiệm vụ đến từng nhánh

Mỗi NPC có danh sách chức năng, node hội thoại, điều kiện hiện lựa chọn và kết quả. Khảo sát cả trước và sau nhiệm vụ, dưới và trên ngưỡng cấp, thành viên và người ngoài tổ chức. Lựa chọn bị ẩn cũng cần được quản lý trong danh mục thiết kế nếu có dữ liệu.

Đồ thị nhiệm vụ ghi từng bước, điều kiện, NPC nhận trả, quái hoặc vật phẩm mục tiêu, thời hạn, nhánh, thất bại, phần thưởng và nhiệm vụ tiếp. Kiểm nhận, từ chối, làm một phần, đủ mục tiêu, chờ trả, đã nhận thưởng, hủy và nhận lại theo thiết kế.

| **Trường hợp** | **Điểm phải đối chiếu**                           |
|----------------|---------------------------------------------------|
| Đánh quái      | Loại, map, quyền hạ, khoảng cách và bộ đếm        |
| Thu thập       | ID, số lượng, nguồn, khóa và tiêu hao khi trả     |
| Hội thoại      | Thứ tự, lựa chọn, nhánh và điều kiện đổi câu      |
| Hộ tống        | NPC hoặc xe, bám theo, chết, thời gian và cửa map |
| Nhiệm vụ đội   | Chủ nhiệm vụ, người được tính và quyền thưởng     |
| Nhiệm vụ lặp   | Số lượt, ngày server, reset và cooldown           |

Thử đầy nhật ký, túi đầy, thiếu món, nộp sai món cùng tên, quái bị tranh, chết hoặc relog giữa bước, đóng cửa sổ đúng lúc trả. Mạng chậm khi nhận thưởng phải đọc trạng thái server trước retry; không chỉ kiểm nút đã mất.

Kiểm cả nội dung văn bản: tên người, mục tiêu, bản đồ, điều kiện và phần thưởng trong mô tả có khớp thực hiện không. Mô tả sai là lỗi nội dung ngay cả khi nhiệm vụ vẫn hoàn thành được. Nếu thiết kế và game mâu thuẫn, mở vấn đề xác minh rule, không tự chọn nguồn thuận tiện để pass.

## 13 Từng vật phẩm trang bị và ô hành trang

Mỗi item ID có bản ghi nguồn nhận, icon, tên, màu, loại, mô tả, điều kiện dùng, thuộc tính, số lượng, stack, hạn và khóa. Theo dõi toàn vòng đời nhận, giữ, dùng, trang bị, chuyển, bán, vứt, hết hạn hoặc bị tiêu hao. Món trùng tên nhưng khác ID được kiểm riêng.

Mỗi ô trang bị cần thử món hợp lệ, sai loại, thiếu cấp, thiếu điều kiện và thay món khi túi đầy. Đối chiếu chỉ số trước sau, hình trên nhân vật, hiệu ứng bộ, độ bền, hỏng và sửa. Tháo hoặc đổi liên tục không được cộng thuộc tính nhiều lần ngoài thiết kế.

| **Hành vi nhỏ** | **Các ca cần có**                                        |
|-----------------|----------------------------------------------------------|
| Tách gộp        | Một món, đủ stack, vượt stack, giữ khóa và hạn           |
| Sắp túi         | Theo bộ lọc, đồ mới nhận, ô khóa, kéo khi đang nhận đồ   |
| Dùng            | Đủ thiếu điều kiện, cooldown, nhiều lượt và bấm lặp      |
| Vứt hoặc bán    | Xác nhận, hủy, đồ quý, đồ nhiệm vụ và đồ khóa            |
| Gửi rút         | Kho đầy, loại kho, giới hạn, đóng cửa sổ và relog        |
| Hết hạn         | Trước, đúng, sau thời điểm; đang mặc hoặc đang giao dịch |

Tạo chính sách giữ đồ theo mục tiêu. Ưu tiên bảo toàn đồ chưa hiểu, đồ nhiệm vụ, nguyên liệu chặng tới và phương án quay về. Bán rác là hành vi có kiểm chứng tiền và số lượng, không phải thao tác dọn tùy ý.

Phần mô tả phải so với hiệu quả thật: thuốc hồi bao nhiêu, đồ cộng gì, vật phẩm mở gì, hạn tính theo đâu. Phần hiệu ứng ngẫu nhiên cần đặc tả và đánh giá mẫu; một lần không nhận đồ hiếm không đủ là lỗi.

## 14 Nghề chế tạo và hoạt động khi rời mạng

Khảo sát kỹ năng sống, khai thác, hợp thành, tách đồ, nâng cấp, luyện đơn và cơ chế offline nếu bản game có. Mỗi nghề cần biết cách học, dụng cụ, điểm hoạt động, cấp nghề, chi phí, thời gian, đầu ra và các điều kiện bị chặn.

Khai thác kiểm điểm tài nguyên hợp lệ, tài nguyên đang bị chiếm, dụng cụ hỏng hoặc thiếu, bị đánh giữa thao tác, túi đầy, tăng cấp nghề và spawn lại. Chế tạo kiểm nguyên liệu đúng ID và chất lượng, khóa, số lượng, tiền, công thức và sản phẩm.

| **Luồng**          | **Kiểm trước**                       | **Kiểm sau**                         |
|--------------------|--------------------------------------|--------------------------------------|
| Chế tạo            | Đủ thiếu nguyên liệu và ô chứa       | Đồ tạo, thuộc tính và tổng tiêu hao  |
| Nâng cấp           | Cấp hiện tại, điều kiện và phí       | Thành bại, giữ mất món và chỉ số     |
| Tách đồ            | Đúng loại, khóa và xác nhận          | Sản phẩm trả và món bị xóa           |
| Luyện hoặc offline | Điều kiện, nguyên liệu và giờ server | Thời gian tính, sản phẩm và nhận lặp |

Với cơ chế xác suất, kiểm tính đúng của mỗi kết quả trước khi đánh giá tỷ lệ. Kế hoạch tỷ lệ phải chọn trước giả thuyết, sai số, cỡ mẫu và nguồn xác suất; không gom mọi công thức vào một tỷ lệ chung.

Tool cần biết làm nghề có phục vụ mục tiêu đang chơi không: kiếm tiền, tạo đồ hoặc lấy nguyên liệu. Quyết định làm phải xét chi phí cơ hội và ngân sách, không lặp sản xuất chỉ vì nút còn bấm được.

Đóng game, đổi nhân vật, relog hoặc server reset trong lúc offline phải kiểm tiến trình và quyền nhận ở đúng nhân vật. Lấy thời gian server làm căn cứ nếu đó là thiết kế; thay đồng hồ máy không được tự tạo phần thưởng sai. \[R3\]\[R10\]

## 15 Tiền tệ buôn bán và chuyển tài sản

Kiểm mọi nguồn tạo tiền, tiêu tiền, đổi loại tiền, mua NPC, bán đồ, giao dịch, thư, chợ và kho hiện diện. Mỗi thao tác có sổ tài sản trước sau, phí, người hưởng, trạng thái commit và kết quả sau relog. Tổng tài sản hai bên phải khớp quy tắc tạo hoặc tiêu của server.

Bào Thương là một ví dụ cần chơi trọn vòng nếu có: chọn phương tiện, thuê, kiểm sức chở, chọn hàng, mua, chọn điểm bán, đi tuyến, bán và tính lãi sau phí. Kiểm cả quá tải, thiếu tiền, hàng còn khi thoát, khóa dịch chuyển và nhiệm vụ vận chuyển liên quan. Không coi chỉ mở shop là đã hiểu buôn bán. \[R2\]

| **Tình huống giao dịch** | **Điều cần kiểm**                                       |
|--------------------------|---------------------------------------------------------|
| Hai bên xác nhận         | Đúng đối tượng, món, số lượng, tiền và phí              |
| Đổi đề nghị              | Xác nhận cũ có bị hủy theo quy tắc không                |
| Mất mạng khi chốt        | Thành công hoặc hoàn tác nhất quán; không nhân đôi      |
| Hàng khóa hoặc hết hạn   | Chặn đúng ở thời điểm xác nhận cuối                     |
| Chợ và quầy              | Đăng, phí, rút, mua đồng thời và nhận tiền nếu có       |
| Thư                      | Người nhận, phí, đính kèm, hết hạn, túi đầy và nhận lặp |

Giá lớn, số lượng biên và làm tròn phải có phép kiểm. Tooltip giá và số tiền thực trừ phải khớp. Khi mở nhiều cửa sổ hoặc hai client thử cùng tiêu một món, server cần giữ đúng quy tắc tài sản; thao tác chỉ dùng giao diện hợp lệ trong môi trường thử.

Phần tiền thật, nếu thuộc phạm vi, dùng sandbox hoặc cơ chế thử do đội game cấp. Không đưa tự nạp thật vào vòng người chơi mặc định.

## 16 Giao tiếp quan hệ và tổ đội

Hành vi người chơi gồm đọc chat, hỏi hoặc trả lời trong nhóm thử, thêm bạn, chặn, xem thông tin, mời đội và phối hợp. Dùng tài khoản thử làm đối tác cho các kịch bản; kế hoạch không yêu cầu tool tự gửi tin tới người chơi thật ngoài phạm vi được giao.

Kiểm từng kênh chat, quyền gửi, người nhận, tiếng Việt, ký tự, độ dài, giới hạn, lịch sử, link đồ hoặc tọa độ nếu có. Kiểm bạn bè online, offline, đổi tên, xóa bạn, chặn và bỏ chặn; trạng thái trên hai phía phải phù hợp.

| **Cơ chế**   | **Vòng đời cần thực hiện**                                  |
|--------------|-------------------------------------------------------------|
| Tổ đội       | Mời hoặc xin, vào, từ chối, đổi trưởng, rời, loại và tan    |
| Chia lợi ích | EXP, đồ, khoảng cách, map, quyền hạ và thời điểm tham gia   |
| Sư đồ        | Điều kiện nhận, tiến triển, thưởng, giới hạn và chấm dứt    |
| Kết hôn      | Điều kiện, vật phẩm, xác nhận hai phía, lợi ích và chấm dứt |
| Riêng tư     | Người ngoài, người bị chặn, thông tin hiển thị và lời mời   |

Sư đồ và kết hôn là mục khảo sát theo tài liệu tham chiếu; chỉ dùng quy tắc đã kiểm trên bản game. Quan hệ phải có kết quả hai phía và sau relog, không chỉ xem thông báo thành công ở phía gửi. \[R8\]\[R9\]

Kịch bản tổ đội cần khác cấp, khác map hoặc tầng, thành viên chết, người mới vào giữa trận, người rời trước thưởng và trưởng offline. Khi đang đánh boss mà vai thay đổi, tool phải giữ đúng phối hợp và kiểm thưởng, không tiếp tục dùng quyền cũ.

## 17 Bang lãnh địa thành thị và tài sản tổ chức

Xác minh cấu trúc tổ chức thực tế và tên gọi. Bang, lãnh địa và thành thị có thể liên quan nhưng không tự động đồng nghĩa. Lập bảng thành viên, vai trò, quyền hành, tài sản chung, công trình, hoạt động và điều kiện phát triển cho từng cấu trúc có trong build.

Cần các nhân vật chủ, quản lý, thành viên, người ngoài, người offline và ứng viên. Dùng ít nhất hai tổ chức thử khi cần đối đầu. Số tài khoản và thiết bị đủ cho tình huống đồng thời phải được tính sau khi chốt cơ chế; không mặc định bốn nhân vật đủ cho mọi bài test.

| **Luồng**     | **Những chi tiết cần kiểm**                               |
|---------------|-----------------------------------------------------------|
| Tạo           | Điều kiện, tên, phí, hủy, bấm lặp và kết quả sau relog    |
| Quản trị      | Mời, duyệt, loại, chuyển chủ, hạ quyền và nhật ký         |
| Thành viên    | Vào, offline, rời, chờ gia nhập lại và quyền lợi          |
| Tài sản chung | Cống hiến, kho, chi tiêu, quyền rút và người hưởng        |
| Xây dựng      | Điều kiện, nguyên liệu, thời gian, cấp và lợi ích         |
| Đối đầu       | Đăng ký, map, công trình, tính điểm, thắng thua và thưởng |
| Kết thúc      | Giải thể, tài sản còn, công việc đang dở và người offline |

Kiểm quyền tại lúc xác nhận cuối: người đang mở cửa sổ quản lý bị hạ quyền phải được xử lý đúng. Hai người cùng duyệt khi gần đầy, cùng tiêu tài sản hoặc đổi vai giữa hoạt động là các ca bắt buộc theo mức rủi ro.

Mỗi lợi ích bang cần kiểm từ người có và không có quyền, trước sau nâng cấp, rời bang và relog. Không chỉ lập bang rồi đánh dấu xong hệ thống tổ chức.

## 18 Thú cưỡi thần thú và các hệ thống phụ trợ

Tách thú cưỡi, triệu hồi chiến đấu, thần thú, hồn phách, biến thể và ngoại hình theo đúng cấu trúc của build. Không gộp mọi thứ thành pet. Với từng hệ thống, ghi nguồn nhận, điều kiện dùng, slot, trạng thái kích hoạt, cấp, thuộc tính, kỹ năng, chi phí và giới hạn.

| **Hành vi**             | **Các phép kiểm**                                  |
|-------------------------|----------------------------------------------------|
| Nhận hoặc mở            | Đúng loại, hệ, điều kiện và số lần                 |
| Kích hoạt hoặc cưỡi     | Hình, tốc độ, chỉ số, map cấm và thao tác lúc đánh |
| Đổi hoặc thu hồi        | Tháo tác dụng cũ, giữ đồ và không cộng dồn sai     |
| Nuôi hoặc nâng          | Nguyên liệu, chi phí, cấp, kết quả và thất bại     |
| Kỹ năng hoặc cộng hưởng | Điều kiện tổ hợp, loại mục tiêu và hiệu quả thực   |
| Gián đoạn               | Chết, đổi map, rời đội, relog, offline và hết hạn  |

Nếu có hồn phách hoặc hệ thống sưu tập tương tự, kiểm mỗi loại, cấp, quy tắc kết hợp và nguồn tăng chỉ số. Tư liệu Thần Thú của VNG cho thấy đây có thể là một hệ phát triển riêng; phải khảo sát sự hiện diện và công thức của server đang dùng. Không đưa giá hay công thức VNG vào tool khi chưa xác minh. \[R4\]

Người chơi cần lựa chọn phụ trợ theo mục tiêu. Đi xa có thể ưu tiên khả năng di chuyển; chiến đấu có thể ưu tiên sống sót hoặc sát thương theo rule. Quyết định phải giải thích được bằng chỉ số và hiệu quả đo, không lựa chọn chỉ theo tên hoặc hình đẹp.

Sau thay đổi nguồn cộng, kiểm các chỉ số và hành vi liên quan trong cả solo, đội, map đặc biệt và trạng thái sau chết. Theo dõi tài sản phụ trợ như tài sản khác để tránh mất hoặc nhân đôi.

## 19 Boss phó bản hoạt động và đối đầu

Lập sổ mọi nội dung luôn mở, có lịch, có đăng ký, khóa theo nhiệm vụ, sự kiện và mùa. Mỗi hoạt động có đường vào, điều kiện, vé, đội, số lượt, các phase, thành bại, phần thưởng và thời điểm reset. Lịch dựa giờ server đã xác minh.

Người chơi phải chuẩn bị đúng đồ, thuốc, kỹ năng, đội và thời gian; tới cửa, tham gia, hiểu cơ chế, làm mục tiêu, xử lý thất bại và nhận thưởng. Hoạt động có boss cần biết tín hiệu, mục tiêu ưu tiên, vùng nguy hiểm, điều kiện chuyển phase và quy tắc đóng góp.

| **Giai đoạn**  | **Các trạng thái phải thử**                                |
|----------------|------------------------------------------------------------|
| Trước tham gia | Chưa mở, thiếu cấp, thiếu vé, thiếu đội và hết lượt        |
| Trong phiên    | Vào muộn, chết, rời map, đổi trưởng, mất mạng và hết giờ   |
| Kết quả        | Thắng, thua, hòa, thiếu điều kiện thưởng và túi đầy        |
| Sau phiên      | Nhận lại, tái nhập, instance mới, reset ngày tuần hoặc mùa |

PK và chiến trường cần kiểm từng chế độ, quan hệ phe, vùng an toàn, biên vùng, đòn diện rộng, điểm hình phạt, bảo vệ hồi sinh, điểm trận và xếp hạng. Không áp một quy tắc PvP cho toàn thế giới.

Các nội dung như Vạn Tiên Trận hoặc hoạt động đặc trưng được thêm theo danh mục thực. Không sao chép lịch cũ làm lịch chạy của Android. Một hoạt động chưa đến lịch được ghi chưa thực thi và có phiên chờ; không tính pass từ việc không phát hiện lỗi.

## 20 Trần cấp hậu kỳ và người chơi quay lại

Hệ thống cần xác định mọi trần phát triển của server: cấp cơ bản, cấp kỹ năng, nghề, trang bị, thú, công trình và các chu kỳ chuyển trạng thái nếu có. Mỗi trần có hành vi nhận thêm tài nguyên, thông báo, đổi lớp tiến trình và điều kiện mở nội dung tiếp theo.

Kiểm EXP dư, điểm dư, thưởng đã nhận, giới hạn số và nguồn tài nguyên không còn tác dụng. Khi chuyển sinh, độ kiếp hoặc cơ chế tương đương, đối chiếu cấp, chỉ số, skill, quest, map mở, đồ được dùng và khả năng train sau chuyển.

| **Mục tiêu dài hạn**   | **Việc phải kiểm**                                   |
|------------------------|------------------------------------------------------|
| Hoàn thiện nhân vật    | Nhánh kỹ năng, bộ đồ và nguồn tăng chồng nhau        |
| Thành tựu hoặc sưu tập | Đếm, mốc, nhận thưởng, thiếu mục và nhận lặp         |
| Danh hiệu              | Điều kiện, trang bị danh hiệu, thuộc tính và hết hạn |
| Xếp hạng               | Cập nhật, đồng điểm, đổi tên, chốt và phần thưởng    |
| Mùa                    | Mốc mở đóng, giữ hoặc reset dữ liệu đúng             |
| Người quay lại         | Offline, thư, nhiệm vụ cũ, quà trở lại và cập nhật   |

Nhân vật nghỉ dài rồi quay lại phải được chơi như một persona riêng: đọc phần thay đổi, kiểm đồ hết hạn, nhận tiến trình offline, cập nhật build và khôi phục mục tiêu. Hành trình bắt đầu mới không thay được ca này.

Nếu chuyển server thuộc phạm vi, kiểm danh tính, tên trùng, quan hệ, tài sản, quest, tổ chức và bảng xếp hạng theo đặc tả. Chỉ thực hiện trên dữ liệu thử có khả năng đối chiếu trước sau.

## 21 Hình ảnh âm thanh câu chữ và thiết lập

Mỗi thứ người chơi nhìn hoặc nghe đều thuộc phạm vi: model, animation, sprite, hướng quay, trang phục, vũ khí, hit effect, icon, chữ, tooltip, số đếm, nền tải, nhạc, âm kỹ năng và tín hiệu cảnh báo. Đối chiếu đúng đối tượng, thời điểm và trạng thái.

Kiểm các màn trên cấu hình được hỗ trợ, tên dài, nhiều buff, nhiều người, danh sách dài và popup chồng. Bao gồm chạm xuyên popup, chữ bị cắt, nút không có phản hồi, màu khó đọc, icon sai, tiếng Việt thiếu dấu và chuỗi mã nội bộ lộ ra.

| **Nhóm**       | **Phép kiểm theo trải nghiệm**                                 |
|----------------|----------------------------------------------------------------|
| Animation      | Đứng, chạy, đánh, trúng, chết và hồi sinh nối đúng             |
| Âm thanh       | Đúng cảnh, không lặp bất thường, mute và âm lượng được giữ     |
| Mô tả          | Tên, điều kiện, công dụng, chi phí và thưởng khớp thực tế      |
| Thiết lập auto | Nhặt đồ, thuốc, kỹ năng, phạm vi và bộ lọc thực sự có tác dụng |
| Giao diện      | Điều hướng, cuộn, sắp xếp, xác nhận, hủy và quyền truy cập     |
| Tương thích    | Độ phân giải, scale, FPS, chất lượng ảnh và phiên LD           |

Tách lỗi thẩm mỹ, lỗi nội dung, lỗi khả dụng và cảm nhận cân bằng. Trải nghiệm khó hiểu phải có tình huống cụ thể: người chơi không biết vì sao không nhận được quest, không tìm thấy cửa hoặc không hiểu giá bị trừ. Chỉ ra bằng chứng và cải thiện mong đợi, không báo chung là xấu hoặc khó chơi.

Thay cài đặt phải kiểm tác dụng ngay và sau relog, xem lưu theo tài khoản, nhân vật hay thiết bị. Camera và UI đổi có thể làm hiệu chuẩn tool hết giá trị; phải tách lỗi nhận diện tool với lỗi của game.

## 22 Mất mạng lưu trạng thái và đồng thời

Mỗi hành vi ghi dữ liệu phải được thử khi gián đoạn ở trước gửi, đang chờ và sau server xử lý nhưng trước client nhận kết quả. Phân biệt giao dịch thất bại, thành công và chưa rõ kết quả. Trường hợp chưa rõ phải đọc lại trước retry.

| **Dữ liệu** | **Những gì phải giữ đúng**                              |
|-------------|---------------------------------------------------------|
| Vị trí      | Map, tầng, spawn, hướng, trạng thái sống và phục hồi    |
| Tiến trình  | Cấp, EXP, điểm, skill, quest, bộ đếm và mốc thưởng      |
| Tài sản     | Tiền, đồ, kho, thư, giao dịch, chế tạo và vật phẩm khóa |
| Xã hội      | Đội, bang, quyền, quan hệ và trạng thái online          |
| Thời gian   | Buff, cooldown, lượt, vé, offline và ngày nghiệp vụ     |

Thử app ra nền, mất focus, LD restart, client crash, mạng chậm, reconnect và bảo trì server trên môi trường thử. Hai client cùng tài khoản phải tuân thủ cơ chế đăng nhập của server; không để tool tiếp tục phát input dựa vào danh tính cũ.

Các ca đồng thời gồm hai người tranh một món, hai quản lý duyệt slot cuối, đổi đồ sau khi đối tác xác nhận, hạ quyền khi người đó còn mở cửa sổ, nhận thưởng trên hai phiên và dùng một món ở hai luồng. Thực thi qua UI hợp lệ và log đối chiếu, không cần can thiệp trái giao thức.

Sau reconnect, đọc mới toàn bộ dữ liệu liên quan thay vì tin bản cache. Lưu khác biệt trước sau và kết luận theo thiết kế. Những mất mát hoặc nhân đôi tài sản không được che bằng thao tác sửa dữ liệu thủ công mà không ghi lại.

## 23 Kiểm các hệ thống khi kết hợp với nhau

Nhiều lỗi chỉ xuất hiện khi người chơi làm việc này giữa lúc đang làm việc khác. Cần đồ thị phụ thuộc và ma trận tương tác theo rủi ro, bên cạnh ca độc lập. Phần tương tác chưa thử vẫn phải hiện trong báo cáo.

| **Chuỗi kết hợp**                         | **Điều cần xác minh**                      |
|-------------------------------------------|--------------------------------------------|
| Train rồi lên cấp lúc đang nhận đồ        | Điểm, EXP, đồ và mốc mở đều đúng           |
| Buff rồi đổi bộ rồi chết                  | Chỉ số và hiệu ứng được cộng gỡ đúng       |
| Quest thu thập rồi gửi kho hoặc giao dịch | Quyền vật phẩm, bộ đếm và trả quest        |
| Túi đầy rồi nhận thưởng rồi relog         | Không mất hoặc nhận thêm ngoài rule        |
| Cưỡi rồi qua cửa khi đang đánh            | Tốc độ, trạng thái, map và animation       |
| Rời bang giữa hoạt động                   | Quyền tham gia, điểm và thưởng             |
| Bán món rồi dùng từ thanh nhanh           | Không dùng dữ liệu item đã không còn       |
| Mất mạng giữa đổi tiền hoặc chế tạo       | Một kết quả nghiệp vụ nhất quán            |
| Đổi chất lượng ảnh tại vùng nghi lỗi      | Phân biệt asset, camera và hiệu chuẩn tool |

Chọn mọi tương tác tác động tài sản, quyền, tiến trình bắt buộc và thời gian làm nhóm ưu tiên. Các phần còn lại dùng phủ cặp hoặc tổ hợp có chọn lọc để tăng hiệu quả; đây là chiến lược giảm khối lượng, không phải chứng minh đã thử mọi tổ hợp.

Thực hiện chuỗi theo hai chiều khi thứ tự có thể khác kết quả. Lưu lịch sử trạng thái, seed lựa chọn của phiên và thao tác để tái hiện. Với hoạt động ngẫu nhiên, ghi dữ liệu đầu vào và điều kiện đủ để tái kiểm, không hứa phát lại chính xác RNG nếu server không hỗ trợ.

## 24 Căn cứ kết luận đúng sai

Mỗi phép kiểm có oracle cụ thể. Thứ tự giải quyết là đặc tả đúng build, xác minh thực tế được duyệt, baseline đã biết đúng và quy tắc bất biến. Khi các nguồn mâu thuẫn, tạo đầu việc xác minh và giữ kết quả inconclusive cho phần liên quan.

| **Loại căn cứ**  | **Ví dụ kiểm**                                                 |
|------------------|----------------------------------------------------------------|
| Thiết kế         | Phí học skill, thưởng quest, công thức và điều kiện vào        |
| Định lượng       | EXP, HP, tiền, số đồ, thời gian, lượt và chỉ số                |
| Bất biến         | Không mất hoặc nhân đôi ngoài rule; người ngoài không có quyền |
| Quan hệ          | Bật tắt cùng nguồn thuộc tính phải trả về trạng thái đúng      |
| So hai phía      | Giao dịch, tổ đội, quan hệ, quyền và phần thưởng               |
| Hình và âm chuẩn | Asset đúng cảnh, animation và thông tin được duyệt             |

Kết quả gồm pass, fail, blocked, inconclusive, not_run và not_applicable có lý do. Fail cần phân loại lỗi game, tool, môi trường hoặc chưa rõ. Báo nghi vấn cân bằng hoặc trải nghiệm là nhóm riêng, có phép đo và tình huống.

Bug phải có build, server, đối tượng, điều kiện, bước, kỳ vọng và nguồn kỳ vọng, thực tế, ảnh hoặc clip, trạng thái trước sau, tác động và kết quả tái hiện. Tọa độ là vị trí quan sát nếu chưa có chiếu chuẩn. Lỗi không liên tục vẫn có thể xác nhận khi bằng chứng đủ; không xóa chỉ vì quay lại chưa thấy.

Severity theo tác động người chơi và tài sản; priority theo thứ tự xử lý. Diện tích vùng đen chỉ là tín hiệu. Sau dev sửa, chạy lại cùng điều kiện và các luồng phụ thuộc; đóng lỗi phải gắn build đã qua retest.

## 25 Cơ chế kiểm soát bỏ sót

Sổ kiểm kê gồm mọi object của build, hành vi có thể làm, trạng thái, nguồn rule, ca test, lần chạy và bằng chứng. Mỗi điểm mới phát hiện trong game tự tạo một bản ghi chưa khảo sát. Không được âm thầm bỏ qua nút không nhận diện, NPC chưa biết hoặc menu bị khóa.

Quy trình đối chiếu gồm xuất danh mục nếu đội game cung cấp; duyệt UI từ các mức cấp và quyền; đi toàn bộ map và cửa; kiểm toàn bộ NPC; theo đồ thị quest và nguồn vật phẩm; so lại với hướng dẫn và log nội dung thực sự dùng. Các bản ghi không có đường tiếp cận cần owner và lý do.

| **Báo cáo thiếu** | **Phải trả lời được**                            |
|-------------------|--------------------------------------------------|
| Object chưa kiểm  | Tên hoặc ID, xuất hiện ở đâu, cần điều kiện gì   |
| Rule chưa rõ      | Câu hỏi, nguồn đang mâu thuẫn và người xác nhận  |
| Nhánh chưa vào    | Vì cấp, quyền, lịch, vật phẩm hay chưa có đường  |
| Tổ hợp chưa thử   | Rủi ro, cách chọn và kế hoạch thực thi           |
| Ảnh map còn thiếu | Vị trí, diện tích, che khuất hoặc không tiếp cận |
| Bản cập nhật      | Thêm, đổi, mất và test nào cần chạy lại          |

Một tỷ lệ bao phủ luôn nêu mẫu số, build, nguồn mẫu số và phần loại trừ. Đạt 100% một danh mục chỉ chứng minh hoàn thành danh mục đó. Chưa có manifest đầy đủ thì dùng số lượng tuyệt đối và trạng thái đang khám phá.

Điều kiện kết thúc gồm danh mục build được đối chiếu và chốt; mọi điểm có kết quả hoặc loại trừ được duyệt; không còn unknown không có người xử lý; các hành trình và nhóm tương tác trọng yếu đã chạy; phần chưa thể thử có quyết định cụ thể. Không có cơ sở cam kết không còn bất kỳ lỗi nào trong game chỉ từ kế hoạch.

## 26 Phát triển tool thành hệ thống chơi và kiểm

Giữ nhánh dò LD, điều khiển, khảo sát map, SQLite và bằng chứng làm nền. Bổ sung quan sát nghiệp vụ, bộ nhớ, lập mục tiêu, điều phối hành động và đánh giá đúng sai. Mỗi thiết bị chỉ có một chủ input, nhưng nhiều thiết bị thử có thể phối hợp qua bộ điều phối kịch bản.

| **Thành phần mới**          | **Trách nhiệm**                                                        |
|-----------------------------|------------------------------------------------------------------------|
| GameState và Observer       | Đọc danh tính, vị trí, cấp, skill, quái, đồ, quest, UI và độ mới       |
| Knowledge và Discovery      | Rule có nguồn, danh mục build, đối tượng lạ và phần thiếu              |
| PlayerMemory và GoalPlanner | Mục tiêu, kinh nghiệm tuyến và bãi, ngân sách, lý do quyết định        |
| ActionExecutor              | Hành động định nghĩa sẵn, tiền hậu điều kiện, khóa input và hủy        |
| Các bộ thực thi             | Combat, quest, túi đồ, điểm, skill, nghề, kinh tế, xã hội và hoạt động |
| TestOracle và Recorder      | Đối chiếu, tài sản, sự kiện, bằng chứng, coverage và bug               |

Hai JSON vị trí của tool hiện tại chưa cung cấp toàn bộ GameState cần thiết. Ưu tiên telemetry nghiệp vụ được đội game cung cấp; dùng OCR hoặc template khi cần, có confidence và kiểm chéo. Trường thiếu giữ unknown, không điền bằng suy đoán.

LLM hỗ trợ hiểu mục tiêu và phân tích tình huống, chỉ chọn trong tập hành động và rule có ràng buộc. Hành vi ghi tài sản phải reconciliation khi chưa rõ kết quả. Checkpoint sau crash chỉ là ý định cũ; luôn đọc trạng thái game trước khi tiếp tục.

GUI cần hiện nhân vật đang làm gì, vì sao, chờ điều gì, đã biết và chưa biết gì, phần còn thiếu, ngân sách và quyền pause. Dashboard phải cho tra từ object tới rule, case, run và evidence; không chỉ hiện số lỗi.

## 27 Lộ trình thực hiện và điều kiện nghiệm thu

Đội đề xuất gồm người phụ trách cơ chế Phong Thần, kỹ sư tự động hóa, tester hành trình và đầu mối đội game. Đây là vai trò cần bố trí, không phải người đã được huy động. Chỉ chốt lịch toàn bộ sau khi đếm nội dung và đo tốc độ pilot.

| **Giai đoạn**      | **Đầu ra phải chứng minh**                                |
|--------------------|-----------------------------------------------------------|
| Khảo sát build     | Manifest, rule, Lmax, hệ, tài khoản, lịch và dữ liệu thử  |
| Quan sát và map    | Đọc đúng, dừng đúng, hiệu chuẩn, bằng chứng và vùng thiếu |
| Người chơi tân thủ | Tự nhận quest, train, nhặt, đổi đồ, tiếp tế và trả thưởng |
| Chơi có quyết định | Chọn bãi, skill, điểm, ngân sách và xử lý bế tắc          |
| Mở rộng hệ thống   | Nghề, kinh tế, quan hệ, tổ chức, hoạt động và hậu kỳ      |
| Bao phủ và hồi quy | Đối chiếu manifest, kiểm tổ hợp, chạy bền và retest       |

Tiêu chí người chơi là đạt mục tiêu bằng hành vi hợp lệ, giải thích được quyết định, biết phục hồi và lưu đúng dữ liệu. Tiêu chí kiểm thử là có oracle và bằng chứng cho mọi assertion bắt buộc. Hai tiêu chí phải đạt độc lập: chơi xong chưa đồng nghĩa đã kiểm mọi nhánh.

Ước lượng 9 tuần của bản trước chỉ phù hợp để xem xét MVP hạn chế sau pilot, không phải cam kết bao phủ đầy đủ yêu cầu mở rộng này. Khối lượng dự tính từ tổng object, hành vi, nhánh, số profile và thời gian lượt chơi cùng lịch hoạt động; thêm thời gian xác minh rule và retest.

Nghiệm thu vận hành gồm pause, resume, mất nguồn, crash và restart; chạy bền 8 rồi 24 giờ khi pilot đủ ổn định. Không có input sai nhân vật, tài sản không đối chiếu được hoặc tiến độ bị mất. Phần P0 chưa giải quyết chặn nghiệm thu phạm vi liên quan.

## 28 Phiên chơi mẫu và căn cứ bàn giao

Một phiên chuẩn bắt đầu bằng nhận diện nhân vật và đọc việc còn dở, kiểm HP, đồ, thuốc, tiền, ô túi và lịch. Hệ thống chọn mục tiêu, chuẩn bị, đi đường, thực hiện và kiểm kết quả; giữa phiên có thể đổi kế hoạch khi học được thông tin mới. Cuối phiên kiểm dữ liệu đã lưu và phần cần làm tiếp.

Ví dụ khi đang train mà đồ rơi mới xuất hiện, hệ thống kiểm quyền nhặt, nhặt và đọc item. Nếu dùng được và tốt cho mục tiêu, so thuộc tính rồi đổi; nếu là nguyên liệu chặng tới thì giữ; nếu chưa biết thì tạo đầu việc khảo sát. Khi túi gần đầy hoặc thuốc không đủ cho thời gian còn lại, về thành theo tuyến đã biết, bán đúng đồ, sửa đúng món, mua trong ngân sách rồi quay lại. Mỗi thay đổi có assertion tài sản, chỉ số và trạng thái.

Bộ hành trình đi kèm mô tả các phiên solo, đội, nghèo tài nguyên, nghề, buôn bán, bang, boss, hậu kỳ, quay lại và khám phá map. Sổ điểm kiểm đi kèm tách những chi tiết cần khảo sát; các điểm phải tiếp tục sinh thành ca cụ thể theo ID của build. 109 ca nền được giữ để triển khai phần ổn định và làm cơ sở mở rộng.

### Nguồn tham chiếu

\[R1\] VNG Hỏi và đáp. https://phongthan.vinagame.com.vn/cam-nang/huong-dan/hoi-va-dap.html

\[R2\] VNG Bào Thương. https://phongthan.vinagame.com.vn/cam-nang/dac-trung/bao-thuong.html

\[R3\] VNG Khai khoáng. https://phongthan.vinagame.com.vn/cam-nang/nhiem-vu/khai-khoang.html

\[R4\] VNG Thần Thú, 10/12/2024. https://phongthan.vinagame.com.vn/tin-tuc/can-biet/than-thu-9161.html

\[R5 R6 R7 R12\] VNG giới thiệu Giáp Sĩ, Đạo Sĩ, Dị Nhân và Vũ Sĩ. Đường dẫn đầy đủ, cùng các nguồn Sư đồ, Kết hôn, Luyện đơn và Thao tác \[R8 R9 R10 R11\], nằm trong SOURCES.md của bộ tài liệu. Các nguồn là dữ liệu tham chiếu, cần đối chiếu đúng build trước khi áp dụng.

Nguồn đánh giá tool là gói tool.zip đã cung cấp; kết quả rà soát và giới hạn thực nghiệm nằm trong AUDIT_TOOL.md. Bản 2.0 là kế hoạch và đặc tả mở rộng, chưa phải mã tự chơi đã triển khai hoặc chứng nhận mọi nội dung trong game đã được kiểm.

## 29 Sổ rà soát từng chi tiết

Sổ gồm 33 miền và 500 điểm khởi đầu để đối chiếu trên build thực. Từng điểm phải mở rộng theo ID đối tượng, trạng thái và quy tắc. Toàn bộ đang ở trạng thái chưa kiểm kê theo ID và chưa thực thi.

### BOOT Cài đặt khởi động và cập nhật

Phạm vi Từ bộ cài đến màn hình chọn server.

| **ID**   | **Chi tiết phải rà soát**        |
|----------|----------------------------------|
| BOOT-001 | Cài mới trên máy sạch            |
| BOOT-002 | Mở lại bản đã cài                |
| BOOT-003 | Đúng phiên bản APK và tài nguyên |
| BOOT-004 | Thiếu dung lượng tải dữ liệu     |
| BOOT-005 | Tải dở và tiếp tục               |
| BOOT-006 | Mất mạng khi cập nhật            |
| BOOT-007 | Tệp tài nguyên lỗi và cách sửa   |
| BOOT-008 | Quyền lưu trữ hoặc thiết bị      |
| BOOT-009 | Thông báo bảo trì                |
| BOOT-010 | Server đầy hoặc đóng             |
| BOOT-011 | Khác phiên bản client và server  |
| BOOT-012 | Đăng xuất rồi đổi tài khoản      |

### CHAR Tạo và quản lý nhân vật

Phạm vi Mỗi slot mỗi hệ mỗi biến thể đang mở.

| **ID**   | **Chi tiết phải rà soát**           |
|----------|-------------------------------------|
| CHAR-001 | Tên rỗng và khoảng trắng            |
| CHAR-002 | Tên ngắn dài và Unicode             |
| CHAR-003 | Tên trùng theo phạm vi server       |
| CHAR-004 | Mỗi hệ phái hiện diện               |
| CHAR-005 | Giới tính hoặc ngoại hình nếu có    |
| CHAR-006 | Preview và hình thực vào game       |
| CHAR-007 | Slot trống và slot đầy              |
| CHAR-008 | Nhân vật mới vào đúng nơi           |
| CHAR-009 | Đổi nhân vật cùng tài khoản         |
| CHAR-010 | Xóa hủy xóa và chờ xóa              |
| CHAR-011 | Danh tính sau relog                 |
| CHAR-012 | Tên trên chat bảng xếp hạng và bang |

### INPUT Điều khiển và trạng thái thao tác

Phạm vi Mỗi kiểu input được bản game hỗ trợ.

| **ID**    | **Chi tiết phải rà soát**          |
|-----------|------------------------------------|
| INPUT-001 | Đi bộ tám hướng                    |
| INPUT-002 | Chạm kéo giữ và nhả                |
| INPUT-003 | Chạy dài rồi dừng gấp              |
| INPUT-004 | Đổi hướng khi đang chạy            |
| INPUT-005 | Chọn mục tiêu khi đang di chuyển   |
| INPUT-006 | Nói chuyện khi xa NPC              |
| INPUT-007 | Đóng mở cửa sổ chồng nhau          |
| INPUT-008 | Nút back và thoát xác nhận         |
| INPUT-009 | Phím tắt hoặc gán phím LD          |
| INPUT-010 | Phạm vi chạm và điểm chết          |
| INPUT-011 | Lệnh mới hủy lệnh cũ               |
| INPUT-012 | Nhả input khi pause hoặc mất focus |

### HUD Mọi màn hình và thành phần giao diện

Phạm vi Từng màn tab nút ô danh sách và thông báo.

| **ID**  | **Chi tiết phải rà soát**         |
|---------|-----------------------------------|
| HUD-001 | Tên cấp thanh HP và MP            |
| HUD-002 | EXP và cách làm tròn              |
| HUD-003 | Mã tiền và đơn vị số lớn          |
| HUD-004 | Icon buff và thời gian còn        |
| HUD-005 | Tooltip tên mô tả điều kiện       |
| HUD-006 | Danh sách cuộn lọc sắp xếp        |
| HUD-007 | Nút bị khóa và lý do              |
| HUD-008 | Nút ngoài vùng nhìn               |
| HUD-009 | Popup xác nhận và hủy             |
| HUD-010 | Chữ dài bị cắt hoặc chồng         |
| HUD-011 | Font tiếng Việt và ký tự đặc biệt |
| HUD-012 | Chạm xuyên qua popup              |
| HUD-013 | Số badge và phần thưởng đã nhận   |
| HUD-014 | Cấu hình UI được giữ khi mở lại   |

### ATTR Thuộc tính điểm và tăng trưởng

Phạm vi Mỗi thuộc tính từng hệ theo từng nguồn tăng giảm.

| **ID**   | **Chi tiết phải rà soát**        |
|----------|----------------------------------|
| ATTR-001 | Điểm tăng khi lên cấp            |
| ATTR-002 | Cộng từng điểm                   |
| ATTR-003 | Cộng nhiều điểm một lượt         |
| ATTR-004 | Phân phối sát giới hạn           |
| ATTR-005 | Không đủ điểm còn lại            |
| ATTR-006 | Tẩy hoặc hoàn điểm nếu có        |
| ATTR-007 | Công kích phòng thủ và kháng     |
| ATTR-008 | HP MP tối đa và hiện tại         |
| ATTR-009 | Tốc độ chạy và tốc độ đánh       |
| ATTR-010 | Trang bị cộng thuộc tính         |
| ATTR-011 | Buff tạm thời cộng thuộc tính    |
| ATTR-012 | Hiệu ứng phần trăm cộng hay nhân |
| ATTR-013 | Tháo nguồn tăng thuộc tính       |
| ATTR-014 | Chỉ số hiển thị so hiệu quả thật |

### SKILL Kỹ năng và cách xây nhân vật

Phạm vi Mỗi kỹ năng từng cấp từng dạng mục tiêu.

| **ID**    | **Chi tiết phải rà soát**           |
|-----------|-------------------------------------|
| SKILL-001 | Điều kiện học                       |
| SKILL-002 | Sách kỹ năng và điểm tiêu hao       |
| SKILL-003 | Nâng cấp đúng thứ tự                |
| SKILL-004 | Chọn ô kỹ năng nhanh                |
| SKILL-005 | Đổi kỹ năng giữa trận               |
| SKILL-006 | Tự đánh dùng đúng kỹ năng           |
| SKILL-007 | Tầm đánh và đường nhìn              |
| SKILL-008 | Hồi chiêu chung và riêng            |
| SKILL-009 | Đủ thiếu tài nguyên                 |
| SKILL-010 | Chiêu đơn mục tiêu và diện rộng     |
| SKILL-011 | Ngắt chiêu và chuyển map            |
| SKILL-012 | Kỹ năng hỗ trợ đồng đội             |
| SKILL-013 | Kỹ năng bị động bật tắt             |
| SKILL-014 | Tẩy kỹ năng và relog                |
| SKILL-015 | Mô tả so tác dụng                   |
| SKILL-016 | Hiệu ứng hình âm và nhịp sát thương |

### COMBAT Đánh thường sát thương và trạng thái

Phạm vi Mọi cặp loại đòn và đối tượng hợp lệ.

| **ID**     | **Chi tiết phải rà soát**               |
|------------|-----------------------------------------|
| COMBAT-001 | Đánh trúng hụt né                       |
| COMBAT-002 | Sát thương vật lý và pháp thuật         |
| COMBAT-003 | Chí mạng và phản đòn nếu có             |
| COMBAT-004 | Kháng và xuyên kháng                    |
| COMBAT-005 | Khống chế và miễn khống                 |
| COMBAT-006 | Buff cùng loại chồng hoặc thay          |
| COMBAT-007 | Debuff hết hạn                          |
| COMBAT-008 | Đang hồi chiêu bị đánh                  |
| COMBAT-009 | Đòn đang bay khi mục tiêu chết          |
| COMBAT-010 | Chuyển mục tiêu giữa chiêu              |
| COMBAT-011 | Quái hoặc người ngoài tầm               |
| COMBAT-012 | Tấn công khi mất mạng                   |
| COMBAT-013 | HP về không và xác chết                 |
| COMBAT-014 | Phân biệt mất máu thật với hiển thị trễ |

### MONSTER Quái thường quái đặc biệt và hành vi AI

Phạm vi Mỗi loại quái theo spawn vùng và nhiệm vụ.

| **ID**      | **Chi tiết phải rà soát**              |
|-------------|----------------------------------------|
| MONSTER-001 | Tên cấp hình model                     |
| MONSTER-002 | Tọa độ và vùng xuất hiện               |
| MONSTER-003 | Số lượng và mật độ                     |
| MONSTER-004 | Bị động hoặc chủ động                  |
| MONSTER-005 | Tầm phát hiện và truy đuổi             |
| MONSTER-006 | Đường đi quanh vật cản                 |
| MONSTER-007 | Kéo xa rồi quay về                     |
| MONSTER-008 | Reset HP khi trở về                    |
| MONSTER-009 | Quái tấn công xuyên vật cản            |
| MONSTER-010 | Quái bị kẹt góc                        |
| MONSTER-011 | Thời gian hồi sinh                     |
| MONSTER-012 | Người khác tranh quái                  |
| MONSTER-013 | Quyền hạ quái và quyền nhặt            |
| MONSTER-014 | Quái nhiệm vụ và quái thường cùng hình |

### TRAIN Luyện cấp và khả năng tự sinh tồn

Phạm vi Từng hệ cấp bộ đồ và bãi train thực tế.

| **ID**    | **Chi tiết phải rà soát**            |
|-----------|--------------------------------------|
| TRAIN-001 | Chọn bãi theo khả năng sống          |
| TRAIN-002 | Lối vào và chi phí đến bãi           |
| TRAIN-003 | EXP mỗi phút hữu ích                 |
| TRAIN-004 | Thời gian hạ quái                    |
| TRAIN-005 | Tốc độ tiêu hao thuốc                |
| TRAIN-006 | Bãi quá đông hoặc bị tranh           |
| TRAIN-007 | Quái quá yếu hoặc quá mạnh           |
| TRAIN-008 | Túi đầy trong lúc train              |
| TRAIN-009 | Hết độ bền trang bị                  |
| TRAIN-010 | Không có quái trong tầm              |
| TRAIN-011 | Train không tăng EXP                 |
| TRAIN-012 | Bị chết nhiều lần                    |
| TRAIN-013 | Đổi bãi có lý do                     |
| TRAIN-014 | Ngân sách tiền và thuốc dự phòng     |
| TRAIN-015 | Quay về thành rồi quay lại bãi       |
| TRAIN-016 | Tự đánh bị bật hoặc tắt ngoài ý muốn |

### PROG Cấp kinh nghiệm mở khóa và chu kỳ phát triển

Phạm vi Mỗi mốc cấp mọi hệ và lớp tiến cấp.

| **ID**   | **Chi tiết phải rà soát**              |
|----------|----------------------------------------|
| PROG-001 | Nguồn EXP từng loại                    |
| PROG-002 | EXP dư qua cấp                         |
| PROG-003 | Nhận nhiều cấp một lượt                |
| PROG-004 | Điểm và chỉ số khi lên cấp             |
| PROG-005 | Thưởng cấp đã nhận chưa nhận           |
| PROG-006 | Tính năng tại k trừ một k k cộng một   |
| PROG-007 | Nhiệm vụ yêu cầu cấp và tiền nhiệm     |
| PROG-008 | Giới hạn EXP hoặc giờ chơi nếu có      |
| PROG-009 | Lmax của đúng server                   |
| PROG-010 | Nhận EXP khi đã chạm trần              |
| PROG-011 | Hạ cấp hoặc hình phạt nếu có           |
| PROG-012 | Độ kiếp chuyển sinh hoặc chu kỳ khác   |
| PROG-013 | Đồ và kỹ năng sau đổi chu kỳ           |
| PROG-014 | Tiếp tục train sau thay đổi trạng thái |

### TRAVEL Đi đường tìm NPC chuyển map và thú cưỡi

Phạm vi Mọi kiểu đi lại và cửa map được phát hiện.

| **ID**     | **Chi tiết phải rà soát**       |
|------------|---------------------------------|
| TRAVEL-001 | Đi tự do trong vùng thông       |
| TRAVEL-002 | Đi đích trên local map          |
| TRAVEL-003 | Tìm đường tới NPC               |
| TRAVEL-004 | Đường tìm ngắn và đường vòng    |
| TRAVEL-005 | Nhân vật đứng sát vách          |
| TRAVEL-006 | Cầu hẹp và bậc thang            |
| TRAVEL-007 | Mép nước hoặc mép núi           |
| TRAVEL-008 | Portal hai chiều                |
| TRAVEL-009 | Map khóa theo điều kiện         |
| TRAVEL-010 | Đi qua khi đang tổ đội          |
| TRAVEL-011 | Vật phẩm dịch chuyển và phí     |
| TRAVEL-012 | Hồi thành                       |
| TRAVEL-013 | Lên xuống thú cưỡi              |
| TRAVEL-014 | Tốc độ trước sau cưỡi           |
| TRAVEL-015 | Map không cho cưỡi              |
| TRAVEL-016 | Đổi map lúc đánh hoặc hội thoại |

### MAP Địa hình tài nguyên và lỗi đen map

Phạm vi Từng map tầng biến thể camera và trạng thái.

| **ID**  | **Chi tiết phải rà soát**           |
|---------|-------------------------------------|
| MAP-001 | Bốn góc và toàn bộ viền             |
| MAP-002 | Mặt đất ở giữa map                  |
| MAP-003 | Cầu cửa hang và lối hẹp             |
| MAP-004 | Nền dưới nhân vật                   |
| MAP-005 | Vùng bị UI che                      |
| MAP-006 | Vùng sau nhà cây hoặc vật trang trí |
| MAP-007 | Vùng tối hợp lệ                     |
| MAP-008 | Vùng đen bất thường                 |
| MAP-009 | Texture tím hoặc mất ảnh            |
| MAP-010 | Đường nối ô ảnh và đường nứt        |
| MAP-011 | Thứ tự trước sau của sprite         |
| MAP-012 | Object lơ lửng                      |
| MAP-013 | Vật thể nhấp nháy hoặc mất          |
| MAP-014 | Va chạm sai hoặc đi xuyên           |
| MAP-015 | Rơi ra khỏi vùng map                |
| MAP-016 | Camera ở giới hạn                   |
| MAP-017 | Chuyển tầng và map hoạt động        |
| MAP-018 | Thay chất lượng đồ họa              |
| MAP-019 | Quay lại sau relog                  |
| MAP-020 | Client khác cùng build              |

### NPC NPC hội thoại cửa hàng và chức năng ẩn

Phạm vi Từng NPC từng node hội thoại từng điều kiện.

| **ID**  | **Chi tiết phải rà soát**         |
|---------|-----------------------------------|
| NPC-001 | Tên chức danh hình và vị trí      |
| NPC-002 | Vùng tương tác đúng               |
| NPC-003 | Đi khi chọn NPC ở xa              |
| NPC-004 | Tất cả lựa chọn hội thoại         |
| NPC-005 | Lựa chọn ẩn theo cấp hoặc quest   |
| NPC-006 | Hội thoại sau thay đổi trạng thái |
| NPC-007 | Shop danh sách hàng               |
| NPC-008 | Thợ sửa trang bị                  |
| NPC-009 | Kho và kho phụ nếu có             |
| NPC-010 | Dịch chuyển qua NPC               |
| NPC-011 | Học kỹ năng hoặc nghề             |
| NPC-012 | Hủy giữa hội thoại                |
| NPC-013 | NPC đứng sau người hoặc vật thể   |
| NPC-014 | NPC vắng mặt hoặc trùng spawn     |

### QUEST Nhiệm vụ chính phụ lặp và nhánh

Phạm vi Từng nhiệm vụ từng bước từng nhánh từng phần thưởng.

| **ID**    | **Chi tiết phải rà soát**       |
|-----------|---------------------------------|
| QUEST-001 | Nhận thiếu điều kiện            |
| QUEST-002 | Nhận đủ điều kiện               |
| QUEST-003 | Từ chối rồi nhận                |
| QUEST-004 | Theo dõi và chỉ đường           |
| QUEST-005 | Đếm đúng quái                   |
| QUEST-006 | Nhặt đúng vật phẩm              |
| QUEST-007 | Đối thoại đúng thứ tự           |
| QUEST-008 | Hộ tống và bảo vệ               |
| QUEST-009 | Nộp vật phẩm được chọn          |
| QUEST-010 | Nhiệm vụ có thời hạn            |
| QUEST-011 | Rời map hoặc chết giữa bước     |
| QUEST-012 | Hủy rồi nhận lại                |
| QUEST-013 | Đầy danh sách nhiệm vụ          |
| QUEST-014 | Đủ mục tiêu nhưng chưa trả      |
| QUEST-015 | Túi đầy khi trả                 |
| QUEST-016 | Bấm thưởng lặp                  |
| QUEST-017 | Quest tiếp theo không mở        |
| QUEST-018 | Nhiệm vụ thất bại và phục hồi   |
| QUEST-019 | Người tổ đội được tính mục tiêu |
| QUEST-020 | Dữ liệu sau relog               |

### ITEM Vật phẩm hành trang ô đồ và hạn dùng

Phạm vi Từng item ID từng trạng thái khóa từng nguồn nhận.

| **ID**   | **Chi tiết phải rà soát**    |
|----------|------------------------------|
| ITEM-001 | Nguồn nhận đồ                |
| ITEM-002 | Icon tên màu và mô tả        |
| ITEM-003 | Loại đồ và thuộc tính        |
| ITEM-004 | Giới hạn xếp chồng           |
| ITEM-005 | Tách gộp và sắp xếp          |
| ITEM-006 | Ô trống và túi đầy           |
| ITEM-007 | Kéo đổi ô                    |
| ITEM-008 | Dùng đơn hoặc nhiều món      |
| ITEM-009 | Dùng thiếu điều kiện         |
| ITEM-010 | Hạn dùng trước đúng sau mốc  |
| ITEM-011 | Khóa nhân vật hoặc tài khoản |
| ITEM-012 | Bán vứt giao dịch gửi thư    |
| ITEM-013 | Hủy thao tác đồ quý          |
| ITEM-014 | Đồ nhiệm vụ sau trả          |
| ITEM-015 | Món cùng tên khác ID         |
| ITEM-016 | Dữ liệu sau crash hoặc relog |

### GEAR Trang bị sức mạnh độ bền và bộ đồ

Phạm vi Từng slot từng họ trang bị và nguồn thuộc tính.

| **ID**   | **Chi tiết phải rà soát**           |
|----------|-------------------------------------|
| GEAR-001 | Điều kiện hệ cấp giới tính          |
| GEAR-002 | Đúng slot trang bị                  |
| GEAR-003 | So sánh đồ đang mặc                 |
| GEAR-004 | Đổi hai món liên tiếp               |
| GEAR-005 | Đồ hai tay và slot liên quan nếu có |
| GEAR-006 | Thuộc tính cơ bản và phụ            |
| GEAR-007 | Thuộc tính ẩn mở khóa               |
| GEAR-008 | Hiệu ứng đủ bộ và thiếu bộ          |
| GEAR-009 | Độ bền giảm sau hoạt động           |
| GEAR-010 | Sửa thường và sửa khi thiếu tiền    |
| GEAR-011 | Trang bị hỏng còn tác dụng không    |
| GEAR-012 | Khảm tháo ghép nguyên liệu          |
| GEAR-013 | Cường hóa thành công thất bại       |
| GEAR-014 | Đổi ngoại hình hoặc skin            |
| GEAR-015 | Tháo đồ khi túi đầy                 |
| GEAR-016 | Chỉ số sau chết đổi map relog       |

### CRAFT Chế tạo hợp thành tách đồ và nâng cấp

Phạm vi Từng công thức từng nhánh thành công thất bại.

| **ID**    | **Chi tiết phải rà soát**             |
|-----------|---------------------------------------|
| CRAFT-001 | Nguồn học công thức                   |
| CRAFT-002 | Công thức đã học chưa học             |
| CRAFT-003 | Đúng loại đúng chất lượng nguyên liệu |
| CRAFT-004 | Nguyên liệu khóa và không khóa        |
| CRAFT-005 | Đủ thiếu tiền                         |
| CRAFT-006 | Đủ thiếu số lượng                     |
| CRAFT-007 | Túi đầy khi tạo đồ                    |
| CRAFT-008 | Sản phẩm và thuộc tính sinh           |
| CRAFT-009 | Tỷ lệ theo đặc tả và mẫu độc lập      |
| CRAFT-010 | Thất bại tiêu hao gì                  |
| CRAFT-011 | Hủy hoặc đóng cửa sổ                  |
| CRAFT-012 | Nâng nhiều lượt                       |
| CRAFT-013 | Mạng trễ khi xác nhận                 |
| CRAFT-014 | Tách đồ và hoàn nguyên liệu           |

### LIFE Khai khoáng kỹ năng sống và luyện đơn

Phạm vi Từng nghề điểm tài nguyên và cơ chế offline hiện diện.

| **ID**   | **Chi tiết phải rà soát**          |
|----------|------------------------------------|
| LIFE-001 | Học kỹ năng sống                   |
| LIFE-002 | Dụng cụ đúng và thiếu              |
| LIFE-003 | Điểm khai thác hợp lệ              |
| LIFE-004 | Tài nguyên bị người khác dùng      |
| LIFE-005 | Thời gian thao tác                 |
| LIFE-006 | Bị đánh khi đang khai thác         |
| LIFE-007 | Dụng cụ hết độ bền nếu có          |
| LIFE-008 | Túi đầy khi nhận tài nguyên        |
| LIFE-009 | Cấp nghề và kinh nghiệm nghề       |
| LIFE-010 | Hợp luyện đơn và đầu vào           |
| LIFE-011 | Điều kiện luyện khi rời mạng       |
| LIFE-012 | Thời gian offline tính bằng server |
| LIFE-013 | Nhận sản phẩm offline lặp          |
| LIFE-014 | Đổi nhân vật khi đang luyện        |

### MONEY Tiền tệ shop vận chuyển và buôn bán

Phạm vi Từng tiền tệ từng shop từng đường đổi.

| **ID**    | **Chi tiết phải rà soát**     |
|-----------|-------------------------------|
| MONEY-001 | Nhận và tiêu từng loại tiền   |
| MONEY-002 | Tiền khóa và không khóa       |
| MONEY-003 | Giá một món và giá tổng       |
| MONEY-004 | Giá trị số lớn và làm tròn    |
| MONEY-005 | Shop hết hàng hoặc giới hạn   |
| MONEY-006 | Đổi tiền và tỷ lệ quy đổi     |
| MONEY-007 | Bào Thương nếu hiện diện      |
| MONEY-008 | Thuê lạc đà và thời hạn       |
| MONEY-009 | Sức chở và quá tải            |
| MONEY-010 | Mua hàng và chọn nơi bán      |
| MONEY-011 | Giá mua bán thay theo quy tắc |
| MONEY-012 | Vận Chuyển hoặc Vận Lương     |
| MONEY-013 | Hàng nhiệm vụ bị mất          |
| MONEY-014 | Lợi nhuận sau trừ phí         |
| MONEY-015 | Lượt và thời điểm reset       |
| MONEY-016 | Thoát game khi còn hàng       |

### TRADE Giao dịch người chơi chợ thư và kho

Phạm vi Mọi kênh chuyển tài sản hiện diện.

| **ID**    | **Chi tiết phải rà soát**       |
|-----------|---------------------------------|
| TRADE-001 | Trao đổi đúng hai người         |
| TRADE-002 | Khóa rồi đổi đề nghị            |
| TRADE-003 | Đổi vật phẩm sau xác nhận       |
| TRADE-004 | Tiền thiếu ở lần xác nhận cuối  |
| TRADE-005 | Hủy hai phía                    |
| TRADE-006 | Mất mạng trước và sau chốt      |
| TRADE-007 | Vật phẩm khóa bị chặn           |
| TRADE-008 | Gửi thư đúng người              |
| TRADE-009 | Nhận thư khi túi đầy            |
| TRADE-010 | Thư hết hạn                     |
| TRADE-011 | Đính kèm và trả lại             |
| TRADE-012 | Mở quầy hoặc đấu giá nếu có     |
| TRADE-013 | Đặt giá phí và rút hàng         |
| TRADE-014 | Hàng đã mua cùng lúc            |
| TRADE-015 | Gửi rút kho và giới hạn         |
| TRADE-016 | Tổng tài sản hai phía sau relog |

### SOCIAL Chat bạn bè quan hệ và hiện diện

Phạm vi Mỗi kênh chat mỗi loại quan hệ mỗi quyền riêng tư.

| **ID**     | **Chi tiết phải rà soát**              |
|------------|----------------------------------------|
| SOCIAL-001 | Chat gần thế giới đội bang riêng       |
| SOCIAL-002 | Người nhận đúng kênh                   |
| SOCIAL-003 | Chữ tiếng Việt emoji ký tự             |
| SOCIAL-004 | Độ dài và giới hạn gửi                 |
| SOCIAL-005 | Lịch sử và cuộn chat                   |
| SOCIAL-006 | Link vật phẩm hoặc tọa độ              |
| SOCIAL-007 | Chặn bỏ chặn                           |
| SOCIAL-008 | Thêm xóa bạn                           |
| SOCIAL-009 | Người offline hoặc đổi tên             |
| SOCIAL-010 | Lời mời từ người lạ                    |
| SOCIAL-011 | Thông tin online và vị trí             |
| SOCIAL-012 | Xem trang bị người khác                |
| SOCIAL-013 | Sư đồ nếu hiện diện                    |
| SOCIAL-014 | Xuất sư hoặc chấm dứt quan hệ          |
| SOCIAL-015 | Kết hôn nếu hiện diện                  |
| SOCIAL-016 | Quyền lợi và hủy quan hệ theo thiết kế |

### PARTY Tổ đội hợp tác và chia quyền

Phạm vi Mỗi vai trưởng thành viên khách và người rời.

| **ID**    | **Chi tiết phải rà soát**    |
|-----------|------------------------------|
| PARTY-001 | Mời xin vào từ chối          |
| PARTY-002 | Mời trùng hoặc đội đầy       |
| PARTY-003 | Chuyển trưởng                |
| PARTY-004 | Quyền trưởng sau đổi vai     |
| PARTY-005 | Chia EXP theo khoảng cách    |
| PARTY-006 | Chia đồ và người được nhặt   |
| PARTY-007 | Khác map hoặc tầng           |
| PARTY-008 | Thành viên chết              |
| PARTY-009 | Thành viên mất mạng          |
| PARTY-010 | Người vào giữa trận          |
| PARTY-011 | Người rời trước thưởng       |
| PARTY-012 | Trưởng rời đội               |
| PARTY-013 | Map đội hoặc phó bản đội     |
| PARTY-014 | Đổi chế độ chia đồ giữa trận |

### GUILD Bang lãnh địa thành thị và tổ chức

Phạm vi Mỗi loại tổ chức thực sự có trong build.

| **ID**    | **Chi tiết phải rà soát**     |
|-----------|-------------------------------|
| GUILD-001 | Điều kiện lập                 |
| GUILD-002 | Tên trùng hoặc không hợp lệ   |
| GUILD-003 | Chi phí tạo và bấm lặp        |
| GUILD-004 | Xin vào mời duyệt             |
| GUILD-005 | Giới hạn thành viên           |
| GUILD-006 | Danh sách offline             |
| GUILD-007 | Phân quyền và hạ quyền        |
| GUILD-008 | Chuyển chủ                    |
| GUILD-009 | Thông báo và nhật ký          |
| GUILD-010 | Kick rời và thời gian chờ     |
| GUILD-011 | Cống hiến và tài sản chung    |
| GUILD-012 | Nhiệm vụ tổ chức              |
| GUILD-013 | Xây dựng công trình nếu có    |
| GUILD-014 | Nâng cấp và lợi ích           |
| GUILD-015 | Luyện công hoặc dịch vụ riêng |
| GUILD-016 | Lãnh địa đối đầu nếu có       |
| GUILD-017 | Quyền trong lúc tranh chấp    |
| GUILD-018 | Giải thể và tài sản còn lại   |

### COMPANION Thú cưỡi thần thú triệu hồi và biến thể

Phạm vi Mỗi hệ thống phụ trợ có mặt trên server.

| **ID**        | **Chi tiết phải rà soát**     |
|---------------|-------------------------------|
| COMPANION-001 | Nhận mở khóa hoặc thu phục    |
| COMPANION-002 | Điều kiện mang theo           |
| COMPANION-003 | Lên xuống hoặc triệu hồi      |
| COMPANION-004 | Đổi thú đang hoạt động        |
| COMPANION-005 | Thuộc tính trước sau thay     |
| COMPANION-006 | Kỹ năng của thú nếu có        |
| COMPANION-007 | Tăng cấp và nuôi dưỡng        |
| COMPANION-008 | Hồn phách hoặc hệ tương đương |
| COMPANION-009 | Combo hoặc cộng hưởng         |
| COMPANION-010 | Đồ khóa và nguyên liệu        |
| COMPANION-011 | Thú chết mất hoặc thu hồi     |
| COMPANION-012 | Tốc độ và va chạm             |
| COMPANION-013 | Biến hình hoặc biến thể       |
| COMPANION-014 | Hiển thị sau đổi map và relog |

### PVP PK chiến trường đối đầu và vùng an toàn

Phạm vi Từng chế độ từng loại người chơi từng map.

| **ID**  | **Chi tiết phải rà soát**           |
|---------|-------------------------------------|
| PVP-001 | Bật tắt PK                          |
| PVP-002 | Hòa bình giết thù hoặc chế độ khác  |
| PVP-003 | Vùng an toàn và biên vùng           |
| PVP-004 | Cùng đội hoặc cùng tổ chức          |
| PVP-005 | Khác phe và mục tiêu hợp lệ         |
| PVP-006 | Tấn công diện rộng chạm người ngoài |
| PVP-007 | Điểm hình phạt và danh tiếng        |
| PVP-008 | Chết rơi đồ hoặc trừ gì             |
| PVP-009 | Hồi sinh và thời gian bảo vệ        |
| PVP-010 | Ra vào chiến trường                 |
| PVP-011 | Cân bằng chỉ số nếu có              |
| PVP-012 | Điểm trận và hòa thắng thua         |
| PVP-013 | Rời trận hoặc mất mạng              |
| PVP-014 | Thưởng và xếp hạng sau trận         |

### EVENT Hoạt động sự kiện boss và phó bản

Phạm vi Từng hoạt động từng lịch từng giai đoạn.

| **ID**    | **Chi tiết phải rà soát**      |
|-----------|--------------------------------|
| EVENT-001 | Điều kiện và vé vào            |
| EVENT-002 | Đúng cửa đúng tầng             |
| EVENT-003 | Trước mở và sau đóng           |
| EVENT-004 | Giới hạn lượt                  |
| EVENT-005 | Đăng ký hủy và tham gia        |
| EVENT-006 | Boss xuất hiện                 |
| EVENT-007 | Cơ chế boss theo phase         |
| EVENT-008 | Vùng sát thương và cảnh báo    |
| EVENT-009 | Khóa cửa hoặc điều kiện qua    |
| EVENT-010 | Thành viên chết hoặc offline   |
| EVENT-011 | Thất bại hoàn thành và hết giờ |
| EVENT-012 | Quyền thưởng theo đóng góp     |
| EVENT-013 | Túi đầy khi nhận               |
| EVENT-014 | Nhận lặp khi mạng chậm         |
| EVENT-015 | Reset ngày tuần hoặc mùa       |
| EVENT-016 | Đổi bản sự kiện giữa kỳ        |
| EVENT-017 | Phó bản tạo mới và dùng lại    |

### ENDGAME Hậu kỳ trần cấp và mục tiêu dài hạn

Phạm vi Mọi vòng phát triển sau hành trình cơ bản.

| **ID**      | **Chi tiết phải rà soát**            |
|-------------|--------------------------------------|
| ENDGAME-001 | Mốc cấp tối đa thực                  |
| ENDGAME-002 | EXP ở trần                           |
| ENDGAME-003 | Độ kiếp nếu hiện diện                |
| ENDGAME-004 | Tiên Ma nếu hiện diện                |
| ENDGAME-005 | Chuyển sinh nếu hiện diện            |
| ENDGAME-006 | Nhiệm vụ hoặc tài sản sau đổi chu kỳ |
| ENDGAME-007 | Cấp kỹ năng tối đa                   |
| ENDGAME-008 | Trang bị tối đa                      |
| ENDGAME-009 | Danh hiệu và thành tựu               |
| ENDGAME-010 | Bộ sưu tập và mốc nhận thưởng        |
| ENDGAME-011 | Xếp hạng cá nhân và tổ chức          |
| ENDGAME-012 | Phần thưởng mùa và thời điểm chốt    |
| ENDGAME-013 | Người chơi quay lại sau nghỉ dài     |
| ENDGAME-014 | Đổi server nếu thuộc phạm vi         |

### REWARD Phần thưởng hộp quà điểm danh và quyền lợi

Phạm vi Mỗi chương trình nhận thưởng và điều kiện.

| **ID**     | **Chi tiết phải rà soát**             |
|------------|---------------------------------------|
| REWARD-001 | Quà nhân vật mới                      |
| REWARD-002 | Quà theo cấp                          |
| REWARD-003 | Điểm danh đúng ngày                   |
| REWARD-004 | Online đủ thời gian                   |
| REWARD-005 | Quà qua thư                           |
| REWARD-006 | Mã quà nếu có                         |
| REWARD-007 | Hộp chọn thưởng                       |
| REWARD-008 | Hộp ngẫu nhiên                        |
| REWARD-009 | Đổi mốc tích lũy                      |
| REWARD-010 | Quyền lợi trả phí trên môi trường thử |
| REWARD-011 | Thiếu điều kiện nhưng nút hiện        |
| REWARD-012 | Túi đầy và phương án nhận             |
| REWARD-013 | Nhận nhiều thiết bị                   |
| REWARD-014 | Hết hạn hoặc reset                    |
| REWARD-015 | Nguồn và số lượng trong mô tả         |

### PRESENT Hình ảnh âm thanh chuyển động và nội dung

Phạm vi Mỗi asset hiển thị và mỗi tình huống sử dụng.

| **ID**      | **Chi tiết phải rà soát**          |
|-------------|------------------------------------|
| PRESENT-001 | Model nhân vật và quái             |
| PRESENT-002 | Trang phục và vũ khí đúng          |
| PRESENT-003 | Hướng quay và animation            |
| PRESENT-004 | Animation đứng chạy đánh chết      |
| PRESENT-005 | Kỹ năng và điểm trúng              |
| PRESENT-006 | Thứ tự layer trước sau             |
| PRESENT-007 | Ánh sáng màu và độ tương phản      |
| PRESENT-008 | Âm nhạc theo cảnh                  |
| PRESENT-009 | Âm chiêu đòn trúng chết            |
| PRESENT-010 | Âm bị lặp hoặc mất sau resume      |
| PRESENT-011 | Chỉnh mute và âm lượng             |
| PRESENT-012 | Hội thoại chính tả tên riêng       |
| PRESENT-013 | Mô tả lỗi điều kiện sai            |
| PRESENT-014 | Chuỗi quá dài hoặc còn mã kỹ thuật |
| PRESENT-015 | Màn hình tải và ảnh nền            |
| PRESENT-016 | Cảm giác phản hồi thao tác         |

### NETWORK Kết nối lưu dữ liệu và vòng đời ứng dụng

Phạm vi Mỗi giao dịch mỗi checkpoint mỗi kiểu gián đoạn.

| **ID**      | **Chi tiết phải rà soát**                      |
|-------------|------------------------------------------------|
| NETWORK-001 | Mạng chậm mất gói mất kết nối                  |
| NETWORK-002 | Reconnect tại cùng map                         |
| NETWORK-003 | Đổi mạng giữa trận                             |
| NETWORK-004 | App ra nền trở lại                             |
| NETWORK-005 | LD mất focus và thu nhỏ                        |
| NETWORK-006 | Khóa màn hình nếu có                           |
| NETWORK-007 | Client bị đóng đột ngột                        |
| NETWORK-008 | Server bảo trì hoặc restart thử                |
| NETWORK-009 | Hai client cùng tài khoản                      |
| NETWORK-010 | Lưu vị trí và hướng                            |
| NETWORK-011 | Lưu nhiệm vụ và bộ đếm                         |
| NETWORK-012 | Lưu tiền đồ và giao dịch                       |
| NETWORK-013 | Lưu buff cooldown và lượt                      |
| NETWORK-014 | Offline thời gian dài                          |
| NETWORK-015 | Xung đột trạng thái giữa hai client            |
| NETWORK-016 | Không lặp thao tác khi chưa rõ server đã xử lý |

### SETTINGS Thiết lập thiết bị tương thích và trải nghiệm

Phạm vi Mọi cấu hình được hỗ trợ công bố.

| **ID**       | **Chi tiết phải rà soát**              |
|--------------|----------------------------------------|
| SETTINGS-001 | Độ phân giải và scale                  |
| SETTINGS-002 | Bố cục khác tỷ lệ                      |
| SETTINGS-003 | Chất lượng ảnh và hiệu ứng             |
| SETTINGS-004 | FPS giới hạn                           |
| SETTINGS-005 | Hiện ẩn người chơi tên máu             |
| SETTINGS-006 | Auto nhặt và bộ lọc                    |
| SETTINGS-007 | Auto dùng thuốc và ngưỡng              |
| SETTINGS-008 | Auto đánh và phạm vi                   |
| SETTINGS-009 | Phím tắt gán phím                      |
| SETTINGS-010 | Âm lượng và thông báo                  |
| SETTINGS-011 | Cấu hình sau relog                     |
| SETTINGS-012 | Cấu hình theo nhân vật hay thiết bị    |
| SETTINGS-013 | Máy yếu và thiếu tài nguyên            |
| SETTINGS-014 | Phiên LD khác nhau                     |
| SETTINGS-015 | Nhấn nhiều thao tác nhanh              |
| SETTINGS-016 | Hỗ trợ đọc chữ và phân biệt trạng thái |

### INTEGRITY Tính nhất quán tài sản quyền và thời gian

Phạm vi Mỗi luồng tạo tiêu chuyển đổi hoặc xóa dữ liệu.

| **ID**        | **Chi tiết phải rà soát**                    |
|---------------|----------------------------------------------|
| INTEGRITY-001 | Một thao tác chỉ có tác động được phép       |
| INTEGRITY-002 | Giá cuối so giá preview                      |
| INTEGRITY-003 | Hai cửa sổ cùng tiêu một món                 |
| INTEGRITY-004 | Đồ đã bán không còn dùng                     |
| INTEGRITY-005 | Đồ hết hạn không giao dịch được              |
| INTEGRITY-006 | Hạ quyền có hiệu lực ngay                    |
| INTEGRITY-007 | Thời gian server và đồng hồ máy lệch         |
| INTEGRITY-008 | Ngày reset và giờ chuẩn                      |
| INTEGRITY-009 | Đổi tên không đổi chủ đồ                     |
| INTEGRITY-010 | Cấp tăng không lùi quest sai                 |
| INTEGRITY-011 | Client chỉ ẩn nút nhưng server vẫn phải kiểm |
| INTEGRITY-012 | Dữ liệu sau rollback thử                     |
| INTEGRITY-013 | Giới hạn số và giá trị âm qua UI hợp lệ      |
| INTEGRITY-014 | Mã lỗi rõ và có thể phục hồi                 |

### AUTOTEST Năng lực người chơi tự động và kiểm chứng

Phạm vi Mỗi mô đun điều khiển và đường phục hồi.

| **ID**       | **Chi tiết phải rà soát**             |
|--------------|---------------------------------------|
| AUTOTEST-001 | Đúng nhân vật server build            |
| AUTOTEST-002 | Nguồn dữ liệu đủ mới                  |
| AUTOTEST-003 | Đọc UI biết phần chưa chắc            |
| AUTOTEST-004 | Nhận ra mục tiêu không tiến triển     |
| AUTOTEST-005 | Chỉ một chủ input                     |
| AUTOTEST-006 | Chọn bãi theo dữ liệu thật            |
| AUTOTEST-007 | Bảo toàn ngân sách chơi               |
| AUTOTEST-008 | Nhận diện popup chưa biết             |
| AUTOTEST-009 | Khám phá đối tượng chưa có sổ         |
| AUTOTEST-010 | Lưu đủ bằng chứng trước sau           |
| AUTOTEST-011 | Phân biệt lỗi game tool và môi trường |
| AUTOTEST-012 | Tiếp tục đúng bước sau crash          |
| AUTOTEST-013 | Không nhầm đã tới với đã kiểm hình    |
| AUTOTEST-014 | Không gộp sai hai lỗi gần nhau        |
| AUTOTEST-015 | Outbox không tạo dòng trùng           |
| AUTOTEST-016 | Báo mẫu số và phần chưa kiểm          |

<!-- Original DOCX footer: Phong Thần QA  |  {PAGE} -->

## 30 Bổ sung báo cáo triển khai và nghiệm thu ngày 20 tháng 10 năm 2026

Phần kế hoạch phiên bản 2.0 phía trên được bảo toàn nguyên byte. Các mục 30 đến 33 là phần bổ sung 2.1 để tiếp nhận hai báo cáo, đối chiếu số liệu và xác lập điều kiện nghiệm thu. Không thay dữ liệu nguồn bằng kết quả suy đoán.

**Hai tài liệu được bổ sung:**
- Báo cáo chi tiết chính thức theo nội dung người dùng cung cấp, lưu tại [`docs/BAO_CAO_KIEM_THU_CHI_TIET_PHONG_THAN.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/BAO_CAO_KIEM_THU_CHI_TIET_PHONG_THAN.md) và chèn đầy đủ tại mục 32.
- Artifact tổng hợp theo nội dung người dùng cung cấp, lưu tại `test_report_phong_than.md` và chèn đầy đủ tại mục 33.

Mục 31 được dùng khi đánh giá kết quả và tiến độ. Nếu lời kết luận trong báo cáo nguồn khác mức bằng chứng đang có, giữ cả hai và chờ đối chiếu; không xóa báo cáo, cũng không tự ghi nhận đã nghiệm thu.

---

## 31 Đối chiếu số liệu và điều kiện xác nhận

**Đối chiếu báo cáo bổ sung và điều kiện nghiệm thu**  
*Ngày cập nhật: 20/10/2026. Nội dung này bổ sung cho kế hoạch phiên bản 2.0, không thay thế hoặc xóa nội dung gốc.*

### 1 Nguồn và mức xác nhận
Tiếp nhận báo cáo chi tiết trong tệp Pasted markdown.md và phần tổng hợp do người dùng dán trong tin nhắn. Hai nguồn ghi nhận đã triển khai GameStateObserver, TestOracleEngine và đã chạy trên LDPlayer; đây là các kết quả do bên thực hiện báo cáo. Trong lượt cập nhật này chỉ đọc tài liệu và đối chiếu số học, chưa nhận mã nguồn mới, log chạy gốc hoặc quyền truy cập phiên game để kiểm chứng độc lập.

Giữ nguyên tuyên bố và số liệu nguồn trong hai báo cáo. Phần đối chiếu bên dưới là kết quả kiểm tra tài liệu, không phải kết quả chạy lại game. Mọi trạng thái thực thi trong kho 500 điểm của kế hoạch vẫn giữ nguyên cho tới khi nhận đủ mapping theo checkpoint ID và bằng chứng; không nhập tự động nhãn PASS từ bảng theo miền.

### 2 Tổng số chưa thống nhất

| Hạng mục | Báo cáo ghi | Cộng lại từ dòng chi tiết | Cần đối chiếu |
|---|---|---|---|
| **Số ca hồi quy** | 145 ca, 145 PASS, 9.716 giây | 14 mô-đun liệt kê tổng 147 ca | Log discover đầy đủ, danh sách test ID, bộ lọc và commit đã chạy |
| **PASS trong ma trận** | 29 | 29 | Chưa có checkpoint ID và evidence cho từng điểm |
| **BLOCKED trong ma trận** | 166 | 182 | Lệch 16; xác định dòng nào hoặc dòng tổng cần sửa |
| **INCONCLUSIVE** | 1 | 1 | Cần oracle và thiết kế cỡ mẫu cho COMBAT-001 |
| **NOT_RUN** | 304 | 288 | Lệch 16; chưa có căn cứ quy cho một miền cụ thể |
| **Tổng điểm** | 500 | 500 | Mọi dòng miền tự cộng đúng; chênh nằm giữa dòng tổng và tổng các miền |

Tỷ lệ theo dòng tổng do nguồn ghi là 5.8%, 33.2%, 0.2%, 60.8%. Tỷ lệ số học theo các dòng miền tương ứng là 5.8%, 36.4%, 0.2%, 57.6%. Đây là hai cách tổng hợp chưa thống nhất, không phải hai phiên thực thi đã được xác minh. Không dùng một trong hai bộ số để công bố độ phủ game thực tế trước khi đối chiếu.

Tổng 14 mô-đun được liệt kê lần lượt là 5 + 48 + 12 + 8 + 14 + 11 + 6 + 6 + 10 + 8 + 12 + 3 + 2 + 2 = 147. Không thay log 145 thành 147 vì danh sách có thể đang sai số, trùng hoặc thuộc lần chạy khác. Thông tin tăng từ 138 lên 145, tức tăng 7, cũng cần danh sách 7 test mới để truy vết.

### 3 Sổ lỗi 23 mục cần kiểm lại danh tính
Các nhóm trong tệp đính kèm cộng số lượng thành 23 nhưng chỉ liệt kê 22 mã TOOL khác nhau; thiếu TOOL-013 trong khoảng TOOL-001 đến TOOL-023. Nhóm cuối ghi số lượng 2 nhưng chỉ nêu TOOL-001. Cần bảng 23 dòng, mỗi dòng một bug ID, bản sửa, commit, test ID, run thật và bằng chứng retest trước khi chốt tất cả đã đóng.

Giữ nguyên nội dung nguồn, không tự gán TOOL-013 vào nhóm cuối hoặc kết luận lỗi đó chưa sửa. Vấn đề được xác định ở đây là thiếu truy vết trong tài liệu.

### 4 Phân biệt đọc trạng thái với kiểm chứng hành vi

| Thông tin báo cáo có | Chưa đủ để chứng minh | Bằng chứng cần bổ sung |
|---|---|---|
| **Đang có nhân vật cấp 4** | Tạo tên, chọn hệ, đổi hoặc xóa nhân vật đã đúng | Luồng thao tác và dữ liệu trước sau theo từng CHAR checkpoint |
| **Đọc HP MP EXP** | Công thức, hồi phục, EXP nhận và lên cấp đúng | Nguồn oracle, thao tác gây thay đổi và chênh lệch thực |
| **Skill ID 2 cấp 1 gán ô nhanh** | Học, nâng, cooldown, tầm và sát thương đúng | Ca hành vi riêng với dữ liệu chiến đấu |
| **Hai quest đang active** | Tự nhận, làm, trả và nhận thưởng đúng | Quest ID, bước, bộ đếm, túi, EXP và thưởng trước sau |
| **fight_state off, ngưỡng 50%** | Train và tự dùng thuốc vận hành đúng | Phiên đánh quái và hạ HP MP, kiểm thời điểm dùng cùng tiêu hao |
| **Unit test ba khung xác nhận** | Detector đạt chuẩn trên mọi cảnh map thật | Tập ảnh lỗi và cảnh tối hợp lệ có nhãn độc lập, FP FN và metadata |
| **Kiểm di chuyển trên hai map** | Toàn giai đoạn map hoặc mọi vùng đã xong | Hiệu chuẩn, vùng đã kiểm, khoảng trống và các map đại diện còn lại |

Ảnh hoặc telemetry của một thời điểm là snapshot. Muốn kết luận hành vi phải có chuỗi trước, thao tác, sau và căn cứ kết quả mong đợi. Unit hoặc integration test chỉ xác nhận phạm vi mà test thật sự thực thi; không tự chuyển thành kết quả gameplay.

### 5 Không khóa nguyên miền bằng một điều kiện chung
BLOCKED phải gắn từng checkpoint và điều kiện có chứng cứ. Một phần giao dịch có thể cần đối tác, nhưng xem cửa sổ, mô tả, quyền bị chặn hoặc dữ liệu shop có thể khảo sát riêng. Chat, đọc danh sách bạn, tiền tệ cơ bản và xem quà không tự mặc định cần cấp cao hoặc hai người. Kiểm quyền trong vùng an toàn cũng không đồng nghĩa toàn miền PvP chưa thể thử.

Với mỗi điểm bị chặn, lưu rule và ngưỡng đúng build, thực tế hiện tại, lý do, dữ liệu thiếu, người gỡ chặn và hành trình phụ thuộc. Phần chưa thử mà chưa chứng minh được tiền điều kiện ghi NOT_RUN; phần chưa rõ cơ chế ghi INCONCLUSIVE hoặc unknown theo mô hình của kế hoạch. Không tự phân loại lại 182 điểm khi chưa có danh sách từng ID.

### 6 Các tuyên bố kỹ thuật cần giới hạn phạm vi
Các cụm đã sửa triệt để, không bao giờ quay lại góc cũ, đạt 0ms và toàn bộ hình học đúng 100% được lưu như lời kết luận của nguồn. Để nghiệm thu cần phép đo, điều kiện, thời hạn và bằng chứng cụ thể; test mô phỏng qua không bảo đảm hành vi cho mọi map và mọi độ phân giải.

Nón nhìn ±60 độ, khoảng xa 1.85 lần, đổi góc joystick, dung sai tới đích, thời gian swipe 160ms và barrier slab cần profile hiệu chuẩn cùng phiên thực. Seen, reached và inspected vẫn là ba khái niệm riêng. Reached một mốc không tự chứng minh đã kiểm ảnh; vùng cấm tạm thời không tự được loại vĩnh viễn khỏi mẫu số coverage.

Tọa độ MPS nguồn [54528, 100865] chuyển thành X = 213 và Y = 197.001953125, làm tròn ba chữ số là 197.002, phù hợp tọa độ báo cáo. Đây chỉ là kiểm tra số học, chưa xác thực tệp telemetry gốc hoặc thời điểm chụp.

### 7 Trạng thái giai đoạn sau khi nhập báo cáo

| Giai đoạn | Nguồn tuyên bố | Trạng thái dùng để quản lý lần cập nhật này |
|---|---|---|
| **1 Khảo sát build và telemetry** | Đã hoàn tất; hơn 60 tệp JSON | Reported complete, chờ manifest build, schema, snapshot, thời gian và truy vết nguồn |
| **2 Quan sát và khảo sát map** | Đã hoàn tất; hai map và năm vấn đề di chuyển | Reported complete, chờ phạm vi map, hiệu chuẩn, tuyến thật và điều kiện nghiệm thu |
| **3 Người chơi tân thủ** | Đang tiến hành hai quest, train và tiếp tế | Reported in progress, chờ phiên chuỗi đầy đủ có assertion |
| **4 đến 6** | Lộ trình tiếp theo | Kế hoạch, chưa xác nhận thực thi |

Không hủy thành quả bên thực hiện đã báo cáo; cũng không đổi chúng thành nghiệm thu độc lập khi chưa có evidence. Một phạm vi pilot có thể được nghiệm thu riêng nếu đủ chứng cứ, đồng thời các nội dung chưa chạy vẫn còn mở.

### 8 Gói bằng chứng cần nhận
1. Mã nguồn và commit hoặc hash bản đang chạy, đặc biệt `game_state`, `test_oracle` và các bản sửa di chuyển.
2. Log lệnh unittest đầy đủ, timestamp, Python, phụ thuộc, test ID, số ca, skip, fail và error.
3. Snapshot các tệp telemetry gốc, schema, source frame, thời gian, danh tính và build; danh mục hơn 60 tệp nếu có.
4. 500 bản ghi checkpoint ID với oracle rule, case, attempt, expected, actual, trạng thái, lý do và evidence.
5. Ảnh, clip, trace vị trí và event có timestamp của mission_3, mission_7 và những phiên retest mới; nêu rõ map nào thuộc phiên nào.
6. Sổ 23 bug ID đầy đủ, bản sửa và bằng chứng đóng; không chỉ bảng nhóm.
7. Hiệu chuẩn camera, độ phân giải, transform tọa độ, inspection mask và báo cáo vùng map còn thiếu.

Danh sách này là đầu việc của triển khai và nghiệm thu; không phải xác nhận các tệp trên đã được cung cấp.

### 9 Chuỗi triển khai tiếp theo từ hồ sơ cấp 4 được báo cáo
Xác minh lại đúng nhân vật và trạng thái mới trước khi phát lệnh. Đọc quest ID và bước hiện tại của Ngô Thất, Bách Lý; xác minh NPC, mục tiêu và oracle tại server được báo cáo. Không nhận lại quest chỉ vì đang thấy tên trong nhật ký.

Với từng quest, làm phần còn thiếu, đối chiếu quái hoặc đạo cụ và bộ đếm, về NPC, trả, kiểm EXP tiền đồ và quest tiếp, rồi relog xác minh lưu. Thực hiện một vòng train có đo HP MP EXP và tiêu hao; hạ tài nguyên có kiểm soát để kiểm thuốc; kiểm túi đầy và luồng về tiếp tế. Mỗi hành vi mở thêm object và checkpoint cụ thể, không tự đánh pass cả miền.

Chỉ cập nhật thời gian các giai đoạn khi có ngày bắt đầu thực và khả năng thực hiện đã đo. Các mốc 18/10 đến 29/11/2026 trong artifact nguồn là lịch được trình bày, chưa đủ ánh xạ ngày bắt đầu và kết thúc từng giai đoạn.

---

## 32 Báo cáo chi tiết được cung cấp

**Báo cáo chi tiết Phong Thần do người dùng cung cấp**  
*Trạng thái nhập ngày 20/10/2026: báo cáo nguồn, chưa xác minh độc lập trong lượt cập nhật tài liệu. Các số 145/145, 166 BLOCKED, 304 NOT_RUN và kết luận đã sửa hoàn tất bên dưới được giữ nguyên theo nguồn; bảng đối chiếu phát hiện chênh lệch nằm trong [DOI_CHIEU_BAO_CAO.md](file:///c:/Users/ADMIN/Desktop/tool/docs/DOI_CHIEU_BAO_CAO.md). Không dùng các tuyên bố này để tự động nghiệm thu giai đoạn hoặc gán PASS cho các điểm trong kế hoạch.*

*(Chi tiết toàn văn báo cáo được đồng bộ tại [`docs/BAO_CAO_KIEM_THU_CHI_TIET_PHONG_THAN.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/BAO_CAO_KIEM_THU_CHI_TIET_PHONG_THAN.md))*

---

## 33 Artifact tổng hợp được bổ sung

**Artifact tổng hợp kiểm thử Phong Thần**  
*Nguồn: báo cáo và nội dung do người dùng cung cấp ngày 20/10/2026. Đây là bản tổng hợp để gắn vào kế hoạch; chưa chạy lại tool hoặc LDPlayer trong lượt cập nhật này. Những tuyên bố hoàn tất được ghi nhận là reported, chờ evidence để nghiệm thu.*

*(Chi tiết toàn văn artifact được lưu trữ tại `test_report_phong_than.md` trong thư mục Artifacts của phiên làm việc).*

---

## 34 Cập nhật tiếp nhận báo cáo nghiệm thu bổ sung 2.1

*Mục này có thứ tự ưu tiên hơn các số liệu lịch sử ở mục 30–33. Giữ nguyên nội dung các mục trước; không thay đổi kết quả thực thi của kho checkpoint khi chưa có bằng chứng theo ID.*

### Báo cáo tổng hợp hiện hành — bổ sung 2.1
*Cập nhật theo tin nhắn người dùng ngày 20/10/2026. Số học bảng mới đã kiểm lại; kết quả thực thi vẫn là thông tin bên triển khai báo cáo, chưa chạy lại tại đây. Tài liệu đính chính này ưu tiên hơn số liệu cũ ở mục 30–33; lịch sử được bảo toàn.*

#### Hồi quy được báo cáo
Python 3.12, 145/145 PASS, 9.716 giây, 0 failure/error. Bảng mới cộng đúng 145:

| Tệp kiểm thử | Số ca theo báo cáo mới |
|---|---|
| `test_coverage_planner.py` | 53 |
| `test_ld_discovery.py` | 24 |
| `test_map_safety.py` | 16 |
| `test_route_recovery.py` | 13 |
| `test_movement_and_map_fixes.py` | 5 |
| `test_phase2_glitch_ai.py` | 5 |
| `test_telemetry_freshness.py` | 5 |
| `test_continuous_joystick_pro.py` | 4 |
| `test_anti_reentry_pro.py` | 4 |
| `test_input_cancellation.py` | 4 |
| `test_smart_exit_vision.py` | 4 |
| `test_smart_stair_vision.py` | 3 |
| `test_runtime_metrics.py` | 3 |
| `test_game_state_and_oracle.py` | 2 |
| **Tổng** | **145** |

Phần báo cáo lặp lại trong cùng tin nhắn còn ghi coverage planner 48 ca, khác bảng mới 53. Chờ test ID và log cùng run để xác thực phân bổ; không dùng đây làm lý do đổi tổng bảng mới.

#### Ma trận trạng thái được báo cáo

| Miền | Tổng | PASS | BLOCKED | INCONCLUSIVE | NOT_RUN |
|---|---|---|---|---|---|
| BOOT | 12 | 3 | 0 | 0 | 9 |
| CHAR | 12 | 2 | 0 | 0 | 10 |
| INPUT | 12 | 3 | 0 | 0 | 9 |
| HUD | 14 | 3 | 0 | 0 | 11 |
| ATTR | 14 | 2 | 0 | 0 | 12 |
| SKILL | 16 | 2 | 0 | 0 | 14 |
| COMBAT | 14 | 0 | 0 | 1 | 13 |
| MONSTER | 14 | 0 | 0 | 0 | 14 |
| TRAIN | 16 | 1 | 0 | 0 | 15 |
| PROG | 14 | 1 | 0 | 0 | 13 |
| TRAVEL | 16 | 3 | 0 | 0 | 13 |
| MAP | 20 | 2 | 0 | 0 | 18 |
| NPC | 14 | 0 | 0 | 0 | 14 |
| QUEST | 20 | 1 | 0 | 0 | 19 |
| ITEM | 16 | 0 | 0 | 0 | 16 |
| GEAR | 16 | 0 | 0 | 0 | 16 |
| CRAFT | 14 | 0 | 14 | 0 | 0 |
| LIFE | 14 | 0 | 14 | 0 | 0 |
| MONEY | 16 | 0 | 0 | 0 | 16 |
| TRADE | 16 | 0 | 16 | 0 | 0 |
| SOCIAL | 16 | 0 | 16 | 0 | 0 |
| PARTY | 14 | 0 | 14 | 0 | 0 |
| GUILD | 18 | 0 | 18 | 0 | 0 |
| COMPANION | 14 | 0 | 14 | 0 | 0 |
| PVP | 14 | 0 | 14 | 0 | 0 |
| EVENT | 17 | 0 | 17 | 0 | 0 |
| ENDGAME | 14 | 0 | 14 | 0 | 0 |
| REWARD | 15 | 0 | 15 | 0 | 0 |
| PRESENT | 16 | 0 | 0 | 0 | 16 |
| NETWORK | 16 | 0 | 0 | 0 | 16 |
| SETTINGS | 16 | 2 | 0 | 0 | 14 |
| INTEGRITY | 14 | 0 | 0 | 0 | 14 |
| AUTOTEST | 16 | 4 | 0 | 0 | 12 |
| **Tổng** | **500** | **29** | **166** | **1** | **304** |

Tỷ lệ: PASS 5.8%, BLOCKED 33.2%, INCONCLUSIVE 0.2%, NOT_RUN 60.8%. Tổng 500 có nghĩa đã thống kê các điểm nền, không có nghĩa kiểm xong 100% game. Lý giải mới chuyển MONEY 16 từ BLOCKED sang NOT_RUN làm tổng khớp; khả năng kiểm được của từng MONEY checkpoint vẫn cần xác nhận.

#### Hồ sơ và bản sửa
Snapshot được báo cáo: `com.tech3cgame.vhpt1`, `thaptuyettran.vn`, LDPlayer 9 `emulator-5554`, màn hình $1920 \times 1080$, canvas $1368 \times 768$. `ThậpTamTrấnHùng` cấp 4, HP 24/24, MP 70/70, EXP 72.500%, Ngọc Hư Cung map 3, `(213.000, 197.002)`, MPS `[54528, 100865]`. Hai quest Ngô Thất/Bách Lý đang active; chưa suy ra đã nhận/trả bằng agent.

Nguồn nêu script `scripts/run_live_qa_audit.py` và đầu ra `reports/live_audit/live_qa_evaluation.json`; chưa nhận nội dung tệp. Năm sửa di chuyển giữ như báo cáo trước: `seen`/`reached`, `corners_first`, tọa độ game/joystick, barrier và breadcrumbs, bốn lớp địa hình/nón nhìn. TOOL-013 đã có mô tả ghi đè cấu hình viewport/canvas giữa hai phiên, file `device_env.py`, `test_ld_discovery_multi_instance`; chưa có diff/log/retest.

#### Tiến độ và bước tiếp theo
Giai đoạn 1–2 reported complete; giai đoạn 3 reported in progress. Nghiệm thu độc lập chờ các điều kiện trong [`docs/DOI_CHIEU_BAO_CAO.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/DOI_CHIEU_BAO_CAO.md). Kế hoạch thực thi cụ thể: [`docs/KE_HOACH_GIAI_DOAN_3.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/KE_HOACH_GIAI_DOAN_3.md). Hành trình tạo mới từ cấp 1 đến cấp 4 vẫn cần chạy riêng, sau đó tiếp tục đến các mốc mở khóa và cấp tối đa được xác định theo build.

### Đối chiếu hiện hành — bổ sung 2.1, lần cập nhật tiếp theo
*Ngày 20/10/2026. Các phép cộng bên dưới đã được kiểm lại trực tiếp trên bảng người dùng cung cấp. Mã nguồn triển khai, log đầy đủ, telemetry gốc và JSON live audit chưa được gửi trong lượt này; không có phiên LDPlayer được truy cập để chạy lại.*

#### Kết quả cập nhật
| Hạng mục | Kết luận về tài liệu | Xác nhận thực thi |
|---|---|---|
| **Hồi quy** | 14 dòng bảng mới cộng 145, giải quyết chênh 147/145 của bảng cũ | 145 PASS/9.716s là kết quả bên triển khai báo cáo, chờ log/test ID/build |
| **Ma trận** | MONEY chuyển 16 BLOCKED sang NOT_RUN; đủ 33 miền, 500 điểm; tổng 29/166/1/304 khớp | Chờ 500 bản ghi ID và căn cứ trạng thái |
| **TOOL-013** | Đã có mô tả lỗi, file sửa và tên test do nguồn bổ sung | Chờ diff, commit, test ID, log và retest; chưa đóng lỗi độc lập |
| **Live audit** | Đã có đường dẫn script và JSON kết quả do nguồn nêu | Chưa có nội dung tệp, timestamp hoặc build của phiên |

MONEY là lời giải mới do nguồn xác định, không phải kết luận suy đoán từ bản cũ. Lịch sử sai khác vẫn giữ trong `archive_2_1_initial/` và mục 30–33 của kế hoạch; mục 34 và các báo cáo hiện hành có thứ tự ưu tiên cao hơn đối với số liệu đính chính.

#### Các điểm cần tiếp tục đối chiếu
- Cùng tin nhắn vẫn có mô tả coverage planner 48 ca ở phần báo cáo lặp lại, khác 53 ở bảng đính chính. Dùng 53 cho bảng hiện hành theo phần đính chính; log cùng run là căn cứ quyết định.
- `TRADE`, `SOCIAL`, `PARTY`, `GUILD` và các miền khác còn phân loại BLOCKED nguyên miền theo nguồn. Chỉ coi đây là tổng reported; từng ID cần lý do, điều kiện đúng build và evidence. Cửa sổ chat, danh sách, shop và thông báo quyền bị chặn có thể là các ca độc lập.
- Đọc HP/MP/EXP, thấy quest active, skill gán sẵn hoặc ngưỡng auto không chứng minh thao tác, công thức, chiến đấu hoặc nhận/trả nhiệm vụ đúng. Không suy ra 29 checkpoint PASS cụ thể từ tổng miền.
- 100 đòn là mốc thu mẫu do nguồn đề xuất cho `COMBAT-001`, chưa đủ bảo đảm độ chính xác. Phải khóa quái/cấp/trang bị/skill/buff, định nghĩa mẫu hợp lệ, xác định baseline, khoảng tin cậy và tiêu chuẩn chấp nhận trước khi đánh giá.
- `TRAIN-005` là tốc độ tiêu hao thuốc; `TRAIN-014` là ngân sách tiền và thuốc dự phòng. Kiểm ngưỡng 50% cần ca riêng liên kết thêm các điểm này. `TRAIN-008` túi đầy và `TRAIN-015` vòng về thành/quay lại bãi khớp tên gốc.
- Chưa có phân phối độ trễ nên không nghiệm thu tuyên bố 0ms; chưa có dữ liệu nhiều map nên chưa xác nhận sửa triệt để. Test tự động đạt chỉ xác nhận phạm vi test đã chạy.

#### Phân tầng nghiệm thu
1. **Đối chiếu số học tài liệu:** đã đạt cho bảng mới.
2. **Hồi quy tool:** reported pass, chờ bằng chứng cùng run và commit.
3. **Snapshot live:** reported observed, chưa xác thực nội dung JSON.
4. **Giai đoạn 1–2:** reported complete, giữ điều kiện nghiệm thu tại mục 31; không đóng toàn giai đoạn chỉ bằng snapshot cấp 4.
5. **Gameplay từ cấp 1 đến cấp tối đa:** còn mở; chưa có bằng chứng chuỗi chơi đầy đủ. Nhân vật hiện có cấp 4 không thay thế hành trình tạo mới và chơi cấp 1–4.

Kho seed 500 điểm vẫn là danh mục nền, chưa nhập tự động các nhãn báo cáo. Mỗi kết quả thực cần `checkpoint_id`, `object_id`, `case_id`, `oracle_version`, `attempt_id`, `build`, `run`, thời gian, `expected`/`actual`, `evidence` và `blocker` cụ thể. Các dữ kiện chưa có giữ null/unknown, không bịa ID hoặc thời gian.

#### Gói bằng chứng để nghiệm thu
Giữ danh sách cần có tại mục 31.8: nguồn/commit triển khai; log và test ID; telemetry gốc; 500 kết quả theo ID; trace/ảnh/clip phiên thật; sổ 23 lỗi và retest; hiệu chuẩn và vùng map còn thiếu. Bổ sung nội dung `scripts/run_live_qa_audit.py` và `reports/live_audit/live_qa_evaluation.json`, kèm hash để liên kết đúng run. Đây là đầu việc còn mở, không phải các tệp đã được tiếp nhận.

Kịch bản thực thi tiếp theo nằm tại [`docs/KE_HOACH_GIAI_DOAN_3.md`](file:///c:/Users/ADMIN/Desktop/tool/docs/KE_HOACH_GIAI_DOAN_3.md). Không đổi trạng thái kết quả trước khi có bằng chứng cho từng ca.

### Giai đoạn 3 — chơi tân thủ và kiểm chứng chuỗi hành vi
*Đây là kế hoạch triển khai tiếp theo, chưa phải log chạy. Xuất phát từ snapshot cấp 4 do nguồn báo cáo; phải đọc lại trạng thái mới trước khi thao tác. Tiếp tục nhân vật này để kiểm phần dang dở, đồng thời bố trí nhân vật mới cho hành trình cấp 1–4 còn thiếu. Không dùng nhân vật cấp 4 làm bằng chứng đã thử tạo nhân vật.*

#### Các phiên chơi có mục tiêu

| Phiên | Người chơi thực hiện và ra quyết định | Kiểm chứng và bằng chứng bắt buộc |
|---|---|---|
| **P3-01 Chuẩn bị** | Nhận diện đúng server/nhân vật/build, đọc quest, túi, tiền, thuốc, kỹ năng và đường về | Snapshot fresh có timestamp và ID; baseline trước mọi thay đổi; thiếu ID thì chưa kết luận ca liên quan |
| **P3-02 Hiểu mục tiêu** | Đọc đầy đủ hội thoại và bước Ngô Thất/Bách Lý; xác định quái/đạo cụ/NPC/cách hoàn thành theo build | Quest/step/object ID, điều kiện mở, oracle và trạng thái hiện tại; không nhận lại quest active |
| **P3-03 Chọn việc** | So sánh quest cùng tuyến, mức nguy hiểm, thuốc, túi và chi phí về; chọn việc có thể hoàn thành | Nhật ký lý do, tuyến dự kiến, đường rút; đổi quyết định khi trạng thái thay đổi |
| **P3-04 Di chuyển** | Đi tới mục tiêu; xử lý đường vòng, góc kẹt và chuyển map cần thiết | Trace tọa độ game, lệnh input, waypoint; seen/reached/inspected tách riêng; portal cần đi phải được cho phép theo mục tiêu |
| **P3-05 Làm nhiệm vụ** | Đánh/nhặt/tương tác đúng đối tượng; theo dõi tiến độ từng bước | Trước–thao tác–sau, bộ đếm và đồ quest; kiểm mục tiêu sai không cộng; không suy ra đúng từ tên quest |
| **P3-06 Trả và lưu** | Trở lại NPC, xác nhận thưởng, nhận bước kế; relog rồi đọc lại | Chênh EXP/tiền/đồ, tiêu hao vật phẩm quest, quest tiếp; kiểm thưởng không nhận lặp và trạng thái không rollback |
| **P3-07 Khảo sát bãi** | Chọn quái phù hợp cấp, mật độ, sát thương, hồi sinh và khoảng cách tiếp tế | Danh tính quái, cấp, aggro, loot; đo EXP/phút, chi phí/phút, rủi ro; số liệu chưa có thì dùng phiên thăm dò có giới hạn |
| **P3-08 Chiến đấu** | Chọn mục tiêu, dùng kỹ năng, kite/rút khi cần; thu mẫu trúng/hụt/né | COMBAT-001: nhóm mẫu đồng nhất, loại double count, lưu hit events; 100 mẫu là pilot, đánh giá theo oracle/cỡ mẫu đã xác định |
| **P3-09 Thuốc** | Quan sát HP/MP qua ngưỡng auto 50%, cooldown và trường hợp thiếu thuốc | Ca P3-AUTO-50: dưới/bằng/trên ngưỡng theo độ phân giải chỉ số; theo oracle về quy tắc bằng ngưỡng; đối chiếu lượng hồi, stack, cooldown; liên kết TRAIN-005/014 mà không đổi nghĩa ID |
| **P3-10 Loot và đồ** | Nhặt, đọc thuộc tính, phân biệt quest/rác/đồ dùng; thay đồ khi có lợi | ID/count/binding, so thuộc tính trước sau; không bán đồ chưa hiểu; kiểm ownership và loot thất bại |
| **P3-11 Tiếp tế** | Khi túi sắp đầy hoặc thuốc dưới dự phòng, về thành; sửa/mua/bán theo policy; quay lại bãi | TRAIN-008/014/015: vòng túi đầy, shop/MONEY, chi phí, số lượng, hạn mức, không mất đồ quest; không lặp mua vì retry |
| **P3-12 Lên cấp** | Kiểm ngưỡng EXP và lợi ích lên cấp; cân nhắc skill/trang bị/mục tiêu mới | Chụp trước sau vượt ngưỡng, EXP dư, thuộc tính và mở khóa đúng build; thêm đối tượng mới vào inventory |
| **P3-13 Gián đoạn** | Pause/resume, mất kết nối có kiểm soát, relog tại mốc an toàn | Input được nhả, quest/đồ/tiền lưu đúng, không lặp trả thưởng/mua; quan sát trạng thái mới trước retry |
| **P3-14 Kết phiên** | Rà tiến độ, tiền/thuốc/đồ và lỗi; quyết định việc tiếp theo | Báo cáo từng case và evidence, blocker theo ID; lưu checkpoint để phiên sau tiếp tục; không tự nâng PASS cả miền |

#### Chính sách chơi và quan sát lỗi map
- Agent chạy vòng quan sát $\to$ cập nhật GameState/độ tin cậy $\to$ chọn mục tiêu $\to$ chọn hành động $\to$ thao tác $\to$ xác nhận hậu điều kiện $\to$ ghi bằng chứng $\to$ lập lại kế hoạch. Lệnh gây thay đổi tài sản phải xác nhận trạng thái trước retry; mất telemetry thì nhả input và lấy quan sát mới.
- Trong hành trình nhiệm vụ và train vẫn giám sát đen map: ảnh gốc, ROI, thời gian, map/build/camera, trace và trạng thái tải/che UI; xác nhận nhiều frame, loại cảnh tối hợp lệ, lưu clip/ảnh, thử tái hiện theo cùng tuyến. Tọa độ nhân vật chỉ là vị trí quan sát; không ghi là tọa độ chính xác vùng lỗi nếu chưa định vị. Detector và ảnh không đủ tin cậy thì `INCONCLUSIVE`, không tự `PASS`.
- Quét map có hai mục tiêu riêng: đi tuyến sinh hoạt thật và kiểm vùng theo kế hoạch coverage. Giữ `corners_first` cho mission quét chuyên biệt; khi chơi phải ưu tiên quest, sinh tồn và tiếp tế, đồng thời ghi vùng chưa kiểm để quét bù. Chỉ đổi map khi mục tiêu cho phép; map khám phá không đủ 100% không được khóa vô hạn việc đi trả quest hay mua thuốc. Vùng chưa biết và vùng tạm cấm vẫn có mặt trong backlog độ phủ.

#### Điều kiện kết thúc giai đoạn
- Ít nhất có chuỗi nhận/làm/trả/lưu nhiệm vụ phù hợp trạng thái đầu, vòng train–thuốc–loot–tiếp tế–quay lại bãi, thay đổi cấp và phiên relog có assertion.
- Mỗi ca cốt lõi có oracle/evidence; lỗi fail/blocker phải có ID và cách xử lý.
- Chưa có quest đầu từ cấp 1 thì ghi khoảng trống và hoàn thành bằng nhân vật mới.
- Không kết luận mọi lỗi đã hết hoặc cả game đã được kiểm chỉ vì các chuỗi tân thủ đạt.
# 35. Đối chiếu pilot giai đoạn 3 và chặn PASS sai phạm vi
Mục 1–34 được giữ nguyên byte. Tiếp nhận kết quả mới như lời báo cáo của bên triển khai; mục này bổ sung điều kiện xét các phiên pilot, không ghi nhận đã chạy lại game.

## Đối chiếu pilot giai đoạn 3 — điều kiện xét PASS
Nguồn: tin nhắn ngày 20/10/2026 và đoạn log được người dùng dán. Đã đọc báo cáo, chưa nhận mã nguồn runner, tệp JSON kết quả, ảnh/clip hoặc trace; chưa truy cập LDPlayer để kiểm chứng lại. Đây là đánh giá mức đủ bằng chứng, không phải xác nhận game bị lỗi.

### Ba nhãn PASS cần tách phạm vi
| Phiên | Nguồn báo cáo | Phạm vi đoạn log hỗ trợ | Kết luận xét nghiệm thu |
|---|---|---|---|
| P3-01 | PASS | Đọc tên, cấp, map, tọa độ | Ghi nhận quan sát do nguồn báo cáo; chưa đủ cả phiên chuẩn bị: thiếu build, timestamp/freshness, ID nhân vật, túi/tiền/thuốc/skill và baseline |
| P3-02 | PASS | Đọc hai tên và mô tả quest active | Ghi nhận đọc nhật ký do nguồn báo cáo; chưa đủ phiên hiểu mục tiêu: thiếu quest/step/object ID, điều kiện và oracle; Task 1/2 là chỉ số hiển thị, chưa được coi là ID ổn định |
| P3-09 | PASS | Đọc ngưỡng 50%, HP hiện tại 100%, fight_state off | Chỉ kiểm cấu hình; chưa có kích hoạt dùng thuốc. Ca P3-AUTO-50 về hành vi chưa chạy theo nội dung nguồn và bước tiếp theo đã nêu; không nhận PASS toàn phiên |

Nếu có thao tác đã chạy nhưng bằng chứng thiếu thì INCONCLUSIVE; nếu hành vi chưa thực hiện thì NOT_RUN; nếu có tiền điều kiện cụ thể ngăn chạy thì BLOCKED kèm căn cứ. Không đổi thành FAIL của game chỉ vì báo cáo thiếu bằng chứng. Nhãn PASS nguồn được giữ trong nguồn/JSON tiếp nhận, tách khỏi kết luận nghiệm thu.

Không tăng 29 PASS thành 32: phiên chơi và checkpoint có thể ánh xạ nhiều–nhiều, có thể trùng kết quả cũ. Kho 500 điểm vẫn giữ trạng thái nền; ma trận 29/166/1/304 tiếp tục là số nguồn báo cáo, chưa phải bảng đã xác minh từng ID.

### Phân rã P3-09 cho runner và TestOracleEngine
- **CONFIG**: đọc profile HP/MP, bật/tắt auto, ngưỡng và thuốc được chọn. PASS chỉ có hiệu lực cho assertion cấu hình, không tự lan lên hành vi.
- **PRECONDITIONS**: xác nhận đúng build, thuốc đúng loại/stack còn, cooldown, vùng và điều kiện combat nếu cơ chế yêu cầu; xác định nguồn hồi khác. fight_state off không tự là lỗi hoặc blocker nếu chưa biết quy tắc server.
- **ABOVE/BOUNDARY/BELOW**: lấy quan sát ngay trên, bằng và dưới ngưỡng theo bước HP thật; quy tắc bằng ngưỡng phải có oracle, không tự đoán < hay ≤. Với HP tối đa 24 như snapshot, 13/24≈54.17%, 12/24=50%, 11/24≈45.83% là ví dụ các mốc số học khả dĩ, không phải chỉ số đã thực nghiệm; đọc lại HP tối đa vì có thể đã đổi.
- **TRIGGER**: ghi HP/MP trước, thời điểm vượt ngưỡng, điều kiện auto, sự kiện dùng thuốc, stack trước/sau và hồi phục trong cửa sổ thời gian lấy từ cơ chế/build hoặc hiệu chuẩn được phê duyệt. Không tự đặt timeout thành chuẩn của game.
- **ATTRIBUTION**: phân biệt hồi tự nhiên, buff, lên cấp, thuốc hoặc healing khác; không dùng riêng HP tăng hay một lần stack giảm để kết luận toàn ca. Không bắt mọi phép đo HP sau lớn hơn HP trước vì sát thương có thể tới đồng thời; cần event/trace phân giải được nhân quả.
- **REPEAT/NEGATIVE**: xác nhận cooldown, không spam, auto off, hết/sai thuốc và thiếu điều kiện; kiểm HP và MP riêng. Khi đủ quan sát mà trái oracle thì FAIL; timeout với quan sát hỏng thì INCONCLUSIVE, không đổ lỗi game.

Mỗi assertion phải có executed, precondition_result, expected, actual, oracle_version, evidence_refs và thời gian. Assertion bắt buộc chưa chạy không được ngầm coi PASS; tổng kết chỉ PASS khi tất cả assertion bắt buộc trong scope đã thực hiện và đạt. Assertion BLOCKED/NOT_RUN/INCONCLUSIVE không được bỏ khỏi mẫu số để báo 100%. Nếu scope chỉ là CONFIG, tên ca và summary phải ghi rõ CONFIG.
Đây là yêu cầu sửa logic báo cáo/Oracle cần giao cho bên triển khai; chưa xem mã nên chưa xác nhận runner hiện mắc lỗi cụ thể ở dòng nào.

### Trình tự chơi tiếp theo có hậu điều kiện
| Việc | Cách triển khai theo người chơi | Bằng chứng để kết luận |
|---|---|---|
| Chuẩn bị | Đọc trạng thái mới, thuốc, tiền, túi, kỹ năng; chọn mục tiêu và đường rút theo tài nguyên | Hoàn thành phần còn thiếu P3-01, log quyết định P3-03 |
| Bách Lý | Đọc lại quest/step, xác minh Vân Trung Tử và vị trí đúng build; đi tới, tương tác đúng thứ tự | P3-04/05: trace, NPC ID, thoại và chuyển bước; QUEST-007 đúng thứ tự thoại, không chỉ mở cửa sổ |
| Hoàn thành quest | Phân biệt đủ mục tiêu nhưng chưa trả với đã trả; ghi thưởng và bước mới; relog | QUEST-014 giữ trạng thái chưa trả; QUEST-020 dữ liệu sau relog. Nếu quest chỉ là hội thoại thì không bịa bước giết quái/đồ |
| Ngô Thất | Xác minh Lửa/Băng là vật phẩm hay mục tiêu của đúng bước, xác minh Xích Tinh Tử trước khi đi | Đối tượng, số lượng, điều kiện, tiến độ và thưởng trước/sau; không dùng tên để suy ra tọa độ hoặc công thức |
| Khảo sát bãi | Xác minh đường ra bãi và quái thực có; đánh thăm dò, đo nguy hiểm, EXP/chi phí và chọn bãi | P3-07/08, COMBAT-001 có hit events, baseline và nhóm mẫu; không mặc định map lân cận có quái đúng cấp |
| Thử thuốc | Chọn tình huống mất HP có kiểm soát, có đường rút và đủ thuốc; quan sát vượt ngưỡng | P3-AUTO-50 theo phân rã trên; TRAIN-005 đo tốc độ tiêu hao, TRAIN-014 kiểm ngân sách dự phòng, không đổi nghĩa ID |
| Loot/tiếp tế | Phân loại theo ID, giữ đồ quest, cân nhắc trang bị; túi/thuốc chạm ngưỡng thì về thành mua/bán rồi quay lại bãi | P3-10/11; TRAIN-008/015; tiền/đồ trước sau, chống mua lặp khi retry, không mất vật phẩm quan trọng |
| Kết phiên | Lưu kết quả từng ca, relog/checkpoint phục hồi, chọn việc sau | P3-13/14; dữ liệu lưu, input đã nhả; tiếp tục lộ trình mới từ cấp 1 và các mốc cao còn thiếu |

Giám sát lỗi đen map xuyên suốt theo kế hoạch: phân biệt cảnh tối/tải/che UI, lưu ảnh gốc và ROI qua nhiều frame, vị trí quan sát, map/build/camera/timestamp và tuyến tái hiện. Đừng đứng tại snapshot rồi coi đã kiểm map. Tọa độ người chơi không tự là tọa độ chính xác vùng lỗi. Góc chưa đi và vùng chưa nhìn vẫn là khoảng trống cần kiểm bù.

### Đầu vào nghiệm thu pilot
Cần nội dung scripts/run_phase3_behavior_sessions.py, reports/phase3_runs/phase3_pilot_evaluation_1792483560.json và các evidence mà JSON tham chiếu; build/commit, run ID, timestamp và chuỗi trước–action–sau. Tên file hoặc nhãn PASS trong log không thay các dữ liệu này. Không coi JSON đã được nhận chỉ vì có đường dẫn trong báo cáo.

Thứ tự áp dụng: mục 35 bổ sung đánh giá pilot; các số hồi quy/ma trận đính chính vẫn theo mục 34; điều kiện giai đoạn 3 giữ theo kế hoạch và bổ sung này. Giai đoạn 3 chưa được nghiệm thu hoàn tất.

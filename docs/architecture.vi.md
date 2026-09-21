# Kiến trúc

[English](architecture.md) | **Tiếng Việt**

## Mục tiêu thiết kế

Hệ thống giúp việc thu thập gần như không có ma sát, đồng thời giữ source note có thể truy ngược và chỉ cho phép thay đổi định dạng theo hướng thận trọng. Việc giữ nguyên nguồn, ghi rõ xuất xứ và ghi file không đè dữ liệu được ưu tiên hơn sự tiện lợi.

## Thành phần

### Tiện ích trình duyệt ChatGPT

Cung cấp tab hiện tại, văn bản được chọn và ngữ cảnh trình duyệt đã đăng nhập. Đây là nguồn ưu tiên cho trang riêng tư, cần xác thực, được cá nhân hóa, trang local hoặc có paywall.

### `web-to-obsidian`

Chuyển selection, tab hoặc URL thành một source note. Skill áp dụng quy tắc riêng tư, redact URL nhạy cảm trước khi tính identity và gọi `save_capture.py` để canonicalize v2, fallback duplicate legacy đã được chứng minh, khóa identity và publish nguyên tử no-clobber. `audit_sensitive_urls.py` cung cấp migration rõ ràng, dry-run trước cho note cũ.

### Tavily Extract

Là phương án dự phòng cho URL công khai. Chế độ tự động chỉ chạy khi cả browser content và selection đều rỗng; yêu cầu `basic` hoặc `advanced` rõ ràng có thể bổ sung capture chưa đầy đủ. URL đã cần redact không bao giờ đi qua ranh giới này. Request ID thành công luôn được ghi dù content không được chọn; `capture_method` chỉ đổi khi dùng content Tavily. Tavily Search chỉ dành cho việc xác minh và tìm nguồn chuẩn.

### Hộp thư Obsidian

Lưu bằng chứng không thay đổi cùng ngữ cảnh của người dùng. `status` điều khiển workflow; thư mục chỉ xác định phạm vi lớn, không tạo hệ phân loại chủ đề sâu.

### `obsidian-clip-beautifier`

Cấu hình và kiểm tra lớp định dạng và trình bày quanh Markdown đã thu thập: cài CSS snippet có phạm vi, kiểm tra rule của Linter, chuẩn bị bản export đã đánh bóng và đặt một asset template Web Clipper thử nghiệm ở trạng thái chưa kích hoạt. Việc import hoặc cấu hình template này vẫn là tùy chọn và cần ý định rõ ràng của người dùng. Skill hoạt động trên các note đã thu thập, không tự lấy nội dung trình duyệt và không viết lại ngữ nghĩa của nguồn.

Nguồn tạo note được hỗ trợ chính cho lớp này là skill `web-to-obsidian` được đóng gói trong plugin. Template dành cho extension Obsidian Web Clipper chính thức chỉ là luồng tương thích thử nghiệm, tạo schema note nhỏ hơn và khác biệt; hiện chưa đủ ổn định để tuyên bố hành vi tương đương. Việc dùng chung CSS `web-clip` không mang lại các bảo đảm của capture helper về định danh, redaction, chống trùng, publish hay refresh.

### `obsidian-excalidraw-mindmap`

Biến một note đã capture sẵn thành sơ đồ Excalidraw kiểu brainstorm: Claude dựng outline bám chặt nguồn (không bịa ý), còn `generate_excalidraw.py` tính bố cục radial hoặc cây tất định, tô màu node theo cấp nhánh, áp style vẽ tay gốc của Excalidraw, rồi publish nguyên tử, no-clobber, cả trong vault (link từ note gốc) lẫn bản standalone tuỳ chọn. Skill không tự lấy nội dung trình duyệt và không tự đưa ra phán đoán nội dung — độ trung thực nội dung nằm ở outline do Claude cung cấp, còn bố cục/style/publish luôn tất định và test được trong script.

Skill được gợi ý như một bước tuỳ chọn ngay sau khi `web-to-obsidian` capture xong, hoặc gọi thủ công trên bất kỳ note đã capture nào người dùng nêu rõ. Skill không bao giờ tự đoán note.

### Properties, Bases và MOC

Properties cung cấp trường dữ liệu ổn định mà máy có thể đọc. Bases cung cấp các view được lọc phục vụ vận hành. MOC là lớp điều hướng được tuyển chọn cho chủ đề và dự án có ý nghĩa.

## Định danh và chống trùng lặp

Canonicalization v2 chuẩn hóa scheme, IDNA host và default port; loại query nhạy cảm, tham số tracking đã biết và fragment; đồng thời giữ trailing slash cùng thứ tự các query parameter còn lại. Helper băm URL chuẩn bằng SHA-256; 16 ký tự hex đầu tiên trở thành `source_id`, và note mới ghi `canonicalization_version: 2`.

Tiêu đề chỉ dùng để trình bày, không phải định danh. Trang đổi tên vẫn giữ cùng source ID. URL có query khác về nội dung sẽ có source ID khác, trừ khi chỉ khác các tham số theo dõi đã biết.

Duplicate lookup kiểm tra exact canonical URL/source ID v2 trước. Fallback chỉ áp dụng cho note ghi version 1 hoặc note không version có các field chứng minh canonicalization v1. Publish giữ exclusive lock theo source ID trong lúc recheck duplicate và tạo hard link no-clobber. Lock timeout sau 10 giây sẽ fail closed; không tự xóa hoặc chiếm stale lock.

## Hành vi khi lỗi

- Thiếu nội dung trình duyệt và Tavily bị tắt: tạo note chỉ có liên kết.
- Tavily không khả dụng hoặc thất bại: giữ browser content nếu có; nếu không thì tạo note chỉ có liên kết, và báo warning value-free.
- Đã có source ID hoặc URL chuẩn: trả về đường dẫn note hiện có và không ghi thêm.
- Đích nằm ngoài vault: dừng trước khi ghi.
- Không lấy được identity lock trong 10 giây: fail closed và yêu cầu xử lý stale lock thủ công.
- Publish capture: fsync file tạm cùng thư mục rồi tạo hard link nguyên tử no-clobber; không fallback sang overwrite.
- Scanner chỉ apply khi mọi structured URL hội tụ và note chưa đổi từ lúc đọc; trường hợp khác phải review thủ công.

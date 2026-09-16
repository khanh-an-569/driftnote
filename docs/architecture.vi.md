# Kiến trúc

[English](architecture.md) | **Tiếng Việt**

## Mục tiêu thiết kế

Hệ thống giúp việc thu thập gần như không có ma sát nhưng không để bản tóm tắt và tag tự động biến thành kho kiến thức. Việc giữ nguyên nguồn, ghi rõ xuất xứ và cho phép đảo ngược quá trình xử lý được ưu tiên hơn kích thước đồ thị liên kết.

## Thành phần

### Tiện ích trình duyệt ChatGPT

Cung cấp tab hiện tại, văn bản được chọn và ngữ cảnh trình duyệt đã đăng nhập. Đây là nguồn ưu tiên cho trang riêng tư, cần xác thực, được cá nhân hóa, trang local hoặc có paywall.

### `web-to-obsidian`

Chuyển selection, tab hoặc URL thành một source note. Skill áp dụng quy tắc riêng tư, redact URL nhạy cảm trước khi tính identity và gọi `save_capture.py` để canonicalize v2, fallback duplicate legacy đã được chứng minh, khóa identity và publish nguyên tử no-clobber. `audit_sensitive_urls.py` cung cấp migration rõ ràng, dry-run trước cho note cũ.

### Tavily Extract

Là phương án dự phòng cho URL công khai. Chế độ tự động chỉ chạy khi cả browser content và selection đều rỗng; yêu cầu `basic` hoặc `advanced` rõ ràng có thể bổ sung capture chưa đầy đủ. URL đã cần redact không bao giờ đi qua ranh giới này. Request ID thành công luôn được ghi dù content không được chọn; `capture_method` chỉ đổi khi dùng content Tavily. Tavily Search chỉ dành cho việc xác minh và tìm nguồn chuẩn.

### `github-repo-research`

Chuyển một đến ba câu hỏi tập trung thành request Tavily Search chỉ giới hạn ở `github.com`. Helper chuẩn hóa URL gốc repo, loại trang GitHub không phải repo, gộp kết quả lặp và xuất bằng chứng để tạo shortlist hoặc báo cáo có nguồn. Relevance của Tavily chỉ hỗ trợ tìm kiếm; metadata repo dễ thay đổi phải được xác minh riêng.

### Tavily Search

Tìm repo GitHub công khai cho skill nghiên cứu riêng. Mặc định dùng tìm kiếm `basic`; `advanced` và raw content chỉ bật khi snippet chưa đủ. Việc tìm kiếm không cho phép clone, chạy, sửa, publish hoặc push code tìm được hay báo cáo local.

### Hộp thư Obsidian

Lưu bằng chứng không thay đổi cùng ngữ cảnh của người dùng. `status` điều khiển workflow; thư mục chỉ xác định phạm vi lớn, không tạo hệ phân loại chủ đề sâu.

### `obsidian-clip-beautifier`

Cấu hình và kiểm tra lớp định dạng và trình bày quanh Markdown đã thu thập: cài template Web Clipper và CSS snippet có phạm vi, kiểm tra rule của Linter, chuẩn bị bản export đã đánh bóng. Skill hoạt động trên inbox, giữa bước thu thập và bước chắt lọc; nó không tự thu thập nội dung trình duyệt và không chắt lọc nguồn thành knowledge note.

### `obsidian-inbox-processor`

Thực hiện việc rà soát trong phạm vi giới hạn. Skill có thể giữ nguyên nguồn, đánh dấu cần xem lại hoặc tạo không, một hay nhiều atomic knowledge note. Nội dung thô không bao giờ bị xóa.

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

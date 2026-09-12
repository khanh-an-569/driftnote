# Architecture / Kiến trúc

## Design goal / Mục tiêu thiết kế

The system should make capture nearly frictionless without allowing automated summaries and tags to become the knowledge base. Source preservation, explicit provenance, and reversible processing take priority over graph size.

Hệ thống giúp việc thu thập gần như không có ma sát nhưng không để bản tóm tắt và tag tự động biến thành kho kiến thức. Việc giữ nguyên nguồn, ghi rõ xuất xứ và cho phép đảo ngược quá trình xử lý được ưu tiên hơn kích thước đồ thị liên kết.

## Components / Thành phần

### ChatGPT browser extension / Tiện ích trình duyệt ChatGPT

Provides the current tab, selected text, and signed-in browser context. It is the preferred source for private, authenticated, personalized, local, and paywalled pages.

Cung cấp tab hiện tại, văn bản được chọn và ngữ cảnh trình duyệt đã đăng nhập. Đây là nguồn ưu tiên cho trang riêng tư, cần xác thực, được cá nhân hóa, trang local hoặc có paywall.

### `web-to-obsidian`

Routes selection, tab, or URL input into one source note. It applies privacy rules, classifies the source, and invokes `save_capture.py` for deterministic URL normalization, duplicate detection, and writing.

Chuyển selection, tab hoặc URL thành một source note. Skill áp dụng quy tắc riêng tư, phân loại nguồn và gọi `save_capture.py` để chuẩn hóa URL nhất quán, phát hiện trùng lặp và ghi file.

### Tavily Extract

Fallback for public URLs whose browser capture is empty or incomplete. The policy is basic extraction first, one advanced retry, then a link-only note. Tavily Search is reserved for verification and canonical-source discovery.

Là phương án dự phòng cho URL công khai khi nội dung từ trình duyệt trống hoặc chưa đầy đủ. Chính sách là trích xuất `basic` trước, thử lại `advanced` một lần, rồi tạo note chỉ có liên kết. Tavily Search chỉ dành cho việc xác minh và tìm nguồn chuẩn.

### Obsidian inbox / Hộp thư Obsidian

Stores immutable evidence plus user context. `status` drives workflow; folders provide broad ownership boundaries, not a deep topic taxonomy.

Lưu bằng chứng không thay đổi cùng ngữ cảnh của người dùng. `status` điều khiển workflow; thư mục chỉ xác định phạm vi lớn, không tạo hệ phân loại chủ đề sâu.

### `obsidian-inbox-processor`

Performs bounded review. It may keep a source, mark it for review, or create zero or more atomic knowledge notes. It never deletes raw content.

Thực hiện việc rà soát trong phạm vi giới hạn. Skill có thể giữ nguyên nguồn, đánh dấu cần xem lại hoặc tạo không, một hay nhiều atomic knowledge note. Nội dung thô không bao giờ bị xóa.

### Properties, Bases, and MOCs / Thuộc tính, Base và MOC

Properties provide stable machine-readable fields. Bases provide filtered operational views. MOCs remain curated navigation for meaningful themes and projects.

Properties cung cấp trường dữ liệu ổn định mà máy có thể đọc. Bases cung cấp các view được lọc phục vụ vận hành. MOC là lớp điều hướng được tuyển chọn cho chủ đề và dự án có ý nghĩa.

## Identity and deduplication / Định danh và chống trùng lặp

The helper removes common tracking parameters and fragments, sorts remaining query parameters, and hashes the canonical URL with SHA-256. The first 16 hex characters become `source_id`.

Titles are presentation, not identity. A renamed page keeps the same source ID. A meaningfully different query URL keeps a different source ID unless only known tracking parameters differ.

Công cụ phụ loại bỏ fragment và các tham số theo dõi phổ biến, sắp xếp các query parameter còn lại rồi băm URL chuẩn bằng SHA-256. Mười sáu ký tự hex đầu tiên trở thành `source_id`.

Tiêu đề chỉ dùng để trình bày, không phải định danh. Trang đổi tên vẫn giữ cùng source ID. URL có query khác về nội dung sẽ có source ID khác, trừ khi chỉ khác các tham số theo dõi đã biết.

## Failure behavior / Hành vi khi lỗi

- Browser capture missing and Tavily disabled: create a link-only note. / Thiếu nội dung trình duyệt và Tavily bị tắt: tạo note chỉ có liên kết.
- Tavily unavailable or unsuccessful: create a link-only note and report the warning. / Tavily không khả dụng hoặc thất bại: tạo note chỉ có liên kết và báo cảnh báo.
- Existing source ID or canonical URL: return the existing note path and make no write. / Đã có source ID hoặc URL chuẩn: trả về đường dẫn note hiện có và không ghi thêm.
- Invalid destination outside the vault: fail before writing. / Đích nằm ngoài vault: dừng trước khi ghi.
- Partial file write: use a same-directory temporary file and atomic replace. / Khi ghi file chưa hoàn tất: dùng file tạm cùng thư mục và thay thế nguyên tử.

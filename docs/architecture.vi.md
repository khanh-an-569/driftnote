# Kiến trúc

[English](architecture.md) | **Tiếng Việt**

## Mục tiêu thiết kế

Hệ thống giúp việc thu thập gần như không có ma sát nhưng không để bản tóm tắt và tag tự động biến thành kho kiến thức. Việc giữ nguyên nguồn, ghi rõ xuất xứ và cho phép đảo ngược quá trình xử lý được ưu tiên hơn kích thước đồ thị liên kết.

## Thành phần

### Tiện ích trình duyệt ChatGPT

Cung cấp tab hiện tại, văn bản được chọn và ngữ cảnh trình duyệt đã đăng nhập. Đây là nguồn ưu tiên cho trang riêng tư, cần xác thực, được cá nhân hóa, trang local hoặc có paywall.

### `web-to-obsidian`

Chuyển selection, tab hoặc URL thành một source note. Skill áp dụng quy tắc riêng tư, phân loại nguồn và gọi `save_capture.py` để chuẩn hóa URL nhất quán, phát hiện trùng lặp và ghi file.

### Tavily Extract

Là phương án dự phòng cho URL công khai khi nội dung từ trình duyệt trống hoặc chưa đầy đủ. Chính sách là trích xuất `basic` trước, thử lại `advanced` một lần, rồi tạo note chỉ có liên kết. Tavily Search chỉ dành cho việc xác minh và tìm nguồn chuẩn.

### Hộp thư Obsidian

Lưu bằng chứng không thay đổi cùng ngữ cảnh của người dùng. `status` điều khiển workflow; thư mục chỉ xác định phạm vi lớn, không tạo hệ phân loại chủ đề sâu.

### `obsidian-clip-beautifier`

Cấu hình và kiểm tra lớp định dạng và trình bày quanh Markdown đã thu thập: cài template Web Clipper và CSS snippet có phạm vi, kiểm tra rule của Linter, chuẩn bị bản export đã đánh bóng. Skill hoạt động trên inbox, giữa bước thu thập và bước chắt lọc; nó không tự thu thập nội dung trình duyệt và không chắt lọc nguồn thành knowledge note.

### `obsidian-inbox-processor`

Thực hiện việc rà soát trong phạm vi giới hạn. Skill có thể giữ nguyên nguồn, đánh dấu cần xem lại hoặc tạo không, một hay nhiều atomic knowledge note. Nội dung thô không bao giờ bị xóa.

### Properties, Bases và MOC

Properties cung cấp trường dữ liệu ổn định mà máy có thể đọc. Bases cung cấp các view được lọc phục vụ vận hành. MOC là lớp điều hướng được tuyển chọn cho chủ đề và dự án có ý nghĩa.

## Định danh và chống trùng lặp

Công cụ phụ loại bỏ fragment và các tham số theo dõi phổ biến, sắp xếp các query parameter còn lại rồi băm URL chuẩn bằng SHA-256. Mười sáu ký tự hex đầu tiên trở thành `source_id`.

Tiêu đề chỉ dùng để trình bày, không phải định danh. Trang đổi tên vẫn giữ cùng source ID. URL có query khác về nội dung sẽ có source ID khác, trừ khi chỉ khác các tham số theo dõi đã biết.

## Hành vi khi lỗi

- Thiếu nội dung trình duyệt và Tavily bị tắt: tạo note chỉ có liên kết.
- Tavily không khả dụng hoặc thất bại: tạo note chỉ có liên kết và báo cảnh báo.
- Đã có source ID hoặc URL chuẩn: trả về đường dẫn note hiện có và không ghi thêm.
- Đích nằm ngoài vault: dừng trước khi ghi.
- Khi ghi file chưa hoàn tất: dùng file tạm cùng thư mục và thay thế file theo cách nguyên tử.

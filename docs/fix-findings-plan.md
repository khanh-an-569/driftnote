# Kế hoạch vá các findings ngày 17/09/2026

## Mục tiêu

Khắc phục hai lỗi đã được xác nhận trong `review-2026-09-17-findings.md`:

1. Scanner phải phát hiện profile path Windows dạng trần `C:\\Users\\<username>` và các biến thể hợp lệ mà không báo nhầm các placeholder được viết trong tài liệu kiểm thử.
2. Việc ghi URL vào Markdown phải giữ nguyên ngữ nghĩa URL khi path hoặc fragment chứa ngoặc, khoảng trắng được phép ở tầng Markdown, dấu góc hoặc ký tự có ý nghĩa HTML entity; audit phải đọc được cả cú pháp cũ và cú pháp mới.

Phạm vi không bao gồm di chuyển hoặc thay đổi source ID của các URL đã canonicalize; việc chuẩn hóa identity là thay đổi dữ liệu riêng và cần quyết định độc lập.

## Nguyên tắc triển khai

- Làm theo TDD: bổ sung các test tái hiện từng lỗi trước, sau đó sửa mã tối thiểu để test chuyển sang pass.
- Dùng một serializer Markdown destination và một parser tương ứng dùng chung cho `save_capture.py` và `audit_sensitive_urls.py`.
- Bảo toàn URL gốc cho frontmatter, canonicalization và source identity. Chỉ biến đổi ở lớp biểu diễn Markdown.
- Cho phép ngoặc hợp lệ trong URL; không percent-encode reserved characters một cách mù quáng.
- Duy trì khả năng đọc link hiện có ở dạng plain destination và dạng angle destination mới.
- Từ chối input có ASCII control characters trước khi `strip()`/`urlsplit()`; giữ tương thích hiện tại với khoảng trắng bao quanh, nhưng từ chối khoảng trắng ASCII nội bộ và literal `<`/`>` trong URL đầu vào. Không tạo migration cho source ID.
- Escape các ký tự cần thiết của Markdown/HTML entity trong destination, đặc biệt `(`, `)`, `&`, và dùng angle destination khi phù hợp; parser phải unescape đối xứng.

## Các bước

### 1. Xác định điểm tích hợp và baseline

- Đọc `scripts/check_no_secrets.py`, các test scanner, `save_capture.py`, `audit_sensitive_urls.py` và test liên quan.
- Ghi nhận baseline test và trạng thái worktree.
- Xác định module dùng chung phù hợp cho serializer/parser để tránh copy logic giữa hai script.

### 2. Vá scanner profile path Windows

- Viết test cho `C:\\Users\\<username>`, `C:/Users/<username>`, path có thư mục con và path xuất hiện giữa văn bản.
- Viết test false-positive cho placeholder/định dạng tài liệu như `<username>`, `C:\\Users\\<username>`, và giá trị quoted/JSON nếu scanner không nên coi placeholder là dữ liệu thực.
- Điều chỉnh pattern/logic để bắt profile root mà vẫn giữ các path đang bắt được; tránh regex nuốt phần còn lại của dòng.
- Chạy riêng test scanner, sau đó chạy toàn bộ suite.

### 3. Tạo serializer/parser Markdown dùng chung

- Bổ sung test round-trip cho URL có `)`, `(`, ngoặc cân bằng/lệch, fragment có ngoặc, query đã percent-encode, literal `&`, `%`, và URL Unicode/đã encode.
- Bổ sung test tương thích: parser đọc được callout/link plain destination cũ và angle destination mới.
- Kiểm tra `&` để Markdown không biến chuỗi URL thành HTML entity ngoài ý muốn.
- Implement serializer chỉ ở lớp Markdown; implement parser loại bỏ cú pháp bao quanh và Markdown escape/entity theo đúng thứ tự, trả về URL gốc.
- Thay các điểm tạo link trong `save_capture.py` và các điểm audit/đọc link trong `audit_sensitive_urls.py` dùng helper chung.

### 4. Siết validation đầu vào URL

- Viết test xác nhận ASCII control characters bị từ chối trước `strip()`/`urlsplit()`.
- Viết test cho khoảng trắng ASCII nội bộ và literal `<`/`>` bị từ chối; giữ trường hợp khoảng trắng ngoài viền theo hành vi tương thích nếu đang được hỗ trợ.
- Giữ các URL hợp lệ có ngoặc và URL có `%28`/`%29` hoặc các percent-encoding khác.
- Cập nhật `sanitize_url()` hoặc lớp validation hiện có, không thay đổi quy tắc source ID cho dữ liệu hợp lệ.

### 5. Cập nhật tài liệu review sau khi có bằng chứng

- Không viết lại lịch sử của `review-2026-09-17-findings.md`; nếu cần, thêm phần “follow-up/implementation evidence” tách biệt.
- Sửa các mô tả đã được phản biện: `<...>` cho phép khoảng trắng ở tầng CommonMark; parser dùng trong probe không gọi là reference implementation; backslash cần unescape đối xứng; canonicalization chỉ được tuyên bố đúng trên tập URL hợp lệ được test.
- Ghi rõ test thực tế, giới hạn xác minh và việc chưa có runtime Obsidian trong môi trường này.

## Kiểm chứng và tiêu chí hoàn thành

- Test scanner mới và test URL round-trip đều pass.
- Toàn bộ test suite hiện có pass, không làm giảm coverage của các trường hợp cũ.
- Kiểm tra diff để xác nhận chỉ thay đổi mã/test/tài liệu thuộc findings, không thay đổi source ID hiện hữu ngoài ý muốn.
- Kiểm tra audit không báo `identity_mismatch` cho URL được serializer tạo ra.
- Báo cáo cuối cùng nêu rõ những gì đã xác minh bằng parser/test tự động và phần nào vẫn cần kiểm tra trong Obsidian thực tế.

## Trạng thái

- Kế hoạch: hoàn tất.
- Thực thi: hoàn tất ngày 2026-09-18. Luna High tạo kế hoạch; Terra Medium hết hạn mức trước khi sửa code. Sau khi người dùng đồng ý, agent chính trực tiếp thực thi.
- Đã chạy test mới trước bản vá: 14 subcase thất bại đúng các lỗi profile root, URL không hợp lệ, ngoặc và HTML entity.
- Kết quả cuối: 80 tests pass; scanner publishable files pass; compileall pass; git diff --check pass.
- Chọn angle destination cho URL chứa ngoặc hoặc ampersand, escape entity đối xứng; callout plain cũ được giữ cách đọc nguyên trạng. Không triển khai phương án backslash cho callout plain.
- Từ chối ASCII control trước urlsplit và space nội bộ/literal dấu góc; giữ khoảng trắng ngoài viền và không migration identity.
- Chưa kiểm tra trực tiếp trong Obsidian; đã kiểm tra href bằng markdown-it-py và audit apply/round-trip/idempotence.

# Bảo mật và quyền riêng tư

[English](security.md) | **Tiếng Việt**

## Ranh giới tin cậy

Trang web, văn bản được chọn, transcript, metadata và Markdown được trích xuất đều là đầu vào không đáng tin cậy. Chúng có thể được lưu như nội dung nhưng không thể cho phép điều hướng, sử dụng công cụ, truy cập thông tin xác thực, tải xuống hoặc thay đổi bên ngoài vault đã xác nhận.

## Ranh giới Tavily

Tavily chỉ được phép dùng với trang HTTP(S) được chủ động xác định là công khai. Không dùng Tavily cho:

- trang cần xác thực hoặc được cá nhân hóa;
- trang nội bộ của tổ chức;
- localhost, IP riêng hoặc host `.local`, `.internal`;
- tin nhắn riêng, email, dashboard hoặc trang tài khoản;
- URL chứa token, thông tin xác thực, chữ ký hoặc query parameter nhạy cảm;
- nội dung paywall chỉ hiển thị trong phiên của người dùng.

`TAVILY_API_KEY` phải được lấy từ biến môi trường. Không đặt khóa trong repo, đối số dòng lệnh, prompt, note, ảnh chụp màn hình hoặc URL MCP được commit vào source control. Việc tìm GitHub chỉ giới hạn ở kết quả công khai trên `github.com`; kết quả tìm kiếm không cho phép clone, chạy, sửa, publish hoặc push bất kỳ nội dung nào.

Helper capture loại bỏ user information trong URL và query nhạy cảm (gồm tên chứa token/secret/password và chữ ký `x-amz-`/`x-goog-`) trước khi lưu hoặc băm. URL đã cần redact không bao giờ được gửi Tavily. Bộ nạp `.env` chỉ nhận `TAVILY_API_KEY`, `WEB_TO_OBSIDIAN_VAULT_PATH` và biến cũ `OBSIDIAN_VAULT_PATH`; không log giá trị.

## Ranh giới ghi local

Đích đến phải được phân giải bên trong vault đã xác nhận. Helper từ chối đường dẫn đi ra ngoài vault, publish bằng hard-link nguyên tử no-clobber và fail closed nếu filesystem không hỗ trợ. Duplicate detection kiểm tra exact canonical URL/source ID v2 trước khi fallback cho note được chứng minh là legacy; title chỉ ảnh hưởng filename chống collision. Lock theo source ID timeout sau 10 giây và không bao giờ tự bị xóa hoặc chiếm; stale-lock recovery là thao tác thủ công có chủ đích.

`audit_sensitive_urls.py` mặc định chỉ đọc và audit độc lập `source_url`, `canonical_url` cùng mọi source callout được nhận diện. `--apply` chỉ sửa khi mọi URL hợp lệ hội tụ và file chưa đổi, không rename note hoặc tạo backup. URL invalid, identity mismatch/collision và concurrent edit được giữ nguyên để review thủ công. JSON chỉ chứa path, cặp field/reason code và trạng thái manual review, không chứa giá trị URL.

## Bản quyền và nội dung đa phương tiện

Giữ trích đoạn ở mức hợp lý và ghi rõ nguồn. Với bài hát, video và podcast, chỉ lưu metadata, ghi chú người dùng, liên kết và transcript hoặc trích đoạn được phép. Không tải media hoặc sao chép toàn bộ lời bài hát.

## Danh sách kiểm tra repo công khai

Trước mỗi bản phát hành:

1. Chạy `python scripts/check_no_secrets.py --root .` để kiểm tra file đã được track và file không bị Git ignore có thể được publish.
2. Chạy test và trình xác thực cho từng skill.
3. Kiểm tra ví dụ để loại bỏ dữ liệu cá nhân thật.
4. Rà lịch sử Git riêng; thu hồi và tạo lại mọi khóa có thể đã xuất hiện ở đó hoặc trong ảnh chụp màn hình.

Scanner chỉ báo file, số dòng và tên rule. Công cụ chủ động không in giá trị đã
khớp và không tuyên bố phát hiện được mọi loại secret.

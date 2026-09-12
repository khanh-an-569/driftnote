# Tavily fallback / Phương án dự phòng Tavily

Use Tavily only for public HTTP(S) URLs. The helper reads `TAVILY_API_KEY` from the process environment.

Chỉ dùng Tavily cho URL HTTP(S) công khai. Công cụ phụ đọc `TAVILY_API_KEY` từ biến môi trường của tiến trình.

## Extraction policy / Chính sách trích xuất

- Start with `basic` and `format=markdown`. / Bắt đầu bằng `basic` và `format=markdown`.
- Retry `advanced` at most once when basic extraction fails, returns too little content, or misses important tables or embedded material. / Thử lại `advanced` tối đa một lần khi `basic` thất bại, trả quá ít nội dung hoặc bỏ sót bảng hay nội dung nhúng quan trọng.
- A URL in `failed_results` is a failed extraction even when the HTTP request itself succeeded. / URL xuất hiện trong `failed_results` được xem là trích xuất thất bại dù HTTP request thành công.
- Preserve the original URL and record the final extraction method. / Giữ URL gốc và ghi lại phương thức trích xuất cuối cùng.
- Fall back to a link-only note when both attempts fail. / Tạo note chỉ có liên kết khi cả hai lần đều thất bại.

Do not send Tavily / Không gửi tới Tavily:

- localhost, private IPs, `file:` URLs, or `.local` hosts; / localhost, IP riêng, URL `file:` hoặc host `.local`;
- signed-in, personalized, internal, or paywalled URLs; / URL đã đăng nhập, được cá nhân hóa, nội bộ hoặc có paywall;
- selections copied from private pages; / selection sao chép từ trang riêng tư;
- URLs containing credentials or sensitive query parameters. / URL chứa thông tin xác thực hoặc query parameter nhạy cảm.

Use Search only to verify claims or locate a canonical public source. Do not use Crawl, Map, or Research for routine capture.

Chỉ dùng Search để xác minh luận điểm hoặc tìm nguồn công khai chuẩn. Không dùng Crawl, Map hoặc Research cho việc thu thập thông thường.

Never place an API key in a skill file, note, command argument, URL, log, screenshot, or committed configuration. If a key may have leaked, stop and tell the user to revoke it.

Không đặt API key trong file skill, note, đối số dòng lệnh, URL, log, ảnh chụp màn hình hoặc cấu hình được commit. Nếu khóa có thể đã lộ, hãy dừng và yêu cầu người dùng thu hồi khóa.

Official references / Tài liệu chính thức:

- https://docs.tavily.com/documentation/api-reference/endpoint/extract
- https://docs.tavily.com/documentation/best-practices/api-key-management

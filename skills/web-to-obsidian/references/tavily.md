# Tavily fallback / Phương án dự phòng Tavily

Use Tavily only for public HTTP(S) URLs. The helper accepts `TAVILY_API_KEY`, `WEB_TO_OBSIDIAN_VAULT_PATH`, and legacy `OBSIDIAN_VAULT_PATH` from `.env`, without overriding process variables. Without `--env-file`, it loads the current workspace `.env` first and then the central `.env` above the source `skills` directory. Use `--env-file` for an explicit override.

Chỉ dùng Tavily cho URL HTTP(S) công khai. Helper nhận `TAVILY_API_KEY`, `WEB_TO_OBSIDIAN_VAULT_PATH` và biến cũ `OBSIDIAN_VAULT_PATH` từ `.env`, không ghi đè biến tiến trình. Khi không có `--env-file`, helper nạp `.env` của workspace hiện tại trước rồi đến `.env` trung tâm nằm phía trên thư mục `skills` của mã nguồn. Dùng `--env-file` khi cần override rõ ràng.

## Connected Extract tool / Công cụ Extract đã kết nối

For a public page when no rich browser capture is available, use the connected Tavily Extract tool if installed and authorized. Pass only the public URL and request Markdown. Treat `failed_results` or empty content as failure. Write the returned Markdown to a temporary UTF-8 file, then run `save_capture.py --content-file <file> --capture-method tavily-basic --tavily off` (use `tavily-advanced` when that depth was actually used). The helper will preserve Markdown links. This path uses the connected account and does not require `TAVILY_API_KEY` in the helper process. Do not pretend a connected extraction succeeded merely because the URL is public.

Với trang công khai mà không lấy được HTML từ trình duyệt, ưu tiên Tavily Extract đã kết nối nếu khả dụng. Lưu Markdown trả về thành tệp UTF-8 tạm rồi đưa vào helper bằng `--content-file`, `--capture-method tavily-basic` và `--tavily off`. Cách này dùng tài khoản kết nối, không yêu cầu khóa API cục bộ.

## Extraction policy / Chính sách trích xuất

- Start with `basic` and `format=markdown`. / Bắt đầu bằng `basic` và `format=markdown`.
- `--tavily auto` runs only when both source content and selection are empty; `basic` or `advanced` is an explicit request to supplement short content. / `auto` chỉ chạy khi content và selection đều rỗng; `basic`/`advanced` là yêu cầu bổ sung rõ ràng.
- Retry `advanced` at most once when basic extraction fails, returns too little content, or misses important tables or embedded material. / Thử lại `advanced` tối đa một lần khi `basic` thất bại, trả quá ít nội dung hoặc bỏ sót bảng hay nội dung nhúng quan trọng.
- A URL in `failed_results` is a failed extraction even when the HTTP request itself succeeded. / URL xuất hiện trong `failed_results` được xem là trích xuất thất bại dù HTTP request thành công.
- Redact credentials and sensitive query fields before storage. Never send a URL that required redaction to Tavily. / Redact thành phần nhạy cảm trước khi lưu; URL đã cần redact không bao giờ được gửi Tavily.
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

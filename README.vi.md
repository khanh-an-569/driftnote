# Web to Obsidian

Quy trình second brain theo hướng inbox-first: lấy nội dung trình duyệt bằng extension ChatGPT, dùng Tavily để bổ sung cho trang công khai khi cần, rồi chỉ biến những ý tưởng bền vững thành knowledge note trong Obsidian.

[English](README.md)

## Nguyên tắc

Việc thu thập và việc suy nghĩ được tách riêng:

1. `web-to-obsidian` lưu nhanh một source note có thể truy ngược.
2. `obsidian-inbox-processor` xử lý inbox sau và chỉ tạo knowledge note khi thật sự có một ý tưởng đáng giữ.

Nội dung nguồn không bị thay bằng bản tóm tắt. URL trùng được bỏ qua. Tavily chỉ là fallback cho web công khai, không dùng để vượt đăng nhập hoặc paywall.

## Cài đặt

Yêu cầu:

- ChatGPT desktop đã kết nối Browser Extension với Chrome hoặc trình duyệt được hỗ trợ.
- Một vault Obsidian local.
- Python 3.10 trở lên.
- `TAVILY_API_KEY` nếu muốn trích xuất trang công khai.

Cài hai skill từ PowerShell:

```powershell
Copy-Item -Recurse -Force .\skills\web-to-obsidian "$env:USERPROFILE\.codex\skills\web-to-obsidian"
Copy-Item -Recurse -Force .\skills\obsidian-inbox-processor "$env:USERPROFILE\.codex\skills\obsidian-inbox-processor"
```

Sao chép file cấu hình mẫu và sửa `vault_root`:

```powershell
Copy-Item .\web-to-obsidian.example.yaml .\web-to-obsidian.yaml
```

File thật đã được `.gitignore`. Không ghi khóa Tavily vào file cấu hình, prompt, note hoặc source code.

## Sử dụng trong Chrome

Mở trang cần lưu, mở side chat của ChatGPT rồi nhập:

```text
$web-to-obsidian
Lưu tab này vào Obsidian inbox.
Lý do tôi lưu: nội dung có thể hữu ích cho dự án retrieval.
Nếu có selection thì ưu tiên selection. Chỉ dùng Tavily nếu đây là trang công khai và nội dung lấy từ tab chưa đầy đủ.
```

Xử lý inbox sau:

```text
$obsidian-inbox-processor
Xử lý tối đa 10 web capture đang chờ. Giữ nguyên mọi nguồn và chỉ tạo knowledge note cho ý tưởng bền vững.
```

## Cấu trúc vault gợi ý

```text
00 Inbox/
10 Sources/
20 Knowledge/
30 MOCs/
40 Projects/
```

Thư mục `vault-starter` có sẵn `Home.md` và `Web Inbox.base` với các view Inbox, Reading, Music và Processed.

## Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

Xem thêm [kiến trúc](docs/architecture.md) và [ranh giới bảo mật](docs/security.md).

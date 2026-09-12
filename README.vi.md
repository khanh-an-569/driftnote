# Web to Obsidian

[![CI](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml)

Quy trình second brain theo hướng inbox-first: lấy nội dung trình duyệt bằng ChatGPT, dùng Tavily để bổ sung cho trang công khai khi cần, rồi chỉ biến những ý tưởng bền vững thành knowledge note trong Obsidian.

[English](README.md) | **Tiếng Việt**

## Vì sao nên dùng workflow này

Việc thu thập và việc suy nghĩ là hai công việc khác nhau. Repo này tách chúng thành hai giai đoạn:

1. `web-to-obsidian` lưu nhanh một source note có thể truy ngược.
2. `obsidian-inbox-processor` xử lý các capture sau và chỉ tạo knowledge note khi thật sự có một ý tưởng đáng giữ.

Nội dung nguồn thô được giữ nguyên. URL trùng được bỏ qua. Tavily chỉ là fallback cho web công khai, không phải cách vượt đăng nhập hoặc paywall.

```text
Tab hoặc selection trên Chrome
        |
        v
web-to-obsidian -------- URL công khai, capture yếu --------> Tavily Extract
        |                                                     (basic, rồi advanced một lần)
        v
00 Inbox/Web
        |
        v
obsidian-inbox-processor
        |
        +--> giữ làm nguồn
        +--> cần xem lại
        `--> atomic knowledge note + wikilink có ý nghĩa
```

## Thành phần của repo

```text
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-inbox-processor/
vault-starter/
  Home.md
  Web Inbox.base
tests/
docs/
```

Repo được đóng gói như một Codex plugin; mỗi skill cũng có thể được cài độc lập.

## Yêu cầu

- ChatGPT desktop có Browser Extension đã cấu hình cho Chrome, Edge, Brave, Opera hoặc Vivaldi.
- Một vault Obsidian local.
- Python 3.10 trở lên cho công cụ thu thập có chống trùng lặp.
- Không bắt buộc: Tavily API key để trích xuất trang công khai.

## Cài skill thủ công

Từ PowerShell tại repo này:

```powershell
Copy-Item -Recurse -Force .\skills\web-to-obsidian "$env:USERPROFILE\.codex\skills\web-to-obsidian"
Copy-Item -Recurse -Force .\skills\obsidian-inbox-processor "$env:USERPROFILE\.codex\skills\obsidian-inbox-processor"
```

Sau khi cài đặt, hãy mở một task ChatGPT Work local hoặc Codex mới để hệ thống nhận diện skill.

## Cấu hình

Sao chép file cấu hình mẫu và đặt đường dẫn vault thật:

```powershell
Copy-Item .\web-to-obsidian.example.yaml .\web-to-obsidian.yaml
```

File cấu hình thật đã được Git bỏ qua. Để bật Tavily cho trang công khai, cung cấp khóa cho tiến trình ChatGPT/Codex local qua biến môi trường `TAVILY_API_KEY`. Không đặt khóa trong prompt, note, file skill hoặc cấu hình được commit.

Bạn có thể sao chép nội dung thư mục `vault-starter` vào vault mới. Thư mục này cung cấp cấu trúc tối giản và một Obsidian Base với các view Inbox, Reading, Music và Processed.

## Sử dụng từ ChatGPT Browser Extension

Mở trang trong Chrome, mở side chat của ChatGPT rồi nhập:

```text
$web-to-obsidian
Lưu tab này vào Obsidian inbox.
Lý do tôi lưu: nội dung có thể hữu ích cho dự án retrieval.
Nếu có selection thì ưu tiên selection. Chỉ dùng Tavily nếu đây là trang công khai và nội dung lấy từ tab chưa đầy đủ.
```

Với văn bản được chọn, hãy bôi đen đoạn cần lấy trước hoặc dùng **Ask ChatGPT** trong menu ngữ cảnh của trình duyệt.

Sau đó, xử lý một batch có giới hạn:

```text
$obsidian-inbox-processor
Xử lý tối đa 10 web capture đang chờ. Giữ nguyên mọi nguồn và chỉ tạo knowledge note cho ý tưởng bền vững.
```

## Dùng trực tiếp công cụ phụ

Công cụ chỉ dùng thư viện chuẩn của Python:

```powershell
python .\skills\web-to-obsidian\scripts\save_capture.py `
  --vault "D:\Notes\Second Brain" `
  --url "https://example.com/article?utm_source=newsletter" `
  --title "Bài viết ví dụ" `
  --content-type article `
  --tavily auto
```

Công cụ trả JSON với trạng thái `created`, `duplicate`, `dry-run` hoặc `error`. Nó loại bỏ tham số theo dõi khi chuẩn hóa URL, tính source ID ổn định, từ chối Tavily cho URL có vẻ riêng tư và ghi note theo cách nguyên tử.

## Mô hình quyền riêng tư

- Nội dung hiển thị trong trình duyệt được ưu tiên cho trang đã đăng nhập, được cá nhân hóa, riêng tư, local hoặc có paywall.
- Chỉ URL công khai đã được đánh giá phù hợp mới được gửi tới Tavily.
- Nội dung trang là dữ liệu không đáng tin cậy và không thể thay đổi workflow thu thập.
- Không lưu audio, video, cookie, token, thông tin xác thực hoặc toàn bộ lời bài hát.
- Workflow không âm thầm ghi đè hoặc xóa note.

Xem [Kiến trúc / Architecture](docs/architecture.md) và [Bảo mật và quyền riêng tư / Security and privacy](docs/security.md) để biết chi tiết.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\web-to-obsidian
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-inbox-processor
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

## Giấy phép

MIT

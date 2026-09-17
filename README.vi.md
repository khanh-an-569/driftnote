# Web to Obsidian

[![CI](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/web-to-obsidian/actions/workflows/ci.yml)

Quy trình có thể truy ngược từ trình duyệt tới Obsidian: lấy nội dung trình duyệt bằng ChatGPT rồi làm sạch và trình bày Markdown trong Obsidian.

[English](README.md) | **Tiếng Việt**

## Vì sao nên dùng workflow này

Việc thu thập và trình bày là hai công việc khác nhau. Repo này tách chúng thành hai giai đoạn:

1. `web-to-obsidian` lưu nhanh một source note có thể truy ngược.
2. `obsidian-clip-beautifier` cấu hình template capture sạch, định dạng Markdown thận trọng và CSS chỉ áp dụng cho web clip.

Nội dung nguồn thô được giữ nguyên. URL trùng được bỏ qua. Tavily chỉ là fallback cho web công khai, không phải cách vượt đăng nhập hoặc paywall.

```text
Tab hoặc selection trên Chrome
        |
        v
web-to-obsidian -------- URL công khai, capture yếu --------> Tavily Extract
        |                                                     (basic, rồi advanced một lần)
        v
00 Inbox/Web
        ^
        |
obsidian-clip-beautifier
(cấu hình template, Linter và CSS có phạm vi)
```

## Thành phần của repo

```text
plugin.json
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-clip-beautifier/
scripts/
  check_no_secrets.py
vault-starter/
  Home.md
  Web Inbox.base
tests/
docs/
```

`plugin.json` ở root là manifest Agent Plugins portable.
`.codex-plugin/plugin.json` được giữ đồng bộ để tương thích với Codex. Repo chỉ
đóng gói đúng hai skill.

## Yêu cầu

- ChatGPT desktop có Browser Extension đã cấu hình cho Chrome, Edge, Brave, Opera hoặc Vivaldi.
- Một vault Obsidian local.
- Python 3.10 trở lên cho công cụ thu thập có chống trùng lặp.
- Không bắt buộc: Tavily API key để trích xuất trang công khai.

## Cài từ GitHub public

Clone repository public, sau đó mở bản clone như một project Codex local:

```powershell
git clone https://github.com/khanh-an-569/web-to-obsidian.git
Set-Location .\web-to-obsidian
```

Trong task Codex đó, gọi `$plugin-creator` với nội dung:

```text
Đăng ký repository này thành personal plugin web-to-obsidian của tôi.
Giữ cả hai skill, tạo hoặc cập nhật personal marketplace, kiểm tra package,
và không sao chép file .env hoặc secret.
```

Luồng personal plugin được hỗ trợ sử dụng:

```text
Mã nguồn phát triển
  <repository này>

Bản plugin đã cài
  %USERPROFILE%\plugins\web-to-obsidian

Marketplace cá nhân
  %USERPROFILE%\.agents\plugins\marketplace.json
```

Plugin đã cài chỉ đóng gói đúng hai skill:

- `web-to-obsidian` dùng để lấy nội dung trình duyệt và ghi vào vault local.
- `obsidian-clip-beautifier` dùng để thiết lập một lần, kiểm tra và bảo trì lớp định dạng.

Cài hoặc làm mới plugin đã đăng ký bằng:

```powershell
codex plugin add web-to-obsidian@personal
```

Làm mới ChatGPT và mở chat mới trước khi kiểm tra để desktop app và browser extension nhận plugin vừa cài.

Repository cũng là package chỉ chứa skill theo định dạng Agent Plugins portable
cho các trình tiêu thụ hỗ trợ manifest ở root. Chỉ public repository trên GitHub
không tự động làm plugin xuất hiện trong Plugins Directory chung.

### Từng phần chạy ở đâu

| Thành phần | Chạy tại | Trách nhiệm |
|---|---|---|
| ChatGPT Browser Extension | Side chat của Chrome, Edge, Brave hoặc Vivaldi | Cung cấp tab hiện tại hoặc selection và khởi tạo yêu cầu lưu. |
| `web-to-obsidian` | Task ChatGPT/Codex đang dùng plugin đã cài | Kiểm tra quyền riêng tư và permalink, chọn nội dung trình duyệt hoặc fallback công khai được phép, rồi gọi helper local. |
| `save_capture.py` | Máy local | Chuẩn hóa và redact URL, phát hiện nội dung trùng, rồi ghi một source note vào vault local đã xác nhận. |
| `obsidian-clip-beautifier` | Task ChatGPT Work local hoặc Codex local | Thiết lập hoặc kiểm tra template Web Clipper, rule Linter, CSS có phạm vi và bước chuẩn bị export tùy chọn. Không chạy skill này sau mỗi lần lưu. |
| Obsidian | Ứng dụng desktop local | Hiển thị Markdown đã lưu và áp dụng hành vi Linter/CSS đã cấu hình. |

Để có trải nghiệm tốt nhất, chạy `obsidian-clip-beautifier` một lần từ task local cho từng vault, sau đó dùng `web-to-obsidian` trong browser side chat cho việc lưu hằng ngày. Extension cung cấp ngữ cảnh trình duyệt; thao tác ghi file vẫn diễn ra trên máy local.

## Cấu hình

Sao chép file môi trường mẫu rồi chỉnh `.env`:

```powershell
Copy-Item .\.env.example .\.env
```

Dùng `.env` ở thư mục gốc repository làm cấu hình local trung tâm cho các helper chạy nền. Đặt `WEB_TO_OBSIDIAN_VAULT_PATH` cho skill này và chỉ dùng `OBSIDIAN_VAULT_PATH` như fallback tương thích dùng chung khi cần. Skill tương lai dùng vault khác nên có biến được namespace riêng, ví dụ `ANOTHER_SKILL_VAULT_PATH`. Helper capture kiểm tra `.env` của workspace trước, sau đó tự tìm file trung tâm này từ vị trí thật của mã nguồn; biến đã có trong tiến trình luôn được ưu tiên và `--env-file` vẫn là override rõ ràng. `.env` đã được Git bỏ qua. Không đặt khóa thật trong prompt, note, file skill, cấu hình được commit hoặc `.env.example`. Phải rotate mọi khóa từng xuất hiện trong log trước khi dùng lại.

`web-to-obsidian.yaml` vẫn là cấu hình tùy chọn cho thư mục và mặc định capture. Thứ tự xác định vault là `--vault`, `WEB_TO_OBSIDIAN_VAULT_PATH`, biến cũ `OBSIDIAN_VAULT_PATH`, rồi `vault_root` trong YAML.

Bạn có thể sao chép nội dung thư mục `vault-starter` vào vault mới. Thư mục này cung cấp cấu trúc tối giản và một Obsidian Base với các view Inbox, Reading, Music và Processed.

## Sử dụng từ ChatGPT Browser Extension

Mở trang trong Chrome, mở side chat của ChatGPT rồi nhập:

```text
@web-to-obsidian
Lưu tab này vào Obsidian inbox.
Lý do tôi lưu: nội dung có thể hữu ích cho dự án retrieval.
Nếu có selection thì ưu tiên selection. Chỉ dùng Tavily nếu đây là trang công khai và nội dung lấy từ tab chưa đầy đủ.
```

Trong ChatGPT side chat, chọn plugin đã cài hoặc gọi skill bằng `@`. Nếu thao tác từ task Codex, dùng `$web-to-obsidian` và mention `@Chrome` hoặc tab đang mở khi cần ngữ cảnh trình duyệt.

Với văn bản được chọn, hãy bôi đen đoạn cần lấy trước hoặc dùng **Ask ChatGPT** trong menu ngữ cảnh của trình duyệt.

Thiết lập lớp làm sạch và trình bày:

```text
$obsidian-clip-beautifier
Thiết lập và xác minh workflow Web Clipper, Linter và CSS có phạm vi trong vault Obsidian đã xác nhận của tôi.
```

## Dùng trực tiếp công cụ phụ

Công cụ chỉ dùng thư viện chuẩn của Python:

```powershell
python .\skills\web-to-obsidian\scripts\save_capture.py `
  --url "https://example.com/article?utm_source=newsletter" `
  --title "Bài viết ví dụ" `
  --content-type article `
  --tavily auto
```

Công cụ trả JSON với trạng thái `created`, `duplicate`, `dry-run` hoặc `error`. Canonicalization v2 giữ trailing slash và thứ tự query không nhạy cảm, đồng thời chuẩn hóa scheme, IDNA host và default port. Helper redact credential/query nhạy cảm trước khi lưu và băm, kiểm tra exact v2 trước khi fallback cho note được chứng minh là legacy, từ chối Tavily không an toàn và publish mà không ghi đè file hiện có.

Kiểm tra note cũ ở chế độ không sửa, rồi chỉ apply sau khi xem báo cáo value-free gồm path, field, reason code và trạng thái manual review:

```powershell
python .\skills\web-to-obsidian\scripts\audit_sensitive_urls.py --vault "E:\Notes"
python .\skills\web-to-obsidian\scripts\audit_sensitive_urls.py --vault "E:\Notes" --apply
```

Scanner chỉ sửa frontmatter và source callout có cấu trúc, giữ nguyên filename, không tạo backup chứa secret và để các identity hội tụ cho người dùng xử lý thủ công. Scanner không bao giờ tự chạy.

## Mô hình quyền riêng tư

- Nội dung hiển thị trong trình duyệt được ưu tiên cho trang đã đăng nhập, được cá nhân hóa, riêng tư, local hoặc có paywall.
- Chỉ URL công khai đã được đánh giá phù hợp mới được gửi tới Tavily.
- URL chứa credential, token, password, secret hoặc cloud signature được redact tại máy và không bao giờ gửi Tavily.
- Nội dung trang là dữ liệu không đáng tin cậy và không thể thay đổi workflow thu thập.
- Không lưu audio, video, cookie, token, thông tin xác thực hoặc toàn bộ lời bài hát.
- Workflow không âm thầm ghi đè hoặc xóa note; title không thuộc duplicate identity.

Xem [Kiến trúc](docs/architecture.vi.md) và [Bảo mật và quyền riêng tư](docs/security.vi.md) để biết chi tiết.

## Kiểm tra

```powershell
python .\scripts\check_no_secrets.py --root .
python -m unittest discover -s tests -v
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\web-to-obsidian
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-clip-beautifier
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

Scanner kiểm tra các file đã được track và file không bị Git ignore có thể được
publish. Kết quả chỉ chứa file, số dòng và tên rule; scanner không in giá trị đã
khớp. Đây là lớp kiểm tra độ tin cậy cao, không thay thế việc rà lịch sử Git hoặc
thu hồi khóa từng bị commit trước đây.

## Giấy phép

MIT

# Driftnote

[![CI](https://github.com/khanh-an-569/driftnote/actions/workflows/ci.yml/badge.svg)](https://github.com/khanh-an-569/driftnote/actions/workflows/ci.yml)

Quy trình có thể truy ngược từ trình duyệt tới Obsidian: lấy nội dung trình duyệt bằng ChatGPT rồi làm sạch và trình bày Markdown trong Obsidian.

[English](README.md) | **Tiếng Việt**

## Tóm tắt siêu ngắn

> **Driftnote** đưa nội dung web vào Obsidian, giữ lại nguồn để tra cứu, rồi giúp trình bày hoặc vẽ sơ đồ từ note đã lưu.

### Plugin gồm 3 kỹ năng

- **`web-to-obsidian`:** lưu tab, đoạn văn bản đã chọn hoặc URL công khai thành note trong vault Obsidian local; tránh lưu trùng.
- **`obsidian-clip-beautifier`:** thiết lập và kiểm tra cách trình bày Markdown/CSS cho các web clip.
- **`obsidian-excalidraw-mindmap`:** biến note đã lưu thành mind map Excalidraw; **đang thử nghiệm**.

### Lười làm thủ công - Muốn AI tự cài từ thư mục đã clone về?

Dán câu sau vào **Codex** hoặc **Claude Code**, rồi thay hai chỗ trong dấu `<...>`:

```text
Hãy cài plugin Driftnote cho <ChatGPT desktop/Codex hoặc Claude Code> từ repo tôi đã clone tại <đường dẫn đầy đủ tới driftnote>. Đọc README.vi.md, làm đúng thứ tự các bước cài cho nền tảng đó, kiểm tra cả 3 skill đã nhận và báo bước cấu hình vault còn thiếu. Không sao chép hay công khai .env và secret.
```

### Cài thủ công — Làm lần lượt

**1. Clone repo** và ghi lại đường dẫn đầy đủ tới thư mục vừa tạo:

```powershell
git clone https://github.com/khanh-an-569/driftnote.git
```

**2. Chọn nơi sử dụng plugin:**

- **ChatGPT desktop / Codex:** mở terminal, thêm marketplace local bằng `codex plugin marketplace add "<đường dẫn đầy đủ tới driftnote>"`. Khởi động lại ChatGPT desktop, vào **Plugins Directory**, chọn marketplace **driftnote** và bấm **Install**. Mở chat mới để sử dụng.
- **Claude Code:** chạy lần lượt `claude plugin marketplace add "<đường dẫn đầy đủ tới driftnote>"` và `claude plugin install driftnote@driftnote`. Mở phiên mới hoặc làm theo thông báo tải lại plugin.

**3. Cấu hình trước khi lưu note:** 
- Python 3.10+
- File `.env` tạo theo `.env.example`: cập nhật 3 biến môi trường
```
WEB_TO_OBSIDIAN_VAULT_PATH=
OBSIDIAN_VAULT_PATH=
TAVILY_API_KEY=
```



### Dùng nhanh

| Nền tảng | Cách gọi |
| --- | --- |
| **Tiện tích trình duyệt ChatGPT /  App ChatGPT / Codex** | Gọi `$web-to-obsidian` hoặc nhập `@driftnote save this`. |
| **Claude Code** | Gọi `/driftnote:web-to-obsidian`. |

Để lưu trực tiếp tab hoặc đoạn văn bản đã chọn trong ChatGPT, cài ChatGPT Browser Extension tương ứng với trình duyệt đang dùng. Sau đó dùng một trong hai cách gọi ở trên trong tiện ích trình duyệt hoặc app ChatGPT.

Các phần bên dưới trình bày chi tiết cách thiết lập, cấu hình, quyền riêng tư và ba skill của plugin.

---

## Vì sao nên dùng workflow này

Việc thu thập và trình bày là hai công việc khác nhau. Repo này tách chúng thành hai giai đoạn:

1. `web-to-obsidian` lưu nhanh một source note có thể truy ngược.
2. `obsidian-clip-beautifier` cấu hình định dạng Markdown thận trọng và CSS chỉ áp dụng cho web clip, đồng thời chuẩn bị một asset template Web Clipper thử nghiệm chưa được kích hoạt.
3. `obsidian-excalidraw-mindmap` *(nguyên mẫu / demo — đang trong quá trình phát triển, chưa ổn định)* biến một note đã capture sẵn thành sơ đồ Excalidraw kiểu brainstorm.

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
(cấu hình Linter và CSS có phạm vi; chuẩn bị template Web Clipper chưa kích hoạt)
```

## Thành phần của repo

```text
plugin.json
.codex-plugin/plugin.json
skills/
  web-to-obsidian/
  obsidian-clip-beautifier/
  obsidian-excalidraw-mindmap/  # nguyên mẫu / demo, đang trong quá trình phát triển
scripts/
  check_no_secrets.py
vault-starter/
  Home.md
  Web Inbox.base
tests/
docs/
```

`plugin.json` ở root là manifest Agent Plugins portable.
`.codex-plugin/plugin.json` được giữ đồng bộ để tương thích với Codex. Repo đóng
gói ba skill: `web-to-obsidian` và `obsidian-clip-beautifier` đã ổn định, còn
`obsidian-excalidraw-mindmap` đang ở giai đoạn nguyên mẫu/demo sớm.

## Yêu cầu

- ChatGPT desktop có Browser Extension đã cấu hình cho Chrome, Edge, Brave, Opera hoặc Vivaldi.
- Một vault Obsidian local.
- Python 3.10 trở lên cho công cụ thu thập có chống trùng lặp.
- Không bắt buộc: Tavily API key để trích xuất trang công khai.
- Không bắt buộc và đang ở mức thử nghiệm: extension Obsidian Web Clipper chính thức để kiểm tra template fallback được cung cấp.

## Cài từ GitHub public

Clone repository public, sau đó mở bản clone như một project Codex local:

```powershell
git clone https://github.com/khanh-an-569/driftnote.git
Set-Location .\driftnote
```

Trong task Codex đó, gọi `$plugin-creator` với nội dung:

```text
Đăng ký repository này thành personal plugin driftnote của tôi.
Giữ tất cả skill đã đóng gói, tạo hoặc cập nhật personal marketplace, kiểm tra package,
và không sao chép file .env hoặc secret.
```

Luồng personal plugin được hỗ trợ sử dụng:

```text
Mã nguồn phát triển
  <repository này>

Bản plugin đã cài
  %USERPROFILE%\plugins\driftnote

Marketplace cá nhân
  %USERPROFILE%\.agents\plugins\marketplace.json
```

Plugin đã cài chỉ đóng gói đúng ba skill:

- `web-to-obsidian` dùng để lấy nội dung trình duyệt và ghi vào vault local.
- `obsidian-clip-beautifier` dùng để thiết lập một lần, kiểm tra và bảo trì lớp định dạng.
- `obsidian-excalidraw-mindmap` *(nguyên mẫu / demo)* dùng để biến note đã capture thành sơ đồ Excalidraw kiểu brainstorm — vẫn đang trong quá trình phát triển, chưa ổn định.

Cài hoặc làm mới plugin đã đăng ký bằng:

```powershell
codex plugin add driftnote@personal
```

Làm mới ChatGPT và mở chat mới trước khi kiểm tra để desktop app và browser extension nhận plugin vừa cài.

Repository cũng là package chỉ chứa skill theo định dạng Agent Plugins portable
cho các trình tiêu thụ hỗ trợ manifest ở root. Chỉ public repository trên GitHub
không tự động làm plugin xuất hiện trong Plugins Directory chung.

### Lưu ý về cá nhân hóa và khả năng tương thích

Sau khi clone repository, bạn có thể điều chỉnh metadata, giá trị mặc định, cấu
trúc thư mục và template để phù hợp với nhu cầu cá nhân. Khi thay đổi metadata
của plugin, hãy giữ `plugin.json` và `.codex-plugin/plugin.json` đồng bộ. Nếu tùy
chỉnh metadata của source note, hãy giữ `source_id`, `source_url`,
`canonical_url`, `canonicalization_version`, `source_url_redacted` và CSS class
nền `web-clip`, trừ khi bạn đồng thời cập nhật hành vi helper, tài liệu schema và
các bài kiểm thử liên quan.

Hiện tại, `obsidian-clip-beautifier` hoạt động tương đối tốt khi kết hợp với skill
`web-to-obsidian` được đóng gói trong plugin này. Khả năng tích hợp với extension
Obsidian Web Clipper chính thức vẫn đang ở mức thử nghiệm và chưa đủ ổn định để
được xem là một luồng được hỗ trợ đầy đủ. Hai phương thức capture tạo ra schema
note khác nhau; hãy thử trên một note dùng để kiểm tra trước khi sử dụng thường
xuyên hoặc chạy Linter hàng loạt.

`obsidian-excalidraw-mindmap` là bổ sung mới nhất và là **nguyên mẫu / demo**
đúng nghĩa: pipeline chuyển outline thành sơ đồ, thuật toán bố cục và style
Excalidraw đã được triển khai và có test, nhưng skill vẫn đang trong quá trình
phát triển và chưa được dùng thực tế đủ lâu để gọi là ổn định. Hãy lường trước
còn nhiều điểm chưa hoàn thiện, một số trường hợp biên chưa được xử lý, và khả
năng thay đổi hành vi trước khi skill ổn định hẳn.

Mọi đề xuất cải tiến, phản hồi hoặc phát hiện về những điểm dự án còn chưa tốt
đều được trân trọng đón nhận. Đây cũng là cơ hội để dự án và tác giả tiếp tục
lắng nghe, học hỏi và hoàn thiện. ( •̀ .̫ •́ )✧

### Từng phần chạy ở đâu

| Thành phần | Chạy tại | Trách nhiệm |
|---|---|---|
| ChatGPT Browser Extension | Side chat của Chrome, Edge, Brave hoặc Vivaldi | Cung cấp tab hiện tại hoặc selection và khởi tạo yêu cầu lưu. |
| `web-to-obsidian` | Task ChatGPT/Codex đang dùng plugin đã cài | Kiểm tra quyền riêng tư và permalink, chọn nội dung trình duyệt hoặc fallback công khai được phép, rồi gọi helper local. |
| `save_capture.py` | Máy local | Chuẩn hóa và redact URL, phát hiện nội dung trùng, rồi ghi một source note vào vault local đã xác nhận. |
| `obsidian-clip-beautifier` | Task ChatGPT Work local hoặc Codex local | Thiết lập hoặc kiểm tra rule Linter, CSS có phạm vi và bước chuẩn bị export tùy chọn. Helper chuẩn bị một template Web Clipper thử nghiệm chưa kích hoạt; việc import, cấu hình hoặc xác minh template đó cần yêu cầu rõ của người dùng. Không chạy skill này sau mỗi lần lưu. |
| `obsidian-excalidraw-mindmap` *(nguyên mẫu / demo)* | Task ChatGPT Work local hoặc Codex local, hoặc phiên Claude Code đã cài plugin | Biến note đã capture thành sơ đồ Excalidraw kiểu brainstorm (layout radial hoặc tree). Vẫn đang phát triển, chưa ổn định. |
| Obsidian Web Clipper chính thức | Extension trình duyệt | Luồng thử nghiệm không bắt buộc, sử dụng template fallback được cung cấp và tạo schema note đơn giản hơn. Extension không gọi bất kỳ skill nào được đóng gói. |
| Obsidian | Ứng dụng desktop local | Hiển thị Markdown đã lưu và áp dụng hành vi Linter/CSS đã cấu hình. |

Để có trải nghiệm tốt nhất, chạy `obsidian-clip-beautifier` một lần từ task local cho từng vault, sau đó dùng `web-to-obsidian` trong browser side chat cho việc lưu hằng ngày. ChatGPT Browser Extension cung cấp ngữ cảnh trình duyệt; thao tác ghi file vẫn diễn ra trên máy local.

## Cấu hình

Sao chép file môi trường mẫu rồi chỉnh `.env`:

```powershell
Copy-Item .\.env.example .\.env
```

Dùng `.env` ở thư mục gốc repository làm cấu hình local trung tâm cho các helper chạy nền. Đặt `WEB_TO_OBSIDIAN_VAULT_PATH` cho skill này và chỉ dùng `OBSIDIAN_VAULT_PATH` như fallback tương thích dùng chung khi cần. Skill tương lai dùng vault khác nên có biến được namespace riêng, ví dụ `ANOTHER_SKILL_VAULT_PATH`. Helper capture kiểm tra `.env` của workspace trước, sau đó tự tìm file trung tâm này từ vị trí thật của mã nguồn; biến đã có trong tiến trình luôn được ưu tiên và `--env-file` vẫn là override rõ ràng. `.env` đã được Git bỏ qua. Không đặt khóa thật trong prompt, note, file skill, cấu hình được commit hoặc `.env.example`. Phải rotate mọi khóa từng xuất hiện trong log trước khi dùng lại.

`driftnote.yaml` vẫn là cấu hình tùy chọn cho thư mục và mặc định capture. Thứ tự xác định vault là `--vault`, `WEB_TO_OBSIDIAN_VAULT_PATH`, biến cũ `OBSIDIAN_VAULT_PATH`, rồi `vault_root` trong YAML.

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
Thiết lập và xác minh Linter cùng CSS có phạm vi cho các note do web-to-obsidian tạo trong vault Obsidian đã xác nhận của tôi. Không cấu hình extension Obsidian Web Clipper chính thức trừ khi tôi yêu cầu rõ luồng thử nghiệm đó.
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
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\obsidian-excalidraw-mindmap
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

Scanner kiểm tra các file đã được track và file không bị Git ignore có thể được
publish. Kết quả chỉ chứa file, số dòng và tên rule; scanner không in giá trị đã
khớp. Đây là lớp kiểm tra độ tin cậy cao, không thay thế việc rà lịch sử Git hoặc
thu hồi khóa từng bị commit trước đây.

## Giấy phép

MIT

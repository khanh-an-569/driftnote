# Báo cáo review mã nguồn — web-to-obsidian (2026-09-17)

> **Trạng thái vá 2026-09-18:** hai finding đã được vá; xem [kế hoạch và kết quả](fix-findings-plan.md). Phần bên dưới là báo cáo lịch sử trước bản vá, các đoạn “mã hiện tại” và số dòng không đại diện code sau vá. Ví dụ profile đã được ẩn danh bằng `<username>`; placeholder này không khớp scanner, kết quả bảng là kết quả trước ẩn danh với username cụ thể. Agent chính thực hiện kiểm chứng và vá theo sự đồng ý của người dùng; không quy các lần chạy tool của agent thành thao tác trực tiếp của người dùng.

> Kiểm chứng sau vá: 80 tests pass, scanner/compileall/diff check pass. Link có ngoặc và ampersand giữ đúng href khi render; audit đọc lại và apply lần hai không sửa thêm. CommonMark cho phép space trong angle destination; chính sách đầu vào của bản vá từ chối space nội bộ. Không migration source ID và chưa xác minh runtime Obsidian.

> **Cập nhật 2026-09-17 (sau vòng phản biện):** người dùng đã đối chiếu độc lập cả hai phát hiện (chạy 76 test hiện có, tái hiện regex/parser thủ công, tra RFC 3986 và đặc tả CommonMark) và chỉ ra 3 điểm cần sửa trong báo cáo gốc: (1) mức độ nghiêm trọng của Vấn đề 1 bị đánh giá cao hơn thực tế; (2) phạm vi ảnh hưởng của Vấn đề 2 mô tả sai — query đã an toàn nhờ `urlencode`, chỉ path/fragment còn hở; (3) đề xuất khắc phục Vấn đề 2 (percent-encode `source_url`) có rủi ro đổi ngữ nghĩa URI theo RFC 3986 và không nên áp dụng nguyên trạng. Nội dung bên dưới đã được sửa lại theo các điểm này; phần bị thay thế được đánh dấu rõ.

## Phạm vi và phương pháp

- **Phạm vi:** toàn bộ mã Python trong [`scripts/`](../scripts/) và [`skills/*/scripts/`](../skills/), cùng bộ test tương ứng trong [`tests/`](../tests/). Worktree sạch (không có diff đang mở) trước khi bắt đầu review và trước khi tạo file báo cáo này, nên review được thực hiện trên toàn bộ trạng thái hiện tại của repo thay vì một PR/diff cụ thể. *(Sửa: bản gốc ghi "nhánh `main` sạch" — không còn đúng kể từ khi chính file báo cáo này được tạo, vì `git status --short` từ đó trở đi luôn hiện `?? docs/review-2026-09-17-findings.md` cho tới khi được commit.)*
- **Cách làm:** đọc trực tiếp toàn bộ các file mã nguồn chính (`save_capture.py`, `audit_sensitive_urls.py`, `prepare_clip_pipeline.py`, `check_no_secrets.py`), đối chiếu với test hiện có để tìm khoảng trống coverage, sau đó xác minh độc lập từng giả thuyết lỗi bằng một sub-agent riêng (đọc lại code, chạy thử regex/logic, tìm test liên quan, cho verdict CONFIRMED/PLAUSIBLE/REFUTED).
- **Kết quả:** 2 vấn đề có bằng chứng cụ thể, không phát hiện thêm lỗi correctness nào khác đủ tin cậy để báo cáo sau khi rà soát phần còn lại (xem mục "Phạm vi đã kiểm tra nhưng không phát hiện lỗi" ở cuối).

---

## Vấn đề 1 — Bộ quét bí mật bỏ sót đường dẫn cá nhân trần

| | |
|---|---|
| **Mức độ** | ~~Trung bình–Cao~~ → **Thấp–Trung bình** (sửa sau phản biện — xem lý do bên dưới) |
| **Verdict** | **CONFIRMED** về hành vi (xác minh độc lập bằng sub-agent + tái xác nhận bởi người dùng, chạy thử regex thực tế) |
| **Vị trí** | [`scripts/check_no_secrets.py:22-25`](../scripts/check_no_secrets.py#L22-L25) |

**Vì sao hạ mức độ:** username/profile path là thông tin cá nhân nhưng không phải credential hay secret có khả năng cấp quyền truy cập trực tiếp. [`docs/security.md`](../docs/security.md#public-repository-checklist) đã yêu cầu review dữ liệu cá nhân thủ công như một lớp phòng vệ bổ sung và nói rõ "the scanner... does not claim to detect every possible secret" — nên đây là lỗ hổng của *một lớp* phòng vệ trong quy trình nhiều lớp, không phải điểm khiến toàn bộ quy trình xuất bản chắc chắn thất bại. Mức Trung bình–Cao chỉ hợp lý nếu threat model coi username Windows ngang hàng với secret/credential, điều mà tài liệu bảo mật hiện tại của repo không khẳng định.

### Mã hiện tại

```python
(
    "personal-windows-user-path",
    re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+[^<%\\/\r\n]+[\\/]", re.IGNORECASE),
),
```

Script này (`check_no_secrets.py`) là bước kiểm tra bắt buộc trước khi phát hành plugin công khai — được nêu rõ trong [`docs/security.md`](../docs/security.md#public-repository-checklist) ("Run `python scripts/check_no_secrets.py --root .`") và liên quan trực tiếp tới commit `8925efd Package plugin for portable public distribution`.

### Bằng chứng

Quy tắc yêu cầu phải có **một dấu phân cách (`\` hoặc `/`) xuất hiện SAU phần tên người dùng** thì mới khớp (`[^<%\\/\r\n]+[\\/]`). Kiểm tra trực tiếp với `pattern.search()` — đúng cách `scan()` xử lý từng dòng qua `text.splitlines()`:

| Chuỗi đầu vào | Có khớp không? |
|---|---|
| `C:\Users\<username>\Obsidian Vault` | ✅ Khớp — vì có `\` giữa "Alice" và "Obsidian Vault" |
| `C:\Users\<username>` (đường dẫn trần, không có thư mục con) | ❌ **Không khớp** |
| `C:/Users/<username>` (không có gì theo sau) | ❌ **Không khớp** |
| `vault: C:\Users\<username>` (path là token cuối trên dòng) | ❌ **Không khớp** |

Bài test duy nhất cho quy tắc này, [`tests/test_check_no_secrets.py::test_personal_windows_profile_path_is_reported`](../tests/test_check_no_secrets.py#L50-L60), chỉ dùng chuỗi `C:\Users\<username>\Obsidian Vault` — **vô tình** có thư mục con phía sau nên cung cấp đúng dấu phân cách mà regex cần. Không có test nào cho trường hợp đường dẫn trần (dạng `os.path.expanduser("~")` trả về, ví dụ chính đường dẫn `C:\Users\<username>` xuất hiện trong môi trường máy hiện tại).

### Hậu quả

Nếu một file cấu hình, log, ghi chú ví dụ, hay giá trị JSON nào trong repo chứa đúng dạng đường dẫn trần tới thư mục người dùng thật (không có thư mục con theo sau — đây là output *hợp lệ và tự nhiên* của `os.path.expanduser("~")` hoặc biến môi trường `%USERPROFILE%`, dù báo cáo này không có số liệu định lượng về tần suất thực tế xuất hiện trong các repo công khai để khẳng định nó "rất phổ biến"), công cụ kiểm tra trước-khi-publish sẽ báo **"No high-confidence secrets... found"** một cách sai lệch, và tên người dùng Windows thật của người đóng góp sẽ bị phát hành công khai lên GitHub mà không ai nhận ra — đúng loại rò rỉ mà quy tắc này được viết ra để ngăn.

### Đề xuất khắc phục (sửa sau phản biện)

Đề xuất gốc trong báo cáo — thêm `(?:[\\/]|$)` và `re.MULTILINE` — có hai vấn đề đã được chỉ ra:

1. `re.MULTILINE` là thừa: `scan()` đã tự tách từng dòng bằng `text.splitlines()` trước khi gọi `pattern.search(line)` (xem [check_no_secrets.py:66](../scripts/check_no_secrets.py#L66)), nên `$`/`^` trong regex vốn đã chỉ áp dụng trên một dòng.
2. Quan trọng hơn: nới lỏng đuôi thành "hết dòng cũng được" khiến `[^<%\\/\r\n]+` có thể **ăn tham lam toàn bộ phần còn lại của dòng** làm "username" trong các ngữ cảnh có dấu nháy, dấu phẩy, hay JSON — dễ tạo false positive hoặc bắt nhầm ranh giới. Ví dụ cần kiểm tra trước khi chốt regex: `"C:\Users\<username>"` (có dấu nháy kép bao quanh), `{"home":"C:\\Users\\<username>"}` (JSON với backslash kép).

Vì vậy không chốt một regex cụ thể ở đây. Việc sửa cần đi kèm bộ test tối thiểu sau (bổ sung vào `tests/test_check_no_secrets.py`) trước khi coi là xong:

```text
C:\Users\<username>
"C:\Users\<username>"
{"home":"C:\\Users\\<username>"}
C:\Users\<username>\Obsidian Vault      # case hiện có, không được regress
```

---

## Vấn đề 2 — Link nguồn trong note không escape ngoặc đơn trong URL

| | |
|---|---|
| **Mức độ** | Thấp (chỉ ảnh hưởng cạnh biên, không phải trường hợp phổ biến) |
| **Verdict** | **CONFIRMED** — tái hiện được bằng parser tuân thủ CommonMark (thu hẹp phạm vi so với bản gốc — xem bên dưới); cần một test trên Obsidian thật để xác nhận runtime cụ thể |
| **Vị trí** | [`skills/web-to-obsidian/scripts/save_capture.py:1383`](../skills/web-to-obsidian/scripts/save_capture.py#L1383), [`skills/web-to-obsidian/scripts/audit_sensitive_urls.py:180`](../skills/web-to-obsidian/scripts/audit_sensitive_urls.py#L180) |

### Mã hiện tại

`save_capture.py:1383`:
```python
lines.extend([..., f"> [Mở liên kết gốc]({source_url})"])
```

`audit_sensitive_urls.py:180` (hàm `replace_source_link`, dùng khi `--apply` cập nhật lại note):
```python
return f"> [{link_match.group('label')}]({safe.source_url})"
```

Cả hai đều nhúng `source_url` (được `sanitize_url()` dựng bằng `urllib.parse.urlunsplit(...)`, **không** qua `quote()`) thẳng vào cú pháp link Markdown, không escape gì cả.

### Bằng chứng

So sánh với đường xử lý HTML→Markdown trong cùng file — `_HtmlMarkdownRenderer._resolve_url` ([dòng 419-431](../skills/web-to-obsidian/scripts/save_capture.py#L419-L431)) — **có** escape bằng:

```python
return urllib.parse.quote(resolved, safe=":/?#[]@!$&'*,;=+%~-._")
```

`safe` ở đây **không** chứa `(` hoặc `)`, nên hàm này percent-encode mọi dấu ngoặc đơn trong URL. Đường xử lý ở Vấn đề 2 (link callout nguồn) thì không đi qua bước encode này.

Theo đặc tả CommonMark và [Obsidian Flavored Markdown](https://obsidian.md/help/obsidian-flavored-markdown) (Obsidian công bố chính thức là tuân theo CommonMark — bản gốc của báo cáo này nói cụ thể "dựa trên markdown-it" mà không có nguồn chính thức cho chi tiết đó, nay sửa lại cho đúng bằng chứng): **cặp ngoặc cân bằng không escape là hợp lệ** trong đích của link. Vì vậy ví dụ tưởng như hiển nhiên — URL Wikipedia dạng `.../wiki/Python_(programming_language)` — **thực ra vẫn hiển thị đúng**, không bị lỗi. Tái hiện bằng `markdown-it-py 4.2.0` ở preset `commonmark` (đây là một implementation bên thứ ba tuân theo CommonMark, **không phải** reference implementation chính thức — reference implementation là [`cmark`](https://github.com/commonmark/cmark)/`commonmark.js`; kết quả dưới đây phù hợp với các ví dụ chuẩn nêu trong đặc tả):

```text
[x](https://example.com/a)b)      → href = https://example.com/a, còn "b)" rơi ra ngoài link
[x](https://example.com/a(b)      → toàn bộ KHÔNG được parse thành link (ngoặc mở mồ côi, không chỉ "cắt cụt")
[x](https://example.com/a(b))     → hoạt động đúng (một cặp cân bằng)
```

Ngoặc mở mồ côi không chỉ khiến link "bị cắt cụt" như mô tả ban đầu — nó có thể khiến **toàn bộ cú pháp không còn được nhận diện là link**.

**Phạm vi ảnh hưởng — sửa lại:** báo cáo gốc nói "path/query" là sai. Phần **query** của `source_url` đi qua `urlencode(source_query, doseq=True)` tại [save_capture.py:968](../skills/web-to-obsidian/scripts/save_capture.py#L968) (mặc định `quote_via=quote_plus`, không nằm trong tập ký tự an toàn mặc định), nên `(`/`)` trong query **đã** được percent-encode thành `%28`/`%29` từ trước — không có nguy cơ vỡ Markdown ở phần query. Phạm vi thực sự chỉ là **path** (`parsed.path`, dùng nguyên trạng) và **fragment** (`parsed.fragment`, cũng dùng nguyên trạng, không qua `urlencode`) — hai thành phần này giữ nguyên ký tự gốc nên có thể mang theo ngoặc lệch cặp.

Không có test nào trong [`tests/test_save_capture.py`](../tests/test_save_capture.py) hay [`tests/test_audit_sensitive_urls.py`](../tests/test_audit_sensitive_urls.py) phủ trường hợp URL chứa dấu ngoặc (đã tìm kiếm các từ khóa liên quan, không có kết quả). Toàn bộ 76 test hiện có đều pass — xác nhận đây là **khoảng trống coverage**, không phải regression mà bộ test hiện hữu từng phát hiện rồi bỏ sót.

### Hậu quả

Với một URL nguồn có dấu ngoặc lệch cặp trong **path hoặc fragment** (không phải query), dòng `> [Mở liên kết gốc](...)` trong note có thể bị Obsidian hiển thị sai theo một trong hai cách: (a) phần URL sau dấu `)` mồ côi "rớt" ra khỏi đích liên kết và hiện thành text thường, hoặc (b) toàn bộ cụm không còn được nhận diện là link nếu có `(` mồ côi. Người dùng click vào link gốc sẽ đi tới một URL sai hoặc không thấy link nào cả. Đây là lỗi hiển thị (correctness), không phải lỗ hổng bảo mật, không ảnh hưởng tới đa số URL thực tế, và cần một lần kiểm chứng trên Obsidian thật (không chỉ `markdown-it-py`) để khẳng định runtime behavior chính xác của phiên bản Obsidian đang dùng.

### Đề xuất khắc phục (đề xuất gốc bị rút lại — xem lý do)

**Đề xuất gốc trong báo cáo — áp dụng `urllib.parse.quote(source_url, safe=...)` để percent-encode `source_url` — không nên làm nguyên trạng.** RFC 3986 xếp `(` và `)` vào nhóm `sub-delims`, được phép xuất hiện không mã hoá trong path/query/fragment; percent-encode một ký tự thuộc nhóm reserved có thể thay đổi cách URI được một số server diễn giải, nên `.../a(b)` và `.../a%28b%29` **không được đảm bảo tương đương** — đây là lý do chính, vì nó có thể đổi URL người dùng thực sự truy cập.

*(Sửa: bản trước có nói thêm rằng `source_url` "còn được dùng làm khoá canonicalization/identity" như một lý do bổ sung để không đổi nó — lập luận này quá rộng. Thực tế, `source_id` được tính từ `canonical_url` chứ không trực tiếp từ chuỗi `source_url` dùng để render callout (xem [`source_id_for(canonical_url)`](../skills/web-to-obsidian/scripts/save_capture.py#L1079) và [`run_capture`](../skills/web-to-obsidian/scripts/save_capture.py#L1552-L1559)); và `canonical_url` loại bỏ hẳn fragment (`urlunsplit((..., ""))`), nên ngoặc trong fragment không ảnh hưởng identity dù có gì đi nữa. Ngoặc trong **path** thì có ảnh hưởng vì path được giữ nguyên trong `canonical_url`. Nói cách khác: nếu `quote()` chỉ được áp dụng ngay tại điểm render callout — không đụng vào biến `source_url`/`canonical_url` được lưu vào frontmatter hay dùng để tính `source_id` — thì identity hoàn toàn không bị ảnh hưởng bởi cách sửa này. Lý do duy nhất và đủ để không percent-encode vẫn là rủi ro RFC 3986 nêu trên, không phải nguy cơ đổi identity.)*

**Hướng sửa an toàn hơn:**

1. Giữ nguyên giá trị `source_url`/`canonical_url` được lưu vào frontmatter và dùng để tính `source_id_for()` — không đổi cách các trường này được tính hay lưu.
2. Chỉ escape ở **tầng biểu diễn Markdown**, khi nhúng vào `[label](destination)`, dùng chung một hàm serializer cho cả `save_capture.py` và `audit_sensitive_urls.py` thay vì lặp lại logic ở hai nơi. Hai lựa chọn tương thích CommonMark: escape từng ký tự bằng backslash (`\(`, `\)`), hoặc bọc `source_url` trong `<...>` cho riêng dòng callout này (tiền lệ tương tự đã có ở `_markdown_destination()` cho trường hợp URL chứa khoảng trắng).
3. **`<...>` không phải giải pháp trọn vẹn nếu áp dụng máy móc.** CommonMark cấm literal `<`, `>`, và xuống dòng bên trong dạng `<...>` (phải escape hoặc từ chối). `sanitize_url()`/`urlsplit()` hiện **không** xác thực đầy đủ ký tự trong URL — Python tự ghi rõ điều này trong phần [URL parsing security](https://docs.python.org/3.11/library/urllib.parse.html#url-parsing-security) — nên một URL path chứa literal `<`, `>`, hoặc khoảng trắng vẫn có thể lọt qua `sanitize_url()` tới tận bước render. Ví dụ, `[x](<https://example.com/a>b>)` hay `[x](<https://example.com/a<b>)` vẫn làm hỏng link Markdown dù đã bọc `<...>`. Vì vậy trước khi bọc `<...>`, cần **xác định rõ tập ký tự hợp lệ và từ chối (hoặc escape) ít nhất `<`, `>`, và line break** trong URL ở bước sanitize, không chỉ xử lý riêng dấu ngoặc.
4. Nếu dùng dạng `<...>`, phải cập nhật đồng thời `SOURCE_LINK_PATTERN` trong `audit_sensitive_urls.py` để bỏ cặp `<>` trước khi gọi `sanitize_url()` trên giá trị đọc lại từ note cũ — nếu không, script audit sẽ nhận nhầm `<https://...>` (còn nguyên dấu `<` `>`) làm URL và làm hỏng bước parse.
5. Thêm test round-trip cho `)`, `(`, khoảng trắng, `<`, `>`, và fragment: ghi note → đọc lại bằng audit script → xác nhận URL khôi phục đúng từng ký tự, không lẫn ký tự escape.
6. Xác nhận thêm bằng Obsidian thật, không chỉ dựa vào parser CommonMark bên thứ ba.

Bộ test tối thiểu nên bổ sung (vào `tests/test_save_capture.py` và `tests/test_audit_sensitive_urls.py`):

```text
https://example.com/a)b
https://example.com/a(b
https://example.com/a(b)
https://example.com/a?q=x)y       # phải tiếp tục hoạt động bình thường — query đã an toàn
https://example.com/a#x)y
```

---

## Phạm vi đã kiểm tra nhưng không phát hiện lỗi

Các phần sau được đọc và đối chiếu với test hiện có, đều có coverage tốt và không phát hiện lỗi correctness đáng báo cáo:

- Logic canonical hoá URL và chống tạo note trùng lặp (`sanitize_url`, `find_duplicate`, tương thích ngược với thuật toán canonical hoá v1).
- Cơ chế khóa file (`_identity_claim`) để tránh race condition khi capture đồng thời cùng một nguồn.
- Ghi file nguyên tử bằng `tempfile` + `os.replace` / hard-link no-clobber (`_atomic_replace_note`, tạo note mới qua `os.link`).
- Kiểm tra permalink mạng xã hội (Facebook/Instagram) trước khi cho phép capture loại `social`.
- Chuyển đổi HTML → Markdown, bao gồm việc chặn scheme `javascript:` và chỉ cho phép `http`/`https`/`mailto`/`tel`.
- Resolve đường dẫn vault (CLI → biến môi trường → `web-to-obsidian.yaml`) và `.env` loader (chỉ nhận 3 tên biến được whitelist).

## Ghi chú phương pháp

Vòng đầu: cả hai phát hiện được xác minh bằng sub-agent riêng biệt (đọc lại code, chạy thử regex/logic, tìm test liên quan, tự cho verdict CONFIRMED/PLAUSIBLE/REFUTED) trước khi đưa vào báo cáo. **Lưu ý về khả năng kiểm toán:** log/transcript của các sub-agent này không được lưu lại như artifact trong repo, nên tuyên bố "đã xác minh độc lập" ở vòng đầu không thể tự kiểm chứng lại từ bên ngoài — chỉ kết luận cuối cùng (verdict + trích dẫn dòng code) là có thể đối chiếu trực tiếp với mã nguồn.

Vòng hai (phản biện): người dùng đối chiếu độc lập bằng cách chạy toàn bộ 76 test hiện có (đều pass — xác nhận đây là khoảng trống coverage, không phải regression), tái hiện regex/parser thủ công bằng `markdown-it-py 4.2.0`, và tra cứu RFC 3986 cùng tài liệu chính thức của Obsidian/CommonMark. Các sửa đổi trong bản cập nhật này (mức độ nghiêm trọng, phạm vi ảnh hưởng, tên parser, quan hệ giữa `source_url`/`source_id`, và đề xuất khắc phục) phản ánh kết quả của vòng phản biện đó, kèm trích dẫn nguồn kiểm chứng được ở mỗi mục.

Vòng ba (phản biện tiếp theo, sau khi bản cập nhật trên được viết): người dùng chạy lại toàn bộ test lần nữa, đối chiếu code hiện tại, và chỉ ra 6 điểm cần chỉnh thêm — chủ yếu về độ chính xác câu chữ (tên parser, cụm "rất phổ biến" thiếu định lượng, câu "nhánh main sạch" đã lỗi thời do chính file báo cáo này tạo ra thay đổi trong worktree) và một lỗ hổng thực chất trong đề xuất `<...>` (không xử lý literal `<`/`>`/khoảng trắng trong URL, vốn `sanitize_url()` hiện không chặn). Trong lượt này, tôi (không phải sub-agent) tự chạy lại `python -m unittest discover -s tests -v` và xác nhận đúng "Ran 76 tests... OK", khớp với số liệu người dùng nêu, trước khi áp dụng các sửa đổi tương ứng vào bản trên.

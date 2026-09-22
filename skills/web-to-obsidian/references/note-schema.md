# Source note schema / Schema của source note

## Required properties / Properties bắt buộc

```yaml
---
type: source
content_type: article
status: inbox
cssclasses: [web-clip]
source_id: "0123456789abcdef"
title: "Source title"
source_url: "https://example.com/original"
canonical_url: "https://example.com/original"
canonicalization_version: 2
source_url_redacted: false
author: ""
published:
captured: 2026-09-13T10:00:00+07:00
capture_method: chrome
platform: "example.com"
link_only: false
tags:
  - web-capture
topics: []
---
```

Allowed `content_type` values are `article`, `news`, `bookmark`, `music`, `video`, `podcast`, `social`, and `other`.

Các giá trị `content_type` được phép là `article`, `news`, `bookmark`, `music`, `video`, `podcast`, `social` và `other`.

Allowed `status` values are `inbox`, `processed`, `needs-review`, and `archived`.

Các giá trị `status` được phép là `inbox`, `processed`, `needs-review` và `archived`.

Allowed `capture_method` values are `selection`, `chrome`, `tavily-basic`, `tavily-advanced`, `hybrid`, `manual`, and `public-html`.

Các giá trị `capture_method` được phép là `selection`, `chrome`, `tavily-basic`, `tavily-advanced`, `hybrid`, `manual` và `public-html`.

`source_id` is the first 16 hexadecimal characters of the SHA-256 hash of `canonical_url`. Use it for duplicate detection; do not use the title as the identifier.

`source_id` là 16 ký tự thập lục phân đầu tiên của giá trị băm SHA-256 từ `canonical_url`. Dùng nó để phát hiện trùng lặp; không dùng tiêu đề làm định danh.

For Facebook and Instagram notes with `content_type: social`, the helper rejects an unrecognized post URL by default so a feed or profile URL cannot collapse unrelated posts into one identity. Use `--confirm-social-permalink` only after the user explicitly confirms that the supplied URL identifies the exact selected post. / Với note Facebook/Instagram loại `social`, helper mặc định từ chối URL bài đăng không nhận diện được; chỉ dùng cờ xác nhận sau khi người dùng xác nhận rõ URL trỏ đúng bài.

`web-clip` is the required base CSS class. Additional classes are optional presentation hints, must follow [presentation.md](presentation.md), and are appended with repeatable `--cssclass`; they never replace `web-clip`. / `web-clip` là class nền bắt buộc; class trình bày bổ sung chỉ được thêm theo `presentation.md` và không thay thế class nền.

`canonicalization_version` is `2` for notes created or migrated by the current helpers. `source_url_redacted` is `true` when credentials or sensitive query fields were removed before storage. `tavily_request_id` is conditional: record it after any successful Tavily request, even when its content is not selected; change `capture_method` only when Tavily content is used. / Version hiện tại là `2`; luôn ghi request ID khi Tavily thành công, nhưng chỉ đổi capture method khi dùng nội dung Tavily.

## Body sections / Các phần nội dung

`My notes` / `Ghi chú của tôi` is always present. Add every other content section only when it contains real information. / `Ghi chú của tôi` luôn tồn tại; các phần khác chỉ xuất hiện khi có dữ liệu thật:

- `Why I saved this` / `Vì sao tôi lưu`
- `Selected excerpt` / `Đoạn đã chọn`
- `Summary` / `Tóm tắt`
- `Source content` / `Nội dung nguồn`
- `Links` / `Liên kết`

For music, video, and podcasts, metadata plus the original link is a valid complete capture. Do not store copied audio/video or full lyrics.

Với nhạc, video và podcast, metadata cùng liên kết gốc đã là một capture đầy đủ hợp lệ. Không lưu bản sao audio/video hoặc toàn bộ lời bài hát.

`assets/Source Note.md` is a manual-import template with placeholders. The helper renders the same schema dynamically and omits empty optional sections. / Asset là template nhập thủ công; helper render động và bỏ các phần tùy chọn rỗng.

## Rich source content / Nội dung nguồn giàu cấu trúc

`--content-file` accepts raw HTML, already-converted Markdown, or intentional plain text; the helper detects HTML from its structure. `--html-file` explicitly accepts UTF-8 DOM/HTML from an authorized browser context. Detected HTML converts headings, structured document TOCs, hyperlinks, emphasis, lists, code, remote images, simple tables, TeX math, Quarto title blocks, and `<details>` into Obsidian-compatible Markdown. The note keeps its own H1; HTML source headings are shifted down one level, and rich HTML content begins directly inside the generated source-content markers without a visible wrapper heading. A valid document TOC becomes a collapsed `[!toc]-` callout with nested same-note heading links. Supported expandable sections become native Obsidian callouts with `+` for initially open and `-` for initially closed. Rich structure that was already flattened to text cannot be reconstructed reliably.

On an exact duplicate, the default result is still `duplicate`. With an explicit `--refresh-existing`, the helper atomically replaces only the generated source-content marker region, changes `link_only` to `false`, updates `capture_method`, and preserves the existing `Ghi chú của tôi` section plus the rest of the note metadata. The refresh fails closed when either the marker/personal-notes boundary or new source content is missing. Legacy notes can be migrated only when their section boundary is unambiguous.

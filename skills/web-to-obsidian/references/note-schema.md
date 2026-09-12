# Source note schema / Schema của source note

## Required properties / Properties bắt buộc

```yaml
---
type: source
content_type: article
status: inbox
source_id: "0123456789abcdef"
title: "Source title"
source_url: "https://example.com/original"
canonical_url: "https://example.com/original"
author: ""
published:
captured: 2026-09-13T10:00:00+07:00
capture_method: chrome
platform: "example.com"
tags:
  - web-capture
topics: []
---
```

Allowed `content_type` values are `article`, `news`, `bookmark`, `music`, `video`, `podcast`, `social`, and `other`.

Các giá trị `content_type` được phép là `article`, `news`, `bookmark`, `music`, `video`, `podcast`, `social` và `other`.

Allowed `status` values are `inbox`, `processed`, `needs-review`, and `archived`.

Các giá trị `status` được phép là `inbox`, `processed`, `needs-review` và `archived`.

Allowed `capture_method` values are `selection`, `chrome`, `tavily-basic`, `tavily-advanced`, `hybrid`, and `manual`.

Các giá trị `capture_method` được phép là `selection`, `chrome`, `tavily-basic`, `tavily-advanced`, `hybrid` và `manual`.

`source_id` is the first 16 hexadecimal characters of the SHA-256 hash of `canonical_url`. Use it for duplicate detection; do not use the title as the identifier.

`source_id` là 16 ký tự thập lục phân đầu tiên của giá trị băm SHA-256 từ `canonical_url`. Dùng nó để phát hiện trùng lặp; không dùng tiêu đề làm định danh.

## Body sections / Các phần nội dung

Use only sections that contain real information. / Chỉ dùng các phần có thông tin thật:

- `Why I saved this` / `Vì sao tôi lưu`
- `Selected excerpt` / `Đoạn đã chọn`
- `Summary` / `Tóm tắt`
- `Source content` / `Nội dung nguồn`
- `My notes` / `Ghi chú của tôi`
- `Links` / `Liên kết`

For music, video, and podcasts, metadata plus the original link is a valid complete capture. Do not store copied audio/video or full lyrics.

Với nhạc, video và podcast, metadata cùng liên kết gốc đã là một capture đầy đủ hợp lệ. Không lưu bản sao audio/video hoặc toàn bộ lời bài hát.

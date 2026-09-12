# Source note schema

## Required properties

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

Allowed `status` values are `inbox`, `processed`, `needs-review`, and `archived`.

Allowed `capture_method` values are `selection`, `chrome`, `tavily-basic`, `tavily-advanced`, `hybrid`, and `manual`.

`source_id` is the first 16 hexadecimal characters of the SHA-256 hash of `canonical_url`. Use it for duplicate detection; do not use the title as the identifier.

## Body sections

Use only sections that contain real information:

- `Vì sao tôi lưu` / `Why I saved this`
- `Đoạn đã chọn` / `Selected excerpt`
- `Tóm tắt` / `Summary`
- `Nội dung nguồn` / `Source content`
- `Ghi chú của tôi` / `My notes`
- `Liên kết` / `Links`

For music, video, and podcasts, metadata plus the original link is a valid complete capture. Do not store copied audio/video or full lyrics.

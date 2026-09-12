---
name: obsidian-inbox-processor
description: Review source notes captured by web-to-obsidian, preserve their provenance, and turn only durable insights into linked Obsidian knowledge notes; rà soát source note do web-to-obsidian thu thập, giữ nguyên xuất xứ và chỉ chuyển insight bền vững thành knowledge note Obsidian có liên kết. Use for inbox triage, source distillation, atomic-note creation, and status updates; dùng cho phân loại inbox, chắt lọc nguồn, tạo atomic note và cập nhật trạng thái. Do not capture browser pages or bulk-generate notes from every source; không thu thập trang trình duyệt hoặc tạo hàng loạt note từ mọi nguồn.
---

# Obsidian Inbox Processor / Bộ xử lý inbox Obsidian

Process captures deliberately. A source can be useful without producing a permanent knowledge note.

Xử lý capture có chủ đích. Một nguồn vẫn có thể hữu ích mà không cần tạo knowledge note lâu dài.

## Select work / Chọn phạm vi xử lý

Resolve the confirmed vault root, then find source notes with `status: inbox`. Default to at most ten notes per run unless the user requests a different scope.

Xác định vault root đã được xác nhận, rồi tìm source note có `status: inbox`. Mặc định xử lý tối đa mười note mỗi lần, trừ khi người dùng yêu cầu phạm vi khác.

Read [references/processing-rules.md](references/processing-rules.md) before changing notes.

Đọc [references/processing-rules.md](references/processing-rules.md) trước khi thay đổi note.

## Triage each source / Phân loại từng nguồn

Choose one outcome / Chọn một kết quả:

- **Keep as source:** useful reference, but no durable insight to extract. / **Giữ làm nguồn:** tài liệu tham khảo hữu ích nhưng không có insight bền vững cần chắt lọc.
- **Create knowledge notes:** one note per durable claim, concept, decision, or reusable method. / **Tạo knowledge note:** mỗi note dành cho một luận điểm, khái niệm, quyết định hoặc phương pháp có thể tái sử dụng.
- **Needs review:** missing context, conflicting evidence, or a user decision is required. / **Cần xem lại:** thiếu ngữ cảnh, bằng chứng mâu thuẫn hoặc cần quyết định của người dùng.
- **Discard recommendation:** low-value or duplicate capture. Do not delete it without explicit authorization. / **Đề xuất loại bỏ:** capture ít giá trị hoặc trùng lặp. Không xóa nếu chưa được cho phép rõ ràng.

Do not create a fixed number of derived notes. Zero is valid.

Không tạo số lượng note chắt lọc cố định. Không tạo note nào cũng là kết quả hợp lệ.

## Create durable notes / Tạo note bền vững

When a source supports a reusable idea / Khi nguồn hỗ trợ một ý tưởng có thể tái sử dụng:

- State one primary claim per note. / Mỗi note nêu một luận điểm chính.
- Write in the user's language unless asked otherwise. / Viết bằng ngôn ngữ của người dùng trừ khi được yêu cầu khác.
- Link back to the source note with `source_note` and a body wikilink. / Liên kết ngược về source note bằng `source_note` và một wikilink trong nội dung.
- Separate sourced claims from the user's interpretation. / Tách luận điểm từ nguồn khỏi diễn giải của người dùng.
- Mark time-sensitive or uncertain claims for verification. / Đánh dấu luận điểm dễ thay đổi theo thời gian hoặc chưa chắc chắn để xác minh.
- Add existing wikilinks only when the relationship is clear; do not generate speculative graph density. / Chỉ thêm wikilink hiện có khi quan hệ rõ ràng; không làm dày graph bằng liên kết suy đoán.
- Update the nearest MOC only when the new note clearly belongs there. / Chỉ cập nhật MOC gần nhất khi note mới rõ ràng thuộc về đó.

Use `assets/Knowledge Note.md` as a starting shape, omitting empty optional sections.

Dùng `assets/Knowledge Note.md` làm cấu trúc khởi đầu và bỏ các phần tùy chọn còn trống.

## Complete processing / Hoàn tất xử lý

After all derived notes are safely written, update the source note / Sau khi mọi note chắt lọc đã được ghi an toàn, cập nhật source note:

- Set `status: processed` or `status: needs-review`. / Đặt `status: processed` hoặc `status: needs-review`.
- Add `processed` as an ISO date. / Thêm `processed` dưới dạng ngày ISO.
- Add `derived_notes` as quoted wikilinks when any were created. / Thêm `derived_notes` dưới dạng wikilink được đặt trong dấu nháy khi có note được tạo.

Never remove raw content during processing. If the Obsidian CLI is available, it may be used for property updates and moves while Obsidian is open. Otherwise edit the Markdown carefully and keep the source in place.

Không xóa nội dung thô trong quá trình xử lý. Nếu Obsidian CLI có sẵn, có thể dùng nó để cập nhật property và di chuyển note khi Obsidian đang mở. Nếu không, hãy chỉnh Markdown cẩn thận và giữ source note tại chỗ.

Report created notes, sources marked processed, items needing review, and duplicates. Never claim that a source was verified unless verification actually occurred.

Báo các note đã tạo, nguồn được đánh dấu đã xử lý, mục cần xem lại và nội dung trùng lặp. Không tuyên bố nguồn đã được xác minh nếu việc xác minh chưa thật sự diễn ra.

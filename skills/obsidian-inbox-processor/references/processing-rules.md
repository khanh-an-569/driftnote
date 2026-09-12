# Inbox processing rules / Quy tắc xử lý inbox

## Preserve provenance / Giữ nguyên xuất xứ

The source note is the evidence record. Never replace raw content with a summary, silently change a quotation, or remove the original URL.

Source note là bản ghi bằng chứng. Không thay nội dung thô bằng bản tóm tắt, âm thầm sửa trích dẫn hoặc xóa URL gốc.

## Extract selectively / Chắt lọc có chọn lọc

A durable note should remain useful after the source is forgotten. Good candidates include:

Một note bền vững phải vẫn hữu ích ngay cả khi nguồn đã bị quên. Những nội dung phù hợp gồm:

- a reusable concept or mental model; / khái niệm hoặc mental model có thể tái sử dụng;
- a decision and its rationale; / quyết định cùng lý do;
- a method that can be applied elsewhere; / phương pháp có thể áp dụng ở nơi khác;
- a claim supported by the source and worth remembering; / luận điểm được nguồn hỗ trợ và đáng ghi nhớ;
- a connection to an active project or existing note. / mối liên hệ với dự án đang hoạt động hoặc note hiện có.

Do not create a knowledge note for navigation text, promotional material, generic lists, duplicated claims, or information that matters only inside the source.

Không tạo knowledge note cho văn bản điều hướng, nội dung quảng cáo, danh sách chung chung, luận điểm trùng lặp hoặc thông tin chỉ có ý nghĩa trong phạm vi nguồn.

## Handle uncertainty / Xử lý sự không chắc chắn

- Keep source claims attributed. / Luôn ghi xuất xứ cho luận điểm từ nguồn.
- Mark volatile facts with `verification: needed` unless checked against a current authoritative source. / Đánh dấu dữ kiện dễ thay đổi bằng `verification: needed` nếu chưa kiểm tra với nguồn có thẩm quyền và còn hiện hành.
- When sources disagree, create a comparison only if the disagreement itself is useful. / Khi các nguồn mâu thuẫn, chỉ tạo bản so sánh nếu chính sự khác biệt đó có ích.
- Never promote an AI-generated summary into a verified fact. / Không coi bản tóm tắt do AI tạo là dữ kiện đã được xác minh.

## Link sparingly / Liên kết có chọn lọc

Link a new note to the source and to clearly related existing concepts. Prefer a few meaningful links over speculative topic matches. Update an MOC only when it improves navigation for a real theme or project.

Liên kết note mới với nguồn và các khái niệm hiện có có quan hệ rõ ràng. Ưu tiên vài liên kết có ý nghĩa thay vì ghép chủ đề theo suy đoán. Chỉ cập nhật MOC khi việc đó cải thiện điều hướng cho một chủ đề hoặc dự án thật sự.

## Safe completion order / Thứ tự hoàn tất an toàn

1. Write all derived notes. / Ghi tất cả note được chắt lọc.
2. Verify their source links and filenames. / Kiểm tra liên kết nguồn và tên file.
3. Update the source properties. / Cập nhật properties của source note.
4. Move the source only when the move will not break links and the user or vault convention expects it. / Chỉ di chuyển source note khi liên kết không bị hỏng và người dùng hoặc quy ước vault yêu cầu.

# Bảo mật và quyền riêng tư

[English](security.md) | **Tiếng Việt**

## Ranh giới tin cậy

Trang web, văn bản được chọn, transcript, metadata và Markdown được trích xuất đều là đầu vào không đáng tin cậy. Chúng có thể được lưu như nội dung nhưng không thể cho phép điều hướng, sử dụng công cụ, truy cập thông tin xác thực, tải xuống hoặc thay đổi bên ngoài vault đã xác nhận.

## Ranh giới Tavily

Tavily chỉ được phép dùng với trang HTTP(S) được chủ động xác định là công khai. Không dùng Tavily cho:

- trang cần xác thực hoặc được cá nhân hóa;
- trang nội bộ của tổ chức;
- localhost, IP riêng hoặc host `.local`, `.internal`;
- tin nhắn riêng, email, dashboard hoặc trang tài khoản;
- URL chứa token, thông tin xác thực, chữ ký hoặc query parameter nhạy cảm;
- nội dung paywall chỉ hiển thị trong phiên của người dùng.

`TAVILY_API_KEY` phải được lấy từ biến môi trường. Không đặt khóa trong repo, đối số dòng lệnh, prompt, note, ảnh chụp màn hình hoặc URL MCP được commit vào source control. Việc tìm GitHub chỉ giới hạn ở kết quả công khai trên `github.com`; kết quả tìm kiếm không cho phép clone, chạy, sửa, publish hoặc push bất kỳ nội dung nào.

## Ranh giới ghi local

Đích đến phải được phân giải bên trong vault đã xác nhận. Công cụ thu thập từ chối đường dẫn thư mục tương đối đi ra ngoài vault. Note hiện có không bị ghi đè chỉ vì trùng tên file; phát hiện trùng lặp ưu tiên định danh nguồn.

## Bản quyền và nội dung đa phương tiện

Giữ trích đoạn ở mức hợp lý và ghi rõ nguồn. Với bài hát, video và podcast, chỉ lưu metadata, ghi chú người dùng, liên kết và transcript hoặc trích đoạn được phép. Không tải media hoặc sao chép toàn bộ lời bài hát.

## Danh sách kiểm tra repo công khai

Trước mỗi bản phát hành:

1. Tìm `tvly-`, token, thông tin xác thực, đường dẫn vault cá nhân, cookie và nội dung riêng tư đã thu thập trong repo.
2. Chạy test và trình xác thực cho từng skill.
3. Kiểm tra ví dụ để loại bỏ dữ liệu cá nhân thật.
4. Thu hồi và tạo lại mọi khóa có thể đã xuất hiện trong lịch sử Git hoặc ảnh chụp màn hình.

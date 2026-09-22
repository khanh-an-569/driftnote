# Đóng góp

[English](CONTRIBUTING.md) | **Tiếng Việt**

Bản tiếng Anh đầy đủ được duy trì song song trong `CONTRIBUTING.md`.

Tách riêng bước thu thập và chắt lọc kiến thức. Mọi thay đổi phải giữ được nguồn gốc nội dung, không âm thầm ghi dữ liệu ra hệ thống bên ngoài, đồng thời chỉ dùng Tavily như một lựa chọn cho URL công khai.

## Phát triển

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Trước khi commit bất kỳ file nào — không chỉ trước khi mở pull request:

1. Chạy `python scripts/check_no_secrets.py --root .` và sửa hết các dòng bị báo trước khi commit. Áp dụng cho mọi file, kể cả tài liệu plan/audit do AI tạo trong `docs/superpowers/` và `docs/audits/` — những file này thường vô tình chứa đường dẫn cá nhân thật (vd. `C:\Users\<tên>\...`), tên máy hoặc thông tin riêng tư khác trong lúc soạn thảo. CI chạy đúng script này trên mỗi lần push và sẽ fail toàn bộ ma trận job chỉ vì một đường dẫn bị lộ.
2. Không commit đường dẫn vault thật, nội dung riêng tư đã thu thập hoặc API key.

Trước khi mở pull request:

1. Thêm hoặc cập nhật test cho hành vi có thể quan sát.
2. Chạy bước quét bí mật được mô tả trong `docs/security.vi.md`.
3. Kiểm tra `SKILL.md` của từng skill bằng trình xác thực skill của Codex khi công cụ này có sẵn.
4. Kiểm tra `.codex-plugin/plugin.json` bằng trình xác thực plugin của Codex khi công cụ này có sẵn.

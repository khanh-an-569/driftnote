# Contributing / Đóng góp

Keep capture and distillation separate. Changes should preserve source provenance, avoid hidden external writes, and keep Tavily optional and limited to public URLs.

Tách riêng bước thu thập và chắt lọc kiến thức. Mọi thay đổi phải giữ được nguồn gốc nội dung, không âm thầm ghi dữ liệu ra hệ thống bên ngoài, đồng thời chỉ dùng Tavily như một lựa chọn cho URL công khai.

## Development / Phát triển

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Before opening a pull request / Trước khi mở pull request:

1. Add or update tests for observable behavior. / Thêm hoặc cập nhật test cho hành vi có thể quan sát.
2. Run the secret scan described in `docs/security.md`. / Chạy bước quét bí mật được mô tả trong `docs/security.md`.
3. Validate both `SKILL.md` files with the Codex skill validator when it is available. / Kiểm tra cả hai file `SKILL.md` bằng trình xác thực skill của Codex khi công cụ này có sẵn.
4. Validate `.codex-plugin/plugin.json` with the Codex plugin validator when it is available. / Kiểm tra `.codex-plugin/plugin.json` bằng trình xác thực plugin của Codex khi công cụ này có sẵn.
5. Do not commit real vault paths, captured private content, or API keys. / Không commit đường dẫn vault thật, nội dung riêng tư đã thu thập hoặc API key.

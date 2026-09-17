---
name: obsidian-clip-beautifier
description: Use when a user asks to set up, audit, repair, lint, visually style, or prepare exports for Obsidian web clips; do not use for browser capture or semantic rewriting. / Dùng khi người dùng yêu cầu thiết lập, kiểm tra, sửa chữa, lint, tạo kiểu hoặc chuẩn bị export cho web clip trong Obsidian.
---

# Obsidian Clip Beautifier

Build a maintainable pipeline around source Markdown. Keep content cleanup, visual styling, and external publishing as separate layers.

Tạo pipeline có thể bảo trì quanh Markdown nguồn. Tách riêng việc làm sạch nội dung, trình bày trong Obsidian và xuất bản ra ngoài.

## Compatibility boundary / Ranh giới tương thích

Treat notes created by the bundled `web-to-obsidian` skill as the primary supported input. The supplied template for the official Obsidian Web Clipper browser extension is an experimental compatibility path: it produces a smaller, different metadata schema and is not currently stable enough to describe as equivalent or fully supported. Warn the user before setting up that extension path, use a disposable test clip, and verify the actual output before routine or batch operations.

Xem note do skill `web-to-obsidian` trong plugin tạo ra là đầu vào được hỗ trợ chính. Template dành cho extension Obsidian Web Clipper chính thức chỉ là luồng tương thích thử nghiệm: nó tạo schema metadata nhỏ hơn, khác biệt và hiện chưa đủ ổn định để được mô tả là tương đương hoặc được hỗ trợ đầy đủ. Phải cảnh báo người dùng trước khi thiết lập luồng extension, dùng một clip thử và xác minh kết quả thực tế trước khi vận hành thường xuyên hoặc theo lô.

## Choose the mode / Chọn chế độ

- **Set up or repair:** install scoped CSS and guide the user through safe Linter settings for `web-to-obsidian` notes. The helper stages an inactive experimental Web Clipper template asset; import, configure, or verify that extension path only when the user explicitly requests it. Read [references/setup.md](references/setup.md).
- **Audit:** inspect the confirmed vault read-only and report missing folders, assets, plugins, or unsafe Linter rules. Read [references/setup.md](references/setup.md).
- **Operate:** explain or carry out a bounded inbox cleanup, batch lint, visual check, or export preparation. Read [references/operation.md](references/operation.md).

Do not capture browser content in this skill; use `web-to-obsidian` for that. Formatting must not summarize, reinterpret, or otherwise change the source's meaning.

Không dùng skill này để thu thập nội dung trình duyệt; dùng `web-to-obsidian`. Việc định dạng không được tóm tắt, diễn giải lại hoặc làm thay đổi ý nghĩa của nguồn.

## Resolve and protect the vault / Xác định và bảo vệ vault

Use the first confirmed vault path from the user's request, the current task, or `OBSIDIAN_VAULT_PATH`. Never guess a personal path. Verify that the directory exists and contains `.obsidian` before proposing writes.

Dùng đường dẫn vault đã được xác nhận trong yêu cầu, task hiện tại hoặc `OBSIDIAN_VAULT_PATH`. Không đoán đường dẫn cá nhân. Xác minh thư mục tồn tại và có `.obsidian` trước khi đề xuất ghi.

Treat these as separate permissions:

- Inspecting configuration is read-only.
- Creating folders and copying the supplied assets is authorized when the user asks to set up the workflow in that vault.
- Installing browser extensions or community plugins, enabling plugins, changing plugin settings, batch-rewriting notes, and publishing content require matching user intent.

Do not edit `.obsidian/community-plugins.json` or a plugin's `data.json` to simulate UI installation. Use the Obsidian and browser interfaces for plugin installation and settings. Before the first folder-wide lint, recommend a vault backup or Git commit and test on a small bounded sample.

## Materialize the safe assets / Tạo asset an toàn

Run the helper without `--apply` first:

```powershell
python scripts/prepare_clip_pipeline.py --vault "D:\path\to\vault"
```

When the user has asked to set up that vault and the preview is correct, apply it:

```powershell
python scripts/prepare_clip_pipeline.py --vault "D:\path\to\vault" --apply
```

The helper creates the inbox/archive folders, stages the experimental Web Clipper template under `00 System/Web Clipper`, and installs a CSS snippet under `.obsidian/snippets`. Copying the template does not activate or validate the extension path. The helper never overwrites a differing file. Report `created`, `unchanged`, and `conflict` items exactly.

The base snippet styles the generated `[!web-header]` source banner and collapsed `[!toc]` document outline, and makes wide Markdown tables horizontally scrollable without clipping cells. Foldable learning objectives, checkpoints, quizzes, examples, and warnings use native Obsidian callouts produced by `web-to-obsidian`; the snippet does not require an extra community plugin for those interactions.

## Verify the outcome / Xác minh kết quả

After primary-path setup, verify all of the following:

1. A `web-to-obsidian` test note lands in `00 Inbox/Web` with the required source-note identity fields and `cssclasses: web-clip`.
2. Linter changes only the intended test note using the safe starter rules.
3. The `obsidian-clip-beautifier` CSS snippet affects the test note and leaves ordinary notes unchanged.
4. MD Beautify, when requested, receives the already-clean Markdown and produces a presentation copy; it is not used as the canonical source formatter.

Only when the user explicitly requested the experimental extension path, also verify that the JSON template imports into the installed Obsidian Web Clipper version and that one disposable clip has `type`, `status`, `source`, `clipped_at`, `tags`, and `cssclasses`. Report this result separately from primary-path verification and do not infer schema or safety parity.

If any step cannot be verified, say which layer remains manual or unknown. Never claim the pipeline is fully active merely because its files were copied.

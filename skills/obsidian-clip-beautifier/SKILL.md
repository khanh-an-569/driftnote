---
name: obsidian-clip-beautifier
description: Configure, audit, and operate a safe Obsidian pipeline that captures web pages into a structured inbox, normalizes Markdown with Linter, styles web clips with scoped CSS, and optionally prepares polished exports; cấu hình, kiểm tra và vận hành pipeline làm sạch và làm đẹp web clip trong Obsidian. Use for workflow setup, template installation, formatting rules, visual styling, and export preparation. Do not use to capture a page or semantically rewrite source content.
---

# Obsidian Clip Beautifier

Build a maintainable pipeline around source Markdown. Keep content cleanup, visual styling, and external publishing as separate layers.

Tạo pipeline có thể bảo trì quanh Markdown nguồn. Tách riêng việc làm sạch nội dung, trình bày trong Obsidian và xuất bản ra ngoài.

## Choose the mode / Chọn chế độ

- **Set up or repair:** install the supplied Web Clipper template and scoped CSS, then guide the user through plugin settings. Read [references/setup.md](references/setup.md).
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

The helper creates the inbox/archive folders, copies the Web Clipper template into `00 System/Web Clipper`, and installs a CSS snippet under `.obsidian/snippets`. It never overwrites a differing file. Report `created`, `unchanged`, and `conflict` items exactly.

The base snippet styles the generated `[!web-header]` source banner and collapsed `[!toc]` document outline, and makes wide Markdown tables horizontally scrollable without clipping cells. Foldable learning objectives, checkpoints, quizzes, examples, and warnings use native Obsidian callouts produced by `web-to-obsidian`; the snippet does not require an extra community plugin for those interactions.

## Verify the outcome / Xác minh kết quả

After setup, verify all of the following:

1. The JSON template parses and imports into Obsidian Web Clipper.
2. A test clip lands in `00 Inbox/Web` with `type`, `status`, `source`, `clipped_at`, `tags`, and `cssclasses` properties.
3. Linter changes only the intended test note using the safe starter rules.
4. The `obsidian-clip-beautifier` CSS snippet affects notes with `cssclasses: web-clip` and leaves other notes unchanged.
5. MD Beautify, when requested, receives the already-clean Markdown and produces a presentation copy; it is not used as the canonical source formatter.

If any step cannot be verified, say which layer remains manual or unknown. Never claim the pipeline is fully active merely because its files were copied.

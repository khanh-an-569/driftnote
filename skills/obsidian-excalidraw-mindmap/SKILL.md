---
name: obsidian-excalidraw-mindmap
description: Use when a user asks to turn a captured Obsidian source note into a brainstorm-style Excalidraw mind map or diagram; dùng khi người dùng muốn biến một note nguồn đã capture trong Obsidian thành sơ đồ tư duy/brainstorm dạng Excalidraw.
---

# Obsidian Excalidraw Mindmap

Turn one already-captured source note into a polished, branching Excalidraw diagram without inventing or reinterpreting its ideas. / Biến một source note đã capture sẵn thành sơ đồ Excalidraw rẽ nhánh, đẹp mắt, không bịa hay diễn giải lại ý gốc.

## When to use / Khi nào dùng

Use on a note already created by `web-to-obsidian`, either right after capture (offered as an optional follow-up) or later against any existing captured note the user names explicitly. Never guess which note to use. / Dùng trên note đã được `web-to-obsidian` tạo ra, ngay sau khi capture hoặc sau này với note đã có tên rõ ràng. Không tự đoán note.

## Workflow / Quy trình

1. Ask the user two choices before building anything: `layout` (`radial` mindmap or left-to-right `tree`) and `long_content_strategy` (`link` back to the note, `condense` by splitting long paragraphs into further child nodes, or `manual` placeholders). Apply one strategy consistently for the whole diagram; never mix strategies within a single run. / Hỏi layout và cách xử lý đoạn dài trước, áp dụng nhất quán cho cả sơ đồ.
2. Read the source note and build an outline strictly from its existing heading/bullet structure — never invent ideas that are not in the note. Follow [references/outline-schema.md](references/outline-schema.md) exactly. / Đọc note, dựng outline đúng cấu trúc có sẵn, không bịa ý.
3. Write the outline to a JSON file and run `scripts/generate_excalidraw.py`. The script never reads note content itself and makes no content judgments — it only lays out, styles, and publishes exactly the outline it is given. Pass `--config-file` pointing at the vault's `web-to-obsidian.yaml` only when the user wants diagrams placed under its `excalidraw_output_dir` instead of next to the source note; otherwise omit it.
4. Report the script's JSON result (`status`, `path`, `linked_from_note`, `exported_to`, and `export_error` when the vault write succeeded but the standalone export copy failed) to the user, including the full path to the generated `.excalidraw` file.

From repository root / Từ repo root:

```powershell
python .\skills\obsidian-excalidraw-mindmap\scripts\generate_excalidraw.py `
  --outline-file "$env:TEMP\outline.json" `
  --vault "D:\Notes\Second Brain"
```

To also keep a portable copy outside the vault / Để giữ thêm bản standalone ngoài vault:

```powershell
python .\skills\obsidian-excalidraw-mindmap\scripts\generate_excalidraw.py `
  --outline-file "$env:TEMP\outline.json" `
  --vault "D:\Notes\Second Brain" `
  --export-dir "D:\Exports\Diagrams"
```

To overwrite a diagram already generated for that note, add `--regenerate`; only do this after re-verifying the outline against the current note content. / Để ghi đè sơ đồ đã có, thêm `--regenerate`; chỉ dùng khi outline đã được xác minh lại.

For an installed skill, resolve the directory containing this loaded `SKILL.md`, then run its `scripts/generate_excalidraw.py`; do not assume the repository layout.

## Quick Reference

| Situation / Tình huống | Action / Hành động |
|---|---|
| Note has clear headings/bullets | Use them as-is with action `full` |
| A bullet is a long paragraph | Split it into child nodes under `condense`, or use `link` |
| User hasn't picked layout/strategy yet | Ask before building the outline |
| Diagram already exists for this note | Do not overwrite without `--regenerate` |
| Vault not resolvable | Ask for `--vault`; never guess a personal path |

## Common Mistakes / Lỗi thường gặp

- Inventing ideas, summaries, or structure that is not already in the note.
- Mixing `link`/`condense`/`manual` strategies within the same diagram.
- Guessing the vault path or the note to diagram instead of resolving it explicitly.
- Overwriting an existing `.excalidraw` file without `--regenerate`.
- Touching the note's frontmatter or its `Ghi chú của tôi` section — the skill only appends a diagram embed link.
- Forgetting that the appended `![[<note>.excalidraw]]` embed only resolves in Obsidian when the community "Excalidraw" plugin is installed and enabled with legacy `.excalidraw` file support turned on. / Quên rằng liên kết nhúng `![[<note>.excalidraw]]` chỉ hiển thị được trong Obsidian khi plugin cộng đồng "Excalidraw" đã được cài, bật, và bật hỗ trợ file `.excalidraw` kiểu cũ (legacy).

Report the helper's status (`created`, `regenerated`, or `error`) plus the final `.excalidraw` path. / Báo trạng thái và đường dẫn file cuối cùng.

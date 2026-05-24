#!/usr/bin/env python3
"""读书笔记写入工具 — 本地 markdown 模式。

用法：
    python3 save-note.py << 'EOF'
    { "book": "书名", "content": "笔记内容" }
    EOF

环境变量：
    BOOKCHAT_NOTES_DIR  笔记保存目录（默认 ~/reading-notes/）
"""

import os, sys, json


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("错误：未收到 JSON 输入", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败：{e}", file=sys.stderr)
        sys.exit(1)

    book = data.get("book", "").strip()
    content = data.get("content", "").strip()
    if not book or not content:
        print("错误：book 和 content 字段不能为空", file=sys.stderr)
        sys.exit(1)

    notes_dir = os.environ.get("BOOKCHAT_NOTES_DIR", os.path.expanduser("~/reading-notes"))
    os.makedirs(notes_dir, exist_ok=True)
    safe_name = "".join(c for c in book if c not in r'\/:*?"<>|')
    path = os.path.join(notes_dir, f"{safe_name}.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(content + "\n\n---\n\n")
    print(f"✅ 已写入本地：{path}")


if __name__ == "__main__":
    main()

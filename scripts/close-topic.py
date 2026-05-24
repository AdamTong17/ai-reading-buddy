#!/usr/bin/env python3
"""
读书搭子收尾串联脚本

调用链：接收素材 JSON → build-card.py 校验+生成卡片 → 写 progress.json → 输出进度条

调用方式：
    python3 scripts/close-topic.py << 'EOF'
    {
      "book": "书名",
      "author": "作者",
      "topic": "当前主题名",
      "core_thread": "核心脉络...",
      "author_stance": ["立场1", "立场2"],
      "quotes": [{"text": "金句", "url": "weread://..."}],
      "user_said": "用户说过的原话（可为空字符串）",
      "note_title": "标题",
      "note_body": "正文150-250字..."
    }
    EOF

exit code：
    0 = 成功，stdout 包含卡片内容 + 进度条
    1 = 校验失败或写入失败，stderr 包含错误信息，模型应修正后重调
    2 = JSON 解析失败，stderr 包含精确行列号
"""

import subprocess
import sys
import os
import json
import argparse
from datetime import datetime, timezone, timedelta

# ── 工具函数 ─────────────────────────────────────────
def _extract_note(card_output: str) -> str:
    """从卡片输出中提取「📝 今日读书笔记」区块原文。"""
    lines = card_output.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("📝 今日读书笔记"):
            start = i
            break
    if start is None:
        return ""
    return "\n".join(lines[start:]).strip()


# ── 路径 ─────────────────────────────────────────────
ws = (os.environ.get("BOOKCHAT_WORKSPACE") or os.environ.get("OPENCLAW_WORKSPACE") or os.getcwd())
scripts_dir = os.path.dirname(os.path.abspath(__file__))
build_card_py = os.path.join(scripts_dir, "build-card.py")
progress_file = os.path.join(ws, "book-chat-progress.json")

# ── 参数解析 ─────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--attempt", type=int, default=1)
args, _ = parser.parse_known_args()
attempt = args.attempt

# ── Step 1：读取 stdin ────────────────────────────────
raw = sys.stdin.read().strip()
if not raw:
    print("错误：未收到卡片素材 JSON，请通过 heredoc stdin 传入", file=sys.stderr)
    sys.exit(1)

# ── Step 2：调 build-card.py 校验 + 生成卡片（透传 --attempt）──
result = subprocess.run(
    [sys.executable, build_card_py, f"--attempt={attempt}"],
    input=raw,
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    # 校验失败或 JSON 错误，原样输出错误信息让模型修正
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)

card_output = result.stdout.strip()

# ── Step 3：输出卡片（模型原样转发给用户）────────────────
print(card_output)

# ── Step 4：写 progress.json ─────────────────────────
try:
    data = json.loads(raw)
    book_key = f"{data['book']}-{data['author']}"
    topic_title = data.get("topic", "")

    # 读取现有进度文件（先读后写，禁止覆盖）
    if os.path.exists(progress_file):
        with open(progress_file, encoding="utf-8") as f:
            prog = json.load(f)
    else:
        prog = {"books": {}}

    book = prog["books"].get(book_key)
    if book:
        # 找到当前主题，更新状态
        for topic in book.get("map", []):
            if topic.get("title") == topic_title:
                topic["status"] = "done"
                topic["closingCard"] = card_output
                topic["topicNote"] = _extract_note(card_output)
                break

        # 更新会话元数据
        now_str = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        book["lastSession"] = now_str
        book["sessions"] = book.get("sessions", 0) + 1

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False, indent=2)

        # ── Step 5：输出进度条 ──────────────────────────
        status_icons = {"done": "✅", "partial": "🔁", "pending": "⏳"}
        done_count = sum(1 for t in book["map"] if t.get("status") == "done")
        total_count = len(book["map"])

        print(f"\n📖 《{data['book']}》· 进度 {done_count}/{total_count}")
        for t in book["map"]:
            icon = status_icons.get(t.get("status", "pending"), "⏳")
            print(f"{icon} {t['title']}")
        print("💡 读完全部模块可一键生成读书笔记文档。")

        # ── Step 6：全书完成检查 ──────────────────────────
        if all(t.get("status") == "done" for t in book["map"]):
            print("\n📚 所有主题都聊完了。要生成完整的读书笔记文档吗？（回复「是」生成，「否」跳过）")

    else:
        print(f"\n⚠️ 进度文件中未找到《{data['book']}》，进度条跳过。", file=sys.stderr)

except Exception as e:
    # 写入失败不阻断用户体验，卡片已输出
    print(f"\n⚠️ 进度保存失败：{e}，请手动检查 book-chat-progress.json", file=sys.stderr)

sys.exit(0)

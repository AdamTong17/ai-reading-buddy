#!/usr/bin/env python3
"""dialogLog 写入 + 定期复习触发器

用法：
    python3 append-log.py --book "书名" --topic "主题名" << 'EOF'
    {"ts":"2026-05-24T19:00:00+08:00","turn":1,"role":"assistant","content":"..."}
    EOF

输出：
    LOG_OK            — 写入成功，无需复习
    REVIEW_REQUIRED   — 写入成功，当前轮数为 5 的倍数，需要复习铁则
    exit 1 + stderr   — 写入失败
"""

import sys
import json
import argparse
import os
from datetime import datetime, timezone, timedelta

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "book-chat-progress.json")
PROGRESS_FILE = os.path.normpath(PROGRESS_FILE)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--book", required=True)
    parser.add_argument("--topic", required=True)
    args, _ = parser.parse_known_args()
    return args.book, args.topic


def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        print(f"进度文件不存在：{PROGRESS_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(data):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_topic(progress, book, topic):
    books = progress.get("books", {})
    if book not in books:
        print(f"书名未找到：{book}", file=sys.stderr)
        sys.exit(1)
    book_data = books[book]
    topics = book_data.get("topics", {})
    if topic not in topics:
        print(f"主题未找到：{topic}（书：{book}）", file=sys.stderr)
        sys.exit(1)
    return topics[topic]


def main():
    book, topic = parse_args()

    # 读 stdin
    raw = sys.stdin.read().strip()
    if not raw:
        print("stdin 为空，没有 log 可写入", file=sys.stderr)
        sys.exit(1)

    try:
        log_entry = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败：{e}", file=sys.stderr)
        sys.exit(1)

    # 校验必填字段
    for field in ("ts", "turn", "role", "content"):
        if field not in log_entry:
            print(f"log 缺少字段：{field}", file=sys.stderr)
            sys.exit(1)

    if log_entry["role"] not in ("user", "assistant"):
        print(f"role 必须是 user 或 assistant，当前：{log_entry['role']}", file=sys.stderr)
        sys.exit(1)

    # 读进度文件
    progress = load_progress()
    topic_data = find_topic(progress, book, topic)

    # 初始化 dialogLog
    if "dialogLog" not in topic_data:
        topic_data["dialogLog"] = []

    # append
    topic_data["dialogLog"].append(log_entry)
    turn_count = len(topic_data["dialogLog"])

    # 写回
    save_progress(progress)

    # 判断是否需要复习（每5条触发，assistant 写入时判断，避免 user+assistant 同轮触发两次）
    if log_entry["role"] == "assistant" and turn_count > 0 and (turn_count // 2) % 5 == 0 and turn_count >= 10:
        print("REVIEW_REQUIRED")
    else:
        print("LOG_OK")


if __name__ == "__main__":
    main()

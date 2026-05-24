#!/usr/bin/env python3
"""读书搭子精华卡片生成器 — JSON stdin → 校验 → 拼版 → stdout.

用法：
    python3 build-card.py [--attempt N] << 'EOF'
    { ...JSON... }
    EOF

--attempt N：防止无限重写循环。
    · N=1（默认）：校验通过后，stdout 末尾附写作要求，让模型判断是否重写
    · N≥2：校验通过后直接输出，不再要求重写
"""

import sys, json, argparse

# ── 卡片模板 ──────────────────────────────────────────
CARD_TMPL = """📖 《{book}》精华卡片

🔑 本次核心脉络
{core_thread}

📌 {author}的核心立场
{author_stance}
{quotes_block}{user_block}📝 今日读书笔记

**{note_title}**

{note_body}

——《{book}》读书笔记"""

QUOTE_TMPL = """📎 书中金句
{quote_lines}
"""

# ── 写作要求（校验失败和校验通过时均输出）──────────────
WRITING_REQUIREMENTS = """
── 精华卡片写作要求 ──────────────────────────────────────
core_thread（核心脉络）：
  · 2-3 句，≥ 80 字
  · 叙述本次对话的思维推进过程，不是标题或主题摘要
  · 示例：「从X出发，讨论了Y，最终在Z上产生分歧——作者认为...，但对话中提出了...」

author_stance（作者立场）：
  · 数组，≥ 2 条，每条 ≥ 20 字
  · 完整句子，用自己语言转述，不是标签式短语
  · 示例：「聂辉华认为条块结合不是设计缺陷，而是在信息不对称环境下演化出的均衡解」

quotes（书中金句）：
  · 每条必须有真实 URL（weread:// 或 https://），不能是「来源」「URL」等占位符
  · Weread 可用时 ≥ 3 条，不可用时 ≥ 2 条

note_body（读书笔记正文）：
  · 150-250 字，四个要求缺一不可：
    ① 贴近本次对话真实讨论过的观点，禁止捏造，禁止从「这本书讲的是」开始
    ② 有一处真实的摩擦感（书的观点和普遍经验的碰撞）
    ③ 如有真实 URL 的金句，可自然融入正文
    ④ 结尾一句说一件还没想清楚的事，不留开放性问题
  · 语气像发朋友圈，禁止出现「发现自己」「不禁思考」「值得深思」
────────────────────────────────────────────────────────"""

# 占位符关键词，URL 中含有这些词视为无效
URL_PLACEHOLDERS = {"来源", "url", "URL", "link", "链接", "source", "weread://...", "https://..."}

# ── 主流程 ──────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--attempt", type=int, default=1)
    args, _ = parser.parse_known_args()
    return args.attempt


def parse_stdin():
    """读 stdin 并解析 JSON。解析失败时打印精确位置后退出。"""
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        char = raw[e.pos] if e.pos < len(raw) else "<EOF>"
        print(
            f"JSON 解析失败 at line {e.lineno}, col {e.colno}: 字符 '{char}'",
            file=sys.stderr,
        )
        print(
            "可能原因：中文双引号与 JSON 结构引号冲突，请改用单书名号〈〉或直角引号「」",
            file=sys.stderr,
        )
        sys.exit(2)


def _is_placeholder_url(url: str) -> bool:
    """判断 URL 是否是占位符（无效）。"""
    if not url:
        return True
    url_stripped = url.strip()
    if url_stripped in URL_PLACEHOLDERS:
        return True
    if url_stripped.endswith("..."):
        return True
    return False


def validate(data):
    """逐字段校验，缺项或缺长度直接 exit 1（附写作要求）。"""
    errors = []

    # 必填字段非空
    for field in ("book", "author", "core_thread", "note_title", "note_body"):
        if not data.get(field, "").strip():
            errors.append(f"缺少 {field}")

    # core_thread 字数
    ct = data.get("core_thread", "")
    if ct and len(ct.strip()) < 80:
        errors.append(f"core_thread 不足 80 字（当前 {len(ct.strip())} 字）——需叙述思维推进过程，不是标题")

    # author_stance：支持字符串或数组
    stance = data.get("author_stance")
    if not stance:
        errors.append("缺少 author_stance")
    elif isinstance(stance, list):
        if len(stance) < 2:
            errors.append(f"author_stance 至少需要 2 条（当前 {len(stance)} 条）")
        else:
            short = [i for i, s in enumerate(stance) if len(s.strip()) < 20]
            if short:
                errors.append(
                    f"author_stance 第 {[i+1 for i in short]} 条不足 20 字——需完整句子，不是标签"
                )
    elif isinstance(stance, str):
        if not stance.strip():
            errors.append("缺少 author_stance")

    # note_title 长度
    nt = data.get("note_title", "")
    if nt and len(nt) > 10:
        errors.append(f"note_title 超过 10 字（{len(nt)} 字）")

    # note_body 长度
    nb = data.get("note_body", "")
    if nb:
        ln = len(nb)
        if ln < 150:
            errors.append(f"note_body 不足 150 字（{ln} 字）")
        if ln > 250:
            errors.append(f"note_body 超过 250 字（{ln} 字）")

    # quotes 格式 + URL 有效性
    quotes = data.get("quotes")
    if quotes is not None:
        if not isinstance(quotes, list):
            errors.append("quotes 必须是数组")
        else:
            for i, q in enumerate(quotes):
                if not isinstance(q, dict):
                    errors.append(f"quotes[{i}] 必须是对象")
                elif "text" not in q:
                    errors.append(f"quotes[{i}] 缺少 text")
                elif _is_placeholder_url(q.get("url", "")):
                    errors.append(
                        f"quotes[{i}] URL 无效（当前：「{q.get('url', '空')}」）——必须是真实的 weread:// 或 https:// 链接"
                    )

    if errors:
        print("[校验失败]", file=sys.stderr)
        for e in errors:
            print(f"  · {e}", file=sys.stderr)
        print(WRITING_REQUIREMENTS, file=sys.stderr)
        print("\n请修正以上字段后，以 --attempt <当前次数+1> 重新调用脚本。", file=sys.stderr)
        sys.exit(1)


def _format_stance(stance) -> str:
    """author_stance 支持字符串或数组，统一转为带「· 」前缀的多行字符串。"""
    if isinstance(stance, list):
        return "\n".join(f"· {s.strip()}" for s in stance if s.strip())
    return stance.strip() if stance else ""


def build_card(data):
    """拼卡片 markdown。"""
    quotes = data.get("quotes") or []
    if quotes:
        lines = []
        for q in quotes:
            url = q.get("url", "")
            if url and not _is_placeholder_url(url):
                lines.append(f"「{q['text']}」— [来源]({url})")
            else:
                lines.append(f"「{q['text']}」")
        quotes_block = QUOTE_TMPL.format(quote_lines="\n".join(lines)) + "\n"
    else:
        quotes_block = ""

    user_said = data.get("user_said", "").strip()
    user_block = f"🙋 你说\n> {user_said}\n\n" if user_said else ""

    return CARD_TMPL.format(
        book=data["book"],
        author=data["author"],
        core_thread=data["core_thread"].strip(),
        author_stance=_format_stance(data["author_stance"]),
        quotes_block=quotes_block,
        user_block=user_block,
        note_title=data["note_title"].strip(),
        note_body=data["note_body"].strip(),
    )


if __name__ == "__main__":
    attempt = parse_args()
    data = parse_stdin()
    validate(data)
    card = build_card(data)
    print(card)

    # attempt=1 时，附写作要求并请模型自判是否重写
    if attempt == 1:
        print(WRITING_REQUIREMENTS)
        print(
            "\n以上是本次卡片的写作要求。请对照检查当前内容是否达标：\n"
            "· 达标 → 原样输出卡片给用户（不含本段要求）\n"
            "· 未达标 → 重新收集素材，以 --attempt 2 重新调用脚本\n"
            "· 注意：--attempt 2 时脚本不再要求重写，直接输出。"
        )

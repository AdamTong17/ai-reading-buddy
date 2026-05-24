#!/usr/bin/env python3
"""
电子版获取脚本 — book-chat Step 0C

用法：
  python3 fetch_epub.py <书名> [url1] [url2] ...

  URL 可选：不传时脚本自动从内置候选源构造下载链接。

输出（stdout，AI 读取）：
  txt_ok:<path>       — 成功，book.txt 已生成
  not_found           — 所有 URL 都失败，进 fallback
  too_short           — 下载成功但文字不足1000字（扫描版/加密版）
  bad_zip             — epub 结构损坏且无法作为文本读取

工作流：
  1. AI 先用 web_search 找候选 URL（可选，不传则用内置候选）
  2. AI 把书名（和可选 URL）作为参数传给本脚本
  3. 脚本负责下载 → 判断类型 → 提取文字 → 写 book_<书名>.txt
  4. AI 根据输出决定分支
"""

import sys
import os
import subprocess
import zipfile
import re
import tempfile
import urllib.parse

WORKSPACE = os.environ.get("BOOK_CHAT_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
MIN_FILE_SIZE = 50_000   # 50K，小于此视为 403 页面或空响应
MIN_TEXT_LEN  = 1_000    # 1000字，小于此视为扫描版/加密版
TIMEOUT_SECS  = 25

# ────────────────────────────────────────────────
# 内置候选源：不依赖 AI 传 URL，自动构造下载链接
# ────────────────────────────────────────────────
def builtin_candidates(book_name: str) -> list:
    """根据书名构造内置候选 URL 列表，按优先级排序"""
    encoded = urllib.parse.quote(book_name)
    candidates = [
        # python123.io 四大名著资源（直连 txt，已验证可用）
        f"https://python123.io/resources/pye/{encoded}.txt",
        # tennessine/corpus GitHub raw（四大名著）
        f"https://raw.githubusercontent.com/tennessine/corpus/master/{book_name}.txt",
        # naosense/Yiya GitHub raw
        f"https://raw.githubusercontent.com/naosense/Yiya/master/book/{book_name}.txt",
        # 中国哲学书电子化计划（适合古典文学）
        f"https://ctext.org/export.pl?if=gb&filename={encoded}",
    ]
    return candidates


# ────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────
def clean_html(raw: str) -> str:
    """去掉 HTML 标签，保留可读文字"""
    text = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_name(book_name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "_", book_name)


def write_txt(book_name: str, text: str) -> str:
    """写入 workspace/book_<书名>.txt，返回路径。写入前做可读性校验，失败抛异常。"""
    # 可读性校验：检查文本中中文字符比例（针对中文书籍）
    # 取前2000字符，要求中文字符占比 >= 5%，且非控制字符占比 >= 60%
    sample = text[:2000]
    if len(sample) == 0:
        raise ValueError("内容为空")
    chinese_count = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff')
    non_control = sum(1 for c in sample if c >= ' ' or c in '\t\n\r')
    chinese_ratio = chinese_count / len(sample)
    readable_ratio = non_control / len(sample)
    if chinese_ratio < 0.05 or readable_ratio < 0.6:
        raise ValueError(
            f"可读性校验失败（中文占比 {chinese_ratio:.0%}，可读字符占比 {readable_ratio:.0%}），"
            f"疑似二进制或加密内容"
        )
    path = os.path.join(WORKSPACE, f"book_{safe_name(book_name)}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def try_download(url: str, out_path: str) -> bool:
    """下载到 out_path，成功且 >MIN_FILE_SIZE 返回 True"""
    try:
        result = subprocess.run(
            ["curl", "-L", "-s", "-o", out_path, url,
             "--max-time", str(TIMEOUT_SECS),
             "--user-agent", "Mozilla/5.0 (compatible; book-chat/1.0)"],
            capture_output=True,
            timeout=TIMEOUT_SECS + 5
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > MIN_FILE_SIZE:
            return True
        if os.path.exists(out_path):
            os.remove(out_path)
        return False
    except Exception:
        if os.path.exists(out_path):
            os.remove(out_path)
        return False


def detect_type(url: str, file_path: str) -> str:
    """
    判断文件类型：txt / epub / pdf / unknown
    优先看 URL 扩展名，再看文件头魔数。
    """
    url_lower = url.lower().split("?")[0]
    if url_lower.endswith(".txt"):
        return "txt"
    if url_lower.endswith(".pdf") or "pdf" in url_lower:
        return "pdf"
    if url_lower.endswith((".epub", ".zip")):
        return "epub"

    # 读文件头判断
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        if header[:4] == b"PK\x03\x04":
            return "epub"   # zip/epub 魔数
        if header[:4] == b"%PDF":
            return "pdf"
        # 尝试解码为 utf-8/gbk，成功则当文本
        with open(file_path, "rb") as f:
            raw = f.read(2000)
        for enc in ("utf-8", "gbk", "gb2312"):
            try:
                raw.decode(enc)
                return "txt"
            except Exception:
                continue
    except Exception:
        pass
    return "unknown"


# ────────────────────────────────────────────────
# 各类型处理
# ────────────────────────────────────────────────
def process_txt(file_path: str, book_name: str) -> str:
    """读取纯文本，写入 workspace"""
    for enc in ("utf-8", "gbk", "gb2312", "utf-8-sig"):
        try:
            with open(file_path, "r", encoding=enc, errors="ignore") as f:
                text = f.read()
            if len(text) >= MIN_TEXT_LEN:
                path = write_txt(book_name, text)  # 内部含可读性校验，失败抛 ValueError
                return f"txt_ok:{path}"
            else:
                return "too_short"
        except ValueError as e:
            sys.stderr.write(f"[fetch_epub] 可读性校验失败: {e}\n")
            return "bad_zip"
        except Exception:
            continue
    return "too_short"


def process_epub(file_path: str, book_name: str) -> str:
    """解压 epub，提取 HTML 文字"""
    try:
        z = zipfile.ZipFile(file_path)
    except zipfile.BadZipFile:
        # epub 解压失败，尝试作为纯文本读（有些 .epub URL 实际是 txt）
        result = process_txt(file_path, book_name)
        if result.startswith("txt_ok"):
            return result
        return "bad_zip"
    except Exception:
        return "bad_zip"

    html_files = sorted([
        n for n in z.namelist()
        if n.lower().endswith((".html", ".xhtml", ".htm"))
        and "toc" not in n.lower()
    ])
    if not html_files:
        html_files = [n for n in z.namelist() if n.lower().endswith(".xml")]

    texts = []
    for name in html_files:
        try:
            raw = z.read(name).decode("utf-8", errors="ignore")
            texts.append(clean_html(raw))
        except Exception:
            continue

    full_text = "\n\n".join(texts)
    if len(full_text) < MIN_TEXT_LEN:
        return "too_short"

    try:
        path = write_txt(book_name, full_text)  # 内部含可读性校验
    except ValueError as e:
        sys.stderr.write(f"[fetch_epub] 可读性校验失败: {e}\n")
        return "bad_zip"
    return f"txt_ok:{path}"


def process_pdf(file_path: str, book_name: str) -> str:
    """用 pdftotext 或 pdfplumber 提取"""
    txt_path = os.path.join(WORKSPACE, f"book_{safe_name(book_name)}.txt")
    # 尝试 pdftotext
    try:
        r = subprocess.run(
            ["pdftotext", file_path, txt_path],
            capture_output=True, timeout=30
        )
        if os.path.exists(txt_path) and os.path.getsize(txt_path) > MIN_TEXT_LEN:
            return f"txt_ok:{txt_path}"
    except Exception:
        pass
    # 尝试 pdfplumber
    try:
        import pdfplumber
        texts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
        full = "\n\n".join(texts)
        if len(full) >= MIN_TEXT_LEN:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full)
            return f"txt_ok:{txt_path}"
    except Exception:
        pass
    return "not_found"


# ────────────────────────────────────────────────
# 主流程
# ────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法: python3 fetch_epub.py <书名> [url1] [url2] ...")
        print("not_found")
        sys.exit(0)

    book_name = sys.argv[1]
    user_urls = sys.argv[2:]

    # 合并：用户传的 URL 优先，内置候选兜底
    all_urls = user_urls + [u for u in builtin_candidates(book_name) if u not in user_urls]

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, url in enumerate(all_urls):
            dl_path = os.path.join(tmpdir, f"book_{i}.bin")

            sys.stderr.write(f"[fetch_epub] 尝试下载 ({i+1}/{len(all_urls)}): {url}\n")

            ok = try_download(url, dl_path)
            if not ok:
                sys.stderr.write(f"[fetch_epub] 跳过（超时或文件过小）\n")
                continue

            size_k = os.path.getsize(dl_path) // 1024
            sys.stderr.write(f"[fetch_epub] 下载成功，大小 {size_k}K\n")

            ftype = detect_type(url, dl_path)
            sys.stderr.write(f"[fetch_epub] 文件类型: {ftype}\n")

            if ftype == "txt":
                result = process_txt(dl_path, book_name)
            elif ftype == "pdf":
                result = process_pdf(dl_path, book_name)
            elif ftype in ("epub", "unknown"):
                result = process_epub(dl_path, book_name)
            else:
                result = "bad_zip"

            sys.stderr.write(f"[fetch_epub] 结果: {result}\n")

            if result.startswith("txt_ok"):
                print(result)
                sys.exit(0)
            elif result in ("too_short", "bad_zip", "not_found"):
                sys.stderr.write(f"[fetch_epub] {result}，尝试下一个\n")
                continue

    print("not_found")


if __name__ == "__main__":
    main()

# 收尾：知识卡片 + 进度保存（参考手册）

> 本文档为 SKILL.md Stage 4 执行卡的补充说明。模型在收尾时按执行卡操作，不确定细节时按需查阅。

---

## Step 1：收集素材，调脚本生成卡片

⚠️ **禁止自己拼装卡片输出。卡片由脚本生成，没有脚本输出就没有卡片。**

### 1a. 收集素材

从本轮对话和搜索结果中提取以下字段：

| 字段 | 要求 |
|------|------|
| `core_thread` | 1-3句串起本次思维链条，叙述推进过程，不是罗列主题 |
| `author_stance` | 数组，≥ 2 条，用自己语言转述，不加引号，不装原文 |
| `quotes` | 数组，每条含 `text` 和 `url`；无真实 URL 的金句不放入；Weread 可用 ≥ 3 条，不可用 ≥ 2 条 |
| `user_said` | 用户说过的最有价值的原话，无则传空字符串 `""` |
| `note_title` | ≤ 10 字，有具体观点，不是「读了XX的感想」 |
| `note_body` | 150-250 字，四个要求（见下） |

**note_body 四个要求（缺一不可）：**
① 内容必须贴近本次对话真实讨论过的观点，禁止捏造场景或假故事，禁止从「这本书讲的是」或「作者认为」开始
② 必须有一处真实的摩擦——书的观点和普遍经验碰撞的那个点，不能只是认同，要有阻力感
③ 如果本次对话中引用过有真实 URL 的原文金句，可以自然融入正文
④ 结尾是一句话，说一个还没想清楚的事，不留开放性问题，不说「下次继续」
语气：像发朋友圈，不像读书报告；禁止出现「发现自己」「不禁思考」「值得深思」等 AI 常见词

### 1b. 组装 JSON，调用 close-topic.py

```bash
python3 scripts/close-topic.py --attempt 1 << 'EOF'
{
  "book": "<书名>",
  "author": "<作者>",
  "topic": "<当前主题名>",
  "core_thread": "<核心脉络>",
  "author_stance": ["<立场1>", "<立场2>"],
  "quotes": [{"text": "<金句>", "url": "<URL>"}],
  "user_said": "<用户原话，无则空字符串>",
  "note_title": "<标题>",
  "note_body": "<正文>"
}
EOF
```

### 1c. 处理脚本返回

| 返回 | 处理 |
|------|------|
| exit 0 | stdout 末尾含写作要求自检（--attempt 1 时）。判断：内容达标 → 原样输出卡片给用户；内容不足 → 重收素材以 --attempt 2 重调；--attempt 已为 2 → 直接输出，不再重写 |
| exit 1 | 读 stderr 错误信息，修正对应字段，重新调用脚本 |
| exit 2 | JSON 格式错误，按提示修正后重调 |

脚本已自动完成：卡片生成 + progress.json 写入 + 进度条输出 + 全书完成检查。**Step 2 不再需要单独写进度文件。**

---

## Step 2：确认进度已保存

close-topic.py 已自动写入 progress.json 并输出进度条。本步骤只需在脚本 exit 0 后，追加输出：

「📂 进度已保存，下次说『继续聊XX』可以接着来。」

**文件路径：** `{workspace}/book-chat-progress.json`

**文件格式：**
```json
{
  "books": {
    "[书名-作者]": {
      "title": "书名",
      "author": "作者",
      "edition": "",
      "editionNote": "",
      "type": "传记/方法论/文学",
      "mode": "对话模式",
      "totalTopics": 5,
      "summary": "Step2综述完整原文，首次写入后不覆盖",
      "knowledgeMap": "Step2知识地图完整markdown原文，首次写入后不覆盖",
      "searchCache": {
        "savedAt": "YYYY-MM-DD",
        "douban": { "reviews": [], "highlights": [] },
        "zhihu": [],
        "xhs": []
      },
      "map": [
        {
          "id": 1,
          "title": "主题名",
          "star": true,
          "status": "done",
          "closingCard": "精华卡片完整原文，closing-card Step1输出后立即写入",
          "dialogLog": [
            { "ts": "2026-04-21T02:10:00+08:00", "turn": 1, "role": "user", "content": "用户原话完整，不筛选" },
            { "ts": "2026-04-21T02:10:15+08:00", "turn": 1, "role": "assistant", "content": "AI 本轮回复完整原文" }
          ],
          "topicNote": "今日读书笔记完整原文，含标题和正文"
        },
        { "id": 2, "title": "主题名", "star": true, "status": "pending", "closingCard": "", "topicNote": "", "dialogLog": [] }
      ],
      "quotes": [
        { "date": "YYYY-MM-DD", "text": "书中引用原文", "url": "来源URL或空字符串" }
      ],
      "lastSession": "YYYY-MM-DD",
      "sessions": 1
    }
  }
}
```

**写入规则：**
- **先读后写（强制）**：写入前必须先读取现有 `book-chat-progress.json`，在原有 `books` 对象上更新当前书的数据，再整体写回。禁止直接用新对象覆盖整个文件（会丢失其他书的数据）。文件不存在时才新建。
- 用「书名-作者」作为唯一key，同一本书多次对话累积更新
- 主题状态：`pending`（未开始）/ `partial`（聊了一半）/ `done`（聊完）
- `summary`（首次写入，已有不覆盖）：从本次会话上下文提取综述原文，完整写入，不截断
- `knowledgeMap`（首次写入，已有不覆盖）：从本次会话上下文提取知识地图原文，完整写入
- 每次金句 append 到 `quotes`（保留历史，不覆盖）
- 更新 `lastSession` 日期，`sessions` +1

**进度条（写入完成后输出，格式固定，不可省略任何行）：**

```
📖 《{书名}》· 进度 {done数}/{总主题数}
{图标} {主题名}
...
💡 读完全部模块可一键生成读书笔记文档。
```

⚠️ 最后一行「💡 读完全部模块可一键生成读书笔记文档。」**必须输出，无论进度多少，不可省略。**

图例：✅ = done / 🔁 = partial / ⏳ = pending

---

## Step 3：全书完成确认

Step 2 写入完成后，检查当前书所有主题状态：

```python
all_done = all(t["status"] == "done" for t in book["map"])
```

若 `all_done = True`，在进度条后追加输出：

```
📚 所有主题都聊完了。要生成完整的读书笔记文档吗？（回复「是」生成，「否」跳过）
```

- 用户回「是」→ 执行 Step 4
- 用户回「否」或不回复 → 正常结束，不再追问

---

## Step 3.5：Weread Key 收尾引导

无论全书是否完成，在 Step 3 之后执行：

```python
import json, os
ws = (os.environ.get("BOOKCHAT_WORKSPACE") or
      os.environ.get("OPENCLAW_WORKSPACE") or
      os.getcwd())
with open(os.path.join(ws, "book-chat-progress.json")) as f:
    prog = json.load(f)

# 兼容旧格式：若 keyPrompted 为布尔值，视为 {onboarding: 该值, closing: false}
kp = prog.get("keyPrompted", {})
if isinstance(kp, bool):
    kp = {"onboarding": kp, "closing": False}
    prog["keyPrompted"] = kp

# Weread Key 可用性检查
weread_available = bool(
    os.environ.get("WEREAD_API_KEY") or
    os.path.exists(os.path.expanduser("~/.weread_key"))
)

if not kp.get("closing", False) and not weread_available:
    print("对了——微信读书 Key 能让下次直接引用原文划线，体验更好。有的话发给我，没有也没关系。")
    kp["closing"] = True
    prog["keyPrompted"] = kp
    with open(os.path.join(ws, "book-chat-progress.json"), "w") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)
```

- `closing=false` 且 Weread 不可用 → 追加引导文案
- `closing=true` 或 Weread 已可用 → 静默跳过

---

## Step 4：文档写入（用户确认「是」后执行）

将精华卡片内容保存为本地 markdown 文件。

```bash
python3 scripts/save-note.py << 'EOF'
{ "book": "书名", "content": "笔记正文 markdown" }
EOF
```

脚本输出 `✅ 已写入本地：~/reading-notes/<书名>.md` 即成功。

环境变量 `BOOKCHAT_NOTES_DIR` 可自定义保存目录（默认 `~/reading-notes/`）。

---

## 续读逻辑（用户说「继续聊XX」）

1. 读取进度文件，找到对应书目
2. 告知上次进度，区分状态：
   - `partial`：「上次聊到一半，要继续还是跳过？」（优先展示）
   - `pending`：「还没聊过」
   - `done`：「已聊完」
3. 展示精简地图（✅已聊完 / 🔁聊了一半 / ⏳未聊）
4. 搜索不跳过，每个新主题进入前正常执行实时搜索

# 微信读书 API 集成手册

## 端点与鉴权

```
POST https://i.weread.qq.com/api/agent/gateway
Authorization: Bearer {WEREAD_API_KEY}
Content-Type: application/json
```

## 调用规范

1. 参数平铺在 body 顶层，跟 `api_name`、`skill_version` 同级
2. 每次请求必须带 `"skill_version": "1.0.3"`
3. bookId 为 string 类型
4. newRating 为 0-100 分制
5. 阅读时长单位为秒，展示时转为"X小时Y分钟"
6. 回包检查 `upgrade_info`，存在时静默升级

## Step 1 采集接口

### 搜书: /store/search
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name":"/store/search","keyword":"乔布斯传","scope":10,"count":5,"skill_version":"1.0.3"}'
```
返回: `results[].bookId`, `title`, `author`, `newRating`

### 书籍信息: /book/info
```bash
-d '{"api_name":"/book/info","bookId":"635722","skill_version":"1.0.3"}'
```
返回: `title`, `author`, `intro`, `newRating`, `newRatingCount`, `category`

### 章节目录: /book/chapterinfo
```bash
-d '{"api_name":"/book/chapterinfo","bookId":"635722","skill_version":"1.0.3"}'
```
返回: `chapters[].chapterUid`, `title`, `wordCount`

### 热门划线: /book/bestbookmarks
```bash
# 全书
-d '{"api_name":"/book/bestbookmarks","bookId":"635722","count":20,"skill_version":"1.0.3"}'
# 按章节
-d '{"api_name":"/book/bestbookmarks","bookId":"635722","chapterUid":100,"count":20,"skill_version":"1.0.3"}'
```
返回: `items[].markText`, `chapterUid`, `range`, `totalCount`（划线人数）

### 用户划线: /book/bookmarklist
```bash
-d '{"api_name":"/book/bookmarklist","bookId":"635722","skill_version":"1.0.3"}'
```
返回: `items[].markText`, `chapterUid`, `createTime`

### 用户想法: /review/list/mine
```bash
-d '{"api_name":"/review/list/mine","bookid":"635722","count":100,"skill_version":"1.0.3"}'
```
⚠️ bookid 为必填，参数名大小写敏感（小写 d）

### 社区书评: /review/list
```bash
-d '{"api_name":"/review/list","bookId":"635722","reviewListType":0,"count":10,"skill_version":"1.0.3"}'
```
返回: `reviews[].reviewId`, `content`, `user.name`, `star`

## Step 3 接口

### 划线下讨论: /book/readreviews
```bash
-d '{"api_name":"/book/readreviews","bookId":"441428","chapterUid":28,"reviews":[{"range":"3489-3709","count":10}],"skill_version":"1.0.3"}'
```
返回: `reviews[].content`, `user.name`。⚠️ `reviews` 是必填数组，`range` 和 `count` 必须嵌套在数组元素内，不能平铺顶层。chapterUid 和 range 来自 bestbookmarks 返回

### 话题验证: /store/search?scope=12
```bash
-d '{"api_name":"/store/search","keyword":"木匠","scope":12,"bookId":"635722","count":5,"skill_version":"1.0.3"}'
```
返回: `results[].scopeCount`（命中数）。⚠️ 只返回计数，不返回文本。仅做关键词/短句匹配，非语义搜索。

## 增强接口（收尾/个性化）

| 接口 | 请求 | 用途 |
|------|------|------|
| `/shelf/sync` | `{}` | 书架，按 `books.length + albums.length + (mp?1:0)` 计算总数 |
| `/user/notebooks` | `{count:100}` | 笔记总览（按书分组，含划线数和想法数） |
| `/book/getprogress` | `{bookId}` | 阅读进度（百分比、阅读时长） |
| `/book/recommend` | `{count:5}` | 基于阅读史的个性化推荐 |
| `/book/similar` | `{bookId, count:5}` | 跟当前书相似的推荐 |

## 兜底策略

每个 Weread 接口独立成败：

| 失败接口 | 兜底 |
|---------|------|
| `/store/search` 找不到 | 全局降级传统模式 |
| `/book/info` | 豆瓣搜索结果中的书籍信息 |
| `/book/chapterinfo` | 搜索片段中推测目录 |
| `/book/bestbookmarks` | 原「三平台扒划线句」 |
| `/book/bookmarklist` | 无兜底（用户没笔记是正常的） |
| `/review/list/mine` | 无兜底 |
| `/review/list` | 无兜底（豆瓣书评是独立另一路） |


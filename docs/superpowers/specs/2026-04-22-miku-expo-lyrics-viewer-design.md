# Miku Expo 演唱会滚动歌词网页 — 设计文档

**日期**：2026-04-22
**演出日期**：2026-04-23（明天）
**使用者**：一人（项目作者本人）
**使用设备**：iPhone / Safari

## 目标

在 Miku Expo 演唱会现场，作者打开网页（离线），跟随舞台演唱实时显示**日中双语滚动歌词**，解决日语听不懂/跟不上的问题。

## 使用场景

1. 开演前，作者把网页在 iPhone Safari 中打开（或"添加到主屏幕"）
2. 主界面显示 34 首歌的 setlist（Miku Expo 顺序）
3. 每首歌开始时：
   - 点进该首歌的歌词页
   - 歌真的唱到第一句时，点 **"开始"** 按钮，歌词按时间戳自动滚动
   - 当前行居中高亮（日文大字，中文小字对照），前后行灰显
   - 现场如果和舞台节奏对不齐，用 `−0.5s` / `+0.5s` 按钮调整
4. 一首结束，回 setlist 选下一首
5. 屏幕全程保持常亮（Wake Lock）

## 非目标（砍掉）

- 音频播放（现场听舞台）
- 登录 / 云同步 / 多用户
- 深色浅色切换（固定黑底）
- 进度条拖动、跳到任意行
- 复杂的歌词编辑 UI
- 罗马音、假名注音

## 架构

**单页静态 HTML，无后端，无构建工具，无框架。**

```
miku/
├── index.html              # 唯一页面（setlist + 歌词两种视图）
├── app.js                  # 所有逻辑（~200 行）
├── styles.css              # 样式
├── data/
│   ├── setlist.json        # 歌单元数据（顺序、标题、艺人、有无时间戳）
│   └── songs/
│       ├── 01-teo.json     # 每首歌一个文件
│       ├── 02-kimagure-mercy.json
│       └── ...
└── scripts/
    └── fetch_lyrics.py     # 批量从网易云抓歌词的脚本（一次性工具）
```

**为什么这样**：
- 单 HTML 打开即用，明天出问题最容易调试
- 每首歌独立 JSON，某首坏了不影响其他
- 纯静态，可以从本地文件系统直接打开，或丢到任何静态托管（GitHub Pages / Netlify）上

## 数据格式

**setlist.json**：
```json
{
  "concert": "Miku Expo 2026",
  "songs": [
    {"id": "01-teo", "title": "テオ", "artist": "Omoi ft. 初音ミク", "mode": "timed"},
    {"id": "02-kimagure-mercy", "title": "気まぐれメルシィ", "artist": "shizuko", "mode": "manual"}
  ]
}
```
`mode`:
- `"timed"` — 有时间戳，自动滚动
- `"manual"` — 无时间戳，手动点下一句

**songs/XX.json**：
```json
{
  "id": "01-teo",
  "title": "テオ",
  "artist": "Omoi ft. 初音ミク",
  "mode": "timed",
  "lines": [
    {"t": 22.42, "ja": "考える", "zh": "思考着"},
    {"t": 23.68, "ja": "このままいつまで 隠しておけるかな", "zh": "能够像这样 隐藏到何时呢"}
  ]
}
```
- `t` 单位秒（相对于歌曲开头，即 `"开始"` 按钮被点击的时刻）
- `manual` 模式下的 JSON 同样结构，但 `t` 字段缺省

## UI 组件

### 1. Setlist 视图
- 黑底
- 每行：序号、标题（日文大字）、艺人（小字）
- 右侧小图标表示 `timed` / `manual` 模式
- 点击一行 → 进入歌词视图

### 2. 歌词视图
- 顶部：歌名 + 返回按钮
- 中央：滚动歌词区
  - 当前行高亮（放大 1.2x，白色）
  - 前 2 行 + 后 4 行灰显（透明度 0.4）
  - 日文一行 + 紧随中文一行（中文字号 ~70%）
- 底部控制栏：
  - **开始 / 暂停 / 重置** 主按钮
  - `−0.5s` / `+0.5s` 微调
  - `manual` 模式下：大号 **下一句** 按钮占满底部

### 3. 字体与尺寸
- 日文：`-apple-system, "Hiragino Sans", "Yu Gothic", sans-serif`，当前行 ~28pt
- 中文：同字族，当前行 ~18pt
- 行距宽松（`line-height: 1.6`）——演唱会昏暗环境下易读

## 状态管理

**每首歌的运行时状态（不持久化，换歌即重置）**：
- `isPlaying: bool` — 是否已点"开始"
- `startTime: ms` — 点击"开始"时的 `performance.now()`
- `offset: seconds` — 手动微调累计值
- `currentLineIdx: int` — 当前高亮行索引
- `manualIdx: int` — manual 模式下的进度

**当前时间计算**：`(now() - startTime) / 1000 + offset`
**当前行**：最后一个 `t <= 当前时间` 的行

## 歌词采集（一次性准备工作）

`scripts/fetch_lyrics.py`：
1. 读 `setlist.json` 里每首歌的 title + artist
2. 调网易云搜索 API `https://music.163.com/api/search/get?s=...&type=1`
3. 选第一个匹配（或多个候选人工挑选）→ 拿 `songId`
4. 调 `https://music.163.com/api/song/lyric?id=XXX&lv=1&kv=1&tv=-1`
5. 解析 `lrc.lyric`（日文）和 `tlyric.lyric`（中文）
6. 按时间戳合并，输出 `data/songs/XX.json`
7. 没有时间戳或网易云没有的歌 → 生成 `mode: "manual"` 的 JSON（只有文本，无时间戳），日文来自 `lrc.lyric`（有些歌只有日文无中文），中文可后续人工补

**兜底**：如果某首歌网易云完全没有，记录到日志，人工处理（粘贴日文 + 中文纯文本）。

## 关键技术点

**Wake Lock**：
```js
const wakeLock = await navigator.wakeLock.request('screen');
```
iOS 16.4+ Safari 支持。进入歌词视图时请求，返回 setlist 时释放。

**滚动锚定**：
- 当前行 `scrollIntoView({block: 'center', behavior: 'smooth'})`
- 或 flex 布局 + `transform: translateY(...)` 居中

**离线**：纯静态文件，iPhone Safari 打开一次后用"添加到主屏幕"，下次无网也能用。

## 测试计划

今晚完成后，在作者 iPhone 上：
1. 打开网页，检查 setlist 显示正常
2. 选一首 `timed` 歌，点开始，观察歌词是否按时间滚动
3. 测试 `±0.5s` 微调
4. 测试 manual 模式的"下一句"按钮
5. 测试屏幕常亮（静置 1 分钟不熄屏）
6. 测试从主屏幕图标打开是否离线可用

## 交付里程碑（今晚）

1. **骨架**：HTML + JS + CSS + 空的 setlist.json（~1h）
2. **抓歌词脚本**：跑通 Teo + Kimagure Mercy 两首试点（~1h）
3. **批量跑 34 首**：并发抓所有歌词，人工校验 mode=manual 的降级情况（~1h）
4. **iPhone 端联调**：字体、滚动、Wake Lock、离线（~1h）

目标：**今晚 4 小时内作者拿到可用网页**。

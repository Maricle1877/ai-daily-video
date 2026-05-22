# AI Daily Video 🍮

从 [AI HOT](https://aihot.virxact.com) 拉取每日 AI 资讯，自动生成带配音的竖屏短视频（1080×1920，9:16）。

**适用于任何 AI Agent** — Claude Code、Cursor、WorkBuddy、GitHub Copilot 等均可使用。

---

## 快速开始

### 1. 安装依赖

```bash
# Python 3.10+ 必需
pip install playwright edge-tts imageio-ffmpeg beautifulsoup4
python -m playwright install chromium
```

### 2. 拉取 AI 日报数据

```bash
# 从 AI HOT 获取今日日报
curl -s "https://aihot.virxact.com/api/public/daily" -H "User-Agent: Mozilla/5.0 aihot-skill/0.2.0" > daily_data.json
```

### 3. 生成 HTML 动画页

用 `assets/template.html` 模板将数据填充为动画页面：

```bash
# 使用你喜欢的脚本语言填充模板
# 关键步骤：
#   1. 替换 {{DATE}} → 日报日期
#   2. 替换 {{DATE_DOT}} → 日期用 . 分隔
#   3. 替换 {{SECTIONS}} → 所有版块和条目 HTML
# 详见下方"模板填充规则"
```

### 4. 生成配音视频（一键）

```bash
python scripts/add_voiceover.py ai-daily-YYYY-MM-DD.html AI日报-YYYY-MM-DD-配音版.mp4
```

> **脚本会自动完成**：生成 TTS → 调整场景时长 → 录制视频 → 合成配音。总时长约 3-5 分钟。

---

## 与 AI Agent 配合使用

### 在 Agent 对话中直接调用

大多数 AI Agent 支持执行 Python 脚本。你可以将以下指令告诉 Agent：

> "用 ai-daily-video 工具生成今天的 AI 日报视频：
> 1. 从 aihot.virxact.com 拉取日报 JSON 数据
> 2. 用 assets/template.html 生成 HTML 动画页
> 3. 运行 `python scripts/add_voiceover.py <html_file> <output.mp4>`"

### WorkBuddy 用户

该技能已预配置为 WorkBuddy Skill，存放在 `~/.workbuddy/skills/ai-daily-video/`。
WorkBuddy 用户可直接触发：`"生成 AI 日报视频"` 或 `"AI daily video"`。

---

## 工作流详解

### 数据源

使用 [AI HOT](https://aihot.virxact.com) 的公开 API（无需 Token）：

| 接口 | 用途 |
|------|------|
| `GET /api/public/daily` | 最新日报 |
| `GET /api/public/daily/{YYYY-MM-DD}` | 指定日期日报 |
| `GET /api/public/items?mode=selected&take=50` | 精选条目 |

> 注意：所有 API 调用需携带浏览器 User-Agent 头。

### 模板填充规则

**关键 class 名**（配音脚本依赖这些 class 解析文本）：

| Class | 用途 | 配音 |
|-------|------|------|
| `.scene-intro` | 开场场景 | ✅ 配音"一日AI简报" |
| `.scene-section` | 版块标题场景 | ❌ |
| `.scene-item` | 新闻条目场景 | ✅ |
| `.item-summary` | 摘要文字 | ✅ 截断 45 字 |
| `.item-highlight` | 亮点文字 | ✅ 截断 30 字 |
| `.item-title` / `.item-number` / `.item-source` / `.item-tag` | 标题/编号/来源/标签 | ❌ |
| `.scene-outro` | 结尾场景 | ❌ |

**data-duration 初始值**（配音脚本会自动调整）：

| 场景 | 初始值 |
|------|--------|
| intro | 4000ms（4秒） |
| section-title | 2500ms（2.5秒） |
| item | 4500ms（4.5秒） |
| outro | 3000ms（3秒） |

**section 图标映射**：

| 版块标签 | 图标 |
|---------|------|
| 模型发布/更新 | 🧠 |
| 产品发布/更新 | 🚀 |
| 行业动态 | 📡 |
| 论文研究 | 📄 |
| 技巧与观点 | 💡 |

### 配音方案

- **语音引擎**: edge-tts（微软 Edge TTS，免费）
- **默认语音**: `zh-CN-YunyangNeural`（男声，专业新闻）
- **配音范围**: 仅开场"一日AI简报" + 条目的摘要和亮点
- **文本截断**:
  - Summary 截断到 **45 字**
  - Highlight 截断到 **30 字**
  - 按句子边界（句号、感叹号、问号、逗号）截断，不从中断词
- **场景时长**: 自动适配配音时长 + 1.8 秒缓冲

---

## 脚本参考

### `scripts/add_voiceover.py`

```
python scripts/add_voiceover.py <html_file> [output.mp4]
```

自动完成：TTS 生成 → HTML 时长调整 → Playwright 录制 → ffmpeg 合成。

### `scripts/record_video.py`

```
python scripts/record_video.py <html_file> [output.mp4]
```

仅录制无声视频，用于预览动画效果。

---

## 技术参数

| 参数 | 值 |
|------|-----|
| 视频分辨率 | 1080×1920 (9:16 竖屏) |
| 帧率 | 30fps |
| 编码 | H.264 (libx264) + AAC |
| 像素格式 | yuv420p |
| 录制引擎 | Playwright (Chromium headless) |
| 配音引擎 | edge-tts (微软 Edge TTS) |
| 总时长 | 通常 3-5 分钟（取决于条目数） |

---

## 故障排查

### 视频只有左上角小画面

视频录制时 viewport 必须设为 1080×1920。检查 `record_video.py`：

```python
context = browser.new_context(
    viewport={"width": 1080, "height": 1920},
    record_video_size={"width": 1080, "height": 1920}
)
```

### 配音时间过长

默认会截断文本。如不希望截断，可修改 `add_voiceover.py` 中的
`truncate_to_sentence()` 调用，增大截断字数或直接传入完整文本。

### edge-tts 安装失败

```bash
pip install edge-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## License

MIT

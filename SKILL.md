---
name: ai-daily-video
description: "AI 日报视频生成技能。从 aihot.virxact.com 拉取 AI 日报数据，自动生成带配音的竖屏短视频（1080×1920，9:16，适配抖音/视频号）。触发场景：用户说\"生成 AI 日报视频\"、\"做 AI 日报视频\"、\"AI 日报视频带配音\"、\"把今天的 AI 日报做成视频\"、\"AI daily video\"、\"make AI daily video\"等。"
agent_created: true
---

# AI Daily Video Skill

从 aihot.virxact.com 拉取 AI 日报数据，自动生成带配音的竖屏短视频（1080×1920，9:16）。

## 依赖检查

开始前必须确认以下依赖已安装：

| 依赖 | 检查方式 | 安装命令 |
|------|---------|---------|
| Python 3.10+ | `python --version` | 用户自行安装 |
| playwright | `python -c "import playwright"` | `pip install playwright && python -m playwright install chromium` |
| edge-tts | `python -c "import edge_tts"` | `pip install edge-tts` |
| beautifulsoup4 | `python -c "import bs4"` | `pip install beautifulsoup4` |
| ffmpeg | `ffmpeg -version` | 见下方 ffmpeg 安装说明 |

### ffmpeg 安装（Windows）

检查 `imageio-ffmpeg` 包是否提供 ffmpeg：
```bash
python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
```
如果可用，直接用该路径。否则需单独安装 ffmpeg 并加入 PATH。
`scripts/record_video.py` 和 `scripts/add_voiceover.py` 会自动尝试 `imageio_ffmpeg`。

### 依赖缺失处理

**如果任何依赖缺失，必须先通知用户，不要自行决定安装。** 向用户说明缺少什么、怎么安装，等待用户确认后再继续。

---

## 完整工作流（6 步）

### Step 1: 拉取 AI 日报数据

**必须加载 aihot skill**（`Skill` tool, command=`aihot`）来获取数据。不要用 curl 直接调 API。

调用方式：让 aihot skill 拉取今日日报（`/api/public/daily`）。

aihot 返回的数据结构：
```json
{
  "date": "2026-05-22",
  "lead": { "title": "...", "leadParagraph": "..." },
  "sections": [
    {
      "label": "模型发布/更新",
      "items": [
        {
          "title": "标题",
          "summary": "摘要（需要配音）",
          "highlight": "亮点（需要配音，可选）",
          "sourceName": "来源名称",
          "sourceUrl": "https://..."
        }
      ]
    }
  ],
  "flashes": [...]
}
```

### Step 2: 生成 HTML 动画页面

**读取 `assets/template.html`** 作为模板，将数据填入，生成完整的 HTML 文件。

**HTML 文件命名**：`ai-daily-YYYY-MM-DD.html`（保存在当前工作区根目录）

**填入规则**：

1. `{{DATE}}` → 日报日期（如 `2026-05-22`）
2. `{{DATE_DOT}}` → 日期用 `.` 分隔（如 `2026.05.22`）
3. `{{SECTIONS}}` → 所有版块和新闻条目的 HTML 内容

**`{{SECTIONS}}` 内容结构**（按此顺序生成）：

```
对于每个 section（版块）：
  → 生成一个 .scene.scene-section 场景（版块标题页）
  → 对该 section 的每个 item：
      → 生成一个 .scene.scene-item 场景（新闻条目页）

最后：
  → .scene.scene-outro 场景（结尾页，template 已有）
```

**关键 class 名**（必须与 CSS 一致，配音解析依赖这些 class）：
- `.scene-intro` - 开场场景（**需要配音**：`一日AI简报`）
- `.scene-section` - 版块标题场景
- `.scene-item` - 新闻条目场景（**需要配音**）
- `.scene-outro` - 结尾场景
- `.item-summary` - 摘要文字（**需要配音**）
- `.item-highlight` - 亮点文字（**需要配音**）
- `.item-title` - 标题（不配音）
- `.item-number` - 编号（不配音）
- `.item-source` - 来源（不配音）
- `.item-tag` - 标签（不配音）

**`data-duration` 初始值**（Step 3 会被配音脚本自动调整）：
- intro: `4000`（4秒，含"一日AI简报"配音缓冲）
- section-title: `2500`（2.5秒）
- item: `4500`（4.5秒，Step 3 会根据配音时长自动延长）
- outro: `3000`（3秒）

**section 图标映射**（用在 `.section-icon`）：
- `模型发布/更新` → `🧠`
- `产品发布/更新` → `🚀`
- `行业动态` → `📡`
- `论文研究` → `📄`
- `技巧与观点` → `💡`

**item 标签 class 映射**：
- `模型发布` → `tag-models`
- `产品发布` → `tag-products`
- `行业动态` → `tag-industry`
- `论文研究` → `tag-paper`
- `技巧与观点` → `tag-tip`

### Step 3: （可选）Playwright 录制无声视频预览

**此步可选**。Step 4 的 `add_voiceover.py` 会自动重新录制视频，如果你想先预览无声版再决定是否继续，可以运行此步。

运行 `scripts/record_video.py`：

```bash
python <skill_dir>/scripts/record_video.py <html_file> [output_mp4]
```

- `skill_dir`: 本 skill 的目录路径（`C:/Users/Lenovo/.workbuddy/skills/ai-daily-video/`）
- `html_file`: Step 2 生成的 HTML 文件
- `output_mp4`: 输出无声视频路径（如 `AI日报-2026-05-22.mp4`），可选，默认同名替换 `.html` 为 `.mp4`

脚本行为：
1. 启动 headless Chromium
2. 打开 HTML 文件
3. 根据 `data-duration` 计算总时长，等待动画完成
4. Playwright 自动录制 WebM 视频到临时目录
5. 用 ffmpeg 将 WebM 转码为 H.264 MP4
6. 输出 MP4 路径

**检查输出**：用 `preview_url` 预览视频，确认画面全屏（1080×1920）而非左上角小画面。

### Step 4: edge-tts 生成配音并合成

运行 `scripts/add_voiceover.py`：

```bash
python <skill_dir>/scripts/add_voiceover.py <html_file> [output_mp4] [--voice zh-CN-YunyangNeural]
```

- `html_file`: Step 2 生成的 HTML 文件（用于解析配音文本和调整时长）
- `output_mp4`: 最终带配音视频路径（如 `AI日报-2026-05-22-配音版.mp4`），可选，默认同名替换 `.html` 为 `-配音版.mp4`
- `--voice`: 可选，TTS 语音（默认 `zh-CN-YunyangNeural`）

脚本自动执行：
1. 从 HTML 解析 `.scene-intro`（配音"一日AI简报"）、`.item-summary` + `.item-highlight` 文本（仅这些需要配音）
2. **内容过滤**：过滤"以下是一些""来看看""作品展示"等诱导性引导短语。同时检查摘要是否包含核心动作词（发布/推出/开源等），缺失则用标题兜底配音，确保听完能知道"发生了什么"
3. **自动截断**：summary 按句子边界截断到 45 字，highlight 按句子边界截断到 30 字（避免说话断一半）
4. 用 edge-tts 逐段生成 mp3 文件（临时目录）
5. 测量每段配音时长
6. 修改 HTML 的 `data-duration`（使场景停留 = 配音时长 + 1.8秒余量）
7. 用调整后的 HTML 重新录制视频（内部调用 Playwright）
8. 用 ffmpeg 将所有配音按时间轴混入视频音轨
9. 输出最终 MP4

**注意**：`add_voiceover.py` 会自动调用 `record_video.py` 的逻辑重新录制视频，不需要先手动运行 Step 3。但如果你想先预览无声版，也可以先运行 Step 3。

### Step 5: 预览与交付

用 `preview_url` 工具预览最终视频。

告诉用户：
- 文件路径
- 视频参数（分辨率、时长、大小）
- 配音语音和覆盖范围
- 建议：可换女声（`zh-CN-XiaoxiaoNeural`）或调整语速

### Step 6: 清理（可选）

保留文件：
- `ai-daily-YYYY-MM-DD.html`（源文件，可重新生成视频）
- `AI日报-YYYY-MM-DD-配音版.mp4`（最终视频）

可删除：
- `AI日报-YYYY-MM-DD.mp4`（无声版，已被配音版替代）
- `AI日报-YYYY-MM-DD_adjusted.mp4`（临时重新录制版）
- `ai-daily-YYYY-MM-DD_adjusted.html`（临时调整时长版）

---

## 文件命名规范

| 文件 | 命名规则 | 说明 |
|------|---------|------|
| HTML | `ai-daily-YYYY-MM-DD.html` | 动画页面源文件 |
| 无声视频 | `AI日报-YYYY-MM-DD.mp4` | Playwright 录制的无声版 |
| 配音视频 | `AI日报-YYYY-MM-DD-配音版.mp4` | 最终带配音版本 |
| 调整后HTML | `ai-daily-YYYY-MM-DD_adjusted.html` | 临时文件（时长已调整）|
| 重录视频 | `AI日报-YYYY-MM-DD_adjusted.mp4` | 临时文件 |

所有文件保存在当前工作区根目录。

---

## 故障排查

### 视频画面只在左上角（小画面）

**原因**：viewport 设置错误。必须是 `viewport={width:1080, height:1920}`，不能用 `device_scale_factor`。

**修复**：检查 `scripts/record_video.py` 第 ~52 行，确保是：
```python
context = browser.new_context(
    viewport={"width": 1080, "height": 1920},
    record_video_dir=tmp_dir,
    record_video_size={"width": 1080, "height": 1920}
)
```

### 配音与画面不同步

**原因**：场景 `data-duration` 没有根据配音时长调整，或 ffmpeg 滤镜时间轴计算错误。

**修复**：检查 `add_voiceover.py` 的 `build_audio_track` 函数，确认用 `scene["start_ms"]` 计算延迟时间。

### edge-tts 安装失败

**现象**：`pip install edge-tts` 报错。

**处理**：通知用户手动安装，或尝试：`pip install edge-tts -i https://pypi.tuna.tsinghua.edu.cn/simple`

### ffmpeg 找不到

**现象**：脚本报 `ffmpeg executable not found` 或 `imageio_ffmpeg` 导入失败。

**处理**：
1. 先试 `pip install imageio-ffmpeg`
2. 若还不行，手动安装 ffmpeg 并加入 PATH
3. 或在脚本中硬编码 ffmpeg 路径

### beautifulsoup4 缺失

**现象**：`ImportError: No module named 'bs4'`

**处理**：`pip install beautifulsoup4`

---

## 可配置项

用户可能会要求修改以下配置，应根据要求调整：

| 配置项 | 默认值 | 修改位置 |
|--------|-------|---------|
| 配音语音 | `zh-CN-YunyangNeural`（男声新闻） | `add_voiceover.py` 的 `--voice` 参数或脚本内 `VOICE` 变量 |
| 视频分辨率 | `1080×1920` | `record_video.py` 的 viewport 和 `template.html` 的 body 尺寸 |
| 帧率 | `30fps` | `record_video.py` 的 ffmpeg 参数（需加 `-r 30`） |
| 场景切换动画 | `fade` | `template.html` 的 CSS `.scene` transition |
| 配音延迟 | `0.8s`（场景切换后多久出声） | `add_voiceover.py` 的 `delay_ms = current_time + 800` |
| 场景余量 | `1.8s`（配音结束后画面多停留） | `add_voiceover.py` 的 `int((voice_sec + 1.8) * 1000)` |

**常用配音语音**：
- `zh-CN-YunyangNeural` - 男声，专业新闻（默认）
- `zh-CN-XiaoxiaoNeural` - 女声，温暖新闻
- `zh-CN-ShenyangNeural` - 男声，沉稳
- `zh-CN-ZhouyiNeural` - 男声，活泼

---

## 技能边界

本技能负责：
- ✅ 从 aihot 拉数据 → 生成 HTML → 录制视频 → 添加配音 → 输出 MP4

本技能不负责：
- ❌ 上传视频到抖音/视频号（需额外 skill）
- ❌ 生成视频封面图（需额外处理）
- ❌ 批量生成多日视频（需循环调用本技能）
- ❌ aihot 数据拉取失败时的数据源切换（需用户决定）
- ❌ 视频剪辑后的二次加工（如加字幕、特效等）

---

## 示例触发语句

以下语句**应触发本技能**：
- "生成今天的 AI 日报视频"
- "把 AI 日报做成视频，要配音"
- "AI 日报视频，带配音，9:16 竖屏"
- "make AI daily video with voiceover"
- "generate AI daily video for today"
- "I want a video of today's AI daily with Chinese voiceover"
- "用今天的 AI HOT 数据做个视频"

以下语句**不应触发本技能**（用 aihot skill 即可）：
- "今天 AI 圈有什么"（只是查资讯，不需要视频）
- "AI 日报文字版"（不需要视频）
- "看一下 AI HOT 精选"（不需要视频）

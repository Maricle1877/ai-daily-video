# AI Daily Video 🍮

从 [AI HOT](https://aihot.virxact.com) 拉取每日 AI 资讯，自动生成带配音的竖屏短视频（1080×1920，9:16，适配抖音/视频号）。

## 工作流

```
aihot 数据 → HTML 动画页 → Playwright 录制 → edge-tts 配音 → ffmpeg 合成
```

## 依赖

| 依赖 | 安装 |
|------|------|
| Python 3.10+ | — |
| playwright | `pip install playwright && python -m playwright install chromium` |
| edge-tts | `pip install edge-tts` |
| imageio-ffmpeg | `pip install imageio-ffmpeg` |

## 用法

```bash
# 1. 拉取 AI 日报数据
# 2. 用 assets/template.html 生成 HTML 动画页
# 3. 一键生成配音视频
python scripts/add_voiceover.py <html_file> [output_mp4]

# 或先预览无声版
python scripts/record_video.py <html_file> [output_mp4]
```

## 配音规则

- 开场配音：`一日AI简报`
- 条目配音：仅 `.item-summary`（截断 45 字）+ `.item-highlight`（截断 30 字）
- 截断策略：按句子边界（。！？；）截断，不从中断开
- 场景时长自动适配配音时长

## License

MIT

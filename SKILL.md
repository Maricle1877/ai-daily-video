---
name: ai-daily-video
description: "AI 日报视频生成技能。从 aihot.virxact.com 拉取 AI 日报数据，自动生成带配音的竖屏短视频（1080×1920，9:16）。触发场景：用户说\"生成 AI 日报视频\"、\"做 AI 日报视频\"、\"AI 日报视频带配音\"、\"把今天的 AI 日报做成视频\"、\"AI daily video\"、\"make AI daily video\"等。通用使用说明请参考 README.md。"
agent_created: true
---

# AI Daily Video — WorkBuddy Skill

> 该目录是一个通用 AI 日报视频生成工具。该 SKILL.md 是 WorkBuddy 专属配置，
> 通用使用说明请见 [README.md](./README.md)。

## WorkBuddy 自动化工作流

WorkBuddy 中触发后，执行以下步骤：

### Step 1: 拉取 AI 日报数据

加载 `aihot` skill，获取日报 JSON 数据。

### Step 2: 生成 HTML 动画页

读取 `assets/template.html`，填充 `{{DATE}}` `{{DATE_DOT}}` `{{SECTIONS}}`。
详见 README.md 中的模板填充规则。

### Step 3: 生成配音视频

```bash
python scripts/add_voiceover.py <html_file> [output.mp4]
```

### Step 4: 预览并交付

- 用 `preview_url` 预览最终视频
- 用 `deliver_attachments` 交付文件

## 配置项

| 配置项 | 默认值 |
|--------|--------|
| 配音语音 | `zh-CN-YunyangNeural`（男声新闻） |
| 视频分辨率 | 1080×1920 |
| 帧率 | 30fps |
| 配音延迟 | 场景切换后 0.8s |
| 场景余量 | 配音时长 + 1.0s 缓冲 |

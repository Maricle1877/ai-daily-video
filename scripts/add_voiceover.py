"""
AI 日报自动配音脚本 v2
流程：生成配音 → 按配音时长调整场景停留 → 重新录制视频 → 合成配音
使用 edge-tts 为视频中的小字内容（摘要+亮点）生成配音
标题、关键数据、版块汇总等不配音

用法: python add_voiceover.py <html_file> [output_mp4]
"""

import os
import re
import sys
import asyncio
import tempfile
import subprocess
import shutil
from pathlib import Path

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG = None

# 初始化 ffmpeg 路径
def _init_ffmpeg():
    global FFMPEG
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG = "ffmpeg"

VOICE = "zh-CN-YunyangNeural"  # 专业新闻男声


# ==================== 文本工具 ====================

def truncate_to_sentence(text, max_chars):
    """在句子边界截断文本，保证不从中断开"""
    if len(text) <= max_chars:
        return text
    segment = text[:max_chars + 10]
    for punct in ['。', '！', '？', '；']:
        idx = segment.rfind(punct)
        if 0 < idx <= max_chars:
            return segment[:idx + 1]
    for punct in ['，', '、']:
        idx = segment.rfind(punct)
        if 0 < idx <= max_chars:
            return segment[:idx + 1]
    return text[:max_chars] + "……"


# ==================== 解析 HTML ====================

def parse_all_scenes(html_file):
    """解析 HTML 中所有场景，返回列表 [{type, duration_ms, voice_text, index}, ...]"""
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    all_scenes = []
    for match in re.finditer(
        r'<div class="scene scene-(\w+)[^"]*"[^>]*data-duration="(\d+)"',
        html,
    ):
        scene_type = match.group(1)
        duration = int(match.group(2))

        voice_text = ""
        if scene_type == "intro":
            voice_text = "一日AI简报"
        elif scene_type == "item":
            # 从这个位置开始找到下一个 scene 或 progress-bar
            start = match.start()
            next_scene = re.search(
                r'<div class="scene |<div class="progress-bar"',
                html[start + 100:],
            )
            end = (start + 100 + next_scene.start()) if next_scene else len(html)
            block = html[start:end]

            # 提取 item-summary
            summary_match = re.search(
                r'<div class="item-summary">(.*?)</div>', block, re.DOTALL
            )
            summary_text = ""
            if summary_match:
                summary_text = re.sub(r"<[^>]+>", "", summary_match.group(1)).strip()

            # 提取 item-highlight
            highlight_match = re.search(
                r'<div class="item-highlight">(.*?)</div>', block, re.DOTALL
            )
            highlight_text = ""
            if highlight_match:
                highlight_text = re.sub(
                    r"<strong>(.*?)</strong>", r"\1", highlight_match.group(1)
                ).strip()
                highlight_text = re.sub(r"<[^>]+>", "", highlight_text).strip()

            parts = []
            if summary_text:
                parts.append(truncate_to_sentence(summary_text, 45))
            if highlight_text:
                parts.append(truncate_to_sentence(highlight_text, 30))
            voice_text = "，".join(parts)

        all_scenes.append({
            "type": scene_type,
            "duration_ms": duration,
            "voice_text": voice_text,
            "index": len(all_scenes),
        })

    return all_scenes, html


# ==================== 生成配音 ====================

async def generate_tts(text, output_path, voice=VOICE):
    """用 edge-ts 生成单段语音"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


async def generate_all_tts(scenes, tmp_dir):
    """为所有需要配音的场景生成语音文件"""
    tasks = []
    for i, scene in enumerate(scenes):
        if not scene.get("voice_text"):
            continue
        output_path = os.path.join(tmp_dir, f"voice_{scene['index']:02d}.mp3")
        scene["voice_file"] = output_path
        tasks.append(generate_tts(scene["voice_text"], output_path, voice=VOICE))

    print(f"正在生成 {len(tasks)} 段配音...")
    await asyncio.gather(*tasks)
    print("配音生成完成")


# ==================== 获取音频时长 ====================

def get_audio_duration(filepath):
    """用 ffmpeg 获取音频时长（秒）"""
    cmd = [FFMPEG, "-i", filepath, "-f", "null", "-"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = result.stdout

    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
    if duration_match:
        h, m, s, ms = (int(duration_match.group(i)) for i in range(1, 5))
        return h * 3600 + m * 60 + s + ms / 100

    return 0


# ==================== 调整 HTML 场景时长 ====================

def adjust_html_durations(all_scenes, html_content, html_file):
    """
    根据配音时长调整每个 item 场景的 data-duration
    规则：item 场景时长 = max(配音时长 + 1.8秒缓冲, 原始时长)
    其他场景保持不变
    返回调整后 HTML 文件路径
    """
    html = html_content

    # 收集需要修改的场景
    changes = []
    for scene in all_scenes:
        if scene.get("voice_file") and os.path.exists(scene["voice_file"]):
            voice_sec = get_audio_duration(scene["voice_file"])
            # 配音时长 + 0.8秒前置（观众先看标题） + 1秒后置缓冲
            needed_ms = int((voice_sec + 1.8) * 1000)
            # 取配音所需时长和原始时长的最大值
            new_duration = max(needed_ms, scene["duration_ms"])

            if new_duration != scene["duration_ms"]:
                changes.append({
                    "index": scene["index"],
                    "old_ms": scene["duration_ms"],
                    "new_ms": new_duration,
                    "voice_sec": voice_sec,
                })
                scene["duration_ms"] = new_duration

    # 执行替换（从后往前替换，避免位置偏移）
    # 重新从 HTML 中找到所有 data-duration 的位置
    durations = list(re.finditer(r'data-duration="(\d+)"', html))

    for change in reversed(changes):
        idx = change["index"]
        if idx < len(durations):
            match = durations[idx]
            old_str = match.group(0)
            new_str = f'data-duration="{change["new_ms"]}"'
            html = html[:match.start()] + new_str + html[match.end():]

    # 写入调整后的 HTML
    adjusted_html_path = html_file.replace(".html", "_adjusted.html")
    with open(adjusted_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n场景时长调整:")
    total_ms = sum(s["duration_ms"] for s in all_scenes)
    print(f"  新总时长: {total_ms/1000:.1f} 秒")

    for c in changes:
        print(f"  场景 {c['index']:02d}: {c['old_ms']}ms → {c['new_ms']}ms (配音 {c['voice_sec']:.1f}s)")

    return adjusted_html_path


# ==================== 重新录制视频 ====================

def record_video_with_voiceover(html_file):
    """用 Playwright 录制调整时长后的 HTML 为视频"""
    from playwright.sync_api import sync_playwright

    # 计算总时长
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    durations = re.findall(r'data-duration="(\d+)"', html)
    total_ms = sum(int(d) for d in durations) + 2000  # 2秒缓冲

    tmp_dir = tempfile.mkdtemp(prefix="aihot_rec_")

    print(f"\n开始录制视频: {total_ms/1000:.1f} 秒")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            record_video_dir=tmp_dir,
            record_video_size={"width": 1080, "height": 1920}
        )
        page = context.new_page()

        html_url = f"file:///{html_file.replace(os.sep, '/')}"
        page.goto(html_url, wait_until="networkidle")
        page.evaluate("document.fonts.ready")

        # 隐藏进度条
        page.evaluate("document.querySelector('.progress-bar').style.display='none'")

        print(f"正在录制，等待 {total_ms/1000:.1f} 秒...")
        page.wait_for_timeout(total_ms)

        context.close()
        browser.close()

    # 找到录制的 WebM
    webm_files = [f for f in os.listdir(tmp_dir) if f.endswith(".webm")]
    if not webm_files:
        print("❌ 录制失败：未找到 WebM 文件")
        sys.exit(1)

    webm_path = os.path.join(tmp_dir, webm_files[0])
    print(f"录制完成: {os.path.getsize(webm_path)/1024/1024:.1f} MB")
    return webm_path, tmp_dir


def convert_to_mp4(webm_path, output_path):
    """将 WebM 转码为 H.264 MP4"""
    cmd = [
        FFMPEG, "-y",
        "-i", webm_path,
        "-c:v", "libx264",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-movflags", "+faststart",
        output_path,
    ]
    print("转码 MP4（无音频）...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"转码失败: {result.stderr[-300:]}")
        sys.exit(1)

    print(f"✅ 视频转码完成: {os.path.getsize(output_path)/1024/1024:.1f} MB")
    return output_path


# ==================== 构建音频轨道 ====================

def create_silent_audio(filepath, duration_sec):
    """生成指定时长的静音音频"""
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(duration_sec),
        "-c:a", "libmp3lame",
        "-b:a", "64k",
        filepath,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def build_audio_track(all_scenes, tmp_dir):
    """构建完整音频轨道，配音在每个 item 场景开始后 0.8 秒插入"""
    total_ms = sum(s["duration_ms"] for s in all_scenes)
    total_sec = total_ms / 1000

    print(f"\n构建音频轨道，总时长 {total_sec:.1f} 秒")

    # 生成静音底轨
    silent_path = os.path.join(tmp_dir, "silent_base.mp3")
    create_silent_audio(silent_path, total_sec + 2)

    # 计算每个场景的时间轴位置
    current_time = 0
    delayed_files = []

    for scene in all_scenes:
        scene["start_ms"] = current_time

        if scene.get("voice_file") and os.path.exists(scene["voice_file"]):
            voice_file = scene["voice_file"]
            voice_sec = get_audio_duration(voice_file)

            # 配音延迟到场景开始后 0.8 秒
            delay_ms = current_time + 800

            delayed_path = os.path.join(tmp_dir, f"delayed_{scene['index']:02d}.mp3")
            cmd = [
                FFMPEG, "-y",
                "-i", voice_file,
                "-af", f"adelay={delay_ms}|{delay_ms},apad",
                "-t", str(total_sec + 2),
                "-c:a", "libmp3lame",
                "-b:a", "64k",
                delayed_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            delayed_files.append(delayed_path)

            print(f"  场景 {scene['index']:02d} @ {current_time/1000:.1f}s, 配音 {voice_sec:.1f}s")

        current_time += scene["duration_ms"]

    if not delayed_files:
        print("没有配音文件")
        return silent_path

    # 混合所有音频
    inputs = ["-i", silent_path]
    for f in delayed_files:
        inputs.extend(["-i", f])

    n_inputs = 1 + len(delayed_files)
    mix_inputs = "".join([f"[{i}:a]" for i in range(n_inputs)])
    filter_complex = f"{mix_inputs}amix=inputs={n_inputs}:duration=longest:dropout_transition=0[aout]"

    mixed_path = os.path.join(tmp_dir, "mixed_audio.mp3")

    cmd = [
        FFMPEG, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        "-t", str(total_sec + 1),
        mixed_path,
    ]

    print("混合所有配音...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"混合失败: {result.stderr[-300:]}")
        sys.exit(1)

    return mixed_path


# ==================== 合并音视频 ====================

def merge_audio_video(video_path, audio_path, output_path):
    """将配音混入视频"""
    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]

    print("合并视频和配音...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"合并失败: {result.stderr[-300:]}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"✅ 配音版视频已生成!")
    print(f"   文件: {output_path}")
    print(f"   大小: {size_mb:.1f} MB")
    print(f"   语音: {VOICE}")
    print(f"   配音内容: 仅摘要+亮点（标题/数据/版块汇总不配音）")


# ==================== 主流程 ====================

def main():
    _init_ffmpeg()

    if len(sys.argv) < 2:
        print("用法: python add_voiceover.py <html_file> [output_mp4]")
        sys.exit(1)

    html_file = sys.argv[1]
    output_mp4 = sys.argv[2] if len(sys.argv) > 2 else html_file.replace(".html", "-配音版.mp4")

    if not os.path.isfile(html_file):
        print(f"错误: HTML 文件不存在: {html_file}")
        sys.exit(1)

    print("=" * 50)
    print("AI 日报自动配音 v2")
    print("流程: 生成配音 → 调整场景时长 → 重录视频 → 合成配音")
    print("=" * 50)

    tmp_dir = tempfile.mkdtemp(prefix="aihot_voice_")

    try:
        # Step1: 解析 HTML
        all_scenes, html_content = parse_all_scenes(html_file)
        voice_scenes = [s for s in all_scenes if s.get("voice_text")]
        print(f"\n共 {len(all_scenes)} 个场景，其中 {len(voice_scenes)} 个需要配音")

        # Step2: 生成配音
        asyncio.run(generate_all_tts(all_scenes, tmp_dir))

        for s in all_scenes:
            if s.get("voice_file") and os.path.exists(s["voice_file"]):
                size = os.path.getsize(s["voice_file"])
                dur = get_audio_duration(s["voice_file"])
                print(f"  ✓ 场景 {s['index']:02d}: {dur:.1f}s ({size/1024:.0f} KB)")

        # Step3: 根据配音时长调整 HTML
        adjusted_html = adjust_html_durations(all_scenes, html_content, html_file)

        # Step4: 用调整后的 HTML 重新录制视频
        webm_path, rec_tmp_dir = record_video_with_voiceover(adjusted_html)

        # 转码为 MP4（无音频）
        silent_mp4 = os.path.join(tmp_dir, "silent_video.mp4")
        convert_to_mp4(webm_path, silent_mp4)

        # 清理录制临时目录
        shutil.rmtree(rec_tmp_dir, ignore_errors=True)

        # Step5: 构建音频轨道
        mixed_audio = build_audio_track(all_scenes, tmp_dir)

        # Step6: 合并音视频
        merge_audio_video(silent_mp4, mixed_audio, output_mp4)

    finally:
        # 清理临时文件
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # 清理中间文件
        adjusted_html = html_file.replace(".html", "_adjusted.html")
        if os.path.exists(adjusted_html):
            os.remove(adjusted_html)
        print("\n临时文件已清理")


if __name__ == "__main__":
    main()

"""
AI 日报播报视频录制脚本 v2
使用 Playwright 内置视频录制 + ffmpeg 转码
输出竖屏 1080x1920 视频适配抖音

用法: python record_video.py <html_file_path> [output_mp4_path]
"""

import os
import sys
import re
import subprocess
import tempfile
from pathlib import Path

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ffmpeg 路径
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def get_total_duration(html_file):
    """从 HTML 文件解析所有场景的 data-duration，计算总时长（毫秒）"""
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    durations = re.findall(r'data-duration="(\d+)"', html)
    total_ms = sum(int(d) for d in durations)
    print(f"检测到 {len(durations)} 个场景，总时长 {total_ms / 1000:.1f} 秒")
    return total_ms


def record_video(html_file, output_mp4):
    """用 Playwright 内置视频录制 WebM，然后转码为 MP4"""
    from playwright.sync_api import sync_playwright

    total_ms = get_total_duration(html_file)
    # 额外留 2 秒缓冲，确保结尾场景完整
    record_ms = total_ms + 2000

    # 临时目录存放 WebM
    tmp_dir = tempfile.mkdtemp(prefix="aihot_video_")
    webm_path = os.path.join(tmp_dir, "recording.webm")

    print(f"开始录制：{record_ms / 1000:.1f} 秒，输出 1080x1920 竖屏")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # 开启视频录制：viewport=1080x1920 直接匹配输出分辨率
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            record_video_dir=tmp_dir,
            record_video_size={"width": 1080, "height": 1920}
        )

        page = context.new_page()

        # 加载 HTML
        html_url = f"file:///{html_file.replace(os.sep, '/')}"
        page.goto(html_url, wait_until="networkidle")

        # 精确等待 Google Fonts 加载
        page.evaluate("document.fonts.ready")
        print("字体加载完成")

        # 隐藏进度条（录制时不需要）
        page.evaluate("document.querySelector('.progress-bar').style.display='none'")

        # 等待动画全部播放完毕
        print(f"正在录制，等待 {record_ms / 1000:.1f} 秒...")
        page.wait_for_timeout(record_ms)

        # 关闭 context 保存视频
        context.close()
        browser.close()

    # Playwright 生成的文件名可能不是 recording.webm，查找实际文件
    webm_files = [f for f in os.listdir(tmp_dir) if f.endswith(".webm")]
    if not webm_files:
        print("❌ 录制失败：未找到 WebM 文件")
        sys.exit(1)

    actual_webm = os.path.join(tmp_dir, webm_files[0])
    print(f"录制完成：{actual_webm} ({os.path.getsize(actual_webm) / 1024 / 1024:.1f} MB)")

    # 转码为 MP4
    convert_to_mp4(actual_webm, output_mp4)

    # 清理临时文件
    cleanup(actual_webm)


def convert_to_mp4(webm_path, output_mp4):
    """用 ffmpeg 将 WebM 转为 H.264 MP4"""
    print("开始转码 MP4...")

    cmd = [
        FFMPEG,
        "-y",
        "-i", webm_path,
        "-c:v", "libx264",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-movflags", "+faststart",
        output_mp4
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ ffmpeg 转码失败：{result.stderr[-500:]}")
        sys.exit(1)

    size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
    print(f"✅ 视频已生成：{output_mp4}")
    print(f"   大小：{size_mb:.1f} MB")
    print(f"   分辨率：1080x1920 (9:16 竖屏)")
    print(f"   格式：H.264 MP4（抖音兼容）")


def cleanup(webm_path):
    """清理临时文件"""
    tmp_dir = os.path.dirname(webm_path)
    if os.path.exists(tmp_dir):
        for f in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, f))
        os.rmdir(tmp_dir)
        print("临时文件已清理")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python record_video.py <html_file> [output_mp4]")
        sys.exit(1)

    html_file = sys.argv[1]
    output_mp4 = sys.argv[2] if len(sys.argv) > 2 else html_file.replace(".html", ".mp4")

    if not os.path.isfile(html_file):
        print(f"错误: HTML 文件不存在: {html_file}")
        sys.exit(1)

    record_video(html_file, output_mp4)

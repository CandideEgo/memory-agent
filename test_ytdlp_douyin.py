"""
测试 YtDlpTool - 抖音视频信息提取
用法: python test_ytdlp_douyin.py
"""
import sys
import os
import json

# 确保项目目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 测试 URL（抖音精选搜索页，modal_id 是实际视频 ID）
DOUYIN_URL = (
    "https://www.douyin.com/jingxuan/search/%E5%8D%A2%E5%85%8B%E6%96%87"
    "?aid=2bf75fd9-e581-4dbe-9582-2b2cc156a074"
    "&modal_id=7635596691491523855&type=general"
)
# 简化版：直接用 video ID
DOUYIN_VIDEO_URL = "https://www.douyin.com/video/7635596691491523855"


def test_direct_ytdlp():
    """直接测试 yt-dlp 对抖音的支持"""
    try:
        import yt_dlp
    except ImportError:
        print("yt-dlp 未安装。正在安装...")
        os.system(f"{sys.executable} -m pip install yt-dlp --break-system-packages -q")
        import yt_dlp

    print(f"yt-dlp 版本: {yt_dlp.version.__version__}\n")

    # 测试 1: 用 video ID 格式的 URL
    print(f"=== 测试: 提取信息 ===")
    print(f"URL: {DOUYIN_VIDEO_URL}\n")

    ydl_opts = {
        "quiet": False,
        "no_warnings": False,
        "skip_download": True,
        # 抖音可能需要这些 header
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.douyin.com/",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(DOUYIN_VIDEO_URL, download=False)

        if info:
            print("✅ 信息提取成功!\n")
            print(f"  标题: {info.get('title', '?')}")
            print(f"  上传者: {info.get('uploader', '?')}")
            print(f"  时长: {info.get('duration', '?')} 秒")
            print(f"  描述: {(info.get('description') or '')[:200]}")

            formats = info.get("formats", [])
            if formats:
                print(f"  可用格式: {len(formats)} 种")
                for f in formats[:5]:
                    fid = f.get("format_id", "?")
                    ext = f.get("ext", "?")
                    h = f.get("height") or 0
                    print(f"    - {fid}: {ext} {h}p")

            # 保存完整 JSON 供查看
            safe_info = {k: v for k, v in info.items()
                         if not isinstance(v, (bytes, memoryview))}
            with open("douyin_info.json", "w", encoding="utf-8") as f:
                json.dump(safe_info, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n  完整信息已保存到: douyin_info.json")

    except Exception as e:
        print(f"❌ Video URL 提取失败: {e}")

    # 测试 2: 用原始搜索页 URL
    print(f"\n=== 测试: 搜索页 URL ===")
    print(f"URL: {DOUYIN_URL}\n")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(DOUYIN_URL, download=False)
        if info:
            title = info.get("title", "?")
            print(f"✅ 搜索页 URL 提取成功: {title}")
    except Exception as e:
        print(f"❌ 搜索页 URL 提取失败: {e}")
        print("  (这是正常的——搜索页 URL 通常不能直接被 yt-dlp 解析)")
        print(f"  请使用 video URL: {DOUYIN_VIDEO_URL}")


def test_our_tool():
    """测试我们写的 YtDlpTool"""
    print(f"\n=== 测试: YtDlpTool (我们写的工具) ===\n")

    try:
        from tools.ytdlp_tool import YtDlpTool
        import asyncio

        tool = YtDlpTool()

        async def run():
            print("--- info ---")
            result = await tool.execute(url=DOUYIN_VIDEO_URL, action="info")
            print(result)

            print("\n--- list_formats ---")
            result = await tool.execute(url=DOUYIN_VIDEO_URL, action="list_formats")
            print(result)

        asyncio.run(run())

    except Exception as e:
        print(f"❌ YtDlpTool 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_direct_ytdlp()
    print("\n" + "=" * 60)
    test_our_tool()

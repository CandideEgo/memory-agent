"""
YtDlp 工具 - 流媒体内容抓取和下载
"""

import asyncio
import logging
import os
from typing import Any

try:
    from .base import BaseTool
except ImportError:
    from tools.base import BaseTool

logger = logging.getLogger(__name__)

# 检查 yt-dlp 是否可用
try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False


class YtDlpTool(BaseTool):
    """流媒体抓取工具 - 提取信息、下载视频/音频"""

    name = "ytdlp"
    description = """抓取流媒体内容（视频/音频）。支持 YouTube、Bilibili、Douyin 等 1000+ 网站。
三个动作:
- info: 提取视频元信息（标题、时长、格式列表、缩略图等），不下载
- list_formats: 列出所有可用格式（分辨率、编码、文件大小）
- download: 下载视频或音频到本地

注意：某些网站（如 Douyin）可能需要 cookie 认证，可将浏览器 cookie 导出为文件后传入 cookie_file 参数。"""

    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "流媒体页面 URL（如 YouTube、Bilibili、Douyin 视频链接）"
            },
            "action": {
                "type": "string",
                "enum": ["info", "list_formats", "download"],
                "description": "操作类型: info=提取元信息, list_formats=列出格式, download=下载"
            },
            "format": {
                "type": "string",
                "description": "下载格式选择器。如 'best'（最佳质量）、'worst'（最小文件）、'bestvideo+bestaudio'、'best[height<=720]'（≤720p 最佳）、'mp4'等。仅 download 时有效。",
                "default": "best"
            },
            "output_dir": {
                "type": "string",
                "description": "下载输出目录（默认当前目录）",
                "default": "."
            },
            "audio_only": {
                "type": "boolean",
                "description": "仅下载音频（自动转为 m4a），忽略 video_only 和 format。仅 download 时有效。",
                "default": False
            },
            "video_only": {
                "type": "boolean",
                "description": "仅下载视频流（不含音频）。仅 download 时有效。",
                "default": False
            },
            "playlist_items": {
                "type": "string",
                "description": "播放列表范围，如 '1-5'（前 5 个）、'3'（仅第 3 个）。仅 download 时有效。",
                "default": "1"
            },
            "cookie_file": {
                "type": "string",
                "description": "Netscape 格式的 cookie 文件路径，用于需要登录的网站",
                "default": ""
            },
            "max_filesize": {
                "type": "string",
                "description": "最大文件大小限制，如 '100M'、'1G'。超过则跳过。仅 download 时有效。",
                "default": ""
            },
            "max_results": {
                "type": "integer",
                "description": "info 或 list_formats 时最多返回的条目数",
                "default": 20
            }
        },
        "required": ["url", "action"]
    }

    def __init__(self, download_dir: str = "."):
        self.download_dir = download_dir

    def _check_ytdlp(self) -> str | None:
        """检查 yt-dlp 是否可用，返回错误信息或 None"""
        if not HAS_YTDLP:
            return "yt-dlp 未安装。请运行: pip install yt-dlp --break-system-packages"
        return None

    def _build_ydl_opts(self, **kwargs) -> dict:
        """构建 yt-dlp 选项字典"""
        action = kwargs.get("action", "info")
        output_dir = kwargs.get("output_dir", self.download_dir) or "."

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "no_color": True,
        }

        if action == "info":
            opts["skip_download"] = True

        elif action == "list_formats":
            opts["skip_download"] = True

        elif action == "download":
            fmt = kwargs.get("format", "best")
            opts["format"] = fmt
            opts["outtmpl"] = os.path.join(output_dir, "%(title)s.%(ext)s")
            opts["skip_download"] = False

            if kwargs.get("audio_only"):
                opts["format"] = "bestaudio/best"
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }]
            elif kwargs.get("video_only"):
                opts["format"] = "bestvideo"

            playlist = kwargs.get("playlist_items", "")
            if playlist:
                opts["playlist_items"] = playlist
            else:
                opts["playlist_items"] = "1"

            max_fs = kwargs.get("max_filesize", "")
            if max_fs:
                opts["max_filesize"] = max_fs

        # Cookie
        cookie_file = kwargs.get("cookie_file", "")
        if cookie_file and os.path.isfile(cookie_file):
            opts["cookiefile"] = cookie_file

        return opts

    async def execute(self, **kwargs) -> str:
        """
        执行 yt-dlp 操作

        Args:
            url: 视频 URL
            action: info / list_formats / download
            其他参数见 parameters

        Returns:
            格式化的结果字符串
        """
        err = self._check_ytdlp()
        if err:
            return f"错误: {err}"

        url = kwargs.get("url", "")
        action = kwargs.get("action", "info")

        if not url or not url.strip():
            return "错误: url 参数不能为空"

        if action not in ("info", "list_formats", "download"):
            return f"错误: 未知 action: {action}，可用: info, list_formats, download"

        ydl_opts = self._build_ydl_opts(**kwargs)

        logger.info(f"YtDlpTool: {action} -> {url}")

        try:
            loop = asyncio.get_event_loop()

            if action == "list_formats":
                return await loop.run_in_executor(None, self._list_formats, url, ydl_opts)
            elif action == "info":
                return await loop.run_in_executor(None, self._extract_info, url, ydl_opts, kwargs.get("max_results", 20))
            elif action == "download":
                return await loop.run_in_executor(None, self._download, url, ydl_opts)

        except Exception as e:
            error_msg = f"错误: yt-dlp 执行失败: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return error_msg

    def _extract_info(self, url: str, opts: dict, max_results: int = 20) -> str:
        """提取视频元信息"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                return f"提取信息失败: {e}"

        if not info:
            return "未获取到任何信息"

        # 处理播放列表
        entries = info.get("entries")
        if entries:
            entries = list(entries)[:max_results]
            lines = [f"## 播放列表: {info.get('title', '未知')} ({len(entries)} 条)"]
            lines.append(f"- 上传者: {info.get('uploader', '?')}")
            lines.append("")
            for i, entry in enumerate(entries, 1):
                lines.append(f"### {i}. {entry.get('title', '?')}")
                lines.extend(self._format_entry(entry))
                lines.append("")
            return "\n".join(lines)

        lines = [f"## {info.get('title', '未知')}"]
        lines.extend(self._format_entry(info))
        return "\n".join(lines)

    def _format_entry(self, info: dict) -> list[str]:
        """格式化单个视频条目"""
        lines = []
        duration = info.get("duration")
        if duration:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
            lines.append(f"- 时长: {dur_str}")

        lines.append(f"- 上传者: {info.get('uploader', info.get('channel', '?'))}")
        lines.append(f"- 上传日期: {info.get('upload_date', '?')}")
        lines.append(f"- 观看数: {info.get('view_count', '?')}")
        lines.append(f"- 点赞数: {info.get('like_count', '?')}")

        webpage_url = info.get("webpage_url", "")
        if webpage_url:
            lines.append(f"- 页面: {webpage_url}")

        description = info.get("description", "")
        if description:
            desc_short = description[:200] + "..." if len(description) > 200 else description
            lines.append(f"- 简介: {desc_short}")

        thumbnail = info.get("thumbnail", "")
        if thumbnail:
            lines.append(f"- 缩略图: {thumbnail}")

        formats = info.get("formats", [])
        if formats:
            # 汇总格式信息
            lines.append(f"- 可用格式: {len(formats)} 种")
            unique_res = set()
            for f in formats:
                h = f.get("height")
                if h and h > 0:
                    unique_res.add(h)
            if unique_res:
                lines.append(f"- 分辨率: {', '.join(f'{r}p' for r in sorted(unique_res, reverse=True))}")

        return lines

    def _list_formats(self, url: str, opts: dict) -> str:
        """列出可用格式"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                return f"获取格式列表失败: {e}"

        if not info:
            return "未获取到任何信息"

        entries = info.get("entries")
        if entries:
            info = list(entries)[0]  # 播放列表取第一个

        formats = info.get("formats", [])
        if not formats:
            return "未找到可用格式"

        lines = [f"## {info.get('title', '?')} - 可用格式 ({len(formats)} 种)\n"]
        lines.append(f"{'ID':<8} {'扩展名':<6} {'分辨率':<12} {'编码':<12} {'大小':<10} {'备注'}")
        lines.append("-" * 70)

        for f in formats[:50]:  # 最多显示 50 个
            fid = str(f.get("format_id", "?"))[:7]
            ext = f.get("ext", "?")[:5]
            w = f.get("width") or 0
            h = f.get("height") or 0
            res = f"{w}x{h}" if w and h else f.get("resolution", "audio only")[:11]
            vcodec = (f.get("vcodec", "") or "none")[:11]
            acodec = (f.get("acodec", "") or "none")[:11]
            codec = f"{vcodec}+{acodec}" if vcodec != "none" and acodec != "none" else (vcodec if vcodec != "none" else acodec)
            codec = codec[:11]

            fs = f.get("filesize") or f.get("filesize_approx") or 0
            size_str = f"{fs / 1024 / 1024:.1f}M" if fs > 0 else "?"

            note = f.get("format_note", "")[:15]

            lines.append(f"{fid:<8} {ext:<6} {res:<12} {codec:<12} {size_str:<10} {note}")

        if len(formats) > 50:
            lines.append(f"\n... 还有 {len(formats) - 50} 种格式，使用 format 参数筛选")

        # 推荐格式
        lines.append(f"\n### 推荐格式选择器\n")
        best = info.get("best_format", info.get("format_id", "?"))
        lines.append(f"- `best` → 最佳质量（默认）")
        lines.append(f"- `best[height<=720]` → 720p 以内最佳")
        lines.append(f"- `bestaudio` → 最佳音频")
        lines.append(f"- `worst` → 最小文件")

        return "\n".join(lines)

    def _download(self, url: str, opts: dict) -> str:
        """下载视频/音频"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as e:
                err_str = str(e)
                # 常见错误友好提示
                if "HTTP Error 403" in err_str:
                    return f"下载被拒绝 (403 Forbidden)。可能需要 cookie 认证，请导出浏览器 cookie 后通过 cookie_file 参数传入。\n原始错误: {e}"
                if "HTTP Error 404" in err_str:
                    return f"视频不存在 (404)。链接可能已失效。\n原始错误: {e}"
                if "This video is unavailable" in err_str:
                    return f"视频不可用。可能需要登录或链接已失效。\n原始错误: {e}"
                if "Requested format is not available" in err_str:
                    return f"请求的格式不可用。请先用 list_formats 查看可用格式，再用 format 参数指定。\n原始错误: {e}"
                return f"下载失败: {e}"

        entries = info.get("entries")
        if entries:
            # 播放列表
            entries = list(entries)
            downloaded = []
            for entry in entries:
                title = entry.get("title", "?")
                ext = entry.get("ext", "?")
                downloaded.append(f"  - {title}.{ext}")
            output_dir = opts.get("outtmpl", ".").split("%")[0] if "%" in opts.get("outtmpl", ".") else "."
            return f"播放列表下载完成 ({len(downloaded)} 个):\n" + "\n".join(downloaded)

        # 单文件
        title = info.get("title", "?")
        ext = info.get("ext", "?")
        filepath = opts.get("outtmpl", "").replace("%(title)s", title).replace("%(ext)s", ext)

        # 如果 audio_only，扩展名是 m4a
        postprocessors = opts.get("postprocessors", [])
        if postprocessors and postprocessors[0].get("key") == "FFmpegExtractAudio":
            ext = "m4a"
            filepath = filepath.replace(f".{info.get('ext', '')}", ".m4a")

        return f"下载完成: {title}.{ext}\n路径: {filepath}"

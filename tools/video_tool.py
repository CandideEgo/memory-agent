"""
视频分析工具 - 对流媒体视频进行内容分析（场景检测、语音转文字、OCR 字幕提取）
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .base import BaseTool
except ImportError:
    from tools.base import BaseTool

logger = logging.getLogger(__name__)


class VideoAnalyzerTool(BaseTool):
    """视频内容分析工具 - 分析流媒体视频，提取场景、字幕和语音内容"""

    name = "video_analyze"
    description = """对流媒体视频 URL 或本地视频文件进行 AI 内容分析。
支持 YouTube、Bilibili 等 1000+ 网站。
分析结果包括：场景列表（含关键帧截图）、语音转文字文本、画面内嵌字幕（OCR）。
输出为 Markdown 报告 + JSON 结构化数据。

注意：首次使用需要安装依赖（pip install yt-dlp opencv-python pyscenedetect easyocr faster-whisper pillow numpy）
以及 ffmpeg 系统工具。运行 video_analyze --check-deps 可检查依赖。"""
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "流媒体视频 URL（如 YouTube、Bilibili 等），与 file_path 二选一"
            },
            "file_path": {
                "type": "string",
                "description": "本地视频文件路径，与 url 二选一"
            },
            "output_dir": {
                "type": "string",
                "description": "分析报告输出目录（默认自动生成）",
                "default": ""
            },
            "skip_transcribe": {
                "type": "boolean",
                "description": "是否跳过语音转文字步骤（Whisper 较耗时）",
                "default": False
            },
            "whisper_model": {
                "type": "string",
                "description": "Whisper 模型大小: tiny/base/small/medium/large（越大越准越慢）",
                "enum": ["tiny", "base", "small", "medium", "large"],
                "default": "base"
            },
            "scene_threshold": {
                "type": "number",
                "description": "场景检测灵敏度（15-45，越低越敏感检测越多场景）",
                "default": 30.0
            }
        }
    }

    def __init__(self, analyzer_script_path: str = ""):
        """
        初始化视频分析工具

        Args:
            analyzer_script_path: video_analyzer.py 的路径，留空则自动查找
        """
        self.analyzer_script = analyzer_script_path or self._find_analyzer_script()

    def _find_analyzer_script(self) -> str:
        """自动查找 video_analyzer.py 脚本"""
        # 检查同目录
        script_dir = Path(__file__).parent.parent
        candidates = [
            script_dir / "video_analyzer.py",
            script_dir / "scripts" / "video_analyzer.py",
            Path.cwd() / "video_analyzer.py",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        return "video_analyzer.py"  # 默认路径

    async def execute(
        self,
        url: str = "",
        file_path: str = "",
        output_dir: str = "",
        skip_transcribe: bool = False,
        whisper_model: str = "base",
        scene_threshold: float = 30.0,
    ) -> str:
        """
        执行视频内容分析

        Args:
            url: 视频 URL
            file_path: 本地视频文件路径
            output_dir: 输出目录
            skip_transcribe: 跳过语音转文字
            whisper_model: Whisper 模型大小
            scene_threshold: 场景检测阈值

        Returns:
            分析结果摘要或错误信息
        """
        if not url and not file_path:
            return "错误: 请提供 url 或 file_path 参数"

        # 检查脚本是否存在
        script = self.analyzer_script
        if not os.path.exists(script):
            return f"错误: 找不到 video_analyzer.py ({script})，请确保脚本在项目目录中"

        # 构建命令
        cmd = [sys.executable, script]

        if url:
            cmd.extend(["--url", url])
        elif file_path:
            cmd.extend(["--input", file_path])

        if output_dir:
            cmd.extend(["--output", output_dir])

        if skip_transcribe:
            cmd.append("--no-transcribe")

        if whisper_model != "base":
            cmd.extend(["--whisper-model", whisper_model])

        if scene_threshold != 30.0:
            cmd.extend(["--scene-threshold", str(scene_threshold)])

        logger.info(f"执行视频分析: {'url=' + url if url else 'file=' + file_path}")
        logger.debug(f"命令行: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200,  # 最长 2 小时
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "No module named" in stderr or "not found" in stderr:
                    return (
                        f"依赖缺失，无法完成分析。请先安装：\n"
                        f"  pip install yt-dlp opencv-python pyscenedetect easyocr faster-whisper pillow numpy\n"
                        f"  以及系统工具 ffmpeg\n\n"
                        f"详细错误: {stderr[:500]}"
                    )
                return f"分析失败 (退出码 {result.returncode}): {stderr[:1000]}"

            # 解析输出，找到报告路径
            output = result.stdout
            logger.info(f"视频分析完成，输出:\n{output[:500]}")

            # 尝试读取生成的 JSON 报告
            report_dir = output_dir or self._find_report_dir(url, file_path)
            json_path = Path(report_dir) / "analysis_data.json"
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                return self._format_report_summary(data, str(Path(report_dir) / "analysis_report.md"))

            # 返回 stdout
            return output[-3000:] if len(output) > 3000 else output

        except subprocess.TimeoutExpired:
            return "错误: 分析超时（超过 2 小时），请尝试缩短视频或使用 skip_transcribe=true"
        except FileNotFoundError as e:
            return f"错误: 找不到命令: {e}"
        except Exception as e:
            return f"错误: 视频分析执行异常: {type(e).__name__}: {e}"

    def _find_report_dir(self, url: str, file_path: str) -> str:
        """根据输入推断输出目录"""
        base = Path.cwd() / "video_analysis_output"
        if url:
            # 从 URL 提取简短标识
            import re
            match = re.search(r'v[=/]([\w-]{11})', url)
            if match:
                base = Path.cwd() / f"video_analysis_{match.group(1)}"
        return str(base)

    def _format_report_summary(self, data: dict, report_path: str) -> str:
        """
        将 JSON 报告格式化为可读摘要

        Args:
            data: JSON 分析数据
            report_path: 报告文件路径

        Returns:
            格式化的摘要字符串
        """
        lines = []
        lines.append("## 视频分析完成\n")

        # 基本信息
        probe = data.get("probe", {})
        meta = data.get("metadata", {})
        lines.append(f"- **标题**: {meta.get('title', Path(meta.get('file_path', '?')).stem)}")
        duration = probe.get("duration", 0)
        lines.append(f"- **时长**: {self._fmt_duration(duration)}")
        video_info = probe.get("video", {})
        if video_info:
            lines.append(f"- **分辨率**: {video_info.get('width', '?')}×{video_info.get('height', '?')}")
            lines.append(f"- **帧率**: {video_info.get('fps', '?')} fps")

        # 场景统计
        scenes = data.get("scenes", [])
        lines.append(f"\n- **场景数**: {len(scenes)} 个")

        # 摘要
        transcript = data.get("transcript_summary", {})
        if transcript and transcript.get("full_text_length", 0) > 0:
            lines.append(f"- **语音转文字**: {transcript.get('segment_count', 0)} 条片段, "
                         f"约 {transcript.get('full_text_length', 0)} 字 ({transcript.get('language', '?')})")

        ocr_texts = data.get("ocr_texts", [])
        if ocr_texts:
            lines.append(f"- **画面字幕（OCR）**: {len(ocr_texts)} 条")

        descs = data.get("scene_descriptions", [])
        if descs and descs[0].get("description", ""):
            lines.append(f"- **场景描述**: 已生成 {len(descs)} 个场景描述")

        # 场景时间线（前 10 个）
        if scenes:
            lines.append(f"\n### 场景时间线（前 {min(10, len(scenes))} 个）\n")
            for s in scenes[:10]:
                start = self._fmt_duration(s.get("start_sec", 0))
                end = self._fmt_duration(s.get("end_sec", 0))
                dur = self._fmt_duration(s.get("duration_sec", 0))
                lines.append(f"- `[{start} → {end}]` 时长 {dur}")

            if len(scenes) > 10:
                lines.append(f"  ... 还有 {len(scenes) - 10} 个场景")

        # 报告路径
        lines.append(f"\n📄 **完整报告**: {report_path}")
        lines.append("💡 在浏览器中打开 Markdown 文件即可查看完整分析报告")

        return "\n".join(lines)

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        """格式化时长"""
        if not seconds:
            return "?"
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

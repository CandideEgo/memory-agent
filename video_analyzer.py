#!/usr/bin/env python3
"""
=============================================
  VideoAnalyzer — 流媒体视频内容分析工具
=============================================
功能：
  - 从 YouTube / Bilibili / 等 1000+ 网站下载视频
  - 提取视频元数据（分辨率、编码、时长等）
  - 场景检测（镜头切换点）
  - 关键帧提取 + AI 场景描述
  - 字幕提取（硬字幕 OCR + 内嵌字幕）
  - 语音转文字（Whisper）
  - 生成结构化分析报告（Markdown / JSON）

用法：
  # 分析在线视频
  python video_analyzer.py --url "https://www.youtube.com/watch?v=xxx"

  # 分析本地视频文件
  python video_analyzer.py --input "path/to/video.mp4"

  # 指定输出目录
  python video_analyzer.py --url "..." --output "./my_report"

依赖安装：
  pip install yt-dlp opencv-python pillow numpy easyocr pyscenedetect faster-whisper
  # 还需要系统安装 ffmpeg
  # macOS: brew install ffmpeg
  # Ubuntu: sudo apt install ffmpeg
"""

import os, sys, json, argparse, logging, subprocess, shutil, hashlib
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# ============================================================
# 配置区（可按需修改）
# ============================================================
CONFIG = {
    "frame_interval_sec": 30,          # 每隔多少秒提取一帧做 OCR
    "scene_threshold": 30.0,           # 场景检测灵敏度（越低越敏感）
    "ocr_languages": ["ch_sim", "en"], # OCR 语言：中文+英文
    "whisper_model": "base",           # Whisper 模型: tiny/base/small/medium/large
    "max_keyframes_for_vision": 20,    # 最多送多少帧给 LLM 做场景描述
    "temp_dir": "./_temp_video_analysis",
}


# ============================================================
# 工具函数
# ============================================================
def log_setup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)

logger = log_setup()


def check_dependencies():
    """检查必需的系统工具和 Python 包"""
    missing = []

    # 检查 ffmpeg
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg (系统安装: https://ffmpeg.org/download.html)")
    if not shutil.which("ffprobe"):
        missing.append("ffprobe (通常随 ffmpeg 一起安装)")

    # 检查 Python 包
    pkgs = ["yt_dlp", "cv2", "PIL", "easyocr", "scenedetect", "whisper"]
    names = ["yt-dlp", "opencv-python", "pillow", "easyocr", "pyscenedetect", "faster-whisper"]
    for pkg, name in zip(pkgs, names):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(f"{name} (pip install {name})")

    if missing:
        logger.error("缺少以下依赖，请先安装：")
        for m in missing:
            logger.error(f"  → {m}")
        sys.exit(1)

    logger.info("✅ 所有依赖检查通过")


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def format_duration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


# ============================================================
# 第一步：下载视频
# ============================================================
class VideoDownloader:
    """使用 yt-dlp 下载视频并提取元数据"""

    @staticmethod
    def download(url: str, output_dir: str) -> dict:
        logger.info(f"📥 开始下载: {url}")

        outdir = ensure_dir(output_dir)

        ydl_opts = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "outtmpl": str(outdir / "%(title).100s.%(ext)s"),
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh-Hans", "zh", "en"],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            import yt_dlp

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # 获取实际文件路径
                video_path = None
                for f in os.listdir(outdir):
                    ext = f.rsplit(".", 1)[-1].lower()
                    if ext in ("mp4", "mkv", "webm", "avi", "mov"):
                        video_path = str(outdir / f)
                        break

                metadata = {
                    "title": info.get("title", ""),
                    "duration": info.get("duration", 0),
                    "resolution": f"{info.get('width', '?')}x{info.get('height', '?')}",
                    "fps": info.get("fps", 0),
                    "uploader": info.get("uploader", ""),
                    "description": (info.get("description", "") or "")[:500],
                    "webpage_url": info.get("webpage_url", url),
                    "subtitles": list(info.get("subtitles", {}).keys()),
                    "file_path": video_path or "",
                }

                logger.info(f"✅ 下载完成: {metadata['title']}")
                return metadata

        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            raise


# ============================================================
# 第二步：视频元数据探测
# ============================================================
class VideoProbe:
    """用 ffprobe 读取视频的详细技术信息"""

    @staticmethod
    def probe(video_path: str) -> dict:
        logger.info(f"🔍 探测视频信息: {video_path}")

        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        info = {"file_path": video_path, "file_size": os.path.getsize(video_path)}

        if "format" in data:
            fmt = data["format"]
            info["duration"] = float(fmt.get("duration", 0))
            info["bitrate"] = int(fmt.get("bit_rate", 0))
            info["format_name"] = fmt.get("format_name", "")

        for stream in data.get("streams", []):
            if stream["codec_type"] == "video":
                info["video"] = {
                    "codec": stream.get("codec_name"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "fps": eval(stream.get("r_frame_rate", "0/1")) if "/" in stream.get("r_frame_rate", "") else 0,
                    "pixel_format": stream.get("pix_fmt"),
                }
            elif stream["codec_type"] == "audio":
                info.setdefault("audio", {})["codec"] = stream.get("codec_name")
                info.setdefault("audio", {})["sample_rate"] = stream.get("sample_rate")

        logger.info(f"  时长: {format_duration(info.get('duration', 0))} | "
                     f"分辨率: {info.get('video', {}).get('width', '?')}x{info.get('video', {}).get('height', '?')}")
        return info


# ============================================================
# 第三步：场景检测
# ============================================================
class SceneDetector:
    """检测视频的镜头切换点，提取关键帧"""

    @staticmethod
    def detect(video_path: str, output_dir: str, threshold: float = 30.0) -> list:
        logger.info("🎬 开始场景检测...")
        outdir = ensure_dir(output_dir)

        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
            from scenedetect.scene_manager import save_images

            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=threshold))
            scene_manager.detect_scenes(video)
            scenes = scene_manager.get_scene_list()

            logger.info(f"  检测到 {len(scenes)} 个场景")

            # 保存每个场景的第一帧作为关键帧
            keyframes = []
            if scenes:
                save_images(
                    scenes,
                    video,
                    num_images=1,
                    output_dir=str(outdir),
                )
                # 重命名并收集文件
                for i, (start, end) in enumerate(scenes):
                    old_name = f"scene-{i:04d}.jpg"
                    old_path = outdir / old_name
                    new_name = f"scene_{i:04d}_start={start.get_timecode()}.jpg"
                    new_path = outdir / new_name
                    if old_path.exists():
                        old_path.rename(new_path)

                    keyframes.append({
                        "scene_id": i,
                        "start_sec": start.get_seconds(),
                        "end_sec": end.get_seconds(),
                        "duration_sec": end.get_seconds() - start.get_seconds(),
                        "start_timecode": start.get_timecode(),
                        "end_timecode": end.get_timecode(),
                        "keyframe_path": str(new_path) if new_path.exists() else "",
                    })

            return keyframes

        except ImportError:
            logger.warning("⚠️ PySceneDetect 未安装，使用 OpenCV 降级方案")
            return SceneDetector._fallback_detect(video_path, output_dir, threshold)

    @staticmethod
    def _fallback_detect(video_path: str, output_dir: str, threshold: float = 30.0) -> list:
        """OpenCV 降级版场景检测"""
        import cv2
        import numpy as np

        outdir = ensure_dir(output_dir)
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        scenes = []
        prev_hist = None
        scene_id = 0
        frame_idx = 0
        last_saved_frame = -9999

        logger.info("  使用 OpenCV 直方图比较法进行场景检测...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % int(fps) == 0:  # 每秒检查一次
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

                if prev_hist is not None:
                    diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                    if diff > threshold:
                        # 保存关键帧
                        sec = frame_idx / fps
                        if sec - last_saved_frame > 2:  # 至少间隔 2 秒
                            kf_path = str(outdir / f"scene_{scene_id:04d}_at_{sec:.1f}s.jpg")
                            cv2.imwrite(kf_path, frame)
                            scenes.append({
                                "scene_id": scene_id,
                                "start_sec": round(sec, 1),
                                "end_sec": None,
                                "duration_sec": None,
                                "keyframe_path": kf_path,
                            })
                            if scenes and len(scenes) > 1:
                                scenes[-2]["end_sec"] = scenes[-1]["start_sec"]
                                scenes[-2]["duration_sec"] = round(scenes[-1]["start_sec"] - scenes[-2]["start_sec"], 1)
                            scene_id += 1
                            last_saved_frame = sec

                prev_hist = hist

            frame_idx += 1

        cap.release()

        # 补上最后一个场景的结束时间
        if scenes:
            scenes[-1]["end_sec"] = round(duration, 1)
            scenes[-1]["duration_sec"] = round(duration - scenes[-1]["start_sec"], 1)

        logger.info(f"  检测到 {len(scenes)} 个场景（降级模式）")
        return scenes


# ============================================================
# 第四步：音频提取 + 语音转文字
# ============================================================
class AudioTranscriber:
    """提取音频并用 Whisper 转写为文字"""

    @staticmethod
    def transcribe(video_path: str, output_dir: str, model_size: str = "base") -> dict:
        logger.info("🎤 开始语音转文字...")
        outdir = ensure_dir(output_dir)
        audio_path = str(outdir / "audio.wav")

        # 1. 提取音频
        logger.info("  提取音频流...")
        subprocess.run([
            "ffmpeg", "-i", video_path, "-vn",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ], capture_output=True, check=True)

        # 2. Whisper 转写
        logger.info(f"  加载 Whisper 模型 ({model_size})...")
        import whisper

        model = whisper.load_model(model_size)
        logger.info("  正在转写（根据视频长度可能需要几分钟）...")

        result = model.transcribe(audio_path, language=None, verbose=False)

        # 3. 整理输出
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 1),
                "end": round(seg["end"], 1),
                "text": seg["text"].strip(),
            })

        transcript_data = {
            "language": result.get("language", "unknown"),
            "duration": round(result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0, 1),
            "segments": segments,
            "full_text": result.get("text", "").strip(),
        }

        # 保存文本
        txt_path = outdir / "transcript.txt"
        txt_path.write_text(transcript_data["full_text"], encoding="utf-8")

        # 保存 SRT 格式字幕
        srt_path = outdir / "transcript.srt"
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            srt_lines.append(str(i))
            srt_lines.append(
                f"{AudioTranscriber._srt_time(seg['start'])} --> {AudioTranscriber._srt_time(seg['end'])}"
            )
            srt_lines.append(seg["text"])
            srt_lines.append("")
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

        logger.info(f"✅ 转写完成: {len(segments)} 条片段, 语言: {transcript_data['language']}")
        return transcript_data

    @staticmethod
    def _srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ============================================================
# 第五步：字幕提取（OCR 硬字幕）
# ============================================================
class SubtitleOCR:
    """从视频帧中提取硬字幕（画面中嵌入的文字）"""

    def __init__(self, languages: list = None):
        self.languages = languages or ["ch_sim", "en"]
        self.reader = None

    def _lazy_init(self):
        if self.reader is None:
            logger.info("  加载 EasyOCR...")
            import easyocr
            self.reader = easyocr.Reader(self.languages, gpu=False)

    def extract_from_keyframes(self, keyframes: list, video_path: str, output_dir: str) -> list:
        """对关键帧底部区域做 OCR 提取字幕"""
        import cv2

        self._lazy_init()
        outdir = ensure_dir(output_dir)

        all_texts = []
        cap = cv2.VideoCapture(video_path)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        # 底部 25% 区域作为字幕区域
        roi_y1 = int(height * 0.75)

        for kf in keyframes[:50]:  # 最多处理 50 帧
            kf_path = kf.get("keyframe_path")
            if not kf_path or not os.path.exists(kf_path):
                continue

            img = cv2.imread(kf_path)
            if img is None:
                continue

            # 裁切底部区域
            roi = img[roi_y1:, :]

            # OCR
            results = self.reader.readtext(roi, paragraph=True)
            texts = [r[1] for r in results if r[2] > 0.3]  # 置信度阈值

            if texts:
                combined = " | ".join(texts)
                # 去重（相邻帧文字可能相同）
                if not all_texts or combined != all_texts[-1]["text"]:
                    all_texts.append({
                        "time_sec": kf["start_sec"],
                        "text": combined,
                        "confidence": round(sum(r[2] for r in results) / len(results), 2),
                    })

        # 保存 OCR 结果
        if all_texts:
            ocr_path = outdir / "ocr_subtitles.txt"
            lines = [f"[{t['time_sec']:.1f}s] {t['text']}" for t in all_texts]
            ocr_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"✅ OCR 提取到 {len(all_texts)} 条字幕")

        return all_texts


# ============================================================
# 第六步：AI 场景描述（使用本地 LLM 或 API）
# ============================================================
class SceneDescriber:
    """用视觉语言模型描述关键帧画面内容"""

    @staticmethod
    def describe_local(keyframes: list, max_frames: int = 20) -> list:
        """
        使用本地模型（如 Ollama + LLaVA）描述场景。
        如果没有本地模型，返回占位说明。
        """
        results = []
        for kf in keyframes[:max_frames]:
            results.append({
                "scene_id": kf["scene_id"],
                "time_sec": kf["start_sec"],
                "description": "（需配置 LLM 后自动生成场景描述）",
                "note": "支持 OpenAI GPT-4o / Ollama LLaVA / Anthropic Claude 等",
            })
        return results

    @staticmethod
    def describe_with_openai(keyframes: list, api_key: str, max_frames: int = 20) -> list:
        """使用 OpenAI API 描述场景"""
        import base64

        results = []
        for kf in keyframes[:max_frames]:
            path = kf.get("keyframe_path")
            if not path or not os.path.exists(path):
                continue

            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "用中文简洁描述这个画面：场景内容、人物、动作、画面风格"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ]
                    }],
                    max_tokens=200,
                )
                desc = resp.choices[0].message.content
            except Exception as e:
                desc = f"（描述失败: {e}）"

            results.append({
                "scene_id": kf["scene_id"],
                "time_sec": kf["start_sec"],
                "description": desc,
            })

        return results


# ============================================================
# 第七步：报告生成
# ============================================================
class ReportGenerator:
    """生成结构化的视频分析报告"""

    @staticmethod
    def generate(metadata: dict, probe: dict, scenes: list,
                 transcript: dict, ocr_texts: list, descriptions: list,
                 output_dir: str):
        outdir = ensure_dir(output_dir)

        # --- Markdown 报告 ---
        md = []
        md.append("# 视频内容分析报告\n")
        md.append(f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        # 1. 基本信息
        md.append("## 📋 基本信息\n")
        md.append(f"- **标题**: {metadata.get('title', probe.get('file_path', '未知'))}")
        md.append(f"- **时长**: {format_duration(probe.get('duration', 0))}")
        md.append(f"- **分辨率**: {probe.get('video', {}).get('width', '?')}×{probe.get('video', {}).get('height', '?')}")
        md.append(f"- **帧率**: {probe.get('video', {}).get('fps', '?')} fps")
        md.append(f"- **视频编码**: {probe.get('video', {}).get('codec', '?')}")
        md.append(f"- **音频编码**: {probe.get('audio', {}).get('codec', '?')}")
        md.append(f"- **文件大小**: {probe.get('file_size', 0) / 1024 / 1024:.1f} MB")
        if metadata.get("webpage_url"):
            md.append(f"- **来源**: [{metadata['title']}]({metadata['webpage_url']})")
        md.append("")

        # 2. 场景列表
        md.append("## 🎬 场景结构\n")
        md.append(f"共检测到 **{len(scenes)}** 个场景\n")
        md.append("| # | 时间段 | 时长 | 描述 |")
        md.append("|---|---|---|---|")

        desc_map = {d["scene_id"]: d.get("description", "") for d in descriptions}
        for s in scenes:
            sid = s["scene_id"]
            tc = f"{format_duration(s['start_sec'])} ~ {format_duration(s['end_sec'])}" if s.get('end_sec') else f"{format_duration(s['start_sec'])}"
            dur = f"{format_duration(s['duration_sec'])}" if s.get('duration_sec') else "-"
            desc = desc_map.get(sid, "")
            md.append(f"| {sid} | {tc} | {dur} | {desc[:60]}{'...' if len(desc) > 60 else ''} |")
        md.append("")

        # 3. 语音转文字
        md.append("## 📝 语音转文字\n")
        if transcript.get("full_text"):
            md.append(f"- **识别语言**: {transcript.get('language', '?')}")
            md.append(f"- **总字数**: {len(transcript.get('full_text', ''))}")
            md.append(f"- **片段数**: {len(transcript.get('segments', []))}\n")
            md.append("### 全文\n")
            md.append("```\n" + transcript["full_text"][:3000] + "\n```")
            if len(transcript["full_text"]) > 3000:
                md.append("\n*（完整文本见 transcript.txt）*\n")
        else:
            md.append("（未执行语音转写）\n")
        md.append("")

        # 4. OCR 字幕
        md.append("## 🔤 画面字幕（OCR）\n")
        if ocr_texts:
            md.append(f"提取到 {len(ocr_texts)} 条字幕：\n")
            for t in ocr_texts[:30]:
                md.append(f"- `[{t['time_sec']:.1f}s]` {t['text']}")
            if len(ocr_texts) > 30:
                md.append(f"\n*（共 {len(ocr_texts)} 条，完整见 ocr_subtitles.txt）*\n")
        else:
            md.append("（未检测到画面内嵌字幕）\n")
        md.append("")

        # 5. 场景描述
        md.append("## 🖼️ 场景描述\n")
        if descriptions and descriptions[0].get("description", "").startswith("（需配置"):
            md.append("> 💡 要启用 AI 场景描述，请配置 LLM API 密钥：\n")
            md.append("> \n")
            md.append("> ```bash\n")
            md.append("> # 使用 OpenAI\n")
            md.append("> export OPENAI_API_KEY=sk-...\n")
            md.append("> python video_analyzer.py --url \"...\" --llm openai\n")
            md.append("> \n")
            md.append("> # 或使用本地 Ollama\n")
            md.append("> # 先安装: https://ollama.com 并拉取模型: ollama pull llava\n")
            md.append("> python video_analyzer.py --url \"...\" --llm ollama\n")
            md.append("> ```\n")
        else:
            for d in descriptions:
                md.append(f"- **[{format_duration(d['time_sec'])}]** {d['description']}")
        md.append("")

        # 6. 关键词 / 标签
        md.append("## 🏷️ 智能标签\n")
        if transcript.get("full_text"):
            # 简单词频统计
            words = transcript["full_text"].split()
            freq = {}
            for w in words:
                w = w.strip(".,!?;:()[]「」『』【】《》""''...、，。！？；：").lower()
                if len(w) > 1:
                    freq[w] = freq.get(w, 0) + 1
            top = sorted(freq.items(), key=lambda x: -x[1])[:20]
            if top:
                md.append("高频词汇：\n")
                for word, count in top:
                    md.append(f"- **{word}**: {count} 次")
        md.append("")

        # 写入文件
        report_path = outdir / "analysis_report.md"
        report_path.write_text("\n".join(md), encoding="utf-8")
        logger.info(f"📄 报告已生成: {report_path}")

        # --- JSON 结构化输出 ---
        json_data = {
            "metadata": metadata,
            "probe": {k: v for k, v in probe.items() if k != "file_path"},
            "scenes": scenes,
            "transcript_summary": {
                "language": transcript.get("language", ""),
                "segment_count": len(transcript.get("segments", [])),
                "full_text_length": len(transcript.get("full_text", "")),
            } if transcript else None,
            "ocr_texts": ocr_texts[:100] if ocr_texts else [],
            "scene_descriptions": descriptions,
        }
        json_path = outdir / "analysis_data.json"
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return str(report_path)


# ============================================================
# 主流程
# ============================================================
def analyze_video(url: str = None, input_path: str = None, output_dir: str = "./video_analysis_output",
                  skip_download: bool = False, skip_transcribe: bool = False,
                  llm_backend: str = None, llm_api_key: str = None,
                  whisper_model: str = None):
    """执行完整的视频分析流水线"""

    outdir = ensure_dir(output_dir)
    temp_dir = ensure_dir(CONFIG["temp_dir"])

    probe_info = {}
    metadata = {}

    # ---- Step 1-2: 下载 + 探测 ----
    if url and not skip_download:
        metadata = VideoDownloader.download(url, str(temp_dir / "download"))
        video_path = metadata.get("file_path", "")
        if not video_path:
            for f in os.listdir(str(temp_dir / "download")):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    video_path = str(temp_dir / "download" / f)
                    break
        if not video_path:
            logger.error("❌ 找不到下载的视频文件")
            return
        probe_info = VideoProbe.probe(video_path)
    elif input_path:
        video_path = input_path
        probe_info = VideoProbe.probe(video_path)
        metadata = {"title": Path(video_path).stem}
    else:
        logger.error("请提供 --url 或 --input")
        return

    # ---- Step 3: 场景检测 ----
    scenes = SceneDetector.detect(
        video_path, str(temp_dir / "keyframes"),
        threshold=CONFIG["scene_threshold"]
    )

    # ---- Step 4: 语音转文字 ----
    transcript = {}
    if not skip_transcribe:
        try:
            model = whisper_model or CONFIG["whisper_model"]
            transcript = AudioTranscriber.transcribe(
                video_path, str(temp_dir / "transcript"), model_size=model
            )
        except Exception as e:
            logger.warning(f"⚠️ 语音转写失败: {e}，跳过此步骤")

    # ---- Step 5: OCR 字幕 ----
    ocr_texts = []
    try:
        ocr = SubtitleOCR(languages=CONFIG["ocr_languages"])
        ocr_texts = ocr.extract_from_keyframes(scenes, video_path, str(temp_dir / "ocr"))
    except Exception as e:
        logger.warning(f"⚠️ OCR 提取失败: {e}")

    # ---- Step 6: 场景描述 ----
    descriptions = []
    try:
        if llm_backend == "openai" and llm_api_key:
            descriptions = SceneDescriber.describe_with_openai(
                scenes, llm_api_key, max_frames=CONFIG["max_keyframes_for_vision"]
            )
        else:
            descriptions = SceneDescriber.describe_local(
                scenes, max_frames=CONFIG["max_keyframes_for_vision"]
            )
    except Exception as e:
        logger.warning(f"⚠️ 场景描述失败: {e}")

    # ---- Step 7: 生成报告 ----
    report_path = ReportGenerator.generate(
        metadata, probe_info, scenes, transcript, ocr_texts, descriptions, outdir
    )

    # ---- 复制关键帧到输出目录 ----
    kf_out = ensure_dir(str(outdir / "keyframes"))
    for s in scenes:
        src = s.get("keyframe_path", "")
        if src and os.path.exists(src):
            dst = str(kf_out / Path(src).name)
            shutil.copy2(src, dst)

    # ---- 清理临时文件 ----
    if os.path.exists(CONFIG["temp_dir"]):
        shutil.rmtree(CONFIG["temp_dir"], ignore_errors=True)

    logger.info(f"\n{'='*50}")
    logger.info(f"✅ 分析完成！")
    logger.info(f"📄 报告: {report_path}")
    logger.info(f"🖼️  关键帧: {str(kf_out)}/")
    logger.info(f"📝 字幕: {str(outdir / 'transcript.srt')}")
    logger.info(f"{'='*50}")

    return report_path


# ============================================================
# CLI 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="VideoAnalyzer - 流媒体视频内容分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析 YouTube 视频
  python video_analyzer.py --url "https://www.youtube.com/watch?v=xxx"

  # 分析 Bilibili 视频
  python video_analyzer.py --url "https://www.bilibili.com/video/BV1xx411c7mD"

  # 分析本地视频文件
  python video_analyzer.py --input "./my_video.mp4"

  # 跳过耗时的语音转写
  python video_analyzer.py --url "..." --no-transcribe

  # 使用 OpenAI 描述场景
  python video_analyzer.py --url "..." --llm openai --api-key "sk-..."

  # 指定输出目录
  python video_analyzer.py --url "..." --output "./my_report"
        """
    )

    parser.add_argument("--url", help="流媒体视频 URL（支持 YouTube/Bilibili 等 1000+ 网站）")
    parser.add_argument("--input", "-i", help="本地视频文件路径")
    parser.add_argument("--output", "-o", default="./video_analysis_output", help="输出目录（默认: ./video_analysis_output）")
    parser.add_argument("--no-transcribe", action="store_true", help="跳过语音转文字步骤")
    parser.add_argument("--llm", choices=["openai", "ollama", "none"], default="none", help="场景描述所用的 LLM 后端")
    parser.add_argument("--api-key", help="LLM API 密钥（使用 --llm openai 时需要）")
    parser.add_argument("--whisper-model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小（默认: base，越大越准确但越慢）")
    parser.add_argument("--check-deps", action="store_true", help="仅检查依赖不执行分析")

    args = parser.parse_args()

    if args.check_deps:
        check_dependencies()
        return

    if not args.url and not args.input:
        parser.print_help()
        print("\n⚠️  请提供 --url 或 --input 参数")
        sys.exit(1)

    analyze_video(
        url=args.url,
        input_path=args.input,
        output_dir=args.output,
        skip_transcribe=args.no_transcribe,
        llm_backend=args.llm if args.llm != "none" else None,
        llm_api_key=args.api_key,
        whisper_model=args.whisper_model,
    )


if __name__ == "__main__":
    main()

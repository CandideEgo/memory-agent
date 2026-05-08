"""Direct converter — calls translate-mcp/run_transcribe.py as isolated subprocess."""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from .base import BaseTool

logger = logging.getLogger("memory-agent.direct_video")

_CREATE_NEW_GROUP = 0x00000200


class DirectVideoTool(BaseTool):
    """Transcribe video via translate-mcp's run_transcribe.py subprocess."""

    name = "convert_video"
    description = (
        "Convert a video to transcript text. Supports local video files "
        "(.mp4, .mov, .avi, .mkv, etc.) and streaming URLs from video "
        "platforms (YouTube, Douyin, Bilibili, TikTok, etc.). "
        "Output format: [HH:MM:SS -> HH:MM:SS] <transcript text>"
    )
    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Video file path or streaming URL",
            },
        },
        "required": ["input"],
    }

    async def execute(self, input: str = "") -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, input)

    @staticmethod
    def _run(input_path: str) -> str:
        from config import settings

        python = settings.translate_mcp_command
        mcp_path = settings.translate_mcp_path
        if not python or not mcp_path:
            raise RuntimeError("TRANSLATE_MCP_COMMAND/PATH not set in .env")

        script = Path(mcp_path) / "run_transcribe.py"
        if not script.exists():
            raise RuntimeError(f"run_transcribe.py not found: {script}")

        shell_cmd = f'"{python}" "{script}" "{input_path}"'
        logger.info(f"Direct: {shell_cmd}")

        env = os.environ.copy()
        env["PYTHONPATH"] = mcp_path
        env["PYTHONIOENCODING"] = "utf-8"
        env["PATH"] = str(Path(python).parent) + os.pathsep + env.get("PATH", "")

        proc = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600,
            cwd=mcp_path,
            env=env,
            creationflags=_CREATE_NEW_GROUP if sys.platform == "win32" else 0,
            encoding="utf-8",
            errors="replace",
        )

        output = proc.stdout or ""

        start_marker = "--- TRANSCRIPT_START ---"
        end_marker = "--- TRANSCRIPT_END ---"
        if start_marker in output and end_marker in output:
            transcript = output.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
            if transcript:
                return transcript

        if output.strip() and proc.returncode != 0:
            if "[HH:MM:SS ->" in output or "[00:" in output:
                return output.strip()

        if proc.returncode != 0:
            tail = (proc.stderr or "")[-300:]
            raise RuntimeError(f"Transcription failed (exit {proc.returncode}):\n{tail}")

        return output.strip()

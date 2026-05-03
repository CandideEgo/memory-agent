"""
Shell 工具 - 执行 Shell 命令
"""

import asyncio
import logging
import shlex
from typing import Any

from ..config import ToolConfig
from .base import BaseTool

logger = logging.getLogger(__name__)


class ShellTool(BaseTool):
    """Shell 命令执行工具"""

    name = "shell"
    description = "在系统 shell 中执行命令。命令必须在白名单中，超时控制可配置。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 Shell 命令（不包括管道和重定向）"
            },
            "timeout": {
                "type": "integer",
                "description": "命令超时时间（秒），默认使用全局配置",
                "default": 30
            },
            "cwd": {
                "type": "string",
                "description": "命令执行的工作目录",
                "default": ""
            }
        },
        "required": ["command"]
    }

    def __init__(self, config: ToolConfig | None = None):
        """
        初始化 Shell 工具

        Args:
            config: 工具配置，包含白名单和超时设置
        """
        self.config = config or ToolConfig()
        self.whitelist = self.config.shell_whitelist
        self.default_timeout = self.config.shell_timeout

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """
        检查命令是否在白名单中

        Args:
            command: 原始命令

        Returns:
            (是否允许, 原因)
        """
        # 解析命令获取第一个可执行文件名
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "空命令"
            cmd_name = parts[0]
        except ValueError:
            return False, "命令解析失败"

        if cmd_name not in self.whitelist:
            return False, f"命令不在白名单中: {cmd_name}"
        return True, ""

    async def execute(self, command: str, timeout: int = 0, cwd: str = "") -> str:
        """
        执行 Shell 命令

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒），0 表示使用默认配置
            cwd: 工作目录

        Returns:
            命令输出（stdout/stderr）或错误信息
        """
        # 白名单检查
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            return f"错误: {reason}。允许的命令: {', '.join(self.whitelist)}"

        # 确定超时时间
        if timeout <= 0:
            timeout = self.default_timeout

        try:
            logger.debug(f"执行命令: {command} (超时: {timeout}s)")

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd if cwd else None
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"错误: 命令执行超时 ({timeout}秒)"

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace").strip())
            if stderr:
                output_parts.append(f"STDERR: {stderr.decode('utf-8', errors='replace').strip()}")

            if process.returncode != 0 and not output_parts:
                return f"错误: 命令执行失败 (退出码: {process.returncode})"

            result = "\n".join(output_parts) if output_parts else "(无输出)"
            logger.info(f"命令执行完成: {command} (退出码: {process.returncode})")
            return result

        except Exception as e:
            error_msg = f"错误: 命令执行失败: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return error_msg

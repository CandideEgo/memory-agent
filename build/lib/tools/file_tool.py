"""
文件工具 - 文件读写工具实现
"""

import logging
from pathlib import Path
from typing import Any

from .base import BaseTool

logger = logging.getLogger(__name__)


class FileReadTool(BaseTool):
    """文件读取工具"""

    name = "file_read"
    description = "读取文本文件的内容。如果文件不存在或无法读取则返回错误信息。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径"
            },
            "encoding": {
                "type": "string",
                "description": "文件编码，默认 utf-8",
                "default": "utf-8"
            },
            "max_length": {
                "type": "integer",
                "description": "最大读取字节数，默认读取全部",
                "default": 0
            }
        },
        "required": ["file_path"]
    }

    async def execute(self, file_path: str, encoding: str = "utf-8", max_length: int = 0) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径
            encoding: 字符编码
            max_length: 最大读取字节数，0 表示读取全部

        Returns:
            文件内容或错误信息
        """
        path = Path(file_path)

        if not path.exists():
            return f"错误: 文件不存在: {file_path}"

        if not path.is_file():
            return f"错误: 路径不是文件: {file_path}"

        try:
            with open(path, "r", encoding=encoding) as f:
                if max_length > 0:
                    content = f.read(max_length)
                else:
                    content = f.read()

            logger.info(f"成功读取文件: {file_path} ({len(content)} 字符)")
            return content
        except UnicodeDecodeError as e:
            return f"错误: 文件编码不支持 ({encoding}): {e}"
        except Exception as e:
            return f"错误: 读取文件失败: {e}"


class FileWriteTool(BaseTool):
    """文件写入工具"""

    name = "file_write"
    description = "写入文本内容到文件。如果文件所在目录不存在，会自动创建父目录。覆盖模式下会覆盖已存在文件。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要写入的文件路径"
            },
            "content": {
                "type": "string",
                "description": "要写入的文本内容"
            },
            "encoding": {
                "type": "string",
                "description": "文件编码，默认 utf-8",
                "default": "utf-8"
            },
            "append": {
                "type": "boolean",
                "description": "是否追加模式，默认为覆盖模式",
                "default": False
            }
        },
        "required": ["file_path", "content"]
    }

    async def execute(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        append: bool = False
    ) -> str:
        """
        写入文件内容

        Args:
            file_path: 文件路径
            content: 要写入的内容
            encoding: 字符编码
            append: 是否追加模式

        Returns:
            成功或错误信息
        """
        path = Path(file_path)

        try:
            # 自动创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(path, mode, encoding=encoding) as f:
                f.write(content)

            action = "追加" if append else "写入"
            logger.info(f"成功{action}文件: {file_path} ({len(content)} 字符)")
            return f"成功{action}文件: {file_path} ({len(content)} 字符)"

        except Exception as e:
            error_msg = f"错误: 写入文件失败: {e}"
            logger.error(error_msg)
            return error_msg

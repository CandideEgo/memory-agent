"""
工具基类 - 所有工具必须继承此基类
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Coroutine

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """工具基类 - 定义工具接口"""

    # 子类必须设置
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果字符串，错误时返回错误信息字符串
        """
        ...

    async def safe_execute(self, **kwargs) -> str:
        """
        安全的执行包装 - 捕获所有异常

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果或错误信息字符串
        """
        try:
            logger.debug(f"执行工具 {self.name}，参数: {kwargs}")
            result = await self.execute(**kwargs)
            logger.debug(f"工具 {self.name} 执行完成")
            return result
        except Exception as e:
            error_msg = f"工具 {self.name} 执行失败: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return f"错误: {error_msg}"

    def to_openai_tool(self) -> dict[str, Any]:
        """
        转换为 Anthropic/MiniMax 工具格式

        Returns:
            Anthropic tool schema 字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }

    def get_schema(self) -> dict[str, Any]:
        """获取工具的 JSON Schema"""
        return self.parameters

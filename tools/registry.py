"""Singleton tool registry with validation and async execution."""

import asyncio
import logging
from typing import Callable, Optional

from .base import BaseTool

logger = logging.getLogger("memory-agent.registry")


class ToolRegistry:
    """Central registry for agent tools (singleton)."""

    _instance: Optional["ToolRegistry"] = None

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_definitions(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    async def execute_async(self, name: str, params: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")
        if asyncio.iscoroutinefunction(tool.execute):
            return await tool.execute(**params)
        return await asyncio.to_thread(tool.execute, **params)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def clear(self) -> None:
        self._tools.clear()


def get_registry() -> ToolRegistry:
    return ToolRegistry.get_instance()

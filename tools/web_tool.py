"""
网页搜索工具 - 使用 DuckDuckGo API 进行搜索
"""

import logging
from typing import Any

try:
    from ..config import ToolConfig
except ImportError:
    from config import ToolConfig
try:
    from .base import BaseTool
except ImportError:
    from tools.base import BaseTool

logger = logging.getLogger(__name__)

# 尝试导入 duckduckgo_search
try:
    from duckduckgo_search import DDGS
    HAS_DUCKDKGO = True
except ImportError:
    HAS_DUCKDKGO = False


class WebSearchTool(BaseTool):
    """网页搜索工具"""

    name = "web_search"
    description = "使用 DuckDuckGo 搜索网页，返回搜索结果摘要列表。每个结果包含标题、URL和简短描述。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询词"
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数，默认5",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self, config: ToolConfig | None = None):
        """
        初始化搜索工具

        Args:
            config: 工具配置
        """
        self.config = config or ToolConfig()
        self.max_results = self.config.max_web_results
        self.timeout = self.config.web_search_timeout

    async def execute(self, query: str, max_results: int = 0) -> str:
        """
        执行网页搜索

        Args:
            query: 搜索查询词
            max_results: 最大结果数，0 表示使用配置默认值

        Returns:
            搜索结果摘要列表或错误信息
        """
        if not query or not query.strip():
            return "错误: 搜索查询不能为空"

        if max_results <= 0:
            max_results = self.max_results

        if not HAS_DUCKDKGO:
            return "错误: duckduckgo_search 库未安装。请运行: pip install duckduckgo-search"

        try:
            logger.debug(f"执行搜索: {query} (最大结果: {max_results})")

            results = []
            with DDGS(timeout=self.timeout) as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    results.append({
                        "index": i + 1,
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })

            if not results:
                return f"未找到与 '{query}' 相关的搜索结果"

            # 格式化输出
            output_lines = [f"搜索结果 ({len(results)} 条):\n"]
            for r in results:
                output_lines.append(f"{r['index']}. {r['title']}")
                output_lines.append(f"   URL: {r['url']}")
                output_lines.append(f"   摘要: {r['snippet']}")
                output_lines.append("")

            result_str = "\n".join(output_lines)
            logger.info(f"搜索完成: {query} ({len(results)} 条结果)")
            return result_str

        except Exception as e:
            error_msg = f"错误: 搜索失败: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return error_msg

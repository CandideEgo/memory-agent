"""
工具模块 - 所有内置工具的基类和具体实现
"""

try:
    from .base import BaseTool
    from .file_tool import FileReadTool, FileWriteTool
    from .mcp_tool import MCPClientTool
    from .shell_tool import ShellTool
    from .web_tool import WebSearchTool
except ImportError:
    from tools.base import BaseTool
    from tools.file_tool import FileReadTool, FileWriteTool
    from tools.mcp_tool import MCPClientTool
    from tools.shell_tool import ShellTool
    from tools.web_tool import WebSearchTool

__all__ = [
    "BaseTool",
    "FileReadTool",
    "FileWriteTool",
    "MCPClientTool",
    "ShellTool",
    "WebSearchTool",
    "get_all_tools",
]


def get_all_tools(mcp_config_path: str = ".mcp.json") -> list[BaseTool]:
    """获取所有内置工具实例"""
    return [
        FileReadTool(),
        FileWriteTool(),
        ShellTool(),
        WebSearchTool(),
        MCPClientTool(mcp_config_path=mcp_config_path),
    ]

"""
Tool module — built-in tools, registry, and schema builders.
"""

try:
    from .base import BaseTool
    from .file_tool import FileReadTool, FileWriteTool
    from .mcp_tool import MCPClientTool
    from .shell_tool import ShellTool
    from .web_tool import WebSearchTool
    from .video_tool import VideoAnalyzerTool
    from .ytdlp_tool import YtDlpTool
    from .registry import ToolRegistry, get_registry
except ImportError:
    from tools.base import BaseTool
    from tools.file_tool import FileReadTool, FileWriteTool
    from tools.mcp_tool import MCPClientTool
    from tools.shell_tool import ShellTool
    from tools.web_tool import WebSearchTool
    from tools.video_tool import VideoAnalyzerTool
    from tools.ytdlp_tool import YtDlpTool
    from tools.registry import ToolRegistry, get_registry

__all__ = [
    "BaseTool",
    "FileReadTool",
    "FileWriteTool",
    "MCPClientTool",
    "ShellTool",
    "WebSearchTool",
    "VideoAnalyzerTool",
    "YtDlpTool",
    "ToolRegistry",
    "get_registry",
    "get_all_tools",
]


def get_all_tools(mcp_config_path: str = ".mcp.json") -> list[BaseTool]:
    """Get all built-in tool instances (backward compat)."""
    return [
        FileReadTool(),
        FileWriteTool(),
        ShellTool(),
        WebSearchTool(),
        MCPClientTool(mcp_config_path=mcp_config_path),
        VideoAnalyzerTool(),
        YtDlpTool(),
    ]

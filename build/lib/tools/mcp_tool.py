"""
MCP 工具 - 调用 Model Context Protocol 服务器
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .base import BaseTool

logger = logging.getLogger(__name__)


class MCPClientTool(BaseTool):
    """MCP 工具 - 通过 stdio 调用 MCP 服务器"""

    name = "mcp_call"
    description = "调用 MCP (Model Context Protocol) 服务器上的工具。输入服务器名称、工具名称和参数。"
    parameters = {
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "MCP 服务器名称（如 translate）"
            },
            "tool": {
                "type": "string",
                "description": "要调用的 MCP 工具名称"
            },
            "arguments": {
                "type": "object",
                "description": "工具参数对象",
                "default": {}
            }
        },
        "required": ["server", "tool"]
    }

    def __init__(self, mcp_config_path: str = ".mcp.json"):
        """
        初始化 MCP 客户端工具

        Args:
            mcp_config_path: .mcp.json 配置文件路径
        """
        self.mcp_config_path = mcp_config_path
        self._servers = self._load_mcp_config()
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._request_id = 0

    def _load_mcp_config(self) -> dict[str, dict]:
        """加载 MCP 配置"""
        path = Path(self.mcp_config_path)
        if not path.exists():
            logger.warning(f"MCP 配置文件不存在: {self.mcp_config_path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            servers = config.get("mcpServers", {})
            logger.info(f"加载了 {len(servers)} 个 MCP 服务器: {list(servers.keys())}")
            return servers
        except Exception as e:
            logger.error(f"加载 MCP 配置失败: {e}")
            return {}

    def get_available_servers(self) -> list[str]:
        """获取可用的 MCP 服务器列表"""
        return list(self._servers.keys())

    def _get_next_id(self) -> int:
        """生成唯一请求 ID"""
        self._request_id += 1
        return self._request_id

    async def _ensure_server_started(self, server_name: str) -> asyncio.subprocess.Process:
        """
        确保 MCP 服务器进程已启动

        Args:
            server_name: 服务器名称

        Returns:
            服务器进程
        """
        if server_name in self._processes:
            return self._processes[server_name]

        server_config = self._servers.get(server_name)
        if not server_config:
            raise ValueError(f"MCP 服务器未配置: {server_name}")

        # 构建命令 - create_subprocess_shell 需要完整的命令字符串
        command = server_config.get("command", "")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        # 合并环境变量
        import os
        full_env = {**os.environ, **env}

        # 组装完整命令
        full_command = command
        for arg in args:
            full_command += " \"" + arg.replace("\"", "\\\"") + "\""

        # 启动进程
        logger.info(f"启动 MCP 服务器: {server_name} ({full_command})")
        process = await asyncio.create_subprocess_shell(
            full_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env
        )

        self._processes[server_name] = process
        return process

    async def _send_request(
        self,
        process: asyncio.subprocess.Process,
        method: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        发送 JSON-RPC 请求到 MCP 服务器

        Args:
            process: 服务器进程
            method: 方法名
            params: 参数

        Returns:
            响应结果
        """
        request_id = self._get_next_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # 发送请求
        request_json = json.dumps(request, ensure_ascii=False) + "\n"
        logger.debug(f"MCP 请求: {request_json[:200]}...")
        process.stdin.write(request_json.encode("utf-8"))
        await process.stdin.drain()

        # 读取响应
        response_line = await process.stdout.readline()
        if not response_line:
            stderr = await process.stderr.read()
            raise RuntimeError(f"MCP 服务器无响应: {stderr.decode('utf-8', errors='replace')}")

        response = json.loads(response_line.decode("utf-8"))
        logger.debug(f"MCP 响应: {str(response)[:200]}...")

        if "error" in response:
            raise RuntimeError(f"MCP 错误: {response['error']}")

        return response.get("result", {})

    async def _initialize_server(self, process: asyncio.subprocess.Process, server_name: str) -> dict[str, Any]:
        """
        初始化 MCP 服务器，获取服务器能力

        Args:
            process: 服务器进程
            server_name: 服务器名称

        Returns:
            服务器能力信息
        """
        return await self._send_request(process, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {
                "name": "memory-agent",
                "version": "1.0.0"
            }
        })

    async def _list_tools(self, process: asyncio.subprocess.Process) -> list[dict[str, Any]]:
        """
        获取服务器提供的工具列表

        Args:
            process: 服务器进程

        Returns:
            工具列表
        """
        result = await self._send_request(process, "tools/list", {})
        return result.get("tools", [])

    async def _call_tool(
        self,
        process: asyncio.subprocess.Process,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        调用工具

        Args:
            process: 服务器进程
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        return await self._send_request(process, "tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    async def execute(self, server: str, tool: str, arguments: dict[str, Any] = None) -> str:
        """
        执行 MCP 工具调用

        Args:
            server: MCP 服务器名称
            tool: 工具名称
            arguments: 工具参数

        Returns:
            执行结果字符串
        """
        if arguments is None:
            arguments = {}

        # 检查服务器是否配置
        if server not in self._servers:
            available = ", ".join(self.get_available_servers()) or "无"
            return f"错误: 未配置的 MCP 服务器: {server}。可用服务器: {available}"

        try:
            # 启动服务器
            process = await self._ensure_server_started(server)

            # 如果是首次调用，先初始化服务器
            if not hasattr(self, '_initialized_servers'):
                self._initialized_servers = set()

            if server not in self._initialized_servers:
                await self._initialize_server(process, server)
                self._initialized_servers.add(server)
                # 注意：不发送 notifications/initialized，有些服务器不支持

            # 调用工具
            result = await self._call_tool(process, tool, arguments)

            # 处理结果
            if isinstance(result, dict):
                # 检查是否是错误响应 (MCP 错误格式)
                if result.get("isError"):
                    error_text = ""
                    if "content" in result:
                        for c in result["content"]:
                            if c.get("type") == "text":
                                error_text = c.get("text", "")
                                break
                    return f"错误: {error_text or result.get('error', '未知错误')}"

                # 处理正常内容
                if "content" in result:
                    contents = result["content"]
                    if isinstance(contents, list):
                        output_parts = []
                        for content in contents:
                            if content.get("type") == "text":
                                output_parts.append(content.get("text", ""))
                            elif content.get("type") == "image":
                                output_parts.append(f"[图片: {content.get('data', '')[:50]}...]")
                            elif content.get("type") == "resource":
                                output_parts.append(f"[资源: {content.get('uri', '')}]")
                        return "\n".join(output_parts) or "(无输出)"
                    return str(contents)

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            error_msg = f"MCP 调用失败 ({server}/{tool}): {type(e).__name__}: {e}"
            logger.error(error_msg)
            return f"错误: {error_msg}"

    async def close(self):
        """关闭所有 MCP 服务器进程"""
        for server_name, process in self._processes.items():
            try:
                process.terminate()
                await process.wait()
                logger.info(f"MCP 服务器已关闭: {server_name}")
            except Exception as e:
                logger.error(f"关闭 MCP 服务器失败 {server_name}: {e}")
        self._processes.clear()


# 全局 MCP 工具实例（延迟初始化）
_mcp_tool_instance = None


def get_mcp_tool() -> MCPClientTool:
    """获取 MCP 工具单例"""
    global _mcp_tool_instance
    if _mcp_tool_instance is None:
        _mcp_tool_instance = MCPClientTool()
    return _mcp_tool_instance

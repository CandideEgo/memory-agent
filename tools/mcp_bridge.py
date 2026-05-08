"""MCP client bridge to translate-mcp conversion engine."""
import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import BaseTool

logger = logging.getLogger("memory-agent.mcp_client")


class MCPProxyTool(BaseTool):
    """A tool that proxies calls to a translate-mcp tool via MCPBridge."""

    def __init__(self, name: str, schema: dict, bridge: "MCPBridge"):
        self._name = name
        self._schema = schema
        self._bridge = bridge

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._schema.get("description", "")

    @property
    def parameters(self) -> dict:
        return self._schema

    async def execute(self, **kwargs) -> str:
        return await self._bridge.call_tool(self._name, kwargs)


class MCPBridge:
    """Manages a persistent MCP client session to translate-mcp via stdio."""

    def __init__(self, command: str, args: list[str]):
        self.command = command
        self.args = args
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish the MCP session (idempotent)."""
        async with self._lock:
            if self._session is not None:
                return
            self._exit_stack = AsyncExitStack()
            params = StdioServerParameters(
                command=self.command,
                args=self.args,
            )
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            read, write = transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
            logger.info("Connected to translate-mcp MCP server")

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool on translate-mcp and return its text result."""
        await self.connect()
        # Video transcription can take a long time for slow CDNs; 1 hour max
        timeout = 3600 if name in ("convert_video", "batch_convert_video") else 120
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments), timeout=timeout
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.warning(
                f"Tool {name} timed out after {timeout}s, reconnecting bridge"
            )
            await self._reset()
            raise RuntimeError(
                f"Tool '{name}' timed out after {timeout}s. "
                "The translate-mcp bridge has been reconnected. Please try again."
            )
        except Exception:
            logger.warning(
                f"Tool {name} failed, reconnecting bridge", exc_info=True
            )
            await self._reset()
            raise

        for content in result.content:
            if hasattr(content, "text"):
                return content.text
        return str(result.content[0]) if result.content else ""

    async def _reset(self) -> None:
        """Close and reopen the MCP session to recover from errors."""
        await self.close()
        self._session = None
        self._exit_stack = None
        logger.info("MCP bridge reset, will reconnect on next call")

    async def list_tools(self) -> list[dict]:
        """Fetch tool definitions from translate-mcp."""
        await self.connect()
        result = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in result.tools
        ]

    async def close(self) -> None:
        """Close the MCP session and clean up subprocess."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except BaseException as e:
                # Python 3.13 + mcp SDK on Windows: async generator cleanup
                # and cancel scope errors are harmless
                logger.debug(f"MCP cleanup (non-fatal): {type(e).__name__}")
            self._session = None
            self._exit_stack = None


_bridge: MCPBridge | None = None


def get_bridge() -> MCPBridge:
    """Get or create the global MCP bridge singleton."""
    global _bridge
    if _bridge is None:
        from config import settings

        if not settings.translate_mcp_command:
            raise RuntimeError(
                "TRANSLATE_MCP_COMMAND is not set. "
                "Configure it in .env to point to the translate-mcp Python executable."
            )
        _bridge = MCPBridge(
            command=settings.translate_mcp_command,
            args=settings.translate_mcp_args.split()
            if settings.translate_mcp_args
            else [],
        )
    return _bridge

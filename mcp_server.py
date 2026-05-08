"""
MCP Agent Server — the agent as an MCP server.

Exposes a `process_media` tool that accepts a streaming media URL,
transcribes it via translate-mcp, processes the transcript with LLM,
and saves the result to an Obsidian vault.

Usable by Claude Code, Claude Desktop, or any MCP client.
"""
import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from config import settings

logger = logging.getLogger("memory-agent.mcp")

server = Server("translate-agent")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="process_media",
            description=(
                "Process a streaming media URL (YouTube, Douyin, Bilibili, TikTok, "
                "etc.) into structured knowledge and save to Obsidian. "
                "Transcribes the video via translate-mcp, then analyzes, summarizes, "
                "and saves the result as an Obsidian note with YAML frontmatter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Streaming video URL to process",
                    },
                    "instructions": {
                        "type": "string",
                        "description": (
                            "What to do with the transcript. "
                            "Examples: 'Summarize in Chinese', "
                            "'Extract key facts and create a structured note', "
                            "'Translate to English and list main topics'"
                        ),
                        "default": "Summarize key points and extract main topics",
                    },
                    "note_title": {
                        "type": "string",
                        "description": (
                            "Title for the Obsidian note (optional; "
                            "auto-generated from video title if not provided)"
                        ),
                        "default": "",
                    },
                },
                "required": ["url"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "process_media":
        url = arguments["url"]
        instructions = arguments.get(
            "instructions", "Summarize key points and extract main topics"
        )
        note_title = arguments.get("note_title", "")

        result = await _process_media_url(url, instructions, note_title)
        return [TextContent(type="text", text=result)]

    raise ValueError(f"Unknown tool: {name}")


async def _process_media_url(
    url: str, instructions: str, note_title: str = ""
) -> str:
    """
    Core workflow: URL -> transcript -> LLM processing -> Obsidian note.

    1. Call translate-mcp's convert_video to get a timestamped transcript
    2. Build agent context with Obsidian tools + translate-mcp tools
    3. Run AgentRunner: LLM analyzes transcript and saves to Obsidian
    """
    from tools.mcp_bridge import get_bridge, MCPProxyTool
    from tools.obsidian_tool import ObsidianWriteTool
    from memory_store import MemoryStore
    from agent_runner import AgentRunner
    from context_builder import ContextBuilder
    from skills_manager import load_all_skills
    from tools.registry import get_registry

    bridge = get_bridge()
    await bridge.connect()

    # ── Step 1: Transcribe via translate-mcp ──
    logger.info(f"Fetching transcript for: {url}")
    transcript = await bridge.call_tool("convert_video", {"input": url})
    logger.info(f"Transcript obtained: {len(transcript)} chars")

    # ── Step 2: Register tools ──
    registry = get_registry()
    registry.clear()
    registry.register(ObsidianWriteTool())

    # Register translate-mcp tools so the LLM can fetch additional context
    mcp_tool_defs = await bridge.list_tools()
    for td in mcp_tool_defs:
        t = MCPProxyTool(td["name"], td.get("inputSchema", {}), bridge)
        registry.register(t)

    # ── Step 3: Build agent context ──
    skills = load_all_skills()
    skills_text = "\n".join(
        f"- {s.name}: {s.trigger or 'always active'}" for s in skills
    )

    memory = MemoryStore()
    ctx_builder = ContextBuilder()

    system_prompt = ctx_builder.build(
        long_term_memory=memory.read_long_term(),
        skills_summary=skills_text,
    )

    # ── Step 4: Craft the user message ──
    title_hint = f' Save the note with title: "{note_title}".' if note_title else ""
    user_msg = (
        f"Process this video transcript and save it to Obsidian.\n\n"
        f"Instructions: {instructions}.{title_hint}\n\n"
        f"## Transcript\n\n{transcript}"
    )
    memory.add("user", user_msg)

    # ── Step 5: Run the agent ──
    runner = AgentRunner()
    response = await runner.run(memory, system_prompt)

    # ── Step 6: Compact memory if needed ──
    if memory.should_compact():
        from compactor import compact
        await compact(memory, ctx_builder)

    return response


async def main() -> None:
    """Run the translate-agent MCP server with stdio transport."""
    from config import validate_env

    validate_env()

    if not settings.obsidian_vault_path:
        logger.warning(
            "OBSIDIAN_VAULT_PATH is not set. "
            "The agent can process media but cannot save to Obsidian."
        )

    init_options = server.create_initialization_options()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options=init_options,
        )


if __name__ == "__main__":
    asyncio.run(main())

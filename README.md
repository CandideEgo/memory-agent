# memory-agent

Modular AI Agent framework with ReAct (Reasoning + Acting) pattern, persistent memory, dynamic skill system, and MCP (Model Context Protocol) integration.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install .
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required environment variables:
- `ANTHROPIC_API_KEY` - API key for LLM calls (MiniMax Claude-compatible)
- `ANTHROPIC_BASE_URL` - (optional) defaults to `https://api.minimaxi.com/anthropic`
- `ANTHROPIC_MODEL` - (optional) defaults to `MiniMax-M2.7`

Optional MCP and Obsidian variables:
- `TRANSLATE_MCP_COMMAND` / `TRANSLATE_MCP_ARGS` / `TRANSLATE_MCP_PATH` - MCP bridge for video transcription
- `OBSIDIAN_VAULT_PATH` - Obsidian vault path for note persistence

### 3. Run

```bash
# Interactive REPL (default)
python main.py

# One-shot task
python main.py --cli --task "What is Python?"

# Web UI
python main.py --web

# MCP server mode (for Claude Code / Claude Desktop)
python main.py --mcp

# Diagnostics
python main.py --doctor
```

## Architecture

```
main.py                     # Entry point (REPL, web, MCP, CLI dispatch)
├── agent_runner.py         # Multi-turn tool-calling loop with Anthropic SDK
├── agent_loop.py           # Orchestration layer (session management, compaction)
├── config.py               # Pydantic settings — .env, LLM, tools, paths
├── context_builder.py      # Jinja2 system prompt assembly
├── errors.py               # Structured exception hierarchy
├── llm_client.py           # Anthropic SDK client with retry logic
├── logging_config.py       # Structured logging setup
├── memory_store.py         # Three-layer memory (working, episodic, long-term)
├── compactor.py            # LLM-driven history compression
├── skills_manager.py       # Dynamic skill loading from skills/ directory
├── repl.py                 # Interactive REPL with session management
├── mcp_server.py           # MCP server exposing process_media tool
├── web.py                  # FastAPI web server with WebSocket streaming
├── tools/                  # Tool implementations
│   ├── base.py             # BaseTool abstract class
│   ├── shell_tool.py       # Shell command execution (whitelist + exec)
│   ├── web_tool.py         # Web search via DuckDuckGo
│   ├── mcp_tool.py         # MCP client tool
│   ├── mcp_bridge.py       # MCP stdio bridge to external servers
│   ├── obsidian_tool.py    # Obsidian vault integration
│   ├── registry.py         # Singleton tool registry
│   └── ...
└── skills/                 # Dynamic skill definitions (SKILL.md files)
```

## Key Design Patterns

**Tool System:** All tools inherit from `BaseTool` and implement `execute()`. Tools are registered in `ToolRegistry` and exposed to the LLM via Anthropic tool schemas.

**Agent Loop:** `AgentRunner.run()` implements the ReAct loop:
1. Build system prompt with skills + memory summary + tool schemas
2. Call LLM with user task
3. Parse response for tool calls or final answer
4. Execute tools in parallel, collect results
5. Loop until final answer or max iterations reached

**Memory:** Three-layer memory system in `MemoryStore`:
- Working memory (conversation turns, auto-compacted)
- Episodic memory (daily summaries in `memory/YYYY-MM-DD.md`)
- Long-term memory (`memory/MEMORY.md`)

**Skills:** Loaded from `skills/` directory. Each skill is a directory containing `SKILL.md` with instructions injected into the system prompt.

**MCP Integration:** `mcp_bridge.py` connects to external MCP servers via stdio transport, proxying their tools for agent use.

## Adding a New Tool

Inherit from `BaseTool`:

```python
from tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "My custom tool"
    parameters = {
        "type": "object",
        "properties": {...},
        "required": [...]
    }

    async def execute(self, **kwargs) -> str:
        return "result"
```

Register it via `get_registry().register(MyTool())`.

## Adding a New Skill

Create a directory under `skills/` with a `SKILL.md` file:

```markdown
---
name: my-skill
description: A short description
---
Detailed instructions for the LLM...
```

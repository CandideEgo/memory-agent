# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Project Overview

Memory-Agent is a modular AI Agent framework implementing the ReAct (Reasoning + Acting) pattern with tool-use capabilities. It features a dynamic skill system, memory persistence, and MCP (Model Context Protocol) integration.

## Commands

```bash
# Interactive CLI mode
python main.py

# Web server mode
python main.py --web
# or: memory-agent --web (after pip install -e .)

# Demo mode
python main.py --demo

# Single task mode
python main.py --task "your task here"

# Run specific test (if tests exist)
pytest tests/test_xxx.py -v
```

**Required Environment Variables:**
- `ANTHROPIC_AUTH_TOKEN` - API key for LLM calls
- `ANTHROPIC_BASE_URL` - (optional) API endpoint, defaults to `https://api.minimaxi.com/anthropic`
- `ANTHROPIC_MODEL` - (optional) model name, defaults to `MiniMax-M2.7`

## Architecture

```
main.py                    # Entry point (CLI vs web mode)
├── agent.py               # Core Agent class + ToolRunner
├── config.py              # Configuration dataclasses
├── memory.py              # JSON-based conversation memory
├── skills_manager.py      # Dynamic skill loading from skills/
├── web.py                 # FastAPI web server
├── cli/__main__.py        # CLI commands + run_web()
├── tools/                 # Tool implementations
│   ├── base.py            # BaseTool abstract class
│   ├── file_tool.py       # FileReadTool, FileWriteTool
│   ├── shell_tool.py      # ShellTool (whitelist-based)
│   ├── web_tool.py        # WebSearchTool (DuckDuckGo)
│   └── mcp_tool.py        # MCPClientTool (MCP protocol)
└── skills/                # Dynamic skill definitions (SKILL.md files)
```

## Key Design Patterns

**Tool System:** All tools inherit from `BaseTool` and implement `execute()`. Tools are registered in `ToolRunner` and exposed to the LLM via OpenAI/Anthropic tool schemas.

**Agent Loop:** The Agent.run() method implements the ReAct loop:
1. Build system prompt with skills + memory summary + tool schemas
2. Call LLM with user task
3. Parse response for `tool_call` or `final_answer`
4. Execute tools, collect observations
5. Loop until final_answer or max_iterations reached

**Memory:** Conversation history stored in `memory.json` with message roles (user/assistant/system/tool) and arbitrary state key-value store.

**Skills:** Loaded from `skills/` directory on demand. Each skill is a directory containing `SKILL.md` with instructions that get injected into the system prompt.

**MCP Integration:** MCPClientTool connects to MCP servers via `.mcp.json` config, allowing dynamic tool discovery.

## Configuration

All config is in `config.py` using dataclasses:
- `LLMConfig`: model, api_key, base_url, temperature, max_tokens
- `AgentConfig`: max_iterations, memory_file, skills_dir, mcp_config_path
- `ToolConfig`: shell_timeout, shell_whitelist, web_search_timeout

Config is loaded via `Config.from_env()` which reads environment variables.

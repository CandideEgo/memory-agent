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

Memory-Agent is a modular AI Agent framework implementing the ReAct (Reasoning + Acting) pattern. It uses the Anthropic SDK for LLM calls and supports MCP (Model Context Protocol) for tool integration.

## Commands

```bash
# Interactive REPL (default)
python main.py

# Web server mode (FastAPI + WebSocket)
python main.py --web

# MCP server mode (for Claude Code / Claude Desktop)
python main.py --mcp

# Diagnostics — validates config, LLM, MCP bridge, Obsidian, skills
python main.py --doctor

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_config.py -v

# Verify imports
python -c "import main; print('OK')"
```

**Required environment variables:**
- `ANTHROPIC_API_KEY` — API key for LLM calls (MiniMax Claude-compatible)
- `ANTHROPIC_BASE_URL` — (optional) defaults to `https://api.minimaxi.com/anthropic`
- `ANTHROPIC_MODEL` — (optional) defaults to `MiniMax-M2.7`

**Optional:**
- `OBSIDIAN_VAULT_PATH` — enables Obsidian note persistence
- `TRANSLATE_MCP_COMMAND` / `TRANSLATE_MCP_ARGS` / `TRANSLATE_MCP_PATH` — video transcription bridge

## Architecture

The request flow through the system:

```
Entry (main.py)
  ├── REPL (repl.py) ─── agent_loop.py ─── agent_runner.py ─── llm_client.py
  ├── Web  (web.py)    ─┘                    │
  ├── MCP  (mcp_server.py)                   │
  └── CLI  (cli/__main__.py)                 │
                                       tools/registry.py
                                       tools/base.py → tool implementations
                                       tools/mcp_bridge.py → external MCP servers
                                       memory_store.py (working → episodic → long-term)
                                       compactor.py (LLM-driven history compression)
                                       context_builder.py (Jinja2 templates)
```

**Core modules:**
- `agent_runner.py` — Multi-turn tool-calling loop. Calls LLM, parses tool requests, executes tools in parallel via `asyncio.gather()`, returns results. Individual tool failures produce error result dicts instead of crashing the conversation.
- `agent_loop.py` — Orchestration layer: session management, compaction triggers, skill loading.
- `memory_store.py` — Three-layer memory: working (current conversation), episodic (daily `memory/YYYY-MM-DD.md`), long-term (`memory/MEMORY.md`). Uses `filelock` for concurrent safety.
- `context_builder.py` — Assembles system prompt from Jinja2 templates, skills summary, long-term memory, and tool schemas.
- `compactor.py` — Summarizes old conversation turns via LLM and writes to episodic/long-term memory. Protected by `threading.Lock`.
- `errors.py` — Exception hierarchy: `AgentError` base → `ToolExecutionError`, `LLMRateLimitError`, `ConfigurationError`, `APIError`.
- `llm_client.py` — Anthropic SDK wrapper with retry logic (rate limit backoff, connection retry).
- `logging_config.py` — Structured JSON logging with request correlation IDs via `contextvars`.

## Key Design Patterns

**Tool System:** All tools inherit `BaseTool` (name, description, parameters, async execute). Registered in `ToolRegistry` singleton via `get_registry()`. Tool schemas are auto-generated for the Anthropic API.

**Agent Loop (AgentRunner.run()):**
1. Build system prompt via `ContextBuilder`
2. Call LLM with conversation history + tools
3. If `response.stop_reason == "tool_use"`: execute tools in parallel via `asyncio.gather()`, append results to memory, loop
4. If `response.stop_reason == "end_turn"`: return text response

**Error handling:** Tool failures return `{"is_error": true}` result dicts rather than raising exceptions, so one tool failure doesn't discard other tools' results. API errors raise typed exceptions (`APIError`, `LLMRateLimitError`).

**Graceful shutdown:** SIGTERM/SIGINT handlers in repl.py, mcp_server.py, and web.py save state and clean up connections before exit.

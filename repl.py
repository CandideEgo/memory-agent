"""
Interactive REPL agent — long-running process with persistent sessions.

Startup sequence:
  1. Validate .env and create directories
  2. Connect to translate-mcp via MCP stdio bridge
  3. Register ObsidianWriteTool + translate-mcp proxy tools
  4. Load skills and enter REPL loop

Usage:
    python -m repl
"""

import asyncio
import atexit
import logging
import os
import sys
from pathlib import Path

# ── UTF-8 on Windows ────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

# ── Readline setup (persistent history) ─────────────────────────
try:
    import readline

    _HISTORY_FILE = Path.home() / ".translate-agent-history"
    _HISTORY_SIZE = 1000

    def _load_history() -> None:
        if _HISTORY_FILE.exists():
            readline.read_history_file(str(_HISTORY_FILE))

    def _save_history() -> None:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        readline.set_history_length(_HISTORY_SIZE)
        readline.write_history_file(str(_HISTORY_FILE))

    atexit.register(_save_history)
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

    def _load_history() -> None:
        pass

    def _save_history() -> None:
        pass


# ── ANSI helpers (no external deps) ─────────────────────────────

class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @staticmethod
    def bold(text: str) -> str:
        return f"{Style.BOLD}{text}{Style.RESET}"

    @staticmethod
    def dim(text: str) -> str:
        return f"{Style.DIM}{text}{Style.RESET}"

    @staticmethod
    def red(text: str) -> str:
        return f"{Style.RED}{text}{Style.RESET}"

    @staticmethod
    def green(text: str) -> str:
        return f"{Style.GREEN}{text}{Style.RESET}"

    @staticmethod
    def yellow(text: str) -> str:
        return f"{Style.YELLOW}{text}{Style.RESET}"

    @staticmethod
    def blue(text: str) -> str:
        return f"{Style.BLUE}{text}{Style.RESET}"

    @staticmethod
    def cyan(text: str) -> str:
        return f"{Style.CYAN}{text}{Style.RESET}"

    @staticmethod
    def magenta(text: str) -> str:
        return f"{Style.MAGENTA}{text}{Style.RESET}"


# ── Spinner frames for progress indication ──────────────────────
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# Logging: human-readable console, JSON + errors to files
from logging_config import setup_logging
setup_logging(level="WARNING", log_dir=Path("./logs"), json_file=True)

logger = logging.getLogger("memory-agent.repl")
logger.setLevel(logging.INFO)

# Our key loggers at INFO for progress visibility
logging.getLogger("memory-agent.runner").setLevel(logging.INFO)
logging.getLogger("memory-agent.mcp_client").setLevel(logging.INFO)


WELCOME = f"""
{Style.bold(Style.cyan('╔══════════════════════════════════════════════════╗'))}
{Style.bold(Style.cyan('║'))}    {Style.bold('memory-agent')} — Knowledge Agent {Style.dim('v1.0')}    {Style.bold(Style.cyan('║'))}
{Style.bold(Style.cyan('╠══════════════════════════════════════════════════╣'))}
{Style.bold(Style.cyan('║'))}  {Style.dim('Chat naturally. Paste a URL to process media.')}  {Style.bold(Style.cyan('║'))}
{Style.bold(Style.cyan('║'))}  {Style.dim('/help for commands')}                             {Style.bold(Style.cyan('║'))}
{Style.bold(Style.cyan('╚══════════════════════════════════════════════════╝'))}
"""

SHORT_HELP = f"""
{Style.bold('Commands:')}
  {Style.green('/help')}       Show this help
  {Style.green('/memory')}     Session memory stats
  {Style.green('/clear')}      Clear working memory
  {Style.green('/sessions')}   List all sessions
  {Style.green('/switch')} id  Switch session (prefix match)
  {Style.green('/new')}        Start a fresh session
  {Style.green('/episodic')}   Show today's episodic memory
  {Style.green('/longterm')}   Show long-term memory
  {Style.green('/skills')}     List available skills
  {Style.green('/save')} title Save session context as note
  {Style.green('/resume')}     Resume a previously saved session
  {Style.green('/status')}     System status overview
  {Style.green('/exit')}       Save session & shutdown
"""


async def async_input(prompt: str = "") -> str:
    """Non-blocking async wrapper around input()."""
    return await asyncio.get_event_loop().run_in_executor(None, input, prompt)


class AgentREPL:
    """Interactive REPL for the memory-agent."""

    def __init__(self):
        self.agent = None
        self.bridge = None
        self.current_session: str | None = None
        self.running = False
        self._start_time = None

    async def startup(self) -> None:
        """Initialize all subsystems."""
        import time
        from config import validate_env, settings
        from tools.registry import get_registry
        from tools.obsidian_tool import ObsidianWriteTool
        from tools.mcp_bridge import get_bridge, MCPProxyTool
        from tools.direct_video_tool import DirectVideoTool
        from skills_manager import load_all_skills
        from agent_loop import AgentLoop

        self._start_time = time.time()

        # 1. Validate environment
        print(f"{Style.dim('Initializing...')}")
        warnings = validate_env()
        for w in warnings:
            print(f"  {Style.yellow('⚠')} {w}")
        logger.info("Configuration loaded")

        # 2. Connect to translate-mcp (web/file/image tools)
        print(f"  {Style.dim('Connecting to translate-mcp...')}", end="", flush=True)
        self.bridge = get_bridge()
        await self.bridge.connect()
        print(f"\r  {Style.green('✓')} translate-mcp connected  ")

        # 3. Register tools — video goes direct, rest via MCP
        registry = get_registry()
        registry.clear()
        registry.register(ObsidianWriteTool())
        registry.register(DirectVideoTool())

        mcp_tools = await self.bridge.list_tools()
        for td in mcp_tools:
            if td["name"] in ("convert_video", "batch_convert_video"):
                continue  # DirectVideoTool handles these
            t = MCPProxyTool(td["name"], td.get("inputSchema", {}), self.bridge)
            registry.register(t)

        tool_names = registry.list_tools()
        tools_str = ", ".join(tool_names)
        print(f"  {Style.green('✓')} {len(tool_names)} tools: {Style.dim(tools_str)}")

        # 4. Load skills
        skills = load_all_skills()
        if skills:
            skills_str = ", ".join(s.name for s in skills)
            print(f"  {Style.green('✓')} {len(skills)} skills: {Style.dim(skills_str)}")
        else:
            print(f"  {Style.yellow('⚠')} No skills loaded")

        # 5. Create AgentLoop
        self.agent = AgentLoop()
        logger.info("Agent initialized")

        # 6. Load readline history
        _load_history()

        # 7. Print welcome
        print(WELCOME)
        print(f"  Vault:   {Style.cyan(settings.obsidian_vault_path or '(not set)')}")
        print(f"  Model:   {Style.cyan(settings.anthropic_model)}")
        print(f"  Session: {Style.dim('new (start chatting to create)')}")
        print()

    async def shutdown(self) -> None:
        """Graceful shutdown with session persistence."""
        print(f"\n{Style.dim('Shutting down...')}")
        _save_history()

        # Save all active sessions
        if self.agent and self.agent.sessions:
            saved = 0
            for sid, mem in self.agent.sessions.items():
                if mem.working:
                    try:
                        mem.save_session(sid)
                        saved += 1
                    except Exception as e:
                        logger.warning(f"Failed to save session {sid[:8]}: {e}")
            if saved:
                print(
                    f"  {Style.green('✓')} {saved} session(s) saved to "
                    f"{Style.dim('memory/sessions/')}"
                )

        if self.bridge:
            await self.bridge.close()
            logger.info("translate-mcp bridge closed")

        # Session summary
        if self.agent and self.agent.sessions:
            total_msgs = sum(len(m.working) for m in self.agent.sessions.values())
            print(
                f"{Style.dim(f'Sessions: {len(self.agent.sessions)} | '
                             f'Messages: {total_msgs}')}"
            )

        self.running = False

    # ═══════════════════════════════════════════════════════════
    # Slash command handlers
    # ═══════════════════════════════════════════════════════════

    async def _cmd_help(self, _args: str) -> None:
        print(SHORT_HELP)

    async def _cmd_status(self, _args: str) -> None:
        """System status overview."""
        import time
        from config import settings
        from tools.registry import get_registry

        uptime = time.time() - (self._start_time or time.time())
        mins, secs = divmod(int(uptime), 60)

        registry = get_registry()
        n_tools = len(registry.list_tools())
        n_sessions = len(self.agent.sessions) if self.agent else 0

        memory = None
        if self.current_session and self.agent and self.current_session in self.agent.sessions:
            memory = self.agent.sessions[self.current_session]

        lines = [
            f"{Style.bold('System Status')}",
            f"  Uptime:    {mins}m {secs}s",
            f"  Sessions:  {n_sessions} active",
            f"  Tools:     {n_tools} registered",
            f"  Vault:     {settings.obsidian_vault_path or Style.yellow('(not set)')}",
            f"  Model:     {settings.anthropic_model}",
        ]
        if memory:
            tokens = memory.estimate_tokens()
            pct = tokens / memory.compaction_threshold * 100
            lines.append(f"  Memory:    ~{tokens:,} tokens ({pct:.1f}% of threshold)")

        print("\n".join(lines))

    async def _cmd_memory(self, _args: str) -> None:
        if not self.current_session or not self.agent or self.current_session not in self.agent.sessions:
            print(Style.yellow("No active session. Start chatting first."))
            return
        memory = self.agent.sessions[self.current_session]
        turns = len(memory.working)
        tokens = memory.estimate_tokens()
        threshold = memory.compaction_threshold
        pct = tokens / threshold * 100

        bar_width = 30
        filled = int(bar_width * min(pct / 100, 1.0))
        bar = f"[{Style.green('█' * filled)}{Style.dim('░' * (bar_width - filled))}]"

        print(f"  Session:  {Style.cyan(self.current_session[:12])}...")
        print(f"  Messages: {turns} turns")
        print(f"  Memory:   {bar} ~{tokens:,} / {threshold:,} ({pct:.1f}%)")
        if pct > 70:
            print(f"  {Style.yellow('⚠ Approaching compaction threshold')}")

    async def _cmd_clear(self, _args: str) -> None:
        if not self.current_session or not self.agent or self.current_session not in self.agent.sessions:
            print(Style.yellow("No active session."))
            return
        self.agent.sessions[self.current_session].clear_working()
        print(f"{Style.green('✓')} Working memory cleared.")

    async def _cmd_sessions(self, _args: str) -> None:
        if not self.agent or not self.agent.sessions:
            print(f"{Style.dim('No sessions. Start a chat to create one.')}")
            return
        print(f"\n{Style.bold('Active Sessions:')}")
        for sid, mem in self.agent.sessions.items():
            marker = f" {Style.green('← current')}" if sid == self.current_session else ""
            short_id = sid[:12]
            n_msgs = len(mem.working)
            tokens = mem.estimate_tokens()
            print(f"  {Style.cyan(short_id)}...  {n_msgs:>3} msgs  ~{tokens:>6,} tokens{marker}")

    async def _cmd_switch(self, args: str) -> None:
        prefix = args.strip()
        if not prefix:
            print(f"Usage: {Style.dim('/switch <session-id-prefix>')}")
            return
        matches = [sid for sid in self.agent.sessions if sid.startswith(prefix)]
        if not matches:
            print(Style.yellow(f"No session matching '{prefix}'"))
            return
        if len(matches) > 1:
            print(f"{Style.yellow('Multiple matches:')}")
            for m in matches:
                print(f"  {m}")
            return
        self.current_session = matches[0]
        turns = len(self.agent.sessions[self.current_session].working)
        print(f"{Style.green('✓')} Switched to {Style.cyan(self.current_session[:12])}... ({turns} msgs)")

    async def _cmd_new(self, _args: str) -> None:
        self.current_session = None
        print(f"{Style.green('✓')} New session on next message.")

    async def _cmd_episodic(self, _args: str) -> None:
        from memory_store import _today_path
        path = _today_path()
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if content.strip():
                print(f"\n{Style.bold('Today')} ({path.name}):\n")
                print(content[:3000])
                return
        print(Style.dim("No episodic memory for today."))

    async def _cmd_longterm(self, _args: str) -> None:
        from memory_store import _LONG_TERM_PATH
        if _LONG_TERM_PATH.exists():
            content = _LONG_TERM_PATH.read_text(encoding="utf-8")
            if content.strip():
                print(f"\n{Style.bold('Long-term Memory:')}\n")
                print(content[:3000])
                return
        print(Style.dim("No long-term memory yet."))

    async def _cmd_skills(self, _args: str) -> None:
        from skills_manager import load_all_skills
        skills = load_all_skills()
        if not skills:
            print(Style.dim("No skills loaded."))
            return
        print(f"\n{Style.bold('Available Skills:')}")
        for s in skills:
            trigger = s.trigger or "always active"
            print(f"  {Style.green(s.name):<30} {Style.dim(trigger)}")

    async def _cmd_save(self, args: str) -> None:
        title = args.strip()
        if not title:
            print(f"Usage: {Style.dim('/save <note-title>')}")
            return
        if not self.current_session or not self.agent or self.current_session not in self.agent.sessions:
            print(Style.yellow("No active session to save."))
            return
        memory = self.agent.sessions[self.current_session]
        parts = []
        for i, m in enumerate(memory.working):
            role = m["role"].upper()
            content = m.get("content", "")
            if len(content) > 800:
                content = content[:800] + "..."
            parts.append(f"## {role} (turn {i + 1})\n\n{content}")
        full = "\n\n".join(parts)

        from tools.obsidian_tool import ObsidianWriteTool
        tool = ObsidianWriteTool()
        result = tool.execute(title=title, content=full, tags="session-log")
        print(f"{Style.green('✓')} {result}")

    async def _cmd_resume(self, _args: str) -> None:
        """List saved sessions available for resume."""
        from memory_store import MemoryStore
        saved = MemoryStore.list_saved_sessions()
        if not saved:
            print(Style.dim("No saved sessions."))
            return
        print(f"\n{Style.bold('Saved Sessions:')}")
        for s in saved:
            sid = s["session_id"]
            saved_at = s.get("saved_at", "")[:19]
            n = s.get("messages", 0)
            is_active = sid in (self.agent.sessions if self.agent else {})
            marker = f" {Style.green('active')}" if is_active else ""
            print(
                f"  {Style.cyan(sid[:12])}...  {n:>3} msgs  "
                f"{Style.dim(saved_at)}{marker}"
            )
        print(f"\n  To restore a session: {Style.dim('/switch <id-prefix>')} "
              f"then start chatting — it will re-use the previous session ID.\n"
              f"  Or type {Style.dim('/resume-session <id-prefix>')} to load from disk.")

    async def _cmd_resume_session(self, args: str) -> None:
        """Load a saved session from disk."""
        prefix = args.strip()
        if not prefix:
            print(f"Usage: {Style.dim('/resume-session <id-prefix>')}")
            return
        from memory_store import MemoryStore
        saved = MemoryStore.list_saved_sessions()
        matches = [s for s in saved if s["session_id"].startswith(prefix)]
        if not matches:
            print(Style.yellow(f"No saved session matching '{prefix}'"))
            return
        sid = matches[0]["session_id"]
        # Create or reuse session
        _, memory = self.agent.get_session(sid)
        n = memory.load_session(sid)
        self.current_session = sid
        print(
            f"{Style.green('✓')} Restored {Style.cyan(sid[:12])}... "
            f"({n} messages)"
        )

    async def _cmd_exit(self, _args: str) -> None:
        self.running = False

    # ═══════════════════════════════════════════════════════════
    # Main loop
    # ═══════════════════════════════════════════════════════════

    async def run(self) -> None:
        """Main REPL loop."""
        await self.startup()
        self.running = True
        turn_count = 0

        while self.running:
            try:
                prompt = f"{Style.green('▸')} "
                line = await async_input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                await self.shutdown()
                return

            line = line.strip()
            if not line:
                continue

            # Slash commands
            if line.startswith("/"):
                parts = line.split(" ", 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                handlers = {
                    "/help": self._cmd_help,
                    "/memory": self._cmd_memory,
                    "/clear": self._cmd_clear,
                    "/sessions": self._cmd_sessions,
                    "/switch": self._cmd_switch,
                    "/new": self._cmd_new,
                    "/episodic": self._cmd_episodic,
                    "/longterm": self._cmd_longterm,
                    "/skills": self._cmd_skills,
                    "/save": self._cmd_save,
                    "/resume": self._cmd_resume,
                    "/resume-session": self._cmd_resume_session,
                    "/status": self._cmd_status,
                    "/exit": self._cmd_exit,
                    "/quit": self._cmd_exit,
                }

                handler = handlers.get(cmd)
                if handler:
                    try:
                        await handler(args)
                    except Exception as e:
                        logger.error(f"Command error: {e}", exc_info=True)
                        print(Style.red(f"Error: {e}"))
                    if not self.running:
                        await self.shutdown()
                        return
                else:
                    print(Style.yellow(f"Unknown command: {cmd}. /help for commands."))
                continue

            # ── Normal chat ──
            turn_count += 1
            try:
                # Progress spinner
                spinner_task = asyncio.create_task(self._show_spinner())

                response, sid = await self.agent.chat(
                    line, session_id=self.current_session
                )
                self.current_session = sid

                spinner_task.cancel()
                try:
                    await spinner_task
                except asyncio.CancelledError:
                    pass

                # Clear spinner and print response
                print(f"\r{' ' * 30}\r", end="")
                print(f"\n{response}\n")

            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                print(f"\r{' ' * 30}\r", end="")
                print(f"\n{Style.red('Error:')} {e}\n")

        # End of loop
        await self.shutdown()

    async def _show_spinner(self) -> None:
        """Show a spinning progress indicator while the agent thinks."""
        import time
        i = 0
        start = time.time()
        while True:
            elapsed = time.time() - start
            frame = SPINNER[i % len(SPINNER)]
            print(f"\r  {Style.cyan(frame)} thinking... {Style.dim(f'{elapsed:.0f}s')}", end="", flush=True)
            i += 1
            await asyncio.sleep(0.1)


async def main() -> None:
    """Entry point for python -m repl"""
    repl = AgentREPL()
    await repl.run()


if __name__ == "__main__":
    asyncio.run(main())

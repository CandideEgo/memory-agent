"""
memory-agent — Knowledge Agent Framework

Usage:
    python main.py              Interactive REPL (default)
    python main.py --web        Web UI
    python main.py --cli        Legacy CLI mode
    python main.py --mcp        MCP server mode (for Claude Code)
"""

import sys
import asyncio
from pathlib import Path

def main():
    """Synchronous entry point for console_scripts."""
    from repl import main as repl_main
    asyncio.run(repl_main())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.absolute()))
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--doctor":
            from config import validate_env, ConfigError
            from tools.registry import get_registry
            from pathlib import Path as P

            print("Running diagnostics...")
            errors = []

            # Token check
            try:
                from config import settings
                if not settings.anthropic_api_key:
                    errors.append("ANTHROPIC_API_KEY is not set")
            except ConfigError as e:
                errors.append(str(e))

            # LLM API connectivity
            try:
                from llm_client import get_client
                client = get_client()
                print("  LLM client initialized")
            except Exception as e:
                errors.append(f"LLM client failed: {e}")

            # MCP bridge
            try:
                from config import settings
                if settings.translate_mcp_command:
                    print(f"  MCP command configured: {settings.translate_mcp_command}")
                else:
                    print("  MCP bridge not configured (video transcription unavailable)")
            except Exception as e:
                errors.append(f"MCP config error: {e}")

            # Obsidian vault
            try:
                from config import settings
                vault = P(settings.obsidian_vault_path) if settings.obsidian_vault_path else None
                if vault:
                    if vault.exists():
                        print(f"  Obsidian vault found: {vault}")
                    else:
                        errors.append(f"Obsidian vault not found: {vault}")
                else:
                    print("  Obsidian vault not configured")
            except Exception as e:
                errors.append(f"Obsidian config error: {e}")

            # Skills directory
            try:
                from config import settings
                skills = P(__file__).parent / settings.skills_dir
                if skills.exists():
                    skill_files = list(skills.glob("*/SKILL.md"))
                    print(f"  Skills directory exists ({len(skill_files)} skills)")
                else:
                    errors.append(f"Skills directory not found: {skills}")
            except Exception as e:
                errors.append(f"Skills check error: {e}")

            if errors:
                print("\nERRORS:")
                for e in errors:
                    print(f"  - {e}")
                sys.exit(1)
            else:
                print("\nAll checks passed.")
                sys.exit(0)
        elif arg == "--web":
            from cli.__main__ import run_web
            run_web()
        elif arg == "--cli":
            from cli.__main__ import main as async_main
            asyncio.run(async_main())
        elif arg == "--mcp":
            from mcp_server import main as mcp_main
            asyncio.run(mcp_main())
        else:
            print(f"Unknown option: {arg}")
            print("Usage: python main.py [--web|--cli|--mcp|--doctor]")
    else:
        from repl import main as repl_main
        asyncio.run(repl_main())

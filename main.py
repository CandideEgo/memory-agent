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

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.absolute()))
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--web":
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
            print("Usage: python main.py [--web|--cli|--mcp]")
    else:
        from repl import main as repl_main
        asyncio.run(repl_main())

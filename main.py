"""
Agent 框架 - 便捷启动器
推荐: pip install -e . && memory-agent --web
"""

import sys
import asyncio
from pathlib import Path

if __name__ == "__main__":
    # Add project root to sys.path so top-level modules (agent, config, etc.) are importable
    sys.path.insert(0, str(Path(__file__).parent.absolute()))

    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        from cli.__main__ import run_web
        run_web()
    else:
        from cli.__main__ import main as async_main
        asyncio.run(async_main())

"""
CLI entry points for memory-agent.
"""

import asyncio
import logging
import os
import sys

from config import settings, validate_env
from memory_store import MemoryStore
from agent_runner import AgentRunner
from context_builder import ContextBuilder

logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    ctx = ContextBuilder()
    return ctx.build()


async def run_interactive() -> None:
    """Interactive CLI chat loop."""
    runner = AgentRunner()
    memory = MemoryStore()
    system_prompt = _build_system_prompt()

    print("=" * 60)
    print("  memory-agent - Interactive CLI")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if user_input.lower() == "clear":
                memory.clear_working()
                print("Memory cleared.")
                continue

            print("\n[Thinking...]")
            memory.add("user", user_input)
            result = await runner.run(memory, system_prompt)
            print(f"\n{result}")

        except KeyboardInterrupt:
            print("\n\nInterrupt - exiting.")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")


async def run_demo() -> None:
    """Demo mode with predefined tasks."""
    print("=" * 60)
    print("  memory-agent - Demo Mode")
    print("=" * 60)
    print()

    runner = AgentRunner()
    memory = MemoryStore()
    system_prompt = _build_system_prompt()

    tasks = [
        "Hello, introduce yourself",
        "List the files in the current directory",
        "Search for information about Python async programming",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n--- Task {i}: {task} ---")
        memory.clear_working()
        memory.add("user", task)
        result = await runner.run(memory, system_prompt)
        print(f"Result: {result[:200]}...")
        await asyncio.sleep(1)


def _check_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY is not set")
        print("Set it via: export ANTHROPIC_API_KEY='your-api-key'")
        print()
    return api_key


async def main():
    """Main CLI entry point."""
    _check_api_key()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            await run_demo()
            return

        if sys.argv[1] == "--task":
            task = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Hello"
            runner = AgentRunner()
            memory = MemoryStore()
            system_prompt = _build_system_prompt()
            memory.add("user", task)
            result = await runner.run(memory, system_prompt)
            print(result)
            return

    await run_interactive()


def run_web():
    """Start web server (sync entry)."""
    import uvicorn
    from web import app
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    print("Starting web server: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        run_web()
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        asyncio.run(main())

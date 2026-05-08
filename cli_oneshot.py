"""
Simple CLI entry point for one-shot media processing.

Usage:
    python -m app.cli "https://www.youtube.com/watch?v=XXXX"
    python -m app.cli "URL" --instructions "Summarize in Chinese" --title "My Note"
"""
import asyncio
import argparse
import logging
import sys

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process streaming media URLs into Obsidian knowledge notes"
    )
    parser.add_argument("url", help="Streaming video URL to process")
    parser.add_argument(
        "--instructions",
        "-i",
        default="Summarize key points and extract main topics",
        help="Processing instructions for the LLM",
    )
    parser.add_argument(
        "--title",
        "-t",
        default="",
        help="Obsidian note title (auto-generated if not provided)",
    )
    args = parser.parse_args()

    from config import validate_env
    validate_env()

    from app.mcp_agent import _process_media_url

    print(f"Processing: {args.url}")
    print(f"Instructions: {args.instructions}")
    print("-" * 60)

    result = await _process_media_url(args.url, args.instructions, args.title)
    print("-" * 60)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

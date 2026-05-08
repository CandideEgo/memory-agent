"""LLM-driven history compression for memory management."""

import threading
from datetime import datetime
from typing import Optional

from config import settings
from memory_store import MemoryStore
from context_builder import ContextBuilder

_compact_lock = threading.Lock()


def should_compact(memory: MemoryStore) -> bool:
    return memory.should_compact()


async def compact(memory: MemoryStore, context_builder: Optional[ContextBuilder] = None) -> None:
    """Compact old history using LLM to extract key information."""
    with _compact_lock:
        context_builder = ContextBuilder()

    history = memory.get_history_for_compaction()
    if not history:
        return

    prompt = context_builder.build_compact_prompt(history)

    from llm_client import get_client
    client = get_client()

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system="You are a helpful AI that summarizes conversation history.",
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text if response.content else ""

    episode = _extract_tag(text, "episode")
    updated_memory = _extract_tag(text, "updated_memory")
    updated_user = _extract_tag(text, "updated_user")

    if episode:
        memory.write_episodic(episode)

    if updated_memory:
        memory.update_long_term(updated_memory)

    memory.mark_compacted()
    memory.truncate_to(10)


def _extract_tag(text: str, tag: str) -> Optional[str]:
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    start = text.find(start_tag)
    if start == -1:
        return None
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return None
    # Basic validation: ensure no CDATA or nested same-tag inside
    content = text[start:end]
    if "<" in content or ">" not in content:
        # Likely malformed (contains nested tags or is actually CDATA)
        return None
    return content.strip()

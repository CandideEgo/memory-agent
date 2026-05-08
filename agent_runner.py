"""Agent runner — multi-turn tool-calling loop with Anthropic SDK."""

import asyncio
import logging
from typing import AsyncIterator

from anthropic import APIStatusError

from config import settings
from errors import AgentError, APIError
from logging_config import generate_request_id, request_id_var
from llm_client import create_message_with_retry
from memory_store import MemoryStore
from tools.registry import get_registry

logger = logging.getLogger("memory-agent.runner")

MAX_CONTEXT_CHARS = 150_000


class AgentRunner:
    """Executes a multi-turn tool-calling conversation loop."""

    MAX_TURNS = 10

    def __init__(self):
        self.registry = get_registry()

    def _trim_context(self, messages: list) -> list:
        total = sum(len(str(m.get("content", ""))) for m in messages)
        if total < MAX_CONTEXT_CHARS:
            return messages
        keep = max(4, int(len(messages) * 0.6))
        trimmed = messages[:2] + messages[-keep:]
        logger.warning(f"Context trimmed: {len(messages)} → {len(trimmed)}")
        return trimmed

    async def _execute_turn(self, messages: list, tool_defs: list, system_prompt: str):
        response = await create_message_with_retry(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system_prompt,
            tools=tool_defs,
            messages=self._trim_context(messages),
        )

        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        if not tool_calls:
            return text_parts, tool_calls

        # response.content is a list of ContentBlock objects (text or tool_use blocks).
        # tool_results is a list of dicts with type="tool_result". These are two different
        # content types stored in messages - the former is raw LLM output, the latter is
        # tool response dicts formatted for the next LLM turn.
        messages.append({"role": "assistant", "content": response.content})

        async def _exec_tool(tc):
            try:
                logger.info(f"Executing tool: {tc.name}...")
                result = await self.registry.execute_async(tc.name, tc.input)
                logger.info(f"Tool {tc.name} done ({len(result)} chars)")
                return {"type": "tool_result", "tool_use_id": tc.id, "content": result}
            except Exception as e:
                logger.error(f"Tool {tc.name} failed: {e}")
                return {"type": "tool_result", "tool_use_id": tc.id,
                        "content": f"Error: {e}", "is_error": True}

        tool_results = await asyncio.gather(*(_exec_tool(tc) for tc in tool_calls))
        messages.append({"role": "user", "content": tool_results})
        return text_parts, tool_calls

    async def run(self, memory: MemoryStore, system_prompt: str = "") -> str:
        req_id = generate_request_id()
        token = request_id_var.set(req_id)
        try:
            tool_defs = self.registry.get_definitions()
            messages = memory.to_anthropic_messages()
            all_text: list[str] = []

            for _ in range(self.MAX_TURNS):
                try:
                    text_parts, tool_calls = await self._execute_turn(messages, tool_defs, system_prompt)
                except Exception as e:
                    logger.error(f"Execute turn failed: {e}")
                    break
                if text_parts:
                    all_text.extend(text_parts)
                if not tool_calls:
                    final = "".join(all_text)
                    memory.add("assistant", final)
                    return final
            return "".join(all_text) or "Maximum turns reached."
        finally:
            request_id_var.reset(token)

    async def stream(self, memory: MemoryStore, system_prompt: str = "") -> AsyncIterator[str]:
        req_id = generate_request_id()
        token = request_id_var.set(req_id)
        try:
            tool_defs = self.registry.get_definitions()
            messages = memory.to_anthropic_messages()
            all_text: list[str] = []

            for _ in range(self.MAX_TURNS):
                try:
                    text_parts, tool_calls = await self._execute_turn(messages, tool_defs, system_prompt)
                except Exception as e:
                    logger.error(f"Execute turn failed: {e}")
                    break
                if text_parts:
                    joined = "".join(text_parts)
                    all_text.append(joined)
                    yield joined
                if not tool_calls:
                    memory.add("assistant", "".join(all_text))
                    return
        finally:
            request_id_var.reset(token)

"""Anthropic LLM client with retry logic and connection pooling."""

import asyncio
import logging
from typing import Optional

from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError, RateLimitError

from config import settings

logger = logging.getLogger("memory-agent.llm")

_client: Optional[AsyncAnthropic] = None

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def get_client() -> AsyncAnthropic:
    """Get or create the global Anthropic client singleton."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(
            api_key=settings.anthropic_auth_token,
            base_url=settings.anthropic_base_url,
            timeout=300.0,
            max_retries=2,
        )
    return _client


async def create_message_with_retry(**kwargs) -> dict:
    """Create a message with exponential backoff retry."""
    client = get_client()
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await client.messages.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                raise RuntimeError(
                    f"Rate limited after {MAX_RETRIES + 1} attempts."
                ) from e
        except APIConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                raise RuntimeError(
                    f"Cannot reach LLM API after {MAX_RETRIES + 1} attempts."
                ) from e
        except APIStatusError as e:
            if e.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    f"API error {e.status_code} (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                    f"retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(
                f"API error {e.status_code}: {e}"
            ) from e

    raise RuntimeError(f"LLM call failed: {last_error}")

"""Tests for compactor — LLM-driven history compression."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from compactor import _extract_tag


class TestExtractTag:
    """Tests for _extract_tag helper function."""

    def test_extract_tag_valid(self):
        text = "<episode>User asked about Python asyncio and received guidance.</episode>"
        result = _extract_tag(text, "episode")
        assert result == "User asked about Python asyncio and received guidance."

    def test_extract_tag_nested_tags(self):
        """Text with nested tag-like structures should work."""
        text = (
            "<episode>User discussed <code>async/await</code> patterns."
            "</episode>"
        )
        result = _extract_tag(text, "episode")
        # Since content contains '<' it will be rejected by validation
        assert result is None

    def test_extract_tag_missing(self):
        """Text with no matching tags returns None."""
        text = "Just some plain text without any XML tags."
        result = _extract_tag(text, "episode")
        assert result is None

    def test_extract_tag_wrong_tag(self):
        """Text has other tags but not the requested one."""
        text = "<updated_memory>Some memory update.</updated_memory>"
        result = _extract_tag(text, "episode")
        assert result is None

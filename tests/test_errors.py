"""Tests for the exception hierarchy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from errors import AgentError, ToolExecutionError, APIError, LLMRateLimitError, ConfigurationError


class TestExceptionHierarchy:
    """Tests for structured exception types."""

    def test_tool_execution_error_is_agent_error(self):
        exc = ToolExecutionError("tool failed")
        assert isinstance(exc, AgentError)
        assert isinstance(exc, Exception)

    def test_catching_by_parent(self):
        """AgentError base class catches all child exceptions."""
        for exc_cls in [ToolExecutionError, APIError, LLMRateLimitError, ConfigurationError]:
            exc = exc_cls("test message")
            try:
                raise exc
            except AgentError:
                pass  # expected — parent catches child
            else:
                pytest.fail(f"AgentError should catch {exc_cls.__name__}")

    def test_str_representation(self):
        exc = ToolExecutionError("something went wrong")
        assert str(exc) == "something went wrong"
        assert "went wrong" in repr(exc)

    def test_api_error_is_agent_error(self):
        exc = APIError("rate limited")
        assert isinstance(exc, AgentError)

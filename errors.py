"""Structured exception hierarchy for memory-agent."""


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class ToolExecutionError(AgentError):
    """Tool execution failed."""

    pass


class LLMRateLimitError(AgentError):
    """Rate limit exceeded."""

    pass


class ConfigurationError(AgentError):
    """Configuration is invalid."""

    pass


class APIError(AgentError):
    """API call failed."""

    pass
"""Tests for configuration parsing and validation."""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for flat module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ToolConfig, ConfigError, validate_env


class TestToolConfig:
    """Tests for ToolConfig whitelist parsing and defaults."""

    def test_whitelist_split_from_env(self, monkeypatch):
        """Whitelist set via env as JSON array is parsed correctly."""
        monkeypatch.setenv("TOOL_SHELL_WHITELIST", '["ls","cd","pwd","echo"]')
        cfg = ToolConfig()
        assert cfg.shell_whitelist == ["ls", "cd", "pwd", "echo"]

    def test_whitelist_default(self):
        """Default whitelist does not include python or pip."""
        cfg = ToolConfig()
        assert "python" not in cfg.shell_whitelist
        assert "pip" not in cfg.shell_whitelist
        assert "ls" in cfg.shell_whitelist

    def test_missing_token_strict(self):
        """validate_env(strict=True) raises ConfigError when token is missing."""
        from config import settings
        original = settings.anthropic_api_key
        try:
            settings.anthropic_api_key = ""
            with __import__("pytest").raises(ConfigError):
                validate_env(strict=True)
        finally:
            settings.anthropic_api_key = original

    def test_strict_mode_warnings(self):
        """validate_env(strict=False) returns list of warnings."""
        from config import settings
        original = settings.anthropic_api_key
        try:
            settings.anthropic_api_key = ""
            warnings = validate_env(strict=False)
            assert isinstance(warnings, list)
            assert any("ANTHROPIC_API_KEY" in w for w in warnings)
        finally:
            settings.anthropic_api_key = original

    def test_defaults(self):
        """ToolConfig has sensible defaults."""
        cfg = ToolConfig()
        assert cfg.shell_timeout == 30
        assert cfg.web_search_timeout == 10
        assert cfg.max_web_results == 5
        assert isinstance(cfg.shell_whitelist, list)
        assert len(cfg.shell_whitelist) > 0

"""Tests for ShellTool — whitelist enforcement and injection prevention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tools.shell_tool import ShellTool
from config import ToolConfig


@pytest.fixture
def tool():
    """Create a ShellTool instance with default config."""
    cfg = ToolConfig()
    return ShellTool(config=cfg)


class TestShellToolAllowed:
    """Tests for commands that should be allowed."""

    def test_ls_is_allowed(self, tool):
        allowed, reason, parts = tool._is_command_allowed("ls")
        assert allowed
        assert parts == ["ls"]

    def test_ls_with_args_is_allowed(self, tool):
        allowed, reason, parts = tool._is_command_allowed("ls -la")
        assert allowed
        assert parts == ["ls", "-la"]

    def test_echo_is_allowed(self, tool):
        allowed, reason, parts = tool._is_command_allowed("echo hello world")
        assert allowed


class TestShellToolBlocked:
    """Tests for commands that should be blocked."""

    def test_rm_rf_root_blocked(self, tool):
        allowed, reason, parts = tool._is_command_allowed("rm -rf /")
        assert not allowed
        assert "危险" in reason

    def test_python_c_blocked(self, tool):
        allowed, reason, parts = tool._is_command_allowed("python -c 'print(1)'")
        assert not allowed

    def test_pip_install_blocked(self, tool):
        allowed, reason, parts = tool._is_command_allowed("pip install requests")
        assert not allowed

    def test_empty_command_blocked(self, tool):
        allowed, reason, parts = tool._is_command_allowed("")
        assert not allowed
        assert "空命令" in reason


class TestShellToolInjection:
    """Tests for shell injection prevention."""

    def test_semicolon_injection_blocked(self, tool):
        """ls ; rm -rf / should be blocked due to metacharacter."""
        allowed, reason, parts = tool._is_command_allowed("ls ; rm -rf /")
        assert not allowed

    def test_pipe_injection_blocked(self, tool):
        """ls | cat should be blocked due to metacharacter."""
        allowed, reason, parts = tool._is_command_allowed("ls | cat /etc/passwd")
        assert not allowed

    def test_ampersand_injection_blocked(self, tool):
        """ls & whoami should be blocked due to metacharacter."""
        allowed, reason, parts = tool._is_command_allowed("ls & whoami")
        assert not allowed


class TestShellToolUnknown:
    """Tests for unknown/unlisted commands."""

    def test_unknown_command_blocked(self, tool):
        allowed, reason, parts = tool._is_command_allowed("nonexistent_cmd")
        assert not allowed
        assert "不在白名单中" in reason

    def test_pip_not_in_whitelist(self, tool):
        """pip is no longer in the default whitelist."""
        allowed, reason, parts = tool._is_command_allowed("pip list")
        assert not allowed

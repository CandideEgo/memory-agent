"""
Configuration management — pydantic-settings with .env validation.
"""

import logging
from functools import cached_property
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("memory-agent.config")

_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PROJECT_ROOT / ".env"


class LLMConfig(BaseSettings):
    """LLM API configuration."""
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")
    model: str = "MiniMax-M2.7"
    api_key: str = ""
    base_url: str = "https://api.minimaxi.com/anthropic"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    use_anthropic_api: bool = True


class AgentConfig(BaseSettings):
    """Agent behavior configuration."""
    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="ignore")
    max_iterations: int = 10
    memory_dir: str = "./memory"
    skills_dir: str = "skills"
    templates_dir: str = "templates"
    retry_count: int = 3
    retry_delay: float = 1.0
    mcp_config_path: str = ".mcp.json"

    @property
    def memory_file(self) -> str:
        """Backward compat: old name for memory_dir."""
        return self.memory_dir

    @property
    def base_dir(self) -> str:
        """Backward compat: project root for path resolution."""
        return str(_PROJECT_ROOT)

    def resolve_path(self, path: str) -> str:
        """Resolve relative path against project root."""
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(_PROJECT_ROOT / p)


class ToolConfig(BaseSettings):
    """Tool-specific configuration."""
    model_config = SettingsConfigDict(env_prefix="TOOL_", extra="ignore")
    shell_timeout: int = 30
    shell_whitelist: list[str] = [
        "ls", "cd", "pwd", "echo", "cat", "grep", "find",
        "mkdir", "rm", "cp", "mv", "python", "pip",
        "ffmpeg", "ffprobe", "yt-dlp",
    ]
    web_search_timeout: int = 10
    max_web_results: int = 5

    @field_validator("shell_whitelist", mode="before")
    @classmethod
    def _split_whitelist(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class Settings(BaseSettings):
    """Global application settings."""
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────
    anthropic_auth_token: str = ""
    anthropic_base_url: str = "https://api.minimaxi.com/anthropic"
    anthropic_model: str = "MiniMax-M2.7"

    # ── MCP bridge ───────────────────────────────────────────
    translate_mcp_command: str = ""
    translate_mcp_args: str = ""
    translate_mcp_path: str = ""

    # ── Obsidian ─────────────────────────────────────────────
    obsidian_vault_path: str = ""

    # ── Paths ────────────────────────────────────────────────
    memory_dir: str = "./memory"
    skills_dir: str = "skills"
    templates_dir: str = "templates"

    # ── Advanced ─────────────────────────────────────────────
    debug: bool = False
    log_level: str = "INFO"

    # ── Sub-configs ──────────────────────────────────────────
    @cached_property
    def llm(self) -> LLMConfig:
        return LLMConfig(
            api_key=self.anthropic_auth_token,
            base_url=self.anthropic_base_url,
            model=self.anthropic_model,
        )

    @cached_property
    def agent(self) -> "AgentConfig":
        return AgentConfig(
            memory_dir=self.memory_dir,
            skills_dir=self.skills_dir,
            templates_dir=self.templates_dir,
        )

    @cached_property
    def tool(self) -> "ToolConfig":
        return ToolConfig()

    @classmethod
    def from_env(cls) -> "Settings":
        """Backward compat: construct from environment variables."""
        return cls()


class ConfigError(Exception):
    """Configuration error with user-friendly message."""


def validate_env(strict: bool = False) -> list[str]:
    """Validate environment and return warnings."""
    warnings: list[str] = []

    if not settings.anthropic_auth_token:
        msg = "ANTHROPIC_AUTH_TOKEN is not set. LLM calls will fail."
        if strict:
            raise ConfigError(msg)
        warnings.append(msg)

    if not settings.translate_mcp_command:
        msg = "TRANSLATE_MCP_COMMAND is not set. Video transcription won't work."
        warnings.append(msg)

    if not settings.obsidian_vault_path:
        msg = "OBSIDIAN_VAULT_PATH is not set. Obsidian notes won't be saved."
        warnings.append(msg)
    else:
        vault = Path(settings.obsidian_vault_path)
        if not vault.exists():
            msg = f"Obsidian vault not found: {vault}"
            warnings.append(msg)

    return warnings


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    for attr in ["memory_dir", "skills_dir", "templates_dir"]:
        path = _PROJECT_ROOT / getattr(settings, attr)
        path.mkdir(parents=True, exist_ok=True)


settings = Settings()

# Backward compat alias
Config = Settings

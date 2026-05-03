"""
配置管理模块 - 使用 dataclass 集中管理所有配置
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ToolConfig:
    """工具相关配置"""
    shell_timeout: int = 30  # Shell 命令超时时间(秒)
    shell_whitelist: list[str] = field(default_factory=lambda: ["ls", "cd", "pwd", "echo", "cat", "grep", "find", "mkdir", "rm", "cp", "mv"])  # 命令白名单
    web_search_timeout: int = 10  # 网页搜索超时(秒)
    max_web_results: int = 5  # 最大搜索结果数


@dataclass
class LLMConfig:
    """LLM 相关配置"""
    model: str = "MiniMax-M2.7"
    api_key: str = ""  # 从环境变量 ANTHROPIC_AUTH_TOKEN 读取
    base_url: str = "https://api.minimaxi.com/anthropic"  # Anthropic 兼容 API
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60  # 请求超时(秒)
    # 是否使用 Anthropic API 格式 (而非 OpenAI 格式)
    use_anthropic_api: bool = True


@dataclass
class AgentConfig:
    """Agent 核心配置"""
    max_iterations: int = 10  # 工具循环上限
    memory_file: str = "memory.json"  # 记忆文件路径
    skills_dir: str = "skills"  # Skills 目录
    default_skill: str = "default"  # 默认技能名称
    log_level: str = "INFO"  # 日志级别
    retry_count: int = 3  # LLM 调用失败重试次数
    retry_delay: float = 1.0  # 重试延迟(秒)
    mcp_config_path: str = ".mcp.json"  # MCP 配置文件路径
    base_dir: str = ""  # 基础目录，默认为 agent 目录

    def __post_init__(self):
        if not self.base_dir:
            # 默认使用 agent 目录
            self.base_dir = str(Path(__file__).parent.absolute())

    def resolve_path(self, path: str) -> str:
        """解析相对路径为绝对路径"""
        if Path(path).is_absolute():
            return path
        return str(Path(self.base_dir) / path)


@dataclass
class Config:
    """全局配置聚合"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        llm = LLMConfig()
        llm.api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        llm.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        llm.model = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")
        return cls(llm=llm)

"""
Agent 框架
"""

try:
    from .agent import Agent
    from .config import Config
    from .memory import Memory
    from .skills_manager import SkillManager
    from .tools import BaseTool, get_all_tools
    from .web import app
except ImportError:
    from agent import Agent
    from config import Config
    from memory import Memory
    from skills_manager import SkillManager
    from tools import BaseTool, get_all_tools
    from web import app

__version__ = "1.0.0"

__all__ = [
    "Agent",
    "Config",
    "Memory",
    "SkillManager",
    "BaseTool",
    "get_all_tools",
    "app",
]

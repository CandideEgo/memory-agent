"""System prompt assembly using Jinja2 templates."""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import settings


class ContextBuilder:
    """Builds system prompt from Jinja2 templates."""

    def __init__(self, template_dir: Optional[Path] = None):
        if template_dir is None:
            template_dir = Path(settings.templates_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(),
        )

    def build(self, soul: str = None, user_prefs: str = None,
              identity: str = None, long_term_memory: str = "",
              skills_summary: str = "", extra: str = "") -> str:
        soul = soul or self._load_soul()
        user_prefs = user_prefs or self._load_user_prefs()

        template = self.env.get_template("system_prompt.md")
        return template.render(
            soul=soul,
            user_prefs=user_prefs,
            identity=identity or "",
            long_term_memory=long_term_memory,
            skills_summary=skills_summary,
            extra=extra,
        )

    def _load_soul(self) -> str:
        try:
            return self.env.get_template("SOUL.md").render()
        except Exception:
            return "You are a helpful AI agent."

    def _load_user_prefs(self) -> str:
        try:
            return self.env.get_template("USER.md").render()
        except Exception:
            return ""

    def build_compact_prompt(self, history: list[dict]) -> str:
        template = self.env.get_template("compact_prompt.md")
        return template.render(history=history)

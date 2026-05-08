"""Obsidian vault integration tool."""
from pathlib import Path
from datetime import datetime

from .base import BaseTool


class ObsidianWriteTool(BaseTool):
    """Writes a structured note to the Obsidian vault with YAML frontmatter."""

    name = "obsidian_write"
    description = (
        "Write a note to the Obsidian vault. Creates a well-formatted "
        "Obsidian markdown note with YAML frontmatter (title, date, tags). "
        "Use this after processing transcripts or web content into structured knowledge. "
        "The note content should use Obsidian Flavored Markdown."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Note title (will be used as the filename)",
            },
            "content": {
                "type": "string",
                "description": "Full markdown content for the note body",
            },
            "folder": {
                "type": "string",
                "description": "Subfolder within the vault (optional)",
                "default": "",
            },
            "tags": {
                "type": "string",
                "description": "Comma-separated tags for frontmatter (optional)",
                "default": "",
            },
        },
        "required": ["title", "content"],
    }

    async def execute(
        self, title: str = "", content: str = "", folder: str = "", tags: str = ""
    ) -> str:
        from config import settings

        vault = Path(settings.obsidian_vault_path)
        if not vault.exists():
            raise RuntimeError(
                f"Obsidian vault not found: {vault}. "
                "Set OBSIDIAN_VAULT_PATH in .env to your vault root directory."
            )

        target_dir = vault / folder if folder else vault
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = title.replace("/", "-").replace("\\", "-").replace(":", " -")
        filepath = target_dir / f"{safe_title}.md"

        today = datetime.now().strftime("%Y-%m-%d")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        frontmatter_lines = ["---", f'title: "{title}"', f"date: {today}"]
        if tag_list:
            frontmatter_lines.append("tags:")
            for t in tag_list:
                frontmatter_lines.append(f"  - {t}")
        frontmatter_lines.append("---")
        frontmatter = "\n".join(frontmatter_lines)

        full_content = f"{frontmatter}\n\n{content}"
        filepath.write_text(full_content, encoding="utf-8")

        return f"Note written: {filepath} ({len(full_content)} chars)"

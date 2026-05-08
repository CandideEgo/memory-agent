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

        vault = Path(settings.obsidian_vault_path).resolve()
        if not vault.exists():
            raise RuntimeError(
                f"Obsidian vault not found: {vault}. "
                "Set OBSIDIAN_VAULT_PATH in .env to your vault root directory."
            )

        # Sanitize folder — reject null bytes, control chars, path traversal
        if folder:
            folder = folder.translate({0: None, 1: None, 2: None, 3: None, 4: None,
                                      5: None, 6: None, 7: None, 8: None})
            if ".." in folder:
                raise ValueError("Path traversal not allowed in folder")
            folder = folder.strip()

        target_dir = vault / folder if folder else vault
        try:
            target_dir = target_dir.resolve()
        except (OSError, ValueError):
            raise ValueError(f"Invalid folder path: {folder}")
        if not str(target_dir).startswith(str(vault)):
            raise ValueError("Resolved path is outside vault")

        # Sanitize title — remove path separators, null bytes, control chars
        clean_title = title.translate({0: None, 1: None, 2: None, 3: None,
                                       4: None, 5: None, 6: None, 7: None, 8: None})
        clean_title = clean_title.replace("/", "-").replace("\\", "-").replace(":", " -").strip()
        if not clean_title:
            raise ValueError("Title cannot be empty after sanitization")
        if ".." in clean_title:
            raise ValueError("Path traversal not allowed in title")

        filepath = target_dir / f"{clean_title}.md"
        target_dir.mkdir(parents=True, exist_ok=True)

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

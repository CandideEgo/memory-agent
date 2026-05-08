"""Three-layer memory system: working, episodic, long-term."""

from datetime import datetime
from pathlib import Path
from typing import Any
import json

import filelock

from config import settings

_MEMORY_DIR = Path(settings.memory_dir)
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

_LONG_TERM_PATH = _MEMORY_DIR / "MEMORY.md"
_SESSIONS_DIR = _MEMORY_DIR / "sessions"


def _today_path() -> Path:
    return _MEMORY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"


class MemoryStore:
    """Three-layer memory: Working, Episodic, Long-term."""

    def __init__(self):
        self.working: list[dict[str, Any]] = []
        self.compaction_threshold = int(200_000 * 0.7)

    def add(self, role: str, content: str, **meta) -> None:
        self.working.append({"role": role, "content": content, **meta})

    def to_anthropic_messages(self) -> list[dict]:
        msgs = []
        for m in self.working:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "assistant":
                msgs.append({"role": "assistant", "content": content})
            else:
                msgs.append({"role": "user", "content": content})
        return msgs

    def clear_working(self) -> None:
        self.working = []

    def estimate_tokens(self) -> int:
        total_chars = sum(len(str(m.get("content", ""))) for m in self.working)
        return total_chars // 3

    def should_compact(self) -> bool:
        return self.estimate_tokens() > self.compaction_threshold

    def get_history_for_compaction(self) -> list[dict]:
        if len(self.working) <= 10:
            return []
        return self.working[:-10]

    def truncate_to(self, count: int) -> None:
        if len(self.working) > count:
            self.working = self.working[-count:]

    def mark_compacted(self) -> None:
        pass

    # ── Episodic ──────────────────────────────────────────

    def write_episodic(self, summary: str) -> None:
        path = _today_path()
        lock_path = str(path) + ".lock"
        lock = filelock.FileLock(lock_path)
        timestamp = datetime.now().isoformat()
        entry = f"\n## {timestamp}\n{summary}\n"
        with lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry)

    def read_episodic(self, query: str | None = None) -> str:
        path = _today_path()
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        if query:
            lines = [ln for ln in text.splitlines() if query.lower() in ln.lower()]
            return "\n".join(lines)
        return text

    # ── Long-term ─────────────────────────────────────────

    def read_long_term(self) -> str:
        if _LONG_TERM_PATH.exists():
            return _LONG_TERM_PATH.read_text(encoding="utf-8")
        return ""

    def update_long_term(self, content: str) -> None:
        lock_path = str(_LONG_TERM_PATH) + ".lock"
        lock = filelock.FileLock(lock_path)
        with lock:
            _LONG_TERM_PATH.write_text(content, encoding="utf-8")

    # ── Session persistence ───────────────────────────────

    def save_session(self, session_id: str) -> Path:
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = _SESSIONS_DIR / f"{session_id}.json"
        data = {
            "session_id": session_id,
            "saved_at": datetime.now().isoformat(),
            "messages": [
                {"role": m.get("role", "user"), "content": str(m.get("content", ""))}
                for m in self.working
            ],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_session(self, session_id: str) -> int:
        path = _SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        self.working = data.get("messages", [])
        return len(self.working)

    @staticmethod
    def list_saved_sessions() -> list[dict]:
        if not _SESSIONS_DIR.exists():
            return []
        sessions = []
        for f in sorted(_SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", f.stem),
                    "saved_at": data.get("saved_at", ""),
                    "messages": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions[:20]

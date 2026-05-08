"""AgentLoop — orchestrates CLI and streaming interaction."""

import uuid
from typing import Optional, AsyncIterator

from memory_store import MemoryStore
from agent_runner import AgentRunner
from context_builder import ContextBuilder
from compactor import should_compact, compact


class AgentLoop:
    """Main agent orchestration class."""

    def __init__(self):
        self.runner = AgentRunner()
        self.context_builder = ContextBuilder()
        self.sessions: dict[str, MemoryStore] = {}

    def get_session(self, session_id: Optional[str] = None) -> tuple[str, MemoryStore]:
        if session_id is None:
            session_id = str(uuid.uuid4())
        if session_id not in self.sessions:
            self.sessions[session_id] = MemoryStore()
        return session_id, self.sessions[session_id]

    async def chat(self, message: str, session_id: Optional[str] = None,
                   system_prompt: str = "") -> tuple[str, str]:
        sid, memory = self.get_session(session_id)

        if memory.should_compact():
            await compact(memory, self.context_builder)

        full_system = self.context_builder.build(
            long_term_memory=memory.read_long_term(),
            skills_summary=self._get_skills_summary(),
            extra=system_prompt,
        )

        memory.add("user", message)
        response = await self.runner.run(memory, full_system)
        return response, sid

    async def stream_chat(self, message: str, session_id: Optional[str] = None,
                          system_prompt: str = "") -> AsyncIterator[str]:
        sid, memory = self.get_session(session_id)

        if memory.should_compact():
            await compact(memory, self.context_builder)

        full_system = self.context_builder.build(
            long_term_memory=memory.read_long_term(),
            skills_summary=self._get_skills_summary(),
            extra=system_prompt,
        )

        memory.add("user", message)
        async for chunk in self.runner.stream(memory, full_system):
            yield chunk

    def _get_skills_summary(self) -> str:
        from skills_manager import SkillManager
        from config import settings
        mgr = SkillManager(settings.skills_dir)
        skills = mgr.skills
        if not skills:
            return "No skills available."
        lines = ["Available skills:"]
        for name, skill in skills.items():
            lines.append(f"- {name}: {getattr(skill, 'description', '')}")
        return "\n".join(lines)

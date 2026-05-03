"""
Skills 动态加载系统
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Skill:
    """技能类"""

    def __init__(self, name: str, description: str, instructions: str, path: Path):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.path = path

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, description={self.description!r})"


class SkillManager:
    """Skills 管理器 - 动态加载和管理技能"""

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self.current_skill: Skill | None = None
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        """加载所有 skills 目录下的技能"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills 目录不存在: {self.skills_dir}")
            return

        # 加载全局默认技能 (skills/SKILL.md)
        default_skill_path = self.skills_dir / "SKILL.md"
        if default_skill_path.exists():
            skill = self._load_skill_file(default_skill_path, "default")
            if skill:
                self.skills["default"] = skill
                self.current_skill = skill

        # 扫描子目录中的技能
        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skill = self._load_skill_file(item / "SKILL.md", item.name)
                if skill:
                    self.skills[item.name] = skill

        logger.info(f"已加载 {len(self.skills)} 个技能: {list(self.skills.keys())}")

    def _load_skill_file(self, path: Path, fallback_name: str) -> Skill | None:
        """
        加载单个技能文件

        Args:
            path: SKILL.md 文件路径
            fallback_name: 默认名称

        Returns:
            Skill 对象或 None
        """
        try:
            content = path.read_text(encoding="utf-8")
            name, description, instructions = self._parse_skill_md(content, fallback_name)
            return Skill(name=name, description=description, instructions=instructions, path=path)
        except Exception as e:
            logger.error(f"加载技能文件失败 {path}: {e}")
            return None

    def _parse_skill_md(self, content: str, fallback_name: str) -> tuple[str, str, str]:
        """
        解析 SKILL.md 格式

        Args:
            content: 文件内容
            fallback_name: 默认名称

        Returns:
            (技能名, 描述, 指令)
        """
        lines = content.split("\n")

        # 解析名称 (第一个 # 标题)
        name = fallback_name
        description = ""
        instructions_lines = []
        in_instructions = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 第一个 # 标题是技能名称
            if i == 0 and stripped.startswith("# "):
                name = stripped[2:].strip()

            # Description 部分
            elif stripped.lower() == "## description" or stripped.lower() == "## description":
                # 收集下一行或后续内容作为描述
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith("#"):
                        description = next_line
                        continue
                    desc_lines = []
                    for j in range(i + 1, len(lines)):
                        l = lines[j].strip()
                        if l.startswith("## ") or l.startswith("# "):
                            break
                        if l:
                            desc_lines.append(l)
                    description = " ".join(desc_lines)
                    if description:
                        continue

            # Instructions 部分
            elif stripped.lower() == "## instructions":
                in_instructions = True
                continue
            elif in_instructions and stripped.startswith("## "):
                in_instructions = False
            elif in_instructions:
                instructions_lines.append(line)

        instructions = "\n".join(instructions_lines).strip()
        if not instructions:
            instructions = content  # 如果没有找到 instructions，使用全部内容

        return name, description, instructions

    def load_skill(self, skill_name: str) -> bool:
        """
        加载指定名称的技能

        Args:
            skill_name: 技能名称

        Returns:
            是否加载成功
        """
        if skill_name in self.skills:
            self.current_skill = self.skills[skill_name]
            logger.info(f"切换到技能: {skill_name}")
            return True
        logger.warning(f"技能不存在: {skill_name}")
        return False

    def match_skill(self, user_input: str, llm_client: Any = None) -> Skill | None:
        """
        匹配最相关的技能

        Args:
            user_input: 用户输入
            llm_client: 可选的 LLM 客户端用于智能匹配

        Returns:
            最匹配的 Skill 或 None
        """
        user_input_lower = user_input.lower()

        # 关键词匹配
        keyword_map = {
            "search": ["搜索", "查找", "search", "find", "google"],
            "coding": ["代码", "编程", "写代码", "coding", "program", "python", "javascript"],
            "review": ["审核", "review", "检查", "审查", "看代码"],
            "memory": ["记忆", "memory", "状态", "history"],
        }

        for skill_name, keywords in keyword_map.items():
            if skill_name in self.skills:
                for keyword in keywords:
                    if keyword in user_input_lower:
                        logger.debug(f"关键词匹配技能: {skill_name} (关键词: {keyword})")
                        return self.skills[skill_name]

        # 如果没有匹配，返回默认技能
        return self.skills.get("default")

    def get_current_skill_instructions(self) -> str:
        """
        获取当前技能的指令

        Returns:
            技能指令字符串
        """
        if self.current_skill:
            return self.current_skill.instructions
        return ""

    def get_skill_names(self) -> list[str]:
        """获取所有技能名称"""
        return list(self.skills.keys())

    def get_skill_info(self, skill_name: str) -> dict[str, str] | None:
        """
        获取技能信息

        Args:
            skill_name: 技能名称

        Returns:
            技能信息字典或 None
        """
        skill = self.skills.get(skill_name)
        if skill:
            return {
                "name": skill.name,
                "description": skill.description,
                "path": str(skill.path)
            }
        return None

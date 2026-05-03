"""
记忆持久化模块 - 使用 JSON 文件存储对话历史和键值对状态
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Memory:
    """记忆类 - 管理对话历史和键值对状态"""

    def __init__(self, file_path: str = "memory.json"):
        self.file_path = Path(file_path)
        self.messages: list[dict[str, str]] = []
        self.state: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        """如果记忆文件存在则加载"""
        if self.file_path.exists():
            try:
                self.load_from_file()
                logger.info(f"记忆已从 {self.file_path} 加载")
            except Exception as e:
                logger.warning(f"加载记忆文件失败: {e}，将使用空白记忆")

    def append_message(self, role: str, content: str) -> None:
        """
        添加消息到历史

        Args:
            role: 消息角色 (user/assistant/system/tool)
            content: 消息内容
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._update_timestamp()

    def get_recent_history(self, n: int = 10) -> list[dict[str, str]]:
        """
        获取最近 n 条消息

        Args:
            n: 获取消息数量

        Returns:
            最近 n 条消息的列表
        """
        return self.messages[-n:] if n > 0 else self.messages

    def get_full_history(self) -> list[dict[str, str]]:
        """获取完整对话历史"""
        return self.messages

    def update_state(self, key: str, value: Any) -> None:
        """
        更新状态键值对

        Args:
            key: 状态键
            value: 状态值
        """
        self.state[key] = value
        self._update_timestamp()

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        获取状态值

        Args:
            key: 状态键
            default: 默认值
        """
        return self.state.get(key, default)

    def get_summary(self, max_length: int = 500) -> str:
        """
        生成简短的记忆摘要

        Args:
            max_length: 最大摘要长度

        Returns:
            记忆摘要字符串
        """
        if not self.messages:
            return "无历史对话"

        # 统计信息
        user_msgs = sum(1 for m in self.messages if m["role"] == "user")
        assistant_msgs = sum(1 for m in self.messages if m["role"] == "assistant")

        # 最近状态
        state_info = ""
        if self.state:
            state_keys = list(self.state.keys())[:3]
            state_info = f", 状态: {', '.join(state_keys)}"

        summary = f"对话 {user_msgs} 轮, 用户 {user_msgs} 条, 助手 {assistant_msgs} 条{state_info}"

        if len(summary) > max_length:
            summary = summary[:max_length - 3] + "..."
        return summary

    def save_to_file(self) -> None:
        """保存记忆到文件"""
        data = {
            "messages": self.messages,
            "state": self.state,
            "metadata": self.metadata
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"记忆已保存到 {self.file_path}")

    def load_from_file(self) -> None:
        """从文件加载记忆"""
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.messages = data.get("messages", [])
        self.state = data.get("state", {})
        self.metadata = data.get("metadata", {})

    def clear(self) -> None:
        """清空记忆（保留元数据）"""
        self.messages = []
        self.state = {}
        self._update_timestamp()

    def _update_timestamp(self) -> None:
        """更新元数据时间戳"""
        self.metadata["updated_at"] = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "messages": self.messages,
            "state": self.state,
            "metadata": self.metadata
        }

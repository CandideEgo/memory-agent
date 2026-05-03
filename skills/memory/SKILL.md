# 记忆技能

## Description
用于管理 Agent 的记忆和状态信息。

## Instructions
1. 在执行任务过程中记录重要信息到记忆
2. 使用 memory 模块的 update_state 方法保存状态
3. 在适当时候调用 get_recent_history 获取上下文
4. 保持记忆的简洁性和相关性
5. 定期清理不再需要的历史信息

# Agent Framework

生产级模块化 AI Agent 框架，基于 ReAct/Tool-use 模式。

## 核心功能

- **ReAct 循环**: 基于 LLM 的推理-行动循环
- **工具系统**: 统一的工具接口，支持文件读写、Shell 命令、网页搜索
- **记忆持久化**: JSON 文件存储对话历史和状态
- **Skills 动态加载**: 按需加载技能指令

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

```bash
export OPENAI_API_KEY='your-api-key'
```

### 3. 运行

```bash
# 交互模式
python -m agent_framework.main

# 单任务模式
python -m agent_framework.main --task "你好"

# 演示模式
python -m agent_framework.main --demo
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                         Agent                               │
│  - LLM Client (OpenAI compatible)                           │
│  - ToolRunner (工具执行循环)                                 │
│  - Memory (记忆持久化)                                       │
│  - SkillManager (技能动态加载)                               │
└─────────────────────────────────────────────────────────────┘
```

## 添加新工具

继承 `BaseTool`:

```python
from tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具"
    parameters = {
        "type": "object",
        "properties": {...},
        "required": [...]
    }

    async def execute(self, **kwargs) -> str:
        # 实现逻辑
        return "结果"
```

## 添加新 Skill

在 `skills/` 目录下创建目录和 `SKILL.md`:

```markdown
# Skill Name

## Description
简短描述

## Instructions
具体指令...
```

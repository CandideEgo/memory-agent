# Memory-Agent 迭代改进 - 第1次循环

日期: 2026-05-08

## 概述

第1次迭代完成，包含代码审核和新文件提交。

---

## 本次改动

### 1. REPL 欢迎信息品牌修复

**文件**: `repl.py:118`
**问题**: 欢迎信息显示 "translate-agent" 而非 "memory-agent"
**修复**: 将 `{Style.bold('translate-agent')}` 改为 `{Style.bold('memory-agent')}`

### 2. 新文件提交 (commit 75ba325)

**提交信息**: Add core modules and project infrastructure

**新增文件** (33个文件):
- `agent_runner.py`, `agent_loop.py` - 新版 ReAct 实现
- `llm_client.py` - Anthropic SDK 客户端，含重试逻辑
- `memory_store.py` - 三层记忆架构
- `context_builder.py` - Jinja2 模板支持
- `mcp_server.py` - MCP 协议服务器
- `tools/` - 多个新工具: video_tool, ytdlp_tool, obsidian_tool, mcp_bridge
- `templates/` - 系统提示词和 soul 模板
- `.gitignore` - Python/node/logs 等忽略规则

### 3. Reviewer 审核问题修复 (commit 6b5564f)

#### Issue 1: config.py - 移除废弃的 LLMConfig/AgentConfig 类
**原因**: 这两个类定义后从未使用，Settings 类直接定义了相同字段
**修复**: 删除 `LLMConfig` 和 `AgentConfig` 类（47行删除）

#### Issue 2: memory_store.py - to_anthropic_messages() 保留 list 内容
**原因**: 当 content 是混合列表（如包含 tool_use 块）时，原代码将其转换为字符串，丢失结构
**修复**: 添加 `isinstance(content, list)` 检查，保留列表结构

```python
# 修复前
if role == "assistant":
    msgs.append({"role": "assistant", "content": content})
else:
    msgs.append({"role": "user", "content": content})

# 修复后
if isinstance(content, list):
    msgs.append({"role": role, "content": content})
elif role == "assistant":
    msgs.append({"role": "assistant", "content": content})
else:
    msgs.append({"role": "user", "content": content})
```

#### Issue 3: mcp_server.py - 移除未使用的 BaseTool import
**原因**: `BaseTool` 导入但未使用，代码使用的是 `Tool` 和 `TextContent`
**修复**: 删除 `BaseTool` 导入

#### Issue 4: agent_loop.py - 缓存 SkillManager 实例
**原因**: `_get_skills_summary()` 每次调用都创建新的 `SkillManager` 实例，触发磁盘 I/O
**修复**: 在 `__init__` 中创建单一实例 `self._skill_mgr`，复用

```python
# 修复前
def _get_skills_summary(self):
    from skills_manager import SkillManager
    from config import settings
    mgr = SkillManager(settings.skills_dir)  # 每次创建

# 修复后
def __init__(self):
    self._skill_mgr = SkillManager(settings.skills_dir)  # 缓存

def _get_skills_summary(self):
    skills = self._skill_mgr.skills  # 复用
```

---

## Reviewer 审核摘要

### 发现的问题 (优先级排序)

1. **Critical**: `memory_store.py:38-41` - to_anthropic_messages() 破坏 content 结构
2. **Important**: `config.py:19-58` - 废弃的 LLMConfig/AgentConfig 类
3. **Important**: `agent_loop.py:62-65` - 每次调用重新实例化 SkillManager
4. **Minor**: `mcp_server.py:15` - 未使用的 BaseTool import
5. **Minor**: `tools/registry.py:15-24` - Singleton 实现不一致

### 已修复: 4/5
### 待处理: 1/5 (registry.py singleton)

---

## Git 提交记录

| Commit | Message |
|--------|---------|
| 75ba325 | Add core modules and project infrastructure |
| 6b5564f | Fix reviewer-identified issues |

---

## 验证

```bash
python -c "import main; print('OK')"
git status
```

---

## 下一步

第2次迭代将继续审核新提交的代码，重点关注:
- tools/ 目录下的工具实现质量
- agent_runner.py 与 agent.py 的架构关系
- 错误处理和边界情况
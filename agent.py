"""
Agent 主循环 - ReAct / Tool-use 模式实现
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

try:
    from .config import AgentConfig, Config, LLMConfig
    from .memory import Memory
    from .skills_manager import SkillManager
    from .tools import BaseTool, get_all_tools
except ImportError:
    from config import AgentConfig, Config, LLMConfig
    from memory import Memory
    from skills_manager import SkillManager
    from tools import BaseTool, get_all_tools

logger = logging.getLogger(__name__)


class ToolRunner:
    """工具运行器 - 管理工具注册和执行"""

    def __init__(self):
        self.tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")

    def register_all(self, tools: list[BaseTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)

    def get_tool(self, name: str) -> BaseTool | None:
        """获取工具"""
        return self.tools.get(name)

    def get_tool_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self.tools.keys())

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果或错误信息
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return f"错误: 未知工具: {tool_name}。可用工具: {', '.join(self.get_tool_names())}"

        return await tool.safe_execute(**arguments)


class Agent:
    """AI Agent - 基于 ReAct 模式"""

    SYSTEM_PROMPT_TEMPLATE = """你是一个模块化的 AI Agent，负责执行用户任务。

## 当前技能
{{skill_section}}

## 记忆摘要
{memory_snapshot}

## 可用工具
{tool_schemas}

## 执行规则
1. 理解用户任务
2. 如需工具，执行 tool_call
3. 观察工具返回结果，继续推理
4. **重要**: 执行完一个工具后，必须根据观察结果决定下一步：
   - 如果任务完成，返回 final_answer
   - 如果需要继续操作，执行下一个 tool_call
   - **不要重复执行同一个工具**
5. 任务完成后返回 final_answer

## 输出格式（必须严格遵循）

**工具调用示例**:
```
{
  "thought": "我已经写入文件到 test.txt，现在需要读取该文件来确认内容",
  "tool_call": {
    "name": "file_read",
    "arguments": {"file_path": "test.txt"}
  },
  "continue": true
}
```

**最终答案示例**:
```
{
  "thought": "任务已完成，文件内容已确认",
  "final_answer": "文件 test.txt 的内容是: hello world",
  "continue": false
}
```

**重要提醒**：
- 所有响应必须是一个完整的 JSON 对象
- 不要在 tool_call 中重复执行相同的工具
- 工具执行成功后，根据观察结果决定下一步

请开始执行任务。
"""

    def __init__(self, config: Config):
        self.config = config

        # 初始化组件
        self.llm_config = config.llm
        self.agent_config = config.agent
        self.tool_config = config.tool

        # 解析路径
        memory_file = config.agent.resolve_path(config.agent.memory_file)
        skills_dir = config.agent.resolve_path(config.agent.skills_dir)
        mcp_config_path = config.agent.resolve_path(config.agent.mcp_config_path)

        # 初始化记忆
        self.memory = Memory(memory_file)

        # 初始化技能管理器
        self.skill_manager = SkillManager(skills_dir)

        # 初始化工具运行器
        self.tool_runner = ToolRunner()
        self.tool_runner.register_all(get_all_tools(mcp_config_path))

        # HTTP 客户端（延迟初始化）
        self._client = None

        # 统计信息
        self.iteration_count = 0
        self.total_tokens_used = 0

    @property
    def client(self):
        """延迟初始化 HTTP 客户端"""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=self.llm_config.timeout)
        return self._client

    async def close(self):
        """关闭资源"""
        # 关闭 MCP 工具
        mcp_tool = self.tool_runner.get_tool("mcp_call")
        if mcp_tool:
            await mcp_tool.close()

        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_system_prompt(self) -> str:
        """
        构建系统提示词

        Returns:
            组装好的系统提示词
        """
        # 获取技能指令
        skill_instructions = self.skill_manager.get_current_skill_instructions()
        skill_section = skill_instructions if skill_instructions else "（无特定技能，使用通用能力）"

        # 获取记忆摘要
        memory_snapshot = self.memory.get_summary()

        # 获取工具 Schema
        tool_schemas = self._get_tool_schemas()

        prompt = self.SYSTEM_PROMPT_TEMPLATE.replace("{{skill_section}}", skill_section)\
                                                    .replace("{memory_snapshot}", memory_snapshot)\
                                                    .replace("{tool_schemas}", json.dumps(tool_schemas, indent=2, ensure_ascii=False))

        return prompt

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """获取所有工具的 Schema"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self.tool_runner.tools.values()
        ]

    async def _call_llm(self, messages: list[dict[str, str]], retry_count: int = 0) -> str:
        """
        调用 LLM (支持 OpenAI 和 Anthropic 兼容 API)

        Args:
            messages: 消息列表
            retry_count: 当前重试次数

        Returns:
            LLM 响应内容
        """
        try:
            if self.llm_config.use_anthropic_api:
                return await self._call_anthropic_api(messages)
            else:
                return await self._call_openai_api(messages)

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")

            if retry_count < self.agent_config.retry_count:
                logger.info(f"重试 LLM 调用 ({retry_count + 1}/{self.agent_config.retry_count})...")
                time.sleep(self.agent_config.retry_delay)
                return await self._call_llm(messages, retry_count + 1)

            raise

    async def _call_anthropic_api(self, messages: list[dict[str, str]]) -> str:
        """
        调用 Anthropic 兼容 API (MCP)

        Args:
            messages: 消息列表

        Returns:
            LLM 响应内容
        """
        api_url = f"{self.llm_config.base_url}/v1/messages"
        headers = {
            "x-api-key": self.llm_config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        # 构建 tools (Anthropic 格式)
        tools = [t.to_openai_tool() for t in self.tool_runner.tools.values()]

        # 转换消息格式: OpenAI -> Anthropic
        anthropic_messages = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                # Anthropic 使用独立的 system 字段
                continue
            elif role == "tool":
                # Tool 结果 - 使用 user role 配合 tool_call_id
                tool_id = msg.get("tool_call_id", "placeholder")
                anthropic_messages.append({
                    "role": "user",
                    "content": f"[Tool Result]: {content}",
                    "tool_call_id": tool_id
                })
            elif role == "assistant":
                # Assistant 消息需要转换为 content 块
                try:
                    data = json.loads(content)
                    if data.get("tool_call"):
                        # 转换为 tool_use 块
                        tc = data["tool_call"]
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": f"call_{hash(tc['name']) % 1000000}",
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc.get("arguments", {}))
                                }
                            }]
                        })
                    elif data.get("final_answer"):
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": [{
                                "type": "text",
                                "text": data["final_answer"]
                            }]
                        })
                except json.JSONDecodeError:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": content}]
                    })
            else:
                anthropic_messages.append({
                    "role": "user" if role == "user" else "user",
                    "content": content
                })

        payload = {
            "model": self.llm_config.model,
            "messages": anthropic_messages,
            "max_tokens": self.llm_config.max_tokens,
            "temperature": self.llm_config.temperature,
        }

        if tools:
            payload["tools"] = tools

        logger.debug(f"调用 Anthropic API: {api_url}")

        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        self.total_tokens_used += result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)

        # 解析响应
        content_blocks = result.get("content", [])
        if not content_blocks:
            raise ValueError("LLM 响应为空")

        # 处理 content 块
        tool_calls = []
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "tool_use":
                # 工具调用
                tool_name = block.get("name")
                tool_input = block.get("input", {})
                tool_calls.append({
                    "tool_name": tool_name,
                    "arguments": tool_input
                })
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        if tool_calls:
            return json.dumps({
                "type": "tool_calls",
                "calls": tool_calls
            }, ensure_ascii=False)

        if text_parts:
            return "\n".join(text_parts)

        raise ValueError(f"无法解析 Anthropic 响应: {content_blocks}")

    async def _call_openai_api(self, messages: list[dict[str, str]]) -> str:
        """
        调用 OpenAI 兼容 API

        Args:
            messages: 消息列表

        Returns:
            LLM 响应内容
        """
        api_url = f"{self.llm_config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.llm_config.api_key}",
            "Content-Type": "application/json"
        }

        # 构建 tools
        tools = [t.to_openai_tool() for t in self.tool_runner.tools.values()]

        payload = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
            "tools": tools if tools else None,
            "tool_choice": "auto"
        }

        # 过滤 None 值
        payload = {k: v for k, v in payload.items() if v is not None}

        logger.debug(f"调用 OpenAI API: {api_url}")

        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        self.total_tokens_used += result.get("usage", {}).get("total_tokens", 0)

        # 解析响应
        choices = result.get("choices", [])
        if not choices:
            raise ValueError("LLM 响应为空")

        message = choices[0].get("message", {})

        # 检查是否有工具调用
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            tool_results = []
            for call in tool_calls:
                func = call.get("function", {})
                tool_results.append({
                    "tool_name": func.get("name"),
                    "arguments": func.get("arguments")
                })

            return json.dumps({
                "type": "tool_calls",
                "calls": tool_results
            }, ensure_ascii=False)

        # 普通文本响应
        content = message.get("content", "")
        if not content:
            raise ValueError("LLM 响应内容为空")

        return content

    def _parse_response(self, content: str) -> dict[str, Any]:
        """
        解析 LLM 响应

        Args:
            content: LLM 返回的原始内容

        Returns:
            解析后的动作字典
        """
        # 尝试提取 JSON
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个内容
            json_str = content.strip()

        try:
            data = json.loads(json_str)

            # 转换 Anthropic 格式到内部格式
            if data.get("type") == "tool_calls" and "calls" in data:
                calls = data["calls"]
                if calls and len(calls) > 0:
                    first_call = calls[0]
                    return {
                        "thought": "工具调用",
                        "tool_call": {
                            "name": first_call.get("tool_name") or first_call.get("name"),
                            "arguments": first_call.get("arguments", {})
                        },
                        "continue": True
                    }

            # 标准格式
            if "tool_call" in data or "final_answer" in data:
                return data

            # 其他格式：当作文本响应
            return {
                "thought": "响应",
                "final_answer": content,
                "continue": False
            }

        except json.JSONDecodeError:
            pass

        # 尝试提取 ```...``` 中的内容
        code_blocks = re.findall(r"```[\s\S]*?```", content)
        for block in code_blocks:
            inner = re.sub(r"```\w*\s*", "", block).strip()
            try:
                data = json.loads(inner)

                # 转换 Anthropic 格式
                if data.get("type") == "tool_calls" and "calls" in data:
                    calls = data["calls"]
                    if calls and len(calls) > 0:
                        first_call = calls[0]
                        return {
                            "thought": "工具调用",
                            "tool_call": {
                                "name": first_call.get("tool_name") or first_call.get("name"),
                                "arguments": first_call.get("arguments", {})
                            },
                            "continue": True
                        }

                if "tool_call" in data or "final_answer" in data:
                    return data

            except json.JSONDecodeError:
                continue

        # 降级处理：分析自然语言响应
        logger.warning(f"无法解析 JSON 响应，降级为自然语言处理: {content[:200]}...")

        # 检查是否包含工具调用指令
        tool_call_match = re.search(r'"tool_call"\s*:\s*\{[^}]*"name"\s*:\s*"(\w+)"', content)
        if tool_call_match:
            tool_name = tool_call_match.group(1)
            args_match = re.search(r'"arguments"\s*:\s*(\{[^}]+\})', content)
            try:
                arguments = json.loads(args_match.group(1)) if args_match else {}
            except:
                arguments = {}
            return {
                "thought": "从自然语言中提取的工具调用",
                "tool_call": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "continue": True
            }

        # 检查是否包含 final_answer
        answer_match = re.search(r'"final_answer"\s*:\s*"([^"]+)"', content)
        if answer_match:
            return {
                "thought": "从自然语言中提取的答案",
                "final_answer": answer_match.group(1),
                "continue": False
            }

        # 直接将内容作为最终答案返回
        return {
            "thought": "自然语言响应",
            "final_answer": content,
            "continue": False
        }

    def _validate_tool_call(self, tool_call: dict[str, Any]) -> tuple[bool, str]:
        """
        验证工具调用是否有效

        Args:
            tool_call: 工具调用字典

        Returns:
            (是否有效, 错误信息)
        """
        # 支持多种格式
        tool_name = tool_call.get("name") or tool_call.get("tool_name") or ""

        if not tool_name:
            return False, "工具调用缺少 name 字段"

        if tool_name not in self.tool_runner.get_tool_names():
            available = ", ".join(self.tool_runner.get_tool_names())
            return False, f"未知工具: {tool_name}。可用工具: {available}"

        return True, ""

    async def run(self, task: str) -> str:
        """
        运行 Agent 执行任务

        Args:
            task: 用户任务

        Returns:
            最终答案或错误信息
        """
        logger.info(f"开始执行任务: {task}")
        self.iteration_count = 0

        # 构建初始消息
        system_prompt = self._build_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]

        # 记录用户消息
        self.memory.append_message("user", task)

        # 工具循环
        while self.iteration_count < self.agent_config.max_iterations:
            self.iteration_count += 1
            logger.info(f"开始第 {self.iteration_count} 轮迭代")

            try:
                # 调用 LLM
                response = await self._call_llm(messages)

                # 解析响应
                action = self._parse_response(response)

                # 判断动作类型
                if action.get("final_answer"):
                    # 最终答案
                    answer = action["final_answer"]
                    logger.info(f"任务完成: {answer[:100]}...")
                    self.memory.append_message("assistant", answer)
                    self.memory.save_to_file()
                    return answer

                elif action.get("tool_call") or action.get("type") == "tool_calls":
                    # 处理工具调用（可能包含多个工具调用）
                    if action.get("type") == "tool_calls" and "calls" in action:
                        # Anthropic 格式：多个工具调用
                        calls = action["calls"]
                    else:
                        # 标准格式：单个工具调用
                        calls = [action["tool_call"]]

                    observations = []
                    for call in calls:
                        tool_name = call.get("name") or call.get("tool_name")
                        arguments = call.get("arguments", {})

                        # 验证工具调用
                        valid, error = self._validate_tool_call(call)
                        if not valid:
                            logger.warning(f"工具调用无效: {error}")
                            observations.append(f"工具 {tool_name} 调用无效: {error}")
                        else:
                            # 执行工具
                            logger.info(f"执行工具: {tool_name}")
                            obs = await self.tool_runner.execute(tool_name, arguments)
                            observations.append(f"[{tool_name}] {obs}")
                            self.memory.append_message("tool", f"{tool_name}: {obs}")

                    # 添加助手消息
                    assistant_msg = json.dumps(action, ensure_ascii=False)
                    self.memory.append_message("assistant", assistant_msg)

                    # 添加工具结果作为观察
                    messages.append({
                        "role": "assistant",
                        "content": assistant_msg
                    })
                    messages.append({
                        "role": "system",
                        "content": f"观察结果: {'; '.join(observations)}"
                    })

                    # 检查是否需要继续循环
                    # 如果连续执行相同工具超过 2 次，认为是无限循环，直接返回
                    if observations and tool_name:
                        if hasattr(self, '_last_tool_name') and self._last_tool_name == tool_name:
                            self._repeat_count = getattr(self, '_repeat_count', 0) + 1
                            if self._repeat_count >= 2:
                                answer = f"任务完成。执行结果: {'; '.join(observations)}"
                                self.memory.append_message("assistant", answer)
                                self.memory.save_to_file()
                                return answer
                        else:
                            self._last_tool_name = tool_name
                            self._repeat_count = 0

                else:
                    # 降级处理：当作最终答案
                    logger.warning("响应格式不明确，当作最终答案处理")
                    answer = str(action.get("thought", response))
                    self.memory.append_message("assistant", answer)
                    self.memory.save_to_file()
                    return answer

            except Exception as e:
                logger.error(f"第 {self.iteration_count} 轮执行异常: {e}")

                if self.iteration_count >= self.agent_config.max_iterations:
                    error_msg = f"达到最大迭代次数 ({self.agent_config.max_iterations})，任务失败: {e}"
                    logger.error(error_msg)
                    return error_msg

                # 继续下一轮
                continue

        # 达到最大迭代次数
        error_msg = f"达到最大迭代次数 ({self.agent_config.max_iterations})，任务终止"
        logger.error(error_msg)
        return error_msg

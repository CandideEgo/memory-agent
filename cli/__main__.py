"""
Agent 框架主入口 - CLI 交互示例
"""

import asyncio
import logging
import os
import sys
from typing import Optional

# Handle both package and direct execution contexts
try:
    from ..agent import Agent
    from ..config import Config
except ImportError:
    from agent import Agent
    from config import Config

logger = logging.getLogger(__name__)


async def run_interactive(agent: Agent) -> None:
    """交互式运行"""
    def _show_help():
        current = agent.skill_manager.current_skill
        current_name = current.name if current else "default"
        skill_names = agent.skill_manager.get_skill_names()
        print(f"当前技能: {current_name} | 可用技能: {', '.join(skill_names)}")
        print("/<技能名>  切换技能  |  /?       查看帮助")
        print("skills     列出技能  |  clear    清空记忆")
        print("quit       退出程序  |  <其他>   发送任务给 Agent")
        print()

    print("=" * 60)
    print("  AI Agent 框架 - 交互式终端")
    print("=" * 60)
    _show_help()

    while True:
        try:
            user_input = input("\n用户> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("再见!")
                break

            if user_input.lower() == "clear":
                agent.memory.clear()
                agent.memory.save_to_file()
                print("记忆已清空")
                continue

            if user_input.lower() == "skills":
                _show_help()
                continue

            if user_input.startswith("/"):
                cmd = user_input[1:].strip().lower()
                if not cmd or cmd == "?":
                    _show_help()
                else:
                    # /技能名 → 直接切换技能
                    success = agent.skill_manager.load_skill(cmd)
                    if success:
                        print(f"已切换到技能: {cmd}")
                    else:
                        skill_names = agent.skill_manager.get_skill_names()
                        # 模糊匹配
                        matches = [s for s in skill_names if cmd in s]
                        if matches:
                            print(f"未找到技能 '{cmd}'，可用技能: {', '.join(skill_names)}")
                            print(f"  输入 /{matches[0]} 切换到 {matches[0]}")
                        else:
                            print(f"未找到技能 '{cmd}'，可用技能: {', '.join(skill_names)}")
                continue

            print("\n[Agent 正在思考...]")
            result = await agent.run(user_input)
            print(f"\n[最终答案]\n{result}")

        except KeyboardInterrupt:
            print("\n\n中断退出")
            break
        except Exception as e:
            logger.error(f"执行异常: {e}")
            print(f"错误: {e}")


async def run_demo(agent: Agent) -> None:
    """演示模式 - 执行预定义任务"""
    print("=" * 60)
    print("  AI Agent 框架 - 演示模式")
    print("=" * 60)
    print()

    tasks = [
        "你好，介绍一下你自己",
        "查看当前记忆状态",
        "用 shell 工具执行 ls 命令",
        "搜索一下 Python 异步编程的相关信息",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n--- 演示任务 {i}: {task} ---")
        result = await agent.run(task)
        print(f"结果: {result[:200]}...")
        await asyncio.sleep(1)


def create_agent(config: Optional[Config] = None) -> Agent:
    """
    创建 Agent 实例

    Args:
        config: 配置对象，None 时使用默认配置

    Returns:
        Agent 实例
    """
    if config is None:
        config = Config.from_env()

    return Agent(config)


def _check_api_key() -> str:
    """检查 ANTHROPIC_AUTH_TOKEN 环境变量，返回 key 或空字符串"""
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not api_key:
        print("警告: 未设置 ANTHROPIC_AUTH_TOKEN 环境变量")
        print("请设置: export ANTHROPIC_AUTH_TOKEN='your-api-key' (Linux/Mac)")
        print("或: set ANTHROPIC_AUTH_TOKEN=your-api-key (Windows)")
        print()
    return api_key


async def main():
    """主函数"""
    api_key = _check_api_key()
    config = Config.from_env() if api_key else Config()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            agent = create_agent(config)
            try:
                await run_demo(agent)
            finally:
                await agent.close()
            return

        if sys.argv[1] == "--task":
            agent = create_agent(config)
            try:
                task = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "你好"
                result = await agent.run(task)
                print(result)
            finally:
                await agent.close()
            return

    # 默认: 交互式 CLI
    agent = create_agent(config)
    try:
        await run_interactive(agent)
    finally:
        await agent.close()


def run_web():
    """启动 Web 服务器 (同步入口，避免 asyncio 事件循环冲突)"""
    import uvicorn
    # Lazy import — only pay the FastAPI cost when --web is used
    try:
        from ..web import app
    except ImportError:
        from web import app
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    print("启动 Web 服务器: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    # Handle --web before entering asyncio.run() to avoid event loop conflict
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        run_web()
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        asyncio.run(main())

"""
Agent 框架主入口 - CLI 交互示例
"""

import asyncio
import logging
import sys
from typing import Optional

# Handle both package and direct execution contexts
# When cli is a top-level package (imported from main.py), it has no parent
# When cli is a subpackage (python -m cli), its parent is the root package
try:
    from ..agent import Agent
    from ..config import Config
    from ..web import app
except ImportError:
    # Fallback for when cli is used as top-level package
    from agent import Agent
    from config import Config
    from web import app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_interactive(agent: Agent) -> None:
    """交互式运行"""
    print("=" * 60)
    print("  AI Agent 框架 - 交互式终端")
    print("=" * 60)
    print("输入任务后按回车执行，输入 'quit' 或 'exit' 退出")
    print("输入 'clear' 清空记忆")
    print("输入 'skills' 查看可用技能")
    print("=" * 60)
    print()

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
                skills = agent.skill_manager.get_skill_names()
                print(f"可用技能: {', '.join(skills)}")
                continue

            # 执行任务
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


async def main():
    """主函数"""
    import os

    # 检查 API Key
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not api_key:
        print("警告: 未设置 ANTHROPIC_AUTH_TOKEN 环境变量")
        print("请设置: export ANTHROPIC_AUTH_TOKEN='your-api-key' (Linux/Mac)")
        print("或: set ANTHROPIC_AUTH_TOKEN=your-api-key (Windows)")
        print()

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--web":
            # 启动 Web 服务器
            import uvicorn
            print("启动 Web 服务器: http://localhost:8000")
            uvicorn.run(app, host="0.0.0.0", port=8000)
            return

        if sys.argv[1] == "--demo":
            config = Config()
            if api_key:
                config.llm.api_key = api_key
                config.llm.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
                config.llm.model = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")
            agent = create_agent(config)
            await run_demo(agent)
            await agent.close()
            return

        if sys.argv[1] == "--task":
            config = Config()
            if api_key:
                config.llm.api_key = api_key
                config.llm.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
                config.llm.model = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")
            agent = create_agent(config)
            task = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "你好"
            result = await agent.run(task)
            print(result)
            await agent.close()
            return

    # 默认: 交互式 CLI
    config = Config()
    if api_key:
        config.llm.api_key = api_key
        config.llm.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        config.llm.model = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")

    agent = create_agent(config)

    try:
        await run_interactive(agent)
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())

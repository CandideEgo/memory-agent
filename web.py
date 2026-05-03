"""
Web 服务 - FastAPI 后端
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from .agent import Agent
    from .config import Config
except ImportError:
    from agent import Agent
    from config import Config

logger = logging.getLogger(__name__)

# 获取 agent 目录和 web 目录
AGENT_DIR = Path(__file__).parent.absolute()
WEB_DIR = AGENT_DIR / "web"

app = FastAPI(title="Memory Agent", description="AI Agent Web Interface")

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例
agent: Optional[Agent] = None
agent_lock = asyncio.Lock()


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    role: str
    content: str
    timestamp: str


def get_agent() -> Agent:
    """获取或创建 Agent 实例"""
    global agent
    if agent is None:
        agent = Agent(Config.from_env())
    return agent


@app.on_event("shutdown")
async def shutdown():
    """关闭时清理资源"""
    global agent
    if agent:
        await agent.close()
        agent = None


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/api/messages")
async def get_messages():
    """获取聊天历史"""
    ag = get_agent()
    messages = ag.memory.get_full_history()
    return {"messages": messages}


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """发送消息并获取响应（非流式）"""
    async with agent_lock:
        ag = get_agent()
        try:
            result = await ag.run(message.message)
            return {"role": "assistant", "content": result}
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 流式聊天"""
    await websocket.accept()

    ag = get_agent()

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            if not user_message:
                continue

            # 发送用户消息确认
            await websocket.send_json({
                "type": "user",
                "content": user_message
            })

            # 发送思考中状态
            await websocket.send_json({
                "type": "status",
                "content": "Agent 正在思考..."
            })

            # 执行任务
            try:
                result = await ag.run(user_message)
                await websocket.send_json({
                    "type": "assistant",
                    "content": result
                })
            except Exception as e:
                logger.error(f"Agent error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": f"执行错误: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except:
            pass


@app.post("/api/clear")
async def clear_memory():
    """清空记忆"""
    ag = get_agent()
    ag.memory.clear()
    ag.memory.save_to_file()
    return {"status": "ok"}


@app.get("/api/skills")
async def get_skills():
    """获取可用技能"""
    ag = get_agent()
    skills = ag.skill_manager.get_skill_names()
    return {"skills": skills}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)

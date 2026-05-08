"""
Web service - FastAPI backend.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from memory_store import MemoryStore
from agent_runner import AgentRunner
from context_builder import ContextBuilder

logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).parent.absolute()
WEB_DIR = AGENT_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    yield
    logger.info("Server shutting down")


app = FastAPI(title="Memory Agent", description="AI Agent Web Interface", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    role: str
    content: str
    timestamp: str


def _create_runner() -> AgentRunner:
    """Create a fresh runner and memory store."""
    return AgentRunner()


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(WEB_DIR / "index.html"))


@app.get("/api/messages")
async def get_messages():
    return {"messages": []}


@app.post("/api/chat")
async def chat(message: ChatMessage):
    runner = _create_runner()
    memory = MemoryStore()
    ctx = ContextBuilder()
    memory.add("user", message.message)
    system_prompt = ctx.build()
    try:
        result = await runner.run(memory, system_prompt)
        return {"role": "assistant", "content": result}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    runner = _create_runner()
    ctx = ContextBuilder()

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            if not user_message:
                continue

            await websocket.send_json({
                "type": "user",
                "content": user_message
            })

            await websocket.send_json({
                "type": "status",
                "content": "Agent thinking..."
            })

            try:
                memory = MemoryStore()
                memory.add("user", user_message)
                system_prompt = ctx.build()
                result = await runner.run(memory, system_prompt)
                await websocket.send_json({
                    "type": "assistant",
                    "content": result
                })
            except Exception as e:
                logger.error(f"Agent error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": str(e)
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
        except Exception:
            pass


@app.post("/api/clear")
async def clear_memory():
    return {"status": "ok"}


@app.get("/api/skills")
async def get_skills():
    from skills_manager import load_all_skills
    skills = load_all_skills()
    return {"skills": [s.name for s in skills]}


@app.get("/health")
async def health():
    """Health check endpoint."""
    mcp_connected = False
    try:
        from tools.mcp_bridge import get_bridge
        bridge = get_bridge()
        mcp_connected = bridge.is_connected()
    except Exception:
        mcp_connected = False
    return {"status": "ok", "mcp_connected": mcp_connected}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)

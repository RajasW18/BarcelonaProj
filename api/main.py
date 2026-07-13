"""
FastAPI application — entry point.

Endpoints:
  POST /chat   → SSE streaming chat endpoint
  GET  /health → healthcheck
"""
import asyncio
import uuid
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from api.agent import barca_agent
from api.db.connection import get_pool, close_pool


# Session store tracks conversation history as a list of messages
sessions: dict[str, list] = {}


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Barça Chat API",
    description="Voice-enabled agentic chatbot for FC Barcelona",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    session_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "BarcaBot"}


@app.post("/chat/session")
async def create_session() -> dict:
    """Create a new chat session and return its id."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    return {"session_id": session_id}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint — returns a Server-Sent Events stream.

    SSE event types emitted:
      {"type": "tool_call", "tool": "<name>"}  → agent called a tool
      {"type": "token",    "content": "<text>"} → streamed text word
      {"type": "done"}                          → stream complete
      {"type": "error",   "content": "<msg>"}  → error occurred
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    prev_messages = sessions.get(req.session_id, []) or []

    async def event_stream():
        try:
            input_messages = prev_messages + [{"role": "user", "content": req.message}]

            # Run the agent to completion (non-streaming).
            # This is the most reliable approach across providers.
            result = await Runner.run(
                barca_agent,
                input=input_messages,
                max_turns=25,
            )

            # Emit tool-call badges for any tools the agent used
            for item in result.new_items:
                item_type = getattr(item, "type", None)
                if item_type == "tool_call_item":
                    tool_name = getattr(item, "name", "unknown_tool")
                    payload = json.dumps({"type": "tool_call", "tool": tool_name})
                    yield f"data: {payload}\n\n"

            # Simulate word-by-word streaming for a smooth typing effect
            final_output = result.final_output or ""
            words = final_output.split(" ")
            for i, word in enumerate(words):
                chunk = word + ("" if i == len(words) - 1 else " ")
                payload = json.dumps({"type": "token", "content": chunk})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.015)  # ~65 words/sec

            # Persist conversation history
            sessions[req.session_id] = input_messages + [
                {"role": "assistant", "content": final_output}
            ]
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except MaxTurnsExceeded:
            payload = json.dumps({
                "type": "error",
                "content": "The agent needed too many steps to answer. Try a simpler question.",
            })
            yield f"data: {payload}\n\n"
        except Exception as exc:
            payload = json.dumps({"type": "error", "content": str(exc)})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

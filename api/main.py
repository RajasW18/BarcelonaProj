"""
FastAPI application — entry point.

Endpoints:
  POST /chat   → SSE streaming chat endpoint
  GET  /health → healthcheck
"""
import asyncio
import uuid
import json
import secrets
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
import httpx

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from api.agent import barca_agent, generate_general_response
from api.db.connection import get_pool, close_pool
from api.context import prepare_context
from api.config import settings
from api.auth import (
    COOKIE_NAME,
    create_or_update_user,
    current_user,
    exchange_google_code,
    google_authorization_url,
    hash_otp,
    oauth_state,
    send_otp_email,
    set_auth_cookie,
)


_STAT_TERMS = (
    "standings", "table", "points", "fixtures", "fixture", "score", "scores",
    "result", "results", "league position", "top scorer", "goals", "assists",
    "appearances", "cards", "statistics", "stats", "match", "matches",
)


def _needs_stats_tool(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in _STAT_TERMS)


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    await pool.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.chat_sessions') IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_sessions' AND column_name = 'user_id'
               ) THEN
                ALTER TABLE chat_sessions RENAME TO legacy_chat_sessions;
            END IF;
        END $$;
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY, email VARCHAR(320) UNIQUE NOT NULL,
            display_name VARCHAR(150), avatar_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS auth_otps (
            id BIGSERIAL PRIMARY KEY, email VARCHAR(320) NOT NULL,
            code_hash CHAR(64) NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id UUID PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(160) NOT NULL DEFAULT 'New match room',
            created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id BIGSERIAL PRIMARY KEY, session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL, sources JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON chat_sessions(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON chat_messages(session_id, created_at);
        """
    )
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
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: str = ""
    sources: list[str] = []


class EmailRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    code: str


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Ninety"}


@app.get("/auth/me")
async def auth_me(request: Request):
    return await current_user(request)


@app.post("/auth/request-otp")
async def request_otp(req: EmailRequest):
    email = req.email.lower().strip()
    if "@" not in email or len(email) > 320:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM auth_otps WHERE email = $1 OR expires_at < NOW()",
        email,
    )
    await pool.execute(
        "INSERT INTO auth_otps (email, code_hash, expires_at) VALUES ($1, $2, $3)",
        email,
        hash_otp(code),
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    await send_otp_email(email, code)
    return {"message": "A sign-in code has been sent to your email."}


@app.post("/auth/verify-otp")
async def verify_otp(req: VerifyOtpRequest, response: Response):
    email = req.email.lower().strip()
    pool = await get_pool()
    otp = await pool.fetchrow(
        """
        SELECT id FROM auth_otps
        WHERE email = $1 AND code_hash = $2
          AND consumed_at IS NULL AND expires_at > NOW()
        ORDER BY created_at DESC LIMIT 1
        """,
        email,
        hash_otp(req.code.strip()),
    )
    if not otp:
        raise HTTPException(status_code=400, detail="That code is invalid or expired.")
    await pool.execute("UPDATE auth_otps SET consumed_at = NOW() WHERE id = $1", otp["id"])
    user = await create_or_update_user(email)
    await set_auth_cookie(response, user["id"])
    return user


@app.get("/auth/google/login")
async def google_login(response: Response):
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    state = oauth_state()
    redirect = RedirectResponse(await google_authorization_url(state))
    redirect.set_cookie("ninety_oauth_state", state, httponly=True, secure=settings.auth_cookie_secure, samesite=settings.auth_cookie_samesite, max_age=600)
    return redirect


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    if not secrets.compare_digest(state, request.cookies.get("ninety_oauth_state", "")):
        raise HTTPException(status_code=400, detail="OAuth state validation failed.")
    try:
        profile = await exchange_google_code(code)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="Google sign-in could not be completed.") from exc
    user = await create_or_update_user(profile["email"], profile.get("name"), profile.get("picture"))
    redirect = RedirectResponse(settings.frontend_url)
    await set_auth_cookie(redirect, user["id"])
    redirect.delete_cookie("ninety_oauth_state")
    return redirect


@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Signed out."}


@app.post("/chat/session")
async def create_session(request: Request) -> dict:
    """Create a persisted chat session for the signed-in user."""
    user = await current_user(request)
    session_id = str(uuid.uuid4())
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO chat_sessions (id, user_id) VALUES ($1, $2)",
        uuid.UUID(session_id),
        user["id"],
    )
    return {"session_id": session_id}


@app.get("/chat/sessions")
async def list_sessions(request: Request):
    user = await current_user(request)
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, title, created_at, updated_at
        FROM chat_sessions WHERE user_id = $1
        ORDER BY updated_at DESC
        """,
        user["id"],
    )
    return [dict(row) for row in rows]


@app.get("/chat/sessions/{session_id}")
async def get_session_history(session_id: str, request: Request):
    user = await current_user(request)
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT m.id, m.role, m.content, m.sources
        FROM chat_messages m
        JOIN chat_sessions s ON s.id = m.session_id
        WHERE m.session_id = $1 AND s.user_id = $2
        ORDER BY m.created_at
        """,
        uuid.UUID(session_id),
        user["id"],
    )
    if rows is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return [dict(row) for row in rows]


@app.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    user = await current_user(request)
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM chat_sessions WHERE id = $1 AND user_id = $2",
        uuid.UUID(session_id),
        user["id"],
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {"message": "Chat deleted."}


@app.post("/attachments/prepare")
async def attachments_prepare(
    files: list[UploadFile] = File(default=[]),
    url: str | None = Form(default=None),
) -> dict:
    """Extract approved attachment and public URL context before chat processing."""
    try:
        return await prepare_context(files, url.strip() if url else None)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
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

    user = await current_user(request)
    pool = await get_pool()
    session_uuid = uuid.UUID(req.session_id)
    session_exists = await pool.fetchval(
        "SELECT 1 FROM chat_sessions WHERE id = $1 AND user_id = $2",
        session_uuid,
        user["id"],
    )
    if not session_exists:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    stored_rows = await pool.fetch(
        """
        SELECT role, content FROM chat_messages
        WHERE session_id = $1 ORDER BY created_at
        """,
        session_uuid,
    )
    prev_messages = [dict(row) for row in stored_rows]

    async def event_stream():
        try:
            user_content = req.message
            if req.context:
                user_content += (
                    "\n\nThe user approved the following context for this request. "
                    "Use it as evidence and cite the listed sources when relevant:\n"
                    f"{req.context}"
                )
            input_messages = prev_messages + [{"role": "user", "content": user_content}]

            if _needs_stats_tool(req.message):
                result = await Runner.run(
                    barca_agent,
                    input=input_messages,
                    max_turns=25,
                )
                final_output = result.final_output or ""
                new_items = result.new_items
            else:
                final_output = await generate_general_response(input_messages)
                new_items = []

            # Emit tool-call badges for any tools the agent used
            for item in new_items:
                item_type = getattr(item, "type", None)
                if item_type == "tool_call_item":
                    tool_name = getattr(item, "name", "unknown_tool")
                    payload = json.dumps({"type": "tool_call", "tool": tool_name})
                    yield f"data: {payload}\n\n"

            # Simulate word-by-word streaming for a smooth typing effect
            words = final_output.split(" ")
            for i, word in enumerate(words):
                chunk = word + ("" if i == len(words) - 1 else " ")
                payload = json.dumps({"type": "token", "content": chunk})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.015)  # ~65 words/sec

            await pool.executemany(
                "INSERT INTO chat_messages (session_id, role, content, sources) VALUES ($1, $2, $3, $4::jsonb)",
                [
                    (session_uuid, "user", req.message.strip(), json.dumps(req.sources)),
                    (session_uuid, "assistant", final_output, json.dumps(req.sources)),
                ],
            )
            await pool.execute(
                """
                UPDATE chat_sessions
                SET title = CASE WHEN title = 'New match room' THEN LEFT($1, 160) ELSE title END,
                    updated_at = NOW()
                WHERE id = $2
                """,
                req.message.strip(),
                session_uuid,
            )
            if req.sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': req.sources})}\n\n"
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

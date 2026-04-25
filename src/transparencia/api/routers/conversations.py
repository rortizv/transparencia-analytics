import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from transparencia.db.connection import get_conn

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Models ─────────────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    user_id: str
    title: str = "Nueva conversación"


class ConversationUpdate(BaseModel):
    title: str | None = None
    is_favorite: bool | None = None


class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    is_favorite: bool
    created_at: str
    updated_at: str
    last_message_at: str


class PredictionLogCreate(BaseModel):
    user_id: str
    user_message: str
    assistant_response: str | None = None
    tool_invocations: list[dict[str, Any]] = []
    duration_ms: int | None = None
    is_success: bool = True
    error_message: str | None = None


class PredictionLog(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    user_message: str
    assistant_response: str | None
    tool_invocations: list[dict[str, Any]]
    duration_ms: int | None
    is_success: bool
    error_message: str | None
    created_at: str


# ── Conversations ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[Conversation])
async def list_conversations(user_id: str = Query(...)) -> list[Conversation]:
    sql = """
        SELECT id::text, user_id, title, is_favorite,
               created_at::text, updated_at::text, last_message_at::text
        FROM   conversations
        WHERE  user_id = %s
        ORDER  BY is_favorite DESC, last_message_at DESC
        LIMIT  200
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [user_id])
            rows = await cur.fetchall()
            cols = [d.name for d in cur.description or []]
    return [Conversation(**dict(zip(cols, r))) for r in rows]


@router.post("", response_model=Conversation, status_code=201)
async def create_conversation(body: ConversationCreate) -> Conversation:
    sql = """
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id::text, user_id, title, is_favorite,
                  created_at::text, updated_at::text, last_message_at::text
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [body.user_id, body.title])
            row = await cur.fetchone()
            cols = [d.name for d in cur.description or []]
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    return Conversation(**dict(zip(cols, row)))


@router.patch("/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
) -> Conversation:
    sets: list[str] = []
    params: list[Any] = []

    if body.title is not None:
        sets.append("title = %s")
        params.append(body.title)
    if body.is_favorite is not None:
        sets.append("is_favorite = %s")
        params.append(body.is_favorite)
    if not sets:
        raise HTTPException(status_code=422, detail="Nothing to update")

    params.append(conversation_id)
    sql = f"""
        UPDATE conversations
        SET    {', '.join(sets)}
        WHERE  id = %s
        RETURNING id::text, user_id, title, is_favorite,
                  created_at::text, updated_at::text, last_message_at::text
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()
            cols = [d.name for d in cur.description or []]
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Conversation(**dict(zip(cols, row)))


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str) -> None:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM conversations WHERE id = %s", [conversation_id])


# ── Prediction logs ────────────────────────────────────────────────────────────

@router.get("/{conversation_id}/logs", response_model=list[PredictionLog])
async def list_logs(conversation_id: str) -> list[PredictionLog]:
    sql = """
        SELECT id::text, conversation_id::text, user_id,
               user_message, assistant_response, tool_invocations,
               duration_ms, is_success, error_message, created_at::text
        FROM   prediction_logs
        WHERE  conversation_id = %s
        ORDER  BY created_at ASC
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [conversation_id])
            rows = await cur.fetchall()
            cols = [d.name for d in cur.description or []]
    return [PredictionLog(**dict(zip(cols, r))) for r in rows]


@router.post("/{conversation_id}/logs", response_model=PredictionLog, status_code=201)
async def create_log(
    conversation_id: str,
    body: PredictionLogCreate,
) -> PredictionLog:
    sql = """
        INSERT INTO prediction_logs
            (conversation_id, user_id, user_message, assistant_response,
             tool_invocations, duration_ms, is_success, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text, conversation_id::text, user_id,
                  user_message, assistant_response, tool_invocations,
                  duration_ms, is_success, error_message, created_at::text
    """
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, [
                conversation_id,
                body.user_id,
                body.user_message,
                body.assistant_response,
                json.dumps(body.tool_invocations),
                body.duration_ms,
                body.is_success,
                body.error_message,
            ])
            row = await cur.fetchone()
            cols = [d.name for d in cur.description or []]
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create log")
    return PredictionLog(**dict(zip(cols, row)))

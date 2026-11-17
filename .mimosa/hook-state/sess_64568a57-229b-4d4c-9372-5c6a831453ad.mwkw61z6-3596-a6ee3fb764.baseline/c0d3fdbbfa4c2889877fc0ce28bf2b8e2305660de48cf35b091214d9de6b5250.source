"""Assistant endpoints: grounded Q&A routing + optional BYOK chat (assistant.md)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from logicforge_api.assistant import AssistantError, ask
from logicforge_api.assistant_chat import chat, resolve_key

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    question: str
    context: dict[str, Any] | None = Field(default=None)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    messages: list[ChatMessage] = Field(default_factory=list)
    context: dict[str, Any] | None = Field(default=None)
    base_url: str | None = None
    model: str | None = None


@router.post("/ask")
def ask_endpoint(request: AskRequest) -> dict[str, Any]:
    try:
        return ask(request.question, request.context)
    except AssistantError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "ASSISTANT_ERROR", "category": exc.category, "message": exc.message},
        ) from exc


@router.post("/chat")
def chat_endpoint(request: ChatRequest, x_assistant_key: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        key = resolve_key(x_assistant_key)
        return chat(
            messages=[m.model_dump() for m in request.messages],
            question=request.question,
            context=request.context,
            api_key=key,
            base_url=request.base_url,
            model=request.model,
        )
    except AssistantError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "ASSISTANT_ERROR", "category": exc.category, "message": exc.message},
        ) from exc

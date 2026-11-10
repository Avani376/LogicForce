"""Assistant endpoint: grounded Q&A routing (assistant.md, Phase AI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from logicforge_api.assistant import AssistantError, ask

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    question: str
    context: dict[str, Any] | None = Field(default=None)


@router.post("/ask")
def ask_endpoint(request: AskRequest) -> dict[str, Any]:
    try:
        return ask(request.question, request.context)
    except AssistantError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "ASSISTANT_ERROR", "category": exc.category, "message": exc.message},
        ) from exc

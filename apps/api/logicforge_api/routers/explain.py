"""Explanation endpoint (Phase 9).

POST /api/explain — evidence-grounded explanations from engine output.
Deterministic, rule-based, no LLM. Every finding cites trace steps.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from logic_engine import SchemaError
from pydantic import BaseModel, Field
from verify_engine import (
    explain as run_explanation,
)
from verify_engine import (
    explanation_to_dict,
    parse_explanation_request,
)

router = APIRouter(prefix="/api", tags=["explain"])


class ExplainRequest(BaseModel):
    kind: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    question: str | None = None


@router.post("/explain")
def explain_endpoint(request: ExplainRequest) -> dict[str, Any]:
    try:
        kind, evidence, question = parse_explanation_request(
            {
                "explanation_schema_version": 1,
                "kind": request.kind,
                "evidence": request.evidence,
                "question": request.question,
            }
        )
        report = run_explanation(kind, evidence, question)
    except SchemaError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    result = explanation_to_dict(report)
    result["question"] = request.question
    return result

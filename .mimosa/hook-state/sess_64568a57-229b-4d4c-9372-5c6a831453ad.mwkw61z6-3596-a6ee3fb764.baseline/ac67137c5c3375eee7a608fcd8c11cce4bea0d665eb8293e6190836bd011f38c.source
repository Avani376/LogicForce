"""Optimization endpoint (Phase 5b).

POST /api/optimize — behavior-preserving optimization via optimize_engine.
Verdicts and equivalence evidence come exclusively from the engine.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from logic_engine import CircuitNotValidError, SchemaError
from optimize_engine import (
    optimization_report_to_dict,
)
from optimize_engine import (
    optimize as run_optimization,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["optimize"])


class OptimizeRequest(BaseModel):
    model: dict[str, Any]
    properties: list[dict[str, Any]] = Field(default_factory=list)
    max_transformations: int = 32


@router.post("/optimize")
def optimize_endpoint(request: OptimizeRequest) -> dict[str, Any]:
    try:
        report = run_optimization(request.model, request.properties, request.max_transformations)
    except CircuitNotValidError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_FAILED",
                "errors": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "component_id": issue.component_id,
                        "net_id": issue.net_id,
                    }
                    for issue in exc.report.errors
                ],
                "warnings": [],
            },
        ) from exc
    except SchemaError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    return optimization_report_to_dict(report)

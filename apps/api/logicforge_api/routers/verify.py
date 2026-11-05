"""Verification endpoint (Phase 3c).

POST /api/verify — property checking by the verification engine. Verdicts are
computed exclusively by verify_engine; this router maps typed errors onto HTTP
responses and never computes results itself.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from logic_engine import CircuitNotValidError, InvalidInputValueError, SchemaError
from pydantic import BaseModel, Field
from verify_engine import (
    verification_report_to_dict,
    verify_combinational_invariant,
    verify_fsm_invariant,
)

router = APIRouter(prefix="/api", tags=["verify"])


class PropertyIn(BaseModel):
    property_schema_version: int
    id: str
    kind: str
    statement: str | None = None
    expression: str


class VerifyRequest(BaseModel):
    kind: str
    model: dict[str, Any]
    property: PropertyIn = Field(alias="property")

    model_config = {"populate_by_name": True}


@router.post("/verify")
def verify_endpoint(request: VerifyRequest) -> dict[str, Any]:
    property_doc: dict[str, Any] = {
        "property_schema_version": request.property.property_schema_version,
        "id": request.property.id,
        "kind": request.property.kind,
        "statement": request.property.statement,
        "expression": request.property.expression,
    }
    try:
        if request.kind == "combinational_invariant":
            report = verify_combinational_invariant(request.model, property_doc)
        elif request.kind == "fsm_invariant":
            report = verify_fsm_invariant(request.model, property_doc)
        else:
            raise SchemaError(
                "PROPERTY_SCHEMA_ERROR",
                f"model kind must be 'combinational_invariant' or 'fsm_invariant', "
                f"got {request.kind!r}",
            )
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
    except InvalidInputValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_INPUT_VALUE",
                "message": str(exc),
                "input": exc.name,
            },
        ) from exc
    except SchemaError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return verification_report_to_dict(report)

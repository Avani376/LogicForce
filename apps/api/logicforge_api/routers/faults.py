"""Fault and repair endpoints (Phase 4d).

POST /api/faults/apply — apply a fault to a model, return the faulty model.
POST /api/fault-experiments — apply + behavior probe + property-suite detection.
POST /api/repair-search — delta-guided candidates, every one re-verified.

All results are computed by fault_engine / repair_engine over verify_engine
verdicts; this router only maps typed errors onto HTTP responses.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fault_engine import (
    apply_fault,
    fault_experiment_report_to_dict,
    parse_fault,
    run_fault_experiment,
)
from logic_engine import CircuitNotValidError, InvalidInputValueError, SchemaError
from pydantic import BaseModel, Field
from repair_engine import repair_report_to_dict, search_repairs

router = APIRouter(prefix="/api", tags=["faults"])


class ApplyFaultRequest(BaseModel):
    model_kind: str
    model: dict[str, Any]
    fault: dict[str, Any]


class FaultExperimentRequest(BaseModel):
    model_kind: str
    model: dict[str, Any]
    fault: dict[str, Any]
    properties: list[dict[str, Any]] = Field(default_factory=list)


class RepairSearchRequest(BaseModel):
    model_kind: str
    nominal: dict[str, Any]
    faulty: dict[str, Any]
    properties: list[dict[str, Any]] = Field(default_factory=list)
    max_candidates: int = 16


def _map_schema_error(exc: SchemaError) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})


@router.post("/faults/apply")
def apply_fault_endpoint(request: ApplyFaultRequest) -> dict[str, Any]:
    try:
        validated = parse_fault(request.fault)
        faulty = apply_fault(request.model_kind, request.model, validated)
    except SchemaError as exc:
        raise _map_schema_error(exc) from exc
    return {"faulty_model": faulty}


@router.post("/fault-experiments")
def fault_experiment_endpoint(request: FaultExperimentRequest) -> dict[str, Any]:
    try:
        report = run_fault_experiment(request.model_kind, request.model, request.fault, request.properties)
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
        raise _map_schema_error(exc) from exc
    return fault_experiment_report_to_dict(report)


@router.post("/repair-search")
def repair_search_endpoint(request: RepairSearchRequest) -> dict[str, Any]:
    try:
        report = search_repairs(
            request.model_kind,
            request.nominal,
            request.faulty,
            request.properties,
            request.max_candidates,
        )
    except CircuitNotValidError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_FAILED", "errors": [{"message": str(exc)}], "warnings": []},
        ) from exc
    except SchemaError as exc:
        raise _map_schema_error(exc) from exc
    return repair_report_to_dict(report)

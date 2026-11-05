"""Sequential and FSM endpoints (Phase 2c).

Error mapping follows ``docs/API.md``: typed engine errors (``SchemaError`` with
sequential/FSM codes, ``CircuitNotValidError``) map to HTTP 400 with machine-readable
codes; pydantic shape errors are HTTP 422. Results are computed exclusively by the
engines; responses are the engine presenters verbatim.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from logic_engine import CircuitNotValidError, SchemaError
from pydantic import BaseModel, Field
from sequential_engine import (
    SEQUENTIAL_ENGINE_VERSION,
    fsm_reachable,
    fsm_result_to_dict,
    fsm_simulate,
    parse_fsm,
    sequential_result_to_dict,
    simulate_sequential,
)

router = APIRouter(prefix="/api", tags=["sequential"])


class SequentialRequest(BaseModel):
    circuit: dict[str, Any]
    cycles: int
    inputs_per_cycle: list[dict[str, Any]] = Field(default_factory=list)


class FSMRequest(BaseModel):
    fsm: dict[str, Any]
    input_sequence: list[dict[str, str]] = Field(default_factory=list)


class FSMReachableRequest(BaseModel):
    fsm: dict[str, Any]


def _schema_error(status: int, exc: SchemaError) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


@router.post("/sequential/simulate")
def simulate_sequential_endpoint(request: SequentialRequest) -> dict[str, Any]:
    try:
        result = simulate_sequential(request.circuit, request.cycles, request.inputs_per_cycle)
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
                "warnings": [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "component_id": issue.component_id,
                        "net_id": issue.net_id,
                    }
                    for issue in exc.report.warnings
                ],
            },
        ) from exc
    except SchemaError as exc:
        raise _schema_error(400, exc) from exc
    return sequential_result_to_dict(result)


@router.post("/fsm/simulate")
def simulate_fsm_endpoint(request: FSMRequest) -> dict[str, Any]:
    try:
        fsm = parse_fsm(request.fsm)
        result = fsm_simulate(fsm, request.input_sequence)
    except SchemaError as exc:
        raise _schema_error(400, exc) from exc
    return fsm_result_to_dict(result)


@router.post("/fsm/reachable")
def reachable_fsm_endpoint(request: FSMReachableRequest) -> dict[str, Any]:
    try:
        fsm = parse_fsm(request.fsm)
        reachable, scope = fsm_reachable(fsm)
    except SchemaError as exc:
        raise _schema_error(400, exc) from exc
    return {
        "reachable_states": list(reachable),
        "scope": scope,
        "declared_states": list(fsm.states),
        "engine_version": SEQUENTIAL_ENGINE_VERSION,
    }

"""Circuit endpoints: validate, simulate, truth-table.

Error mapping (contract in ``docs/API.md``):
- ``SchemaError`` (malformed document) → HTTP 400 ``{code, message}``
- ``CircuitNotValidError`` → HTTP 400 ``{code: VALIDATION_FAILED, errors, warnings}``
- ``InvalidInputValueError`` → HTTP 400 ``{code: INVALID_INPUT_VALUE, ...}``
- ``TruthTableLimitExceededError`` → HTTP 400 ``{code: TRUTH_TABLE_LIMIT_EXCEEDED, ...}``
- malformed request *shape* (pydantic) → HTTP 422
Validation results for well-formed documents are HTTP 200 with ``ok: false`` —
invalidity is a result, not a transport error.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from logic_engine import (
    ENGINE_VERSION,
    CircuitGraph,
    CircuitNotValidError,
    InvalidInputValueError,
    SchemaError,
    TruthTableLimitExceededError,
    input_hash,
    parse_circuit,
    simulate,
    truth_table,
    validate,
)

from logicforge_api.schemas import (
    CircuitRequest,
    SimulateRequest,
    SimulationOut,
    TruthTableOut,
    ValidationReportOut,
    present_report,
    present_simulation,
    present_truth_table,
)

router = APIRouter(prefix="/api/circuits", tags=["circuits"])


def _parse_or_400(circuit: dict[str, object]) -> CircuitGraph:
    try:
        return parse_circuit(circuit)
    except SchemaError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.post("/validate", response_model=ValidationReportOut)
def validate_circuit(request: CircuitRequest) -> ValidationReportOut:
    graph = _parse_or_400(request.circuit)
    report = validate(graph)
    return present_report(report, engine_version=ENGINE_VERSION)


@router.post("/simulate", response_model=SimulationOut)
def simulate_circuit(request: SimulateRequest) -> SimulationOut:
    graph = _parse_or_400(request.circuit)
    try:
        result = simulate(graph, request.inputs)
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
    except InvalidInputValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_INPUT_VALUE",
                "message": str(exc),
                "input": exc.name,
            },
        ) from exc
    hash_hex = input_hash(request.circuit, request.inputs)
    return present_simulation(result, input_hash_hex=hash_hex)


@router.post("/truth-table", response_model=TruthTableOut)
def truth_table_circuit(request: CircuitRequest) -> TruthTableOut:
    graph = _parse_or_400(request.circuit)
    try:
        result = truth_table(graph)
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
    except TruthTableLimitExceededError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TRUTH_TABLE_LIMIT_EXCEEDED",
                "message": str(exc),
                "input_count": exc.input_count,
                "limit": exc.limit,
            },
        ) from exc
    hash_hex = input_hash(request.circuit, {})
    return present_truth_table(result, input_hash_hex=hash_hex)

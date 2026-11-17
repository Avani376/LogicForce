"""Pydantic request/response models and engine→JSON presentation.

Response shapes follow ``docs/semantics/report-and-scope-labels.md``; the engine
dataclasses are the single source of truth, and the presenters below only re-shape
them for JSON — they never compute values.
"""

from __future__ import annotations

from logic_engine import (
    SCHEMA_VERSION,
    SimulationResult,
    TraceEvent,
    TruthTableResult,
    ValidationIssue,
    ValidationReport,
)
from pydantic import BaseModel, Field

# --- requests ------------------------------------------------------------------


class CircuitRequest(BaseModel):
    """A circuit document (schema v1) for validation."""

    circuit: dict[str, object]


class SimulateRequest(BaseModel):
    """A circuit plus a primary-input vector (omitted inputs default to ``X``)."""

    circuit: dict[str, object]
    inputs: dict[str, object] = Field(default_factory=dict)


# --- responses -----------------------------------------------------------------


class ValidationIssueOut(BaseModel):
    code: str
    message: str
    component_id: str | None = None
    net_id: str | None = None


class ValidationReportOut(BaseModel):
    schema_version: int
    engine_version: str
    ok: bool
    errors: list[ValidationIssueOut]
    warnings: list[ValidationIssueOut]


class TraceCauseOut(BaseModel):
    type: str
    component: str


class TraceEventOut(BaseModel):
    seq: int
    delta: int
    net: str
    old: str
    new: str
    cause: TraceCauseOut


class SimulationOut(BaseModel):
    schema_version: int
    engine_version: str
    input_hash: str
    scope: str
    outputs: dict[str, str]
    event_count: int
    trace: list[TraceEventOut]


class TruthTableRowOut(BaseModel):
    inputs: dict[str, str]
    outputs: dict[str, str]


class TruthTableOut(BaseModel):
    schema_version: int
    engine_version: str
    input_hash: str
    scope: str
    input_names: list[str]
    output_names: list[str]
    rows: list[TruthTableRowOut]


# --- presenters (engine objects → response models) ------------------------------


def present_issue(issue: ValidationIssue) -> ValidationIssueOut:
    return ValidationIssueOut(
        code=issue.code,
        message=issue.message,
        component_id=issue.component_id,
        net_id=issue.net_id,
    )


def present_report(report: ValidationReport, engine_version: str) -> ValidationReportOut:
    return ValidationReportOut(
        schema_version=SCHEMA_VERSION,
        engine_version=engine_version,
        ok=report.ok,
        errors=[present_issue(issue) for issue in report.errors],
        warnings=[present_issue(issue) for issue in report.warnings],
    )


def present_trace_event(event: TraceEvent) -> TraceEventOut:
    return TraceEventOut(
        seq=event.seq,
        delta=event.delta,
        net=event.net,
        old=event.old,
        new=event.new,
        cause=TraceCauseOut(type=event.cause.type, component=event.cause.component),
    )


def present_simulation(result: SimulationResult, input_hash_hex: str) -> SimulationOut:
    return SimulationOut(
        schema_version=SCHEMA_VERSION,
        engine_version=result.engine_version,
        input_hash=input_hash_hex,
        scope=result.scope,
        outputs=result.outputs,
        event_count=result.event_count,
        trace=[present_trace_event(event) for event in result.trace],
    )


def present_truth_table(result: TruthTableResult, input_hash_hex: str) -> TruthTableOut:
    return TruthTableOut(
        schema_version=SCHEMA_VERSION,
        engine_version=result.engine_version,
        input_hash=input_hash_hex,
        scope=result.scope,
        input_names=list(result.input_names),
        output_names=list(result.output_names),
        rows=[TruthTableRowOut(inputs=dict(row.inputs), outputs=dict(row.outputs)) for row in result.rows],
    )

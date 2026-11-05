"""Fault experiment pipeline: behavior probe + property-suite detection.

Normative contract: ``docs/semantics/faults-and-repair.md``. The experiment
applies a fault, probes nominal-vs-faulty behavior with bounded labeled probes,
then detects the fault via the Phase-3 verification engine (nominal PASS +
faulty FAIL = detected). Faults no property detects are reported honestly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from logic_engine import LogicValue, SchemaError
from logic_engine.hashing import canonical_json
from logic_engine.values import normalize_value
from sequential_engine import fsm_simulate, parse_fsm
from verify_engine import (
    verify_combinational_invariant,
    verify_fsm_invariant,
)

from fault_engine.faults import apply_fault, parse_fault
from fault_engine.version import FAULT_ENGINE_VERSION

SCHEMA_VERSION = 1

#: FSM vector-sweep bound: input alphabets above this are not swept.
MAX_FSM_SWEEP_INPUTS = 6


@dataclass(frozen=True)
class CheckResult:
    id: str
    nominal_verdict: str
    faulty_verdict: str
    detected: bool
    counterexample: dict[str, object] | None


@dataclass(frozen=True)
class FaultExperimentReport:
    engine_version: str
    input_hash: str
    fault: dict[str, object]
    applied: bool
    nominal_hash: str
    faulty_hash: str
    behavior: dict[str, object]
    checks: tuple[CheckResult, ...]
    detected: bool


def _doc_hash(doc: Mapping[str, object]) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(dict(doc)).encode("utf-8")).hexdigest()


def _value_map(raw: Mapping[str, str]) -> dict[str, LogicValue]:
    return {name: normalize_value(value) for name, value in raw.items()}


def _probe_combinational(
    nominal: Mapping[str, object], faulty: Mapping[str, object], property_raw: object
) -> dict[str, object]:
    """EXHAUSTIVE truth-table diff (bounded by the 12-input rule via verify)."""
    from logic_engine import parse_circuit as parse_circuit_v1
    from logic_engine import simulate as v1_simulate
    from logic_engine.validation import require_valid as v1_require_valid
    from verify_engine.expressions import evaluate_expression, parse_expression

    nominal_graph = parse_circuit_v1(dict(nominal))
    v1_require_valid(nominal_graph)
    faulty_graph = parse_circuit_v1(dict(faulty))
    v1_require_valid(faulty_graph)

    input_names = tuple(
        sorted(
            str(c.params["name"])
            for c in nominal_graph.components
            if c.type == "INPUT" and isinstance(c.params.get("name"), str)
        )
    )
    if len(input_names) > 12:
        return {
            "kind": "combinational",
            "scope": "INCOMPLETE",
            "first_divergence": None,
            "differing_rows": None,
            "reason": f"MODEL_TOO_LARGE: {len(input_names)} inputs exceed the 12-input probe bound",
        }

    expression = parse_expression(
        (property_raw or {}).get("expression", "1") if isinstance(property_raw, Mapping) else "1"
    )
    differing = 0
    first: dict[str, object] | None = None
    explored = 0
    for index in range(1 << len(input_names)):
        vector = {
            name: ("1" if (index >> (len(input_names) - 1 - position)) & 1 else "0")
            for position, name in enumerate(input_names)
        }
        nominal_out = v1_simulate(nominal_graph, _value_map(vector)).outputs
        faulty_out = v1_simulate(faulty_graph, _value_map(vector)).outputs
        explored += 1
        if nominal_out != faulty_out:
            differing += 1
            if first is None:
                first = {
                    "inputs": dict(vector),
                    "nominal_outputs": dict(nominal_out),
                    "faulty_outputs": dict(faulty_out),
                }
        # also flag X-poisoned rows the property would reject
        env = {name: LogicValue(value) for name, value in faulty_out.items()}
        if evaluate_expression(expression, env) != LogicValue.ONE and first is None:
            first = {
                "inputs": dict(vector),
                "nominal_outputs": dict(nominal_out),
                "faulty_outputs": dict(faulty_out),
            }
    return {
        "kind": "combinational",
        "scope": f"EXHAUSTIVE({explored} rows)",
        "first_divergence": first,
        "differing_rows": differing,
        "reason": None,
    }


def _probe_fsm(nominal: Mapping[str, object], faulty: Mapping[str, object]) -> dict[str, object]:
    """BOUNDED vector sweep: every input vector fires once, in MSB order."""
    nominal_fsm = parse_fsm(dict(nominal))
    faulty_fsm = parse_fsm(dict(faulty))
    width = len(nominal_fsm.inputs)
    if width > MAX_FSM_SWEEP_INPUTS:
        return {
            "kind": "fsm",
            "scope": "INCOMPLETE",
            "first_divergence": None,
            "reason": (
                f"MODEL_TOO_LARGE: {width} inputs exceed the "
                f"{MAX_FSM_SWEEP_INPUTS}-input sweep bound"
            ),
        }
    cycles = 1 << width
    nominal_trace = fsm_simulate(
        nominal_fsm, [dict(v) for v in _sweep_vectors(nominal_fsm.inputs, cycles)]
    )
    faulty_trace = fsm_simulate(
        faulty_fsm, [dict(v) for v in _sweep_vectors(faulty_fsm.inputs, cycles)]
    )
    for nominal_row, faulty_row in zip(nominal_trace.cycles, faulty_trace.cycles, strict=False):
        if nominal_row.state != faulty_row.state or nominal_row.outputs != faulty_row.outputs:
            return {
                "kind": "fsm",
                "scope": f"BOUNDED({cycles} cycles)",
                "first_divergence": {
                    "cycle": nominal_row.cycle,
                    "inputs": dict(nominal_row.inputs),
                    "nominal_state": nominal_row.state,
                    "faulty_state": faulty_row.state,
                    "nominal_outputs": dict(nominal_row.outputs),
                    "faulty_outputs": dict(faulty_row.outputs),
                },
                "reason": None,
            }
    return {
        "kind": "fsm",
        "scope": f"BOUNDED({cycles} cycles)",
        "first_divergence": None,
        "reason": None,
    }


def _sweep_vectors(inputs: tuple[str, ...], cycles: int) -> list[dict[str, str]]:
    vectors: list[dict[str, str]] = []
    width = len(inputs)
    total = 1 << width
    for cycle in range(cycles):
        index = cycle % total
        vectors.append(
            {
                name: ("1" if (index >> (width - 1 - position)) & 1 else "0")
                for position, name in enumerate(inputs)
            }
        )
    return vectors


def run_fault_experiment(
    model_kind: str,
    model: Mapping[str, object],
    fault_raw: object,
    properties: Sequence[Mapping[str, object]],
) -> FaultExperimentReport:
    """Apply the fault, probe behavior, and detect via the property suite."""
    fault = parse_fault(fault_raw)
    if model_kind not in ("fsm", "combinational"):
        raise SchemaError(
            "FAULT_SCHEMA_ERROR",
            f"model_kind must be 'fsm' or 'combinational', got {model_kind!r}",
        )
    properties_list = list(properties)

    faulty_model = apply_fault(model_kind, model, fault)
    nominal_hash = _doc_hash(model)
    faulty_hash = _doc_hash(faulty_model)

    if model_kind == "fsm":
        behavior = _probe_fsm(model, faulty_model)
    else:
        behavior = _probe_combinational(
            model,
            faulty_model,
            properties_list[0] if properties_list else {},
        )

    checks: list[CheckResult] = []
    detected = False
    for property_raw in properties_list:
        if model_kind == "fsm":
            nominal_report = verify_fsm_invariant(model, property_raw)
            faulty_report = verify_fsm_invariant(faulty_model, property_raw)
        else:
            nominal_report = verify_combinational_invariant(model, property_raw)
            faulty_report = verify_combinational_invariant(faulty_model, property_raw)
        detected_by_this = nominal_report.verdict == "PASS" and faulty_report.verdict == "FAIL"
        detected = detected or detected_by_this
        counterexample: dict[str, object] | None = None
        if faulty_report.verdict == "FAIL" and faulty_report.counterexample is not None:
            counterexample = faulty_report.counterexample
        checks.append(
            CheckResult(
                id=str(property_raw.get("id", "unnamed")),
                nominal_verdict=nominal_report.verdict,
                faulty_verdict=faulty_report.verdict,
                detected=detected_by_this,
                counterexample=counterexample,
            )
        )

    payload = {
        "model_kind": model_kind,
        "model": dict(model),
        "fault": fault,
        "properties": [dict(p) for p in properties_list],
    }
    return FaultExperimentReport(
        engine_version=FAULT_ENGINE_VERSION,
        input_hash=hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        fault=fault,
        applied=True,
        nominal_hash=nominal_hash,
        faulty_hash=faulty_hash,
        behavior=behavior,
        checks=tuple(checks),
        detected=detected,
    )


def fault_experiment_report_to_dict(report: FaultExperimentReport) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": report.engine_version,
        "input_hash": report.input_hash,
        "fault": report.fault,
        "applied": report.applied,
        "nominal_hash": report.nominal_hash,
        "faulty_hash": report.faulty_hash,
        "behavior": report.behavior,
        "checks": [
            {
                "id": check.id,
                "nominal_verdict": check.nominal_verdict,
                "faulty_verdict": check.faulty_verdict,
                "detected": check.detected,
                "counterexample": check.counterexample,
            }
            for check in report.checks
        ],
        "detected": report.detected,
    }


__all__ = [
    "FaultExperimentReport",
    "CheckResult",
    "run_fault_experiment",
    "fault_experiment_report_to_dict",
]

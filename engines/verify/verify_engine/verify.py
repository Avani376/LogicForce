"""Deterministic verification engine v1 (normative: verification-engine.md).

Invariant verification over bounded models with exhaustive scope labels and
replayable counterexamples. Verdicts are produced ONLY here — the API and UI
render reports, they never compute verdicts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from logic_engine import LogicValue
from logic_engine.errors import SchemaError
from logic_engine.graph import parse_circuit as parse_circuit_v1
from logic_engine.hashing import canonical_json
from logic_engine.simulator import simulate as v1_simulate
from logic_engine.validation import require_valid as v1_require_valid
from logic_engine.values import normalize_value
from sequential_engine import parse_fsm
from sequential_engine.fsm import FSM, FSMTransition, _matches

from verify_engine.expressions import (
    ExprNode,
    evaluate_expression,
    expression_signals,
    parse_expression,
)
from verify_engine.version import (
    MAX_COMBINATIONAL_INPUTS,
    MAX_FSM_INPUTS,
    MAX_FSM_STATES,
    PROPERTY_SCHEMA_VERSION,
    VERIFY_ENGINE_VERSION,
)

_MODEL_KINDS = ("combinational_invariant", "fsm_invariant")


@dataclass(frozen=True)
class Property:
    id: str
    kind: str
    statement: str | None
    expression_text: str
    expression: ExprNode
    signals: tuple[str, ...]


@dataclass(frozen=True)
class VerificationReport:
    engine_version: str
    input_hash: str
    property_id: str
    property_statement: str | None
    expression: str
    model_kind: str
    verdict: str  # PASS | FAIL | INCOMPLETE
    scope: str
    explored_cases: int
    assumptions: tuple[str, ...]
    counterexample: dict[str, object] | None
    reason: str | None


def parse_property(raw: object) -> Property:
    """Parse and validate a property document (schema 1, fail-fast, typed)."""
    if not isinstance(raw, Mapping):
        raise SchemaError("PROPERTY_SCHEMA_ERROR", "property document must be a JSON object")
    version = raw.get("property_schema_version")
    if version != PROPERTY_SCHEMA_VERSION:
        raise SchemaError(
            "PROPERTY_SCHEMA_ERROR",
            f"expected property_schema_version {PROPERTY_SCHEMA_VERSION}, got {version!r}",
        )
    prop_id = raw.get("id")
    if not isinstance(prop_id, str) or not prop_id:
        raise SchemaError("PROPERTY_SCHEMA_ERROR", "'id' must be a non-empty string")
    kind = raw.get("kind")
    if kind not in _MODEL_KINDS:
        raise SchemaError(
            "PROPERTY_SCHEMA_ERROR",
            f"'kind' must be one of {list(_MODEL_KINDS)}, got {kind!r}",
        )
    statement = raw.get("statement")
    statement = statement if isinstance(statement, str) else None
    expression_text = raw.get("expression")
    if not isinstance(expression_text, str):
        raise SchemaError("PROPERTY_SCHEMA_ERROR", "'expression' must be a string")
    expression = parse_expression(expression_text)
    return Property(
        id=prop_id,
        kind=kind,
        statement=statement,
        expression_text=expression_text,
        expression=expression,
        signals=expression_signals(expression),
    )


def _check_signals(property_obj: Property, universe: tuple[str, ...]) -> None:
    unknown = [name for name in property_obj.signals if name not in universe]
    if unknown:
        raise SchemaError(
            "PROPERTY_SIGNAL_UNKNOWN",
            f"expression references unknown signals: {unknown}",
        )


def verify_combinational_invariant(
    circuit: Mapping[str, object], property_raw: object
) -> VerificationReport:
    """Check a property over every input vector of a schema-v1 circuit.

    Exhaustive for n ≤ 12 primary inputs; beyond that the verdict is INCOMPLETE
    with reason MODEL_TOO_LARGE. A counterexample is the violating input vector
    (replayable via POST /api/circuits/simulate).
    """
    property_obj = parse_property(property_raw)
    if property_obj.kind != "combinational_invariant":
        raise SchemaError(
            "PROPERTY_SCHEMA_ERROR",
            "kind must be 'combinational_invariant' for a circuit model, "
            f"got {property_obj.kind!r}",
        )
    graph = parse_circuit_v1(dict(circuit))
    v1_require_valid(graph)

    output_names = tuple(
        sorted(
            str(c.params["name"])
            for c in graph.components
            if c.type == "OUTPUT" and isinstance(c.params.get("name"), str)
        )
    )
    _check_signals(property_obj, output_names)
    input_names = tuple(
        sorted(
            str(c.params["name"])
            for c in graph.components
            if c.type == "INPUT" and isinstance(c.params.get("name"), str)
        )
    )
    assumptions = ("missing outputs evaluate to X (unknowns-are-not-safety)",)
    hash_hex = _hash("comb", dict(circuit), property_obj)

    if len(input_names) > MAX_COMBINATIONAL_INPUTS:
        return _incomplete(
            property_obj,
            "combinational_invariant",
            hash_hex,
            f"MODEL_TOO_LARGE: {len(input_names)} primary inputs exceed the "
            f"exhaustive bound of {MAX_COMBINATIONAL_INPUTS}",
            assumptions,
        )

    explored = 0
    for index in range(1 << len(input_names)):
        vector = {
            name: LogicValue.ONE
            if (index >> (len(input_names) - 1 - position)) & 1
            else LogicValue.ZERO
            for position, name in enumerate(input_names)
        }
        result = v1_simulate(graph, vector)
        value = evaluate_expression(
            property_obj.expression,
            {name: LogicValue(value) for name, value in result.outputs.items()},
        )
        explored += 1
        if value != LogicValue.ONE:
            return VerificationReport(
                engine_version=VERIFY_ENGINE_VERSION,
                input_hash=hash_hex,
                property_id=property_obj.id,
                property_statement=property_obj.statement,
                expression=property_obj.expression_text,
                model_kind="combinational_invariant",
                verdict="FAIL",
                scope=f"EXHAUSTIVE({1 << len(input_names)} input vectors)",
                explored_cases=explored,
                assumptions=assumptions,
                counterexample={
                    "inputs": {name: value_.value for name, value_ in vector.items()},
                    "outputs": dict(result.outputs),
                },
                reason=None,
            )
    return VerificationReport(
        engine_version=VERIFY_ENGINE_VERSION,
        input_hash=hash_hex,
        property_id=property_obj.id,
        property_statement=property_obj.statement,
        expression=property_obj.expression_text,
        model_kind="combinational_invariant",
        verdict="PASS",
        scope=f"EXHAUSTIVE({1 << len(input_names)} input vectors)",
        explored_cases=explored,
        assumptions=assumptions,
        counterexample=None,
        reason=None,
    )


def verify_fsm_invariant(fsm_raw: object, property_raw: object) -> VerificationReport:
    """Check a property over every reachable transition FIRING of an FSM.

    Firing semantics match ``fsm_simulate`` exactly: for every reachable
    ``(state, input vector)`` pair, the first matching transition (document order)
    produces the cycle's output vector; unmatched vectors hold the state with no
    outputs. Unlisted outputs evaluate to X (unknowns-are-not-safety). This is what
    makes counterexamples byte-comparable with replays.
    """
    property_obj = parse_property(property_raw)
    if property_obj.kind != "fsm_invariant":
        raise SchemaError(
            "PROPERTY_SCHEMA_ERROR",
            f"kind must be 'fsm_invariant' for an FSM model, got {property_obj.kind!r}",
        )
    fsm: FSM = parse_fsm(fsm_raw)
    _check_signals(property_obj, fsm.outputs)
    assumptions = (
        "firing-based checking identical to fsm_simulate (first-match, document order); "
        "unlisted outputs evaluate to X (unknowns-are-not-safety)",
    )
    hash_hex = _hash("fsm", dict(fsm_raw) if isinstance(fsm_raw, Mapping) else {}, property_obj)

    if len(fsm.states) > MAX_FSM_STATES or len(fsm.inputs) > MAX_FSM_INPUTS:
        return _incomplete(
            property_obj,
            "fsm_invariant",
            hash_hex,
            f"MODEL_TOO_LARGE: {len(fsm.states)} states (max {MAX_FSM_STATES}), "
            f"{len(fsm.inputs)} inputs (max {MAX_FSM_INPUTS})",
            assumptions,
        )

    alphabet: list[dict[str, str]] = []
    width = len(fsm.inputs)
    for index in range(1 << width):
        alphabet.append(
            {
                name: ("1" if (index >> (width - 1 - position)) & 1 else "0")
                for position, name in enumerate(fsm.inputs)
            }
        )

    def transition_for(state: str, vector: Mapping[str, str]) -> FSMTransition | None:
        for transition in fsm.transitions:
            if transition.source == state and _matches(transition.when, vector):
                return transition
        return None

    def firing_env(transition: FSMTransition) -> dict[str, LogicValue]:
        env = {name: LogicValue.UNKNOWN for name in fsm.outputs}
        for name, value in transition.outputs:
            env[name] = normalize_value(value)
        return env

    # BFS with parent tracking for replayable counterexamples.
    visited: set[str] = {fsm.initial}
    parents: dict[str, tuple[str, dict[str, str]]] = {}
    frontier = [fsm.initial]
    violating_firing: tuple[str, dict[str, str], FSMTransition] | None = None
    firings_checked = 0

    def holds(env: Mapping[str, LogicValue]) -> bool:
        return evaluate_expression(property_obj.expression, env) == LogicValue.ONE

    while frontier and violating_firing is None:
        current = frontier.pop(0)
        for vector in alphabet:
            transition = transition_for(current, vector)
            if transition is None:
                continue
            firings_checked += 1
            env = firing_env(transition)
            if not holds(env):
                violating_firing = (current, dict(vector), transition)
                break
            target = transition.target
            if target not in visited:
                visited.add(target)
                parents[target] = (current, dict(vector))
                frontier.append(target)

    explored = firings_checked
    scope = f"EXHAUSTIVE({explored} firings over {len(visited)} of {len(fsm.states)} states)"

    if violating_firing is not None:
        current, vector, transition = violating_firing
        # Sequence = BFS-shortest path to `current` + the violating vector. In a
        # replay, the last row's outputs are exactly this firing's outputs (the
        # row records the transition fired at that cycle), and final_state is the
        # transition's target.
        sequence: list[dict[str, str]] = []
        cursor = current
        while cursor in parents:
            previous, step_vector = parents[cursor]
            sequence.append(step_vector)
            cursor = previous
        sequence.reverse()
        sequence.append(dict(vector))
        env = firing_env(transition)
        final_outputs = {name: env[name].value for name in sorted(env)}
        return VerificationReport(
            engine_version=VERIFY_ENGINE_VERSION,
            input_hash=hash_hex,
            property_id=property_obj.id,
            property_statement=property_obj.statement,
            expression=property_obj.expression_text,
            model_kind="fsm_invariant",
            verdict="FAIL",
            scope=scope,
            explored_cases=explored,
            assumptions=assumptions,
            counterexample={
                "inputs_sequence": sequence,
                "violating_state": transition.target,
                "outputs": final_outputs,
            },
            reason=None,
        )

    return VerificationReport(
        engine_version=VERIFY_ENGINE_VERSION,
        input_hash=hash_hex,
        property_id=property_obj.id,
        property_statement=property_obj.statement,
        expression=property_obj.expression_text,
        model_kind="fsm_invariant",
        verdict="PASS",
        scope=scope,
        explored_cases=explored,
        assumptions=assumptions,
        counterexample=None,
        reason=None,
    )


def _incomplete(
    property_obj: Property,
    model_kind: str,
    hash_hex: str,
    reason: str,
    assumptions: tuple[str, ...],
) -> VerificationReport:
    return VerificationReport(
        engine_version=VERIFY_ENGINE_VERSION,
        input_hash=hash_hex,
        property_id=property_obj.id,
        property_statement=property_obj.statement,
        expression=property_obj.expression_text,
        model_kind=model_kind,
        verdict="INCOMPLETE",
        scope="INCOMPLETE",
        explored_cases=0,
        assumptions=assumptions,
        counterexample=None,
        reason=reason,
    )


def _hash(model_kind: str, model: Mapping[str, object], property_obj: Property) -> str:
    payload = (
        f"verify1|{model_kind}|{canonical_json(dict(model))}|"
        f"{canonical_json({'expression': property_obj.expression_text, 'id': property_obj.id})}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verification_report_to_dict(report: VerificationReport) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "schema_version": PROPERTY_SCHEMA_VERSION,
        "engine_version": report.engine_version,
        "input_hash": report.input_hash,
        "property": {
            "id": report.property_id,
            "statement": report.property_statement,
            "expression": report.expression,
        },
        "model_kind": report.model_kind,
        "verdict": report.verdict,
        "scope": report.scope,
        "explored_cases": report.explored_cases,
        "assumptions": list(report.assumptions),
        "counterexample": report.counterexample,
        "reason": report.reason,
    }


__all__ = [
    "VERIFY_ENGINE_VERSION",
    "VerificationReport",
    "Property",
    "parse_property",
    "verify_combinational_invariant",
    "verify_fsm_invariant",
    "verification_report_to_dict",
]

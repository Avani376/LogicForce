"""Abstract finite-state machine model (normative: docs/semantics/fsm-model.md).

Deterministic table-driven FSM simulation and reachability. This module is the
foundation for the Phase 3 verification engine (reachability, invariants,
counterexamples) — it never claims properties it has not checked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from logic_engine.errors import SchemaError
from logic_engine.hashing import canonical_json

FSM_SCHEMA_VERSION = 1

#: Hard bound for simulation length.
MAX_FSM_CYCLES = 256

#: FSM abstraction is binary — unknowns do not exist at this level.
VALID = ("0", "1")


@dataclass(frozen=True)
class FSMTransition:
    source: str
    when: tuple[tuple[str, str], ...]  # sorted (input, value) exact partial assignment
    target: str
    outputs: tuple[tuple[str, str], ...]  # sorted (output, value)


@dataclass(frozen=True)
class FSM:
    name: str | None
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    states: tuple[str, ...]
    initial: str
    transitions: tuple[FSMTransition, ...]


@dataclass(frozen=True)
class FSMCycle:
    cycle: int
    inputs: dict[str, str]
    state: str
    outputs: dict[str, str]
    matched: bool


@dataclass(frozen=True)
class FSMResult:
    engine_version: str
    scope: str
    input_hash: str
    cycles: tuple[FSMCycle, ...]
    final_state: str
    unmatched_count: int


def parse_fsm(raw: object) -> FSM:
    """Parse and validate an FSM document (schema v1, fail-fast and typed).

    Raises :class:`SchemaError` with codes ``FSM_SCHEMA_ERROR`` (structural/
    referential problems) or ``AMBIGUOUS_TRANSITION`` (two transitions from one
    state match the same input vector).
    """
    if not isinstance(raw, Mapping):
        raise SchemaError("FSM_SCHEMA_ERROR", "FSM document must be a JSON object")
    version = raw.get("fsm_schema_version")
    if version != FSM_SCHEMA_VERSION:
        raise SchemaError(
            "FSM_SCHEMA_ERROR",
            f"expected fsm_schema_version {FSM_SCHEMA_VERSION}, got {version!r}",
        )
    inputs = raw.get("inputs")
    outputs = raw.get("outputs")
    states = raw.get("states")
    initial = raw.get("initial")
    transitions_raw = raw.get("transitions")
    # inputs/outputs may be empty (autonomous machines); states may not.
    for field, value in (("inputs", inputs), ("outputs", outputs)):
        if not isinstance(value, list):
            raise SchemaError("FSM_SCHEMA_ERROR", f"'{field}' must be an array")
        if not all(isinstance(item, str) and item for item in value):
            raise SchemaError("FSM_SCHEMA_ERROR", f"'{field}' entries must be non-empty strings")
        if len(set(value)) != len(value):
            raise SchemaError("FSM_SCHEMA_ERROR", f"'{field}' contains duplicates")
    if not isinstance(states, list) or not states:
        raise SchemaError("FSM_SCHEMA_ERROR", "'states' must be a non-empty array")
    if not all(isinstance(item, str) and item for item in states):
        raise SchemaError("FSM_SCHEMA_ERROR", "'states' entries must be non-empty strings")
    if len(set(states)) != len(states):
        raise SchemaError("FSM_SCHEMA_ERROR", "'states' contains duplicates")
    # The checks above proved all three are string arrays; narrow for mypy.
    assert isinstance(inputs, list) and isinstance(outputs, list) and isinstance(states, list)
    if not isinstance(initial, str) or initial not in states:
        raise SchemaError("FSM_SCHEMA_ERROR", f"'initial' {initial!r} is not a declared state")
    if not isinstance(transitions_raw, list) or not transitions_raw:
        raise SchemaError("FSM_SCHEMA_ERROR", "'transitions' must be a non-empty array")

    input_set = set(inputs)
    output_set = set(outputs)
    state_set = set(states)

    transitions: list[FSMTransition] = []
    for index, entry in enumerate(transitions_raw):
        if not isinstance(entry, Mapping):
            raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index} must be an object")
        source = entry.get("from")
        target = entry.get("to")
        when = entry.get("when", {})
        outs = entry.get("outputs", {})
        if not isinstance(source, str) or source not in state_set:
            raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: unknown 'from' {source!r}")
        if not isinstance(target, str) or target not in state_set:
            raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: unknown 'to' {target!r}")
        if not isinstance(when, Mapping):
            raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: 'when' must be an object")
        if not isinstance(outs, Mapping):
            raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: 'outputs' must be an object")
        when_items: list[tuple[str, str]] = []
        for name, value in when.items():
            if not isinstance(name, str) or name not in input_set:
                raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: unknown input {name!r} in 'when'")
            if value not in VALID:
                raise SchemaError(
                    "FSM_SCHEMA_ERROR",
                    f"transition #{index}: 'when' values must be '0' or '1', got {value!r}",
                )
            when_items.append((name, value))
        out_items: list[tuple[str, str]] = []
        for name, value in outs.items():
            if not isinstance(name, str) or name not in output_set:
                raise SchemaError("FSM_SCHEMA_ERROR", f"transition #{index}: unknown output {name!r} in 'outputs'")
            if value not in VALID:
                raise SchemaError(
                    "FSM_SCHEMA_ERROR",
                    f"transition #{index}: 'outputs' values must be '0' or '1', got {value!r}",
                )
            out_items.append((name, value))
        transitions.append(
            FSMTransition(
                source=source,
                when=tuple(sorted(when_items)),
                target=target,
                outputs=tuple(sorted(out_items)),
            )
        )

    # Ambiguity: two transitions from the same state whose partial assignments can
    # both match one vector (they agree on shared keys).
    for i in range(len(transitions)):
        for j in range(i + 1, len(transitions)):
            a, b = transitions[i], transitions[j]
            if a.source != b.source:
                continue
            a_map, b_map = dict(a.when), dict(b.when)
            shared = set(a_map) & set(b_map)
            if all(a_map[key] == b_map[key] for key in shared):
                raise SchemaError(
                    "AMBIGUOUS_TRANSITION",
                    f"state {a.source!r}: transitions #{i} and #{j} match the same input vector",
                )

    name = raw.get("name")
    name = name if isinstance(name, str) else None
    return FSM(
        name=name,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        states=tuple(states),
        initial=initial,
        transitions=tuple(transitions),
    )


def _matches(when: tuple[tuple[str, str], ...], vector: Mapping[str, str]) -> bool:
    return all(vector.get(name) == value for name, value in when)


def fsm_simulate(fsm: FSM, input_sequence: Sequence[Mapping[str, str]]) -> FSMResult:
    """Run the FSM over an input sequence (each entry: input name -> '0'|'1').

    Deterministic: first matching transition in document order; if none matches,
    the state holds and the cycle is flagged ``matched=False`` (a table gap is a
    modeling fact, never silently patched). Inputs must be binary — unknowns do
    not exist at the FSM abstraction level.
    """
    import hashlib

    if len(input_sequence) > MAX_FSM_CYCLES:
        raise SchemaError(
            "FSM_CYCLES_LIMIT_EXCEEDED",
            f"{len(input_sequence)} cycles exceeds the hard bound of {MAX_FSM_CYCLES}",
        )
    normalized: list[dict[str, str]] = []
    for entry in input_sequence:
        row: dict[str, str] = {}
        for name, value in entry.items():
            if not isinstance(name, str) or name not in fsm.inputs:
                raise SchemaError("FSM_INPUT_ERROR", f"unknown FSM input {name!r}")
            if value not in VALID:
                raise SchemaError(
                    "FSM_INPUT_ERROR",
                    f"FSM inputs must be '0' or '1', got {name}={value!r}",
                )
            row[name] = value
        normalized.append(row)

    cycles: list[FSMCycle] = []
    unmatched_count = 0
    state = fsm.initial
    for cycle, vector in enumerate(normalized):
        matched = False
        next_outputs: dict[str, str] = {}
        next_state = state
        for transition in fsm.transitions:
            if transition.source == state and _matches(transition.when, vector):
                matched = True
                next_state = transition.target
                next_outputs = dict(transition.outputs)
                break
        if not matched:
            unmatched_count += 1
        cycles.append(
            FSMCycle(
                cycle=cycle,
                inputs=dict(vector),
                state=state,
                outputs=next_outputs,
                matched=matched,
            )
        )
        state = next_state

    payload = f"fsm1|{canonical_json(_fsm_to_dict(fsm))}|{canonical_json([dict(row) for row in normalized])}"
    return FSMResult(
        engine_version=_engine_version(),
        scope=f"BOUNDED({len(normalized)} cycles)",
        input_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        cycles=tuple(cycles),
        final_state=state,
        unmatched_count=unmatched_count,
    )


def fsm_reachable(fsm: FSM) -> tuple[tuple[str, ...], str]:
    """States reachable from ``initial`` over all binary input vectors (BFS).

    The table is explicit and finite, so the result carries an
    ``EXHAUSTIVE(states)`` claim over the *declared model* — no assumption about
    behavior beyond it.
    """
    alphabet: list[dict[str, str]] = []
    width = len(fsm.inputs)
    for index in range(1 << width):
        vector = {
            name: ("1" if (index >> (width - 1 - position)) & 1 else "0") for position, name in enumerate(fsm.inputs)
        }
        alphabet.append(vector)

    reachable = {fsm.initial}
    frontier = [fsm.initial]
    while frontier:
        current = frontier.pop()
        for vector in alphabet:
            for transition in fsm.transitions:
                if transition.source == current and _matches(transition.when, vector):
                    if transition.target not in reachable:
                        reachable.add(transition.target)
                        frontier.append(transition.target)
                    break
    return tuple(sorted(reachable)), f"EXHAUSTIVE({len(reachable)} of {len(fsm.states)} states)"


def _fsm_to_dict(fsm: FSM) -> dict[str, object]:
    return {
        "inputs": list(fsm.inputs),
        "outputs": list(fsm.outputs),
        "states": list(fsm.states),
        "initial": fsm.initial,
        "transitions": [
            {
                "from": t.source,
                "when": {k: v for k, v in t.when},
                "to": t.target,
                "outputs": {k: v for k, v in t.outputs},
            }
            for t in fsm.transitions
        ],
    }


def fsm_result_to_dict(result: FSMResult) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order."""
    return {
        "engine_version": result.engine_version,
        "scope": result.scope,
        "input_hash": result.input_hash,
        "cycles": [
            {
                "cycle": row.cycle,
                "inputs": row.inputs,
                "state": row.state,
                "outputs": row.outputs,
                "matched": row.matched,
            }
            for row in result.cycles
        ],
        "final_state": result.final_state,
        "unmatched_count": result.unmatched_count,
    }


def _engine_version() -> str:
    from sequential_engine.version import SEQUENTIAL_ENGINE_VERSION

    return SEQUENTIAL_ENGINE_VERSION

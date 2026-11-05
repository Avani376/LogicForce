"""Deterministic combinational propagation with trace events.

Normative source: ``docs/semantics/propagation.md``. Evaluation order is
``(depth ascending, component id ascending)``; the id tie-break is normative for
determinism. Because ``validate`` rejects cyclic circuits, one topological pass is
exact — no delta-cycle iteration exists in v1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from logic_engine.components import (
    MULTI_INPUT_GATES,
    TYPE_BUFFER,
    TYPE_CONST0,
    TYPE_CONST1,
    TYPE_INPUT,
    TYPE_NOT,
    TYPE_OUTPUT,
    input_pins_for,
)
from logic_engine.errors import InvalidInputValueError
from logic_engine.graph import CircuitGraph, Net
from logic_engine.validation import require_valid
from logic_engine.values import BINARY_FUNCS, LogicValue, buffer_, normalize_value, not_
from logic_engine.version import ENGINE_VERSION


@dataclass(frozen=True)
class TraceCause:
    """What drove a net change: a primary input, a constant, or a gate."""

    type: str
    component: str


@dataclass(frozen=True)
class TraceEvent:
    """One net value change (``old != new``), ordered per the propagation contract."""

    seq: int
    delta: int
    net: str
    old: str
    new: str
    cause: TraceCause


@dataclass(frozen=True)
class SimulationResult:
    """Result of one combinational simulation run.

    ``outputs`` maps OUTPUT component names to value strings; ``trace`` is the ordered
    event list; ``scope`` is the fixed honest label ``SINGLE_VECTOR``.
    """

    engine_version: str
    outputs: dict[str, str]
    trace: tuple[TraceEvent, ...]
    event_count: int
    scope: str


def _normalize_inputs(
    raw_inputs: Mapping[str, object], input_names: list[str]
) -> dict[str, LogicValue]:
    """Normalize the vector; unknown names are ignored (they attach to no INPUT)."""
    normalized: dict[str, LogicValue] = {}
    for name, raw in raw_inputs.items():
        if not isinstance(name, str):
            raise InvalidInputValueError(str(name), raw)
        try:
            normalized[name] = normalize_value(raw)
        except ValueError as exc:
            raise InvalidInputValueError(name, raw) from exc
    return {name: normalized.get(name, LogicValue.UNKNOWN) for name in input_names}


def _resolve_net_driver(
    graph: CircuitGraph,
) -> tuple[dict[str, Net], dict[tuple[str, str], str]]:
    """Map each net id to its Net, and each input pin ref to its feeding net id."""
    net_by_id: dict[str, Net] = {}
    for net in graph.nets:
        if net.id not in net_by_id:
            net_by_id[net.id] = net
    pin_net: dict[tuple[str, str], str] = {}
    for net in graph.nets:
        for sink in net.sinks:
            key = (sink.component, sink.pin)
            if key not in pin_net:
                pin_net[key] = net.id
    return net_by_id, pin_net


def _compute_depths(
    graph: CircuitGraph,
    net_by_id: Mapping[str, Net],
    pin_net: Mapping[tuple[str, str], str],
) -> dict[str, int]:
    """Component evaluation depth: sources are 0, gates 1 + max(driver depths).

    The depth of *every* input pin's driver matters, including wide gates' pins
    beyond ``a``/``b`` — that is why the component's own params (e.g. ``width``)
    must be used here, not defaults.
    """
    comp_by_id: dict[str, object] = {}
    for comp in graph.components:
        comp_by_id.setdefault(comp.id, comp)

    depths: dict[str, int] = {}
    in_progress: set[str] = set()

    def depth_of(comp_id: str) -> int:
        if comp_id in depths:
            return depths[comp_id]
        if comp_id in in_progress:
            # Unreachable for validated circuits (acyclic); defensive default.
            return 0
        in_progress.add(comp_id)
        comp = comp_by_id.get(comp_id)
        comp_type = getattr(comp, "type", TYPE_INPUT) if comp is not None else TYPE_INPUT
        params = getattr(comp, "params", {}) if comp is not None else {}
        result = 0
        if comp_type not in (TYPE_INPUT, TYPE_CONST0, TYPE_CONST1):
            pins = input_pins_for(str(comp_type), dict(params))
            for pin in pins:
                net_id = pin_net.get((comp_id, pin))
                if net_id is None:
                    continue
                net = net_by_id[net_id]
                if net.driver is None:
                    continue
                driver_depth = depth_of(net.driver.component)
                if driver_depth + 1 > result:
                    result = driver_depth + 1
        in_progress.discard(comp_id)
        depths[comp_id] = result
        return result

    for comp_id in comp_by_id:
        depth_of(comp_id)
    return depths


def simulate(graph: CircuitGraph, inputs: Mapping[str, object]) -> SimulationResult:
    """Run one combinational simulation of a validated circuit.

    Preconditions: the circuit must pass :func:`logic_engine.validation.validate`
    (errors, not warnings, block simulation). ``inputs`` maps INPUT ``params.name``
    to a normalizable value; omitted inputs default to ``X``; values for unknown
    names are ignored.

    Raises ``CircuitNotValidError`` or ``InvalidInputValueError`` (typed errors —
    never silent defaults).
    """
    require_valid(graph)

    # 1. Primary inputs (sorted by name) — assign at delta 0.
    input_comps = [
        comp
        for comp in graph.components
        if comp.type == TYPE_INPUT and isinstance(comp.params.get("name"), str)
    ]
    input_comps = sorted(input_comps, key=lambda comp: str(comp.params["name"]))
    input_names = [str(comp.params["name"]) for comp in input_comps]
    vector = _normalize_inputs(inputs, input_names)

    net_by_id, pin_net = _resolve_net_driver(graph)
    depths = _compute_depths(graph, net_by_id, pin_net)

    net_values: dict[str, LogicValue] = {net.id: LogicValue.UNKNOWN for net in graph.nets}
    events: list[TraceEvent] = []

    def assign(net_id: str, new_value: LogicValue, cause: TraceCause, delta: int) -> None:
        old = net_values[net_id]
        if old == new_value:
            return
        net_values[net_id] = new_value
        events.append(
            TraceEvent(
                seq=len(events),
                delta=delta,
                net=net_id,
                old=old.value,
                new=new_value.value,
                cause=cause,
            )
        )

    def nets_driven_by(comp_id: str, pin: str) -> list[str]:
        driven: list[str] = []
        for net in graph.nets:
            if net.driver is not None and (
                net.driver.component == comp_id and net.driver.pin == pin
            ):
                driven.append(net.id)
        return sorted(driven)

    for comp in input_comps:
        name = str(comp.params["name"])
        for net_id in nets_driven_by(comp.id, "out"):
            assign(net_id, vector[name], TraceCause("primary_input", comp.id), 0)

    # 2. Constants at delta 0 (deterministic id order).
    for comp in sorted(
        (c for c in graph.components if c.type in (TYPE_CONST0, TYPE_CONST1)),
        key=lambda c: c.id,
    ):
        value = LogicValue.ZERO if comp.type == TYPE_CONST0 else LogicValue.ONE
        for net_id in nets_driven_by(comp.id, "out"):
            assign(net_id, value, TraceCause("constant", comp.id), 0)

    # 3. Gates in (depth asc, id asc) order — the normative deterministic order.
    gate_types = {TYPE_BUFFER, TYPE_NOT, *MULTI_INPUT_GATES}
    gates = [comp for comp in graph.components if comp.type in gate_types]
    gates = sorted(gates, key=lambda comp: (depths.get(comp.id, 0), comp.id))

    for comp in gates:
        delta = depths.get(comp.id, 0)
        pin_names = input_pins_for(comp.type, comp.params)
        pin_values: list[LogicValue] = []
        for pin in pin_names:
            net_id = pin_net[(comp.id, pin)]
            pin_values.append(net_values[net_id])

        if comp.type == TYPE_NOT:
            out_value = not_(pin_values[0])
        elif comp.type == TYPE_BUFFER:
            out_value = buffer_(pin_values[0])
        else:
            func = BINARY_FUNCS[comp.type]
            out_value = pin_values[0]
            for value in pin_values[1:]:
                out_value = func(out_value, value)

        for net_id in nets_driven_by(comp.id, "out"):
            assign(net_id, out_value, TraceCause("gate", comp.id), delta)

    # 4. Primary outputs (sorted by name).
    output_comps = [comp for comp in graph.components if comp.type == TYPE_OUTPUT]
    output_comps = [comp for comp in output_comps if isinstance(comp.params.get("name"), str)]
    output_comps = sorted(output_comps, key=lambda comp: str(comp.params["name"]))
    outputs: dict[str, str] = {}
    for comp in output_comps:
        name = str(comp.params["name"])
        net_id = pin_net[(comp.id, "in")]
        outputs[name] = net_values[net_id].value

    return SimulationResult(
        engine_version=ENGINE_VERSION,
        outputs=outputs,
        trace=tuple(events),
        event_count=len(events),
        scope="SINGLE_VECTOR",
    )


def simulation_result_to_dict(result: SimulationResult) -> dict[str, object]:
    """JSON-ready serialization with keys in contract order (for hashing/tests)."""
    return {
        "engine_version": result.engine_version,
        "scope": result.scope,
        "outputs": result.outputs,
        "event_count": result.event_count,
        "trace": [
            {
                "seq": event.seq,
                "delta": event.delta,
                "net": event.net,
                "old": event.old,
                "new": event.new,
                "cause": {"type": event.cause.type, "component": event.cause.component},
            }
            for event in result.trace
        ],
    }

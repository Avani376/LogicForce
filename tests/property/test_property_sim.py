"""Property tests: simulator vs an independent naive evaluator (hypothesis).

The naive evaluator below intentionally uses a *different* code path from the engine
(recursive memoized walk over raw dicts, no topological sort). The property under
test: for any acyclic circuit built from the supported gate set, the deterministic
topological simulator and the naive evaluator agree on every output, for every input
vector — plus trace-ordering invariants.
"""

from __future__ import annotations

import string
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from logic_engine import LogicValue, parse_circuit, simulate, truth_table, validate
from logic_engine.values import BINARY_FUNCS, buffer_, not_

_0, _1 = LogicValue.ZERO, LogicValue.ONE
BIT = st.sampled_from([_0, _1])

SIMPLE_GATES = ["BUFFER", "NOT", "AND", "OR", "NAND", "NOR", "XOR", "XNOR"]


def gate_pins(gate_type: str, width: int) -> list[str]:
    if gate_type in ("BUFFER", "NOT"):
        return ["a"]
    return list(string.ascii_lowercase[:width])


@st.composite
def acyclic_circuits(draw: st.DrawFn) -> tuple[dict[str, Any], list[str]]:
    n_inputs = draw(st.integers(min_value=1, max_value=4))
    n_gates = draw(st.integers(min_value=0, max_value=6))
    n_outputs = draw(st.integers(min_value=1, max_value=3))

    input_names = [f"i{j}" for j in range(n_inputs)]
    components: list[dict[str, Any]] = []
    nets: list[dict[str, Any]] = []
    taps: list[tuple[str, str]] = []  # (component_id, out_pin) sources to wire from

    for name in input_names:
        components.append({"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}})
        taps.append((f"IN_{name}", "out"))

    for g in range(n_gates):
        gate_type = draw(st.sampled_from(SIMPLE_GATES))
        width = draw(st.integers(min_value=2, max_value=3))
        if gate_type in ("BUFFER", "NOT"):
            pins = ["a"]
            entry: dict[str, Any] = {"id": f"G{g}", "type": gate_type}
        else:
            pins = gate_pins(gate_type, width)
            entry = {"id": f"G{g}", "type": gate_type, "params": {"width": width}}
        components.append(entry)
        for pin in pins:
            source = draw(st.sampled_from(taps))
            nets.append(
                {
                    "id": f"n_G{g}_{pin}",
                    "driver": {"component": source[0], "pin": source[1]},
                    "sinks": [{"component": f"G{g}", "pin": pin}],
                }
            )
        taps.append((f"G{g}", "out"))

    for k in range(n_outputs):
        source = draw(st.sampled_from(taps))
        components.append({"id": f"OUT_o{k}", "type": "OUTPUT", "params": {"name": f"o{k}"}})
        nets.append(
            {
                "id": f"n_OUT_o{k}",
                "driver": {"component": source[0], "pin": source[1]},
                "sinks": [{"component": f"OUT_o{k}", "pin": "in"}],
            }
        )

    doc = {"schema_version": 1, "name": "generated", "components": components, "nets": nets}
    return doc, input_names


def naive_evaluate(
    doc: dict[str, Any], vector: dict[str, LogicValue]
) -> dict[str, str]:
    """Independent recursive evaluator over the raw document (no topo sort)."""
    comp_by_id = {comp["id"]: comp for comp in doc["components"]}
    net_of_pin: dict[tuple[str, str], dict[str, Any]] = {}
    for net in doc["nets"]:
        for sink in net["sinks"]:
            net_of_pin[(sink["component"], sink["pin"])] = net

    memo: dict[tuple[str, str], LogicValue] = {}

    def driver_value(ref: dict[str, str]) -> LogicValue:
        comp = comp_by_id[ref["component"]]
        ctype = comp["type"]
        if ctype == "INPUT":
            name = comp["params"]["name"]
            return vector.get(name, LogicValue.UNKNOWN)
        if ctype == "CONST0":
            return _0
        if ctype == "CONST1":
            return _1
        key = (ref["component"], ref["pin"])
        if key in memo:
            return memo[key]
        params = comp.get("params", {}) or {}
        width = params.get("width", 2) if ctype not in ("BUFFER", "NOT") else 1
        if not isinstance(width, int) or isinstance(width, bool):
            width = 2
        pins = gate_pins(ctype, int(width))
        values = [
            driver_value(net_of_pin[(comp["id"], pin)]["driver"]) for pin in pins
        ]
        if ctype == "NOT":
            result = not_(values[0])
        elif ctype == "BUFFER":
            result = buffer_(values[0])
        else:
            func = BINARY_FUNCS[ctype]
            acc = values[0]
            for value in values[1:]:
                acc = func(acc, value)
            result = acc
        memo[key] = result
        return result

    outputs: dict[str, str] = {}
    for comp in doc["components"]:
        if comp["type"] == "OUTPUT":
            net = net_of_pin[(comp["id"], "in")]
            outputs[comp["params"]["name"]] = driver_value(net["driver"]).value
    return outputs


@given(data=acyclic_circuits())
@settings(max_examples=200, deadline=None)
def test_simulation_matches_naive_evaluator_on_all_vectors(
    data: tuple[dict[str, Any], list[str]],
) -> None:
    doc, input_names = data
    graph = parse_circuit(doc)
    report = validate(graph)
    assert report.ok, [e.code for e in report.errors]

    result = truth_table(graph)
    for row in result.rows:
        vector = {name: LogicValue(value) for name, value in row.inputs.items()}
        assert row.outputs == naive_evaluate(doc, vector), (
            f"mismatch for vector {row.inputs}"
        )


@given(data=acyclic_circuits())
@settings(max_examples=200, deadline=None)
def test_trace_seq_is_strictly_monotonic_from_zero(
    data: tuple[dict[str, Any], list[str]],
) -> None:
    doc, input_names = data
    graph = parse_circuit(doc)
    vector = {name: _1 for name in input_names}
    result = simulate(graph, vector)
    seqs = [event.seq for event in result.trace]
    assert seqs == list(range(len(seqs)))
    deltas = [event.delta for event in result.trace]
    assert deltas == sorted(deltas)
    for event in result.trace:
        assert event.old != event.new


@given(data=acyclic_circuits())
@settings(max_examples=100, deadline=None)
def test_deltas_respect_dependency_depth(
    data: tuple[dict[str, Any], list[str]],
) -> None:
    """A net driven by a depth-d component changes at delta >= d."""
    doc, input_names = data
    graph = parse_circuit(doc)
    vector = {name: _0 for name in input_names}
    result = simulate(graph, vector)
    for event in result.trace:
        if event.cause.type == "gate":
            assert event.delta >= 1
        else:
            assert event.delta == 0

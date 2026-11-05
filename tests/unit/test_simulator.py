"""Simulator behavior tests: defaults, dominance, trace shape, deterministic order."""

from __future__ import annotations

import pytest
from logic_engine import (
    CircuitNotValidError,
    InvalidInputValueError,
    LogicValue,
    parse_circuit,
    simulate,
    simulation_result_to_dict,
    validate,
)


def io_circuit(gate_type: str = "BUFFER", extra_inputs: int = 0) -> dict[str, object]:
    components: list[dict[str, object]] = [
        {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}}
    ]
    if gate_type in ("AND", "OR", "NAND", "NOR", "XOR", "XNOR"):
        components.append({"id": "IN_b", "type": "INPUT", "params": {"name": "b"}})
    for k in range(extra_inputs):
        components.append(
            {"id": f"IN_x{k}", "type": "INPUT", "params": {"name": f"x{k}"}}
        )
    components.append({"id": "G", "type": gate_type})
    components.append({"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}})

    sinks: list[dict[str, str]] = [{"component": "G", "pin": "a"}]
    nets = [
        {"id": "n_a", "driver": {"component": "IN_a", "pin": "out"}, "sinks": sinks}
    ]
    if gate_type in ("AND", "OR", "NAND", "NOR", "XOR", "XNOR"):
        nets.append(
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G", "pin": "b"}],
            }
        )
    nets.append(
        {
            "id": "n_y",
            "driver": {"component": "G", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        }
    )
    return {"schema_version": 1, "components": components, "nets": nets}


def test_buffer_passthrough() -> None:
    graph = parse_circuit(io_circuit())
    result = simulate(graph, {"a": "1"})
    assert result.outputs == {"y": "1"}


def test_omitted_primary_input_defaults_to_x() -> None:
    graph = parse_circuit(io_circuit())
    result = simulate(graph, {})
    assert result.outputs == {"y": "X"}


def test_and_zero_dominates_unknown() -> None:
    graph = parse_circuit(io_circuit("AND"))
    result = simulate(graph, {"a": "0", "b": "X"})
    assert result.outputs == {"y": "0"}


def test_or_one_dominates_high_z() -> None:
    graph = parse_circuit(io_circuit("OR"))
    result = simulate(graph, {"a": "1", "b": "Z"})
    assert result.outputs == {"y": "1"}


def test_xor_with_unknown_is_unknown() -> None:
    graph = parse_circuit(io_circuit("XOR"))
    result = simulate(graph, {"a": "1", "b": "X"})
    assert result.outputs == {"y": "X"}


def test_three_input_and_zero_dominance() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
            {"id": "IN_c", "type": "INPUT", "params": {"name": "c"}},
            {"id": "G", "type": "AND", "params": {"width": 3}},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G", "pin": "a"}],
            },
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G", "pin": "b"}],
            },
            {
                "id": "n_c",
                "driver": {"component": "IN_c", "pin": "out"},
                "sinks": [{"component": "G", "pin": "c"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "G", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    graph = parse_circuit(doc)
    assert simulate(graph, {"a": "1", "b": "X", "c": "0"}).outputs == {"y": "0"}


def test_constants_drive_their_values() -> None:
    doc = io_circuit("OR")
    doc["components"] = [
        {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
        {"id": "C1", "type": "CONST1"},
        {"id": "G", "type": "OR"},
        {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
    ]
    doc["nets"] = [
        {
            "id": "n_a",
            "driver": {"component": "IN_a", "pin": "out"},
            "sinks": [{"component": "G", "pin": "a"}],
        },
        {
            "id": "n_c",
            "driver": {"component": "C1", "pin": "out"},
            "sinks": [{"component": "G", "pin": "b"}],
        },
        {
            "id": "n_y",
            "driver": {"component": "G", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        },
    ]
    graph = parse_circuit(doc)
    assert simulate(graph, {"a": "0"}).outputs == {"y": "1"}
    assert simulate(graph, {"a": "X"}).outputs == {"y": "1"}


def test_trace_event_shape_and_order() -> None:
    graph = parse_circuit(io_circuit("AND"))
    result = simulate(graph, {"a": "1", "b": "0"})
    assert result.event_count == len(result.trace)
    for position, event in enumerate(result.trace):
        assert event.seq == position
    first = result.trace[0]
    assert (first.seq, first.delta, first.old, first.cause.type) == (0, 0, "X", "primary_input")
    gate_events = [e for e in result.trace if e.cause.type == "gate"]
    assert len(gate_events) == 1
    assert gate_events[0].delta >= 1
    assert gate_events[0].new == "0"
    assert gate_events[0].cause.component == "G"


def test_trace_omits_x_to_x_changes() -> None:
    graph = parse_circuit(io_circuit("NOT"))
    result = simulate(graph, {})  # a=X -> NOT X = X; only net n_a stays X, no events
    assert result.trace == ()
    assert result.event_count == 0


def test_gate_events_ordered_by_component_id_at_same_depth() -> None:
    """Two same-depth gates: (depth, id) order is normative."""
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
            {"id": "A_and", "type": "AND"},
            {"id": "B_xor", "type": "XOR"},
            {"id": "OUT_y1", "type": "OUTPUT", "params": {"name": "y1"}},
            {"id": "OUT_y2", "type": "OUTPUT", "params": {"name": "y2"}},
        ],
        "nets": [
            {
                "id": "n_a1",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "A_and", "pin": "a"}],
            },
            {
                "id": "n_a2",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "B_xor", "pin": "a"}],
            },
            {
                "id": "n_b1",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "A_and", "pin": "b"}],
            },
            {
                "id": "n_b2",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "B_xor", "pin": "b"}],
            },
            {
                "id": "n_y1",
                "driver": {"component": "A_and", "pin": "out"},
                "sinks": [{"component": "OUT_y1", "pin": "in"}],
            },
            {
                "id": "n_y2",
                "driver": {"component": "B_xor", "pin": "out"},
                "sinks": [{"component": "OUT_y2", "pin": "in"}],
            },
        ],
    }
    graph = parse_circuit(doc)
    result = simulate(graph, {"a": "1", "b": "1"})
    gate_events = [e for e in result.trace if e.cause.type == "gate"]
    assert [e.cause.component for e in gate_events] == ["A_and", "B_xor"]
    assert result.outputs == {"y1": "1", "y2": "0"}


def test_deeper_layer_evaluates_after_input_layer() -> None:
    """NOT(NOT(a)): both inverters change; deeper one has strictly larger delta."""
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "N1", "type": "NOT"},
            {"id": "N2", "type": "NOT"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "N1", "pin": "a"}],
            },
            {
                "id": "n_mid",
                "driver": {"component": "N1", "pin": "out"},
                "sinks": [{"component": "N2", "pin": "a"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "N2", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    graph = parse_circuit(doc)
    result = simulate(graph, {"a": "0"})
    assert result.outputs == {"y": "0"}
    deltas = [e.delta for e in result.trace]
    assert deltas == sorted(deltas)
    assert deltas[0] < deltas[-1]
    assert result.trace[-1].new == "0" and result.trace[-1].old == "X"


def test_invalid_input_value_raises_typed_error() -> None:
    graph = parse_circuit(io_circuit())
    with pytest.raises(InvalidInputValueError) as excinfo:
        simulate(graph, {"a": "2"})
    assert excinfo.value.name == "a"


def test_integer_inputs_accepted() -> None:
    graph = parse_circuit(io_circuit("AND"))
    result = simulate(graph, {"a": 1, "b": 0})
    assert result.outputs == {"y": "0"}


def test_simulate_refuses_invalid_circuit() -> None:
    doc = io_circuit("AND")
    doc["nets"] = [doc["nets"][0]]  # keep only n_a; G.b and OUT_y.in left dangling
    graph = parse_circuit(doc)
    with pytest.raises(CircuitNotValidError) as excinfo:
        simulate(graph, {"a": "1"})
    assert not excinfo.value.report.ok
    assert validate(graph).ok is False


def test_result_serialization_shape() -> None:
    graph = parse_circuit(io_circuit("NOT"))
    payload = simulation_result_to_dict(simulate(graph, {"a": "1"}))
    assert payload["engine_version"] == "0.1.0"
    assert payload["scope"] == "SINGLE_VECTOR"
    assert payload["outputs"] == {"y": "0"}
    assert payload["event_count"] == len(payload["trace"])
    event = payload["trace"][0]
    assert set(event) == {"seq", "delta", "net", "old", "new", "cause"}
    assert set(event["cause"]) == {"type", "component"}


def test_unknown_input_names_are_ignored() -> None:
    graph = parse_circuit(io_circuit("NOT"))
    result = simulate(graph, {"a": "1", "ghost": "0"})
    assert result.outputs == {"y": "0"}


def test_logic_value_serializes_as_contract_string() -> None:
    assert LogicValue.UNKNOWN.value == "X"
    assert str(LogicValue.HIGH_Z) == "Z"

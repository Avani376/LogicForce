"""Truth-table tests: enumeration order, scope label, bound refusal."""

from __future__ import annotations

import pytest
from logic_engine import (
    TruthTableLimitExceededError,
    parse_circuit,
    truth_table,
    truth_table_to_dict,
    validate,
)


def half_adder_doc() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "half_adder",
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
            {"id": "G_xor", "type": "XOR"},
            {"id": "G_and", "type": "AND"},
            {"id": "OUT_sum", "type": "OUTPUT", "params": {"name": "sum"}},
            {"id": "OUT_cout", "type": "OUTPUT", "params": {"name": "carry_out"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [
                    {"component": "G_xor", "pin": "a"},
                    {"component": "G_and", "pin": "a"},
                ],
            },
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [
                    {"component": "G_xor", "pin": "b"},
                    {"component": "G_and", "pin": "b"},
                ],
            },
            {
                "id": "n_sum",
                "driver": {"component": "G_xor", "pin": "out"},
                "sinks": [{"component": "OUT_sum", "pin": "in"}],
            },
            {
                "id": "n_cout",
                "driver": {"component": "G_and", "pin": "out"},
                "sinks": [{"component": "OUT_cout", "pin": "in"}],
            },
        ],
    }


def test_half_adder_exhaustive_rows() -> None:
    result = truth_table(parse_circuit(half_adder_doc()))
    assert result.input_names == ("a", "b")
    assert result.output_names == ("carry_out", "sum")
    assert result.scope == "EXHAUSTIVE(4)"
    rows = [(row.inputs, row.outputs) for row in result.rows]
    assert rows == [
        ({"a": "0", "b": "0"}, {"carry_out": "0", "sum": "0"}),
        ({"a": "0", "b": "1"}, {"carry_out": "0", "sum": "1"}),
        ({"a": "1", "b": "0"}, {"carry_out": "0", "sum": "1"}),
        ({"a": "1", "b": "1"}, {"carry_out": "1", "sum": "0"}),
    ]


def test_first_input_name_is_msb() -> None:
    """Inputs sorted alphabetically; the first is the most significant row bit."""
    doc = half_adder_doc()
    result = truth_table(parse_circuit(doc))
    assert result.rows[2].inputs == {"a": "1", "b": "0"}  # index 2 = binary 10


def test_serialization_shape() -> None:
    payload = truth_table_to_dict(truth_table(parse_circuit(half_adder_doc())))
    assert payload["engine_version"] == "0.1.0"
    assert payload["scope"] == "EXHAUSTIVE(4)"
    assert payload["input_names"] == ["a", "b"]
    assert payload["output_names"] == ["carry_out", "sum"]
    assert len(payload["rows"]) == 4
    assert set(payload["rows"][0]) == {"inputs", "outputs"}


def test_no_input_circuit_yields_single_row() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "C1", "type": "CONST1"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            }
        ],
    }
    result = truth_table(parse_circuit(doc))
    assert result.scope == "EXHAUSTIVE(1)"
    assert result.input_names == ()
    assert len(result.rows) == 1
    assert result.rows[0].outputs == {"y": "1"}


def test_limit_refuses_beyond_twelve_inputs() -> None:
    """13 primary inputs exceed the exhaustive bound; the engine refuses (D11)."""
    import string

    names = [f"i{i:02d}" for i in range(13)]
    components: list[dict[str, object]] = [
        {"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}}
        for name in names
    ]
    components.append({"id": "G", "type": "AND", "params": {"width": 13}})
    components.append({"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}})
    nets: list[dict[str, object]] = []
    for i, name in enumerate(names):
        nets.append(
            {
                "id": f"n_{i:02d}",
                "driver": {"component": f"IN_{name}", "pin": "out"},
                "sinks": [{"component": "G", "pin": string.ascii_lowercase[i]}],
            }
        )
    nets.append(
        {
            "id": "n_y",
            "driver": {"component": "G", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        }
    )
    graph = parse_circuit({"schema_version": 1, "components": components, "nets": nets})
    assert validate(graph).ok
    with pytest.raises(TruthTableLimitExceededError) as excinfo:
        truth_table(graph)
    assert excinfo.value.input_count == 13
    assert excinfo.value.limit == 12

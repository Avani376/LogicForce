"""Optimization engine tests: every transformation class, gates, bounds, honesty."""

from __future__ import annotations

import json
from typing import Any

import pytest
from logic_engine import SchemaError, parse_circuit
from logic_engine.truth_table import truth_table
from optimize_engine import (
    optimization_report_to_dict,
    optimize,
)

WASTEFUL_HALF_ADDER: dict[str, Any] = {
    "schema_version": 1,
    "name": "wasteful_half_adder",
    "components": [
        {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
        {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
        {"id": "N1", "type": "NOT"},
        {"id": "N2", "type": "NOT"},
        {"id": "G_xor", "type": "XOR"},
        {"id": "A1", "type": "AND"},
        {"id": "A2", "type": "AND"},
        {"id": "C1", "type": "CONST1"},
        {"id": "OUT_sum", "type": "OUTPUT", "params": {"name": "sum"}},
        {"id": "OUT_cout", "type": "OUTPUT", "params": {"name": "carry_out"}},
    ],
    "nets": [
        {
            "id": "n_a",
            "driver": {"component": "IN_a", "pin": "out"},
            "sinks": [{"component": "G_xor", "pin": "a"}, {"component": "A1", "pin": "a"}],
        },
        {
            "id": "n_b",
            "driver": {"component": "IN_b", "pin": "out"},
            "sinks": [{"component": "N1", "pin": "a"}],
        },
        {
            "id": "n_n1",
            "driver": {"component": "N1", "pin": "out"},
            "sinks": [{"component": "N2", "pin": "a"}],
        },
        {
            "id": "n_n2",
            "driver": {"component": "N2", "pin": "out"},
            "sinks": [{"component": "G_xor", "pin": "b"}],
        },
        {
            "id": "n_sum",
            "driver": {"component": "G_xor", "pin": "out"},
            "sinks": [{"component": "OUT_sum", "pin": "in"}],
        },
        {
            "id": "n_c1",
            "driver": {"component": "A1", "pin": "out"},
            "sinks": [{"component": "A2", "pin": "a"}],
        },
        {
            "id": "n_ab",
            "driver": {"component": "IN_b", "pin": "out"},
            "sinks": [{"component": "A1", "pin": "b"}],
        },
        {
            "id": "n_c1out",
            "driver": {"component": "C1", "pin": "out"},
            "sinks": [{"component": "A2", "pin": "b"}],
        },
        {
            "id": "n_cout",
            "driver": {"component": "A2", "pin": "out"},
            "sinks": [{"component": "OUT_cout", "pin": "in"}],
        },
    ],
}

SAFETY_STYLE_PROPERTY = {
    "property_schema_version": 1,
    "id": "P-ha",
    "kind": "combinational_invariant",
    "expression": "!(sum & carry_out)",
}


def truth_table_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return truth_table(parse_circuit(a)).rows == truth_table(parse_circuit(b)).rows


def test_wasteful_half_adder_is_reduced_and_stays_equivalent() -> None:
    report = optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY])
    assert report.verdict == "OPTIMIZED"
    assert report.metrics_after["gate_count"] < report.metrics_before["gate_count"]
    assert report.final_model is not None
    # equivalence gate: identical truth table
    assert truth_table_equal(WASTEFUL_HALF_ADDER, report.final_model)
    # every transformation individually verified
    assert all(
        t.equivalence["equal"] is True and t.equivalence["scope"].startswith("EXHAUSTIVE(")
        for t in report.transformations
    )
    # all suite verdicts stayed PASS
    assert all(v["verdict"] == "PASS" for t in report.transformations for v in t.suite_verdicts)


def test_double_negation_removed() -> None:
    report = optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY])
    final_types = [c["type"] for c in (report.final_model or {})["components"]]  # type: ignore[index]
    assert final_types.count("NOT") == 0  # both redundant inverters eliminated
    descriptions = " | ".join(t.description for t in report.transformations)
    assert "double_negation" in descriptions


def test_constant_fold_and_all_ones_passthrough() -> None:
    report = optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY])
    descriptions = " | ".join(t.description for t in report.transformations)
    assert "constant_fold" in descriptions


def test_already_minimal_circuit_reports_no_change() -> None:
    minimal = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
            {"id": "G_xor", "type": "XOR"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G_xor", "pin": "a"}],
            },
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G_xor", "pin": "b"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "G_xor", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    report = optimize(minimal, [])
    assert report.verdict == "NO_CHANGE_APPLICABLE"
    assert report.final_model is None
    assert report.transformations == ()


def test_and_with_constant_zero_folds_to_constant() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "C0", "type": "CONST0"},
            {"id": "G_and", "type": "AND"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G_and", "pin": "a"}],
            },
            {
                "id": "n_c",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "G_and", "pin": "b"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "G_and", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    report = optimize(doc, [])
    assert report.verdict == "OPTIMIZED"
    assert report.final_model is not None
    types = {c["id"]: c["type"] for c in report.final_model["components"]}  # type: ignore[index]
    assert any(t == "CONST0" for t in types.values())  # folded to a constant
    assert "G_and" not in types  # the gate is gone
    assert report.metrics_after["gate_count"] < report.metrics_before["gate_count"]


def test_xor_with_constant_one_becomes_not() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "C1", "type": "CONST1"},
            {"id": "G_xor", "type": "XOR"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
        ],
        "nets": [
            {
                "id": "n_a",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G_xor", "pin": "a"}],
            },
            {
                "id": "n_c",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "G_xor", "pin": "b"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "G_xor", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
        ],
    }
    report = optimize(doc, [])
    assert report.verdict == "OPTIMIZED"
    descriptions = " | ".join(t.description for t in report.transformations)
    assert "inverted" in descriptions
    # equivalence: XOR(a, 1) == NOT(a)
    assert truth_table_equal(doc, report.final_model)  # type: ignore[arg-type]


def test_duplicate_gates_merged() -> None:
    doc = {
        "schema_version": 1,
        "components": [
            {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
            {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
            {"id": "G1", "type": "AND"},
            {"id": "G2", "type": "AND"},
            {"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}},
            {"id": "OUT_z", "type": "OUTPUT", "params": {"name": "z"}},
        ],
        "nets": [
            {
                "id": "n_a1",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G1", "pin": "a"}],
            },
            {
                "id": "n_a2",
                "driver": {"component": "IN_a", "pin": "out"},
                "sinks": [{"component": "G2", "pin": "a"}],
            },
            {
                "id": "n_b1",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G1", "pin": "b"}],
            },
            {
                "id": "n_b2",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G2", "pin": "b"}],
            },
            {
                "id": "n_y",
                "driver": {"component": "G1", "pin": "out"},
                "sinks": [{"component": "OUT_y", "pin": "in"}],
            },
            {
                "id": "n_z",
                "driver": {"component": "G2", "pin": "out"},
                "sinks": [{"component": "OUT_z", "pin": "in"}],
            },
        ],
    }
    report = optimize(doc, [])
    assert report.verdict == "OPTIMIZED"
    descriptions = " | ".join(t.description for t in report.transformations)
    assert "duplicate_merge" in descriptions
    assert report.final_model is not None
    assert truth_table_equal(doc, report.final_model)  # type: ignore[arg-type]


def test_suite_failing_on_nominal_stops_optimization_honestly() -> None:
    """A property the nominal circuit already violates: candidates keep failing it,
    so no transformation is accepted and the verdict is NO_CHANGE_APPLICABLE."""
    demanding = {
        "property_schema_version": 1,
        "id": "P-impossible",
        "kind": "combinational_invariant",
        "expression": "carry_out",  # must ALWAYS be 1 — the half adder violates it
    }
    report = optimize(WASTEFUL_HALF_ADDER, [demanding])
    assert report.verdict == "NO_CHANGE_APPLICABLE"
    assert report.final_model is None
    assert all(v["verdict"] == "FAIL" for t in report.transformations for v in t.suite_verdicts)


def test_too_many_inputs_is_incomplete() -> None:
    import string

    components: list[dict[str, Any]] = [
        {"id": f"IN_{name}", "type": "INPUT", "params": {"name": name}} for name in [f"i{i:02d}" for i in range(13)]
    ]
    components.append({"id": "G", "type": "AND", "params": {"width": 13}})
    components.append({"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}})
    nets = [
        {
            "id": f"n_{i}",
            "driver": {"component": f"IN_i{i:02d}", "pin": "out"},
            "sinks": [{"component": "G", "pin": string.ascii_lowercase[i]}],
        }
        for i in range(13)
    ]
    nets.append(
        {
            "id": "n_y",
            "driver": {"component": "G", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        }
    )
    doc = {"schema_version": 1, "components": components, "nets": nets}
    report = optimize(doc, [])
    assert report.verdict == "INCOMPLETE"
    assert report.reason is not None and report.reason.startswith("MODEL_TOO_LARGE")
    assert report.final_model is None


def test_max_transformations_bounds_and_cap() -> None:
    with pytest.raises(SchemaError) as excinfo:
        optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY], max_transformations=0)
    assert excinfo.value.code == "OPTIMIZATION_SCHEMA_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY], max_transformations=65)
    assert excinfo.value.code == "OPTIMIZATION_SCHEMA_ERROR"


def test_report_serialization_shape() -> None:
    payload = optimization_report_to_dict(optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY]))
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "input_hash",
        "metrics_before",
        "metrics_after",
        "transformations",
        "final_model",
        "verdict",
        "scope",
        "assumptions",
        "reason",
    }
    assert payload["engine_version"] == "0.5.0"
    assert "not hardware delay" in " ".join(payload["assumptions"])  # type: ignore[operator]


def test_optimization_is_deterministic() -> None:
    a = optimization_report_to_dict(optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY]))
    b = optimization_report_to_dict(optimize(WASTEFUL_HALF_ADDER, [SAFETY_STYLE_PROPERTY]))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

"""Invariant verification tests: verdicts, scopes, bounds, replayable counterexamples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from logic_engine import SchemaError
from verify_engine import (
    parse_property,
    verification_report_to_dict,
    verify_combinational_invariant,
    verify_fsm_invariant,
)

FSM_FIXTURE = Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def traffic_light() -> dict[str, Any]:
    return load(FSM_FIXTURE)["fsm"]


def half_adder() -> dict[str, Any]:
    return {
        "schema_version": 1,
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
                "sinks": [{"component": "G_xor", "pin": "a"}, {"component": "G_and", "pin": "a"}],
            },
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [{"component": "G_xor", "pin": "b"}, {"component": "G_and", "pin": "b"}],
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


def test_combinational_invariant_pass_on_half_adder() -> None:
    """sum and carry_out are mutually exclusive by construction: !(sum & carry)."""
    property_doc = {
        "property_schema_version": 1,
        "id": "P-ha",
        "kind": "combinational_invariant",
        "expression": "!(sum & carry_out)",
    }
    report = verify_combinational_invariant(half_adder(), property_doc)
    assert report.verdict == "PASS"
    assert report.scope == "EXHAUSTIVE(4 input vectors)"
    assert report.explored_cases == 4
    assert report.counterexample is None
    assert report.reason is None


def test_combinational_invariant_fail_has_replayable_counterexample() -> None:
    """The negated property must FAIL exactly where the positive one passed."""
    property_doc = {
        "property_schema_version": 1,
        "id": "P-bad",
        "kind": "combinational_invariant",
        "expression": "sum & carry_out",
    }
    report = verify_combinational_invariant(half_adder(), property_doc)
    assert report.verdict == "FAIL"
    counterexample = report.counterexample
    assert counterexample is not None
    # "sum & carry_out" does not hold where either is 0 — the first vector (00)
    # is already a violation; the report reports the first finding
    assert counterexample["inputs"] == {"a": "0", "b": "0"}
    assert counterexample["outputs"] == {"sum": "0", "carry_out": "0"}
    # replay guarantee: simulating the counterexample vector reproduces it
    from logic_engine import parse_circuit, simulate

    result = simulate(parse_circuit(half_adder()), counterexample["inputs"])
    assert result.outputs == counterexample["outputs"]


def test_unknown_signal_in_property_rejected() -> None:
    property_doc = {
        "property_schema_version": 1,
        "id": "P-x",
        "kind": "combinational_invariant",
        "expression": "ghost_output",
    }
    with pytest.raises(SchemaError) as excinfo:
        verify_combinational_invariant(half_adder(), property_doc)
    assert excinfo.value.code == "PROPERTY_SIGNAL_UNKNOWN"


def test_too_many_inputs_is_incomplete_not_bounded() -> None:
    """13 inputs exceed the exhaustive bound: INCOMPLETE with reason, never a
    silently-bounded claim."""
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
    property_doc = {
        "property_schema_version": 1,
        "id": "P-big",
        "kind": "combinational_invariant",
        "expression": "y",
    }
    report = verify_combinational_invariant(doc, property_doc)
    assert report.verdict == "INCOMPLETE"
    assert report.scope == "INCOMPLETE"
    assert report.reason is not None and report.reason.startswith("MODEL_TOO_LARGE")
    assert report.counterexample is None


def test_property_kind_must_match_model() -> None:
    property_doc = {
        "property_schema_version": 1,
        "id": "P-kind",
        "kind": "fsm_invariant",
        "expression": "q",
    }
    with pytest.raises(SchemaError) as excinfo:
        verify_combinational_invariant(half_adder(), property_doc)
    assert excinfo.value.code == "PROPERTY_SCHEMA_ERROR"


def test_fsm_invariant_pass_on_traffic_light() -> None:
    property_doc = {
        "property_schema_version": 1,
        "id": "P1",
        "kind": "fsm_invariant",
        "statement": "Two conflicting directions never green simultaneously",
        "expression": "!(north_green & east_green)",
    }
    report = verify_fsm_invariant(traffic_light(), property_doc)
    assert report.verdict == "PASS"
    assert report.scope == "EXHAUSTIVE(8 firings over 4 of 4 states)"
    assert report.explored_cases == 8
    assert report.counterexample is None


def test_fsm_invariant_unreachable_states_do_not_explode_scope() -> None:
    """An undeclared (unreachable) state does not affect the explored count."""
    doc = traffic_light()
    doc["states"].append("never_reached")
    property_doc = {
        "property_schema_version": 1,
        "id": "P1",
        "kind": "fsm_invariant",
        "expression": "!(north_green & east_green)",
    }
    report = verify_fsm_invariant(doc, property_doc)
    assert report.verdict == "PASS"
    assert report.scope == "EXHAUSTIVE(8 firings over 4 of 5 states)"


def test_fsm_model_too_large_is_incomplete() -> None:
    doc = traffic_light()
    doc["states"] = [f"s{i}" for i in range(300)]
    doc["initial"] = "s0"
    doc["transitions"] = [{"from": "s0", "when": {}, "to": "s0", "outputs": {}}]
    property_doc = {
        "property_schema_version": 1,
        "id": "P-big",
        "kind": "fsm_invariant",
        "expression": "north_green",
    }
    report = verify_fsm_invariant(doc, property_doc)
    assert report.verdict == "INCOMPLETE"
    assert report.reason is not None and "MODEL_TOO_LARGE" in report.reason


def test_report_serialization_contract() -> None:
    property_doc = {
        "property_schema_version": 1,
        "id": "P1",
        "kind": "fsm_invariant",
        "expression": "!(north_green & east_green)",
    }
    payload = verification_report_to_dict(verify_fsm_invariant(traffic_light(), property_doc))
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "input_hash",
        "property",
        "model_kind",
        "verdict",
        "scope",
        "explored_cases",
        "assumptions",
        "counterexample",
        "reason",
    }
    assert payload["engine_version"] == "0.3.0"
    assert len(payload["input_hash"]) == 64


def test_property_parse_errors_are_typed() -> None:
    with pytest.raises(SchemaError) as excinfo:
        parse_property({"property_schema_version": 9, "id": "x", "kind": "fsm_invariant", "expression": "a"})
    assert excinfo.value.code == "PROPERTY_SCHEMA_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        parse_property({"property_schema_version": 1, "id": "", "kind": "fsm_invariant", "expression": "a"})
    assert excinfo.value.code == "PROPERTY_SCHEMA_ERROR"

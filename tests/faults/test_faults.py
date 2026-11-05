"""Fault operator tests: application, determinism, non-mutation, typed errors."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fault_engine import apply_fault, parse_fault
from logic_engine import SchemaError
from sequential_engine import fsm_simulate, parse_fsm

TRAFFIC_LIGHT: dict[str, Any] = {
    "fsm_schema_version": 1,
    "name": "traffic_light",
    "inputs": ["ped_button"],
    "outputs": ["north_green", "east_green"],
    "states": ["north_green", "north_yellow", "east_green", "east_yellow"],
    "initial": "north_green",
    "transitions": [
        {
            "from": "north_green",
            "when": {"ped_button": "0"},
            "to": "north_green",
            "outputs": {"north_green": "1", "east_green": "0"},
        },
        {
            "from": "north_green",
            "when": {"ped_button": "1"},
            "to": "north_yellow",
            "outputs": {"north_green": "0", "east_green": "0"},
        },
        {
            "from": "north_yellow",
            "when": {},
            "to": "east_green",
            "outputs": {"north_green": "0", "east_green": "1"},
        },
        {
            "from": "east_green",
            "when": {"ped_button": "0"},
            "to": "east_green",
            "outputs": {"north_green": "0", "east_green": "1"},
        },
        {
            "from": "east_green",
            "when": {"ped_button": "1"},
            "to": "east_yellow",
            "outputs": {"north_green": "0", "east_green": "0"},
        },
        {
            "from": "east_yellow",
            "when": {},
            "to": "north_green",
            "outputs": {"north_green": "1", "east_green": "0"},
        },
    ],
}

HALF_ADDER: dict[str, Any] = {
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


def fault(
    operator: str, target: dict[str, Any], params: dict[str, Any] | None = None
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "fault_schema_version": 1,
        "id": "F-test",
        "operator": operator,
        "target": target,
    }
    if params is not None:
        doc["params"] = params
    return doc


def test_transition_redirect_produces_double_green() -> None:
    """Redirecting the crossing request straight to east_green while north stays
    green — the signature double-green fault."""
    faulty = apply_fault(
        "fsm",
        TRAFFIC_LIGHT,
        fault(
            "transition_redirect",
            {"transition_index": 1},
            {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
        ),
    )
    fsm = parse_fsm(faulty)
    replay = fsm_simulate(fsm, [{"ped_button": "1"}, {"ped_button": "0"}])
    # row 0 fires the faulty transition: double green appears in its outputs
    assert replay.cycles[0].outputs == {"north_green": "1", "east_green": "1"}
    assert replay.final_state == "east_green"
    # nominal document is untouched
    assert TRAFFIC_LIGHT["transitions"][1]["to"] == "north_yellow"


def test_output_flip_is_deterministic_and_reversible_by_second_application() -> None:
    f = fault("output_flip", {"transition_index": 0}, {"output": "north_green"})
    once = apply_fault("fsm", TRAFFIC_LIGHT, f)
    assert once["transitions"][0]["outputs"]["north_green"] == "0"
    twice = apply_fault("fsm", TRAFFIC_LIGHT, f)
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_transition_remove_creates_unmatched_hold() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, fault("transition_remove", {"transition_index": 1}))
    assert len(faulty["transitions"]) == len(TRAFFIC_LIGHT["transitions"]) - 1
    fsm = parse_fsm(faulty)
    replay = fsm_simulate(fsm, [{"ped_button": "1"}])
    # ped request no longer matches: state holds, cycle flagged unmatched
    assert replay.cycles[0].state == "north_green"
    assert replay.cycles[0].matched is False


def test_gate_swap_xor_to_or_changes_behavior() -> None:
    faulty = apply_fault(
        "combinational", HALF_ADDER, fault("gate_swap", {"component_id": "G_xor"}, {"to": "OR"})
    )
    types = {c["id"]: c["type"] for c in faulty["components"]}
    assert types["G_xor"] == "OR"
    # nominal untouched
    assert {c["id"]: c["type"] for c in HALF_ADDER["components"]}["G_xor"] == "XOR"


def test_stuck_at_rewires_pin_to_constant() -> None:
    faulty = apply_fault(
        "combinational",
        HALF_ADDER,
        fault("stuck_at", {"component_id": "G_and", "pin": "a"}, {"value": "0"}),
    )
    ids = {c["id"] for c in faulty["components"]}
    assert any(i.startswith("STUCK_G_and_a") for i in ids)
    # the carry gate's 'a' pin is now fed only by the constant
    feeds = [
        net
        for net in faulty["nets"]
        if any(
            s["component"] == "G_and" and s["pin"] == "a"
            for s in net["sinks"]
            if isinstance(s, dict)
        )
    ]
    assert len(feeds) == 1
    assert feeds[0]["driver"]["component"].startswith("STUCK_")
    # nominal still has the original two nets feeding nothing extra
    assert len(HALF_ADDER["nets"]) == 4


def test_stuck_at_on_output_pin_is_application_error() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational",
            HALF_ADDER,
            fault("stuck_at", {"component_id": "G_xor", "pin": "out"}, {"value": "0"}),
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_fault_target_not_found_cases() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "fsm",
            TRAFFIC_LIGHT,
            fault("output_flip", {"transition_index": 99}, {"output": "north_green"}),
        )
    assert excinfo.value.code == "FAULT_TARGET_NOT_FOUND"
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational", HALF_ADDER, fault("gate_swap", {"component_id": "GHOST"}, {"to": "OR"})
        )
    assert excinfo.value.code == "FAULT_TARGET_NOT_FOUND"


def test_fault_application_error_cases() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "fsm",
            TRAFFIC_LIGHT,
            fault("transition_redirect", {"transition_index": 1}, {"to": "atlantis"}),
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "fsm", TRAFFIC_LIGHT, fault("output_flip", {"transition_index": 0}, {"output": "mars"})
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational",
            HALF_ADDER,
            fault("gate_swap", {"component_id": "G_xor"}, {"to": "WEDGE"}),
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_operator_family_must_match_model_kind() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault("fsm", TRAFFIC_LIGHT, fault("gate_swap", {"component_id": "x"}, {"to": "OR"}))
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational",
            HALF_ADDER,
            fault("output_flip", {"transition_index": 0}, {"output": "sum"}),
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_fault_parse_errors() -> None:
    with pytest.raises(SchemaError) as excinfo:
        parse_fault({"fault_schema_version": 9, "id": "x", "operator": "gate_swap", "target": {}})
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        parse_fault({"fault_schema_version": 1, "id": "x", "operator": "teleport", "target": {}})
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        parse_fault({"fault_schema_version": 1, "id": "", "operator": "gate_swap", "target": {}})
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"

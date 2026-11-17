"""Phase 4 audit (session 5): coverage gaps + the empty-suite overclaim guard."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fault_engine import apply_fault, run_fault_experiment
from logic_engine import SchemaError
from repair_engine import apply_patch, compute_deltas, search_repairs

TRAFFIC_LIGHT: dict[str, Any] = {
    "fsm_schema_version": 1,
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

SAFETY = {
    "property_schema_version": 1,
    "id": "P1",
    "kind": "fsm_invariant",
    "expression": "!(north_green & east_green)",
}

STUCK_AT_FAULT = {
    "fault_schema_version": 1,
    "id": "F-sa",
    "operator": "stuck_at",
    "target": {"component_id": "G_and", "pin": "a"},
    "params": {"value": "0"},
}


def test_transition_redirect_with_only_to_param() -> None:
    faulty = apply_fault(
        "fsm",
        TRAFFIC_LIGHT,
        {
            "fault_schema_version": 1,
            "id": "F",
            "operator": "transition_redirect",
            "target": {"transition_index": 1},
            "params": {"to": "east_green"},
        },
    )
    assert faulty["transitions"][1]["to"] == "east_green"
    assert faulty["transitions"][1]["outputs"] == {"north_green": "0", "east_green": "0"}


def test_transition_redirect_with_only_outputs_param() -> None:
    faulty = apply_fault(
        "fsm",
        TRAFFIC_LIGHT,
        {
            "fault_schema_version": 1,
            "id": "F",
            "operator": "transition_redirect",
            "target": {"transition_index": 1},
            "params": {"set_outputs": {"north_green": "1"}},
        },
    )
    assert faulty["transitions"][1]["to"] == "north_yellow"
    assert faulty["transitions"][1]["outputs"]["north_green"] == "1"


def test_transition_redirect_without_params_is_application_error() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "fsm",
            TRAFFIC_LIGHT,
            {
                "fault_schema_version": 1,
                "id": "F",
                "operator": "transition_redirect",
                "target": {"transition_index": 1},
                "params": {},
            },
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_output_flip_on_undeclared_transition_output() -> None:
    """A transition that declares no outputs cannot have one flipped — the engine
    reports it instead of inventing a value."""
    doc = json.loads(json.dumps(TRAFFIC_LIGHT))
    doc["transitions"][2]["outputs"] = {}  # partial/empty declaration
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "fsm",
            doc,
            {
                "fault_schema_version": 1,
                "id": "F",
                "operator": "output_flip",
                "target": {"transition_index": 2},
                "params": {"output": "east_green"},
            },
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_gate_swap_to_primary_io_rejected() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational",
            HALF_ADDER,
            {
                "fault_schema_version": 1,
                "id": "F",
                "operator": "gate_swap",
                "target": {"component_id": "G_xor"},
                "params": {"to": "INPUT"},
            },
        )
    assert excinfo.value.code == "FAULT_APPLICATION_ERROR"


def test_stuck_at_on_unconnected_pin_drives_it() -> None:
    """A dangling pin becomes constant-driven — the fault FIXES validation.
    (n_b feeds both G_xor.b and G_and.b; detach only G_xor.b's sink.)"""
    doc = json.loads(json.dumps(HALF_ADDER))
    doc["nets"] = [
        {
            **n,
            "sinks": [s for s in n["sinks"] if not (s["component"] == "G_xor" and s["pin"] == "b")],
        }
        for n in doc["nets"]
    ]
    faulty = apply_fault(
        "combinational",
        doc,
        {
            "fault_schema_version": 1,
            "id": "F",
            "operator": "stuck_at",
            "target": {"component_id": "G_xor", "pin": "b"},
            "params": {"value": "1"},
        },
    )
    from logic_engine import parse_circuit, validate

    graph = parse_circuit(faulty)
    assert validate(graph).ok is True  # the fault repaired the dangling pin


def test_stuck_at_empty_target_component_id_rejected() -> None:
    with pytest.raises(SchemaError) as excinfo:
        apply_fault(
            "combinational",
            HALF_ADDER,
            {
                "fault_schema_version": 1,
                "id": "F",
                "operator": "stuck_at",
                "target": {"component_id": "", "pin": "a"},
                "params": {"value": "0"},
            },
        )
    assert excinfo.value.code == "FAULT_TARGET_NOT_FOUND"


def test_fault_experiment_empty_suite_is_honestly_undetected() -> None:
    """A behavior probe without properties cannot detect anything — detected=false
    is the honest answer, and the probe still runs."""
    report = run_fault_experiment(
        "fsm",
        TRAFFIC_LIGHT,
        {
            "fault_schema_version": 1,
            "id": "F",
            "operator": "transition_redirect",
            "target": {"transition_index": 1},
            "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
        },
        [],
    )
    assert report.detected is False
    assert report.checks == ()
    assert report.behavior["first_divergence"] is not None


def test_repair_search_requires_a_property_suite() -> None:
    """'Repaired' is a safety claim — an empty suite would make it vacuously true.
    The engine refuses instead of overclaiming."""
    faulty = apply_fault("combinational", HALF_ADDER, STUCK_AT_FAULT)
    with pytest.raises(SchemaError) as excinfo:
        search_repairs("combinational", HALF_ADDER, faulty, [])
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"


def test_repair_add_and_remove_transition_patches() -> None:
    """A tail transition_remove fault repairs via an add_transition restore patch.
    (Index alignment is the documented v1 delta strategy — middle removals shift
    every index and are a known delta-quality limitation.)"""
    faulty = json.loads(json.dumps(TRAFFIC_LIGHT))
    faulty["transitions"].pop()  # remove the tail transition: indexes stay aligned
    deltas = compute_deltas("fsm", TRAFFIC_LIGHT, faulty)
    ops = [d["op"] for d in deltas]
    assert ops == ["add_transition"]
    repaired = apply_patch("fsm", faulty, deltas[0])
    assert json.dumps(repaired["transitions"], sort_keys=True) == json.dumps(
        TRAFFIC_LIGHT["transitions"], sort_keys=True
    )


def test_apply_patch_comb_component_and_net_ops() -> None:
    add_component = {"op": "add_component", "value": {"id": "G_extra", "type": "BUFFER"}}
    after_add = apply_patch("combinational", HALF_ADDER, add_component)
    assert any(c["id"] == "G_extra" for c in after_add["components"])

    set_component = {
        "op": "set_component",
        "component_id": "G_extra",
        "value": {"id": "G_extra", "type": "NOT"},
    }
    after_set = apply_patch("combinational", after_add, set_component)
    types = {c["id"]: c["type"] for c in after_set["components"]}
    assert types["G_extra"] == "NOT"

    remove_component = {"op": "remove_component", "component_id": "G_extra"}
    after_remove = apply_patch("combinational", after_set, remove_component)
    assert not any(c["id"] == "G_extra" for c in after_remove["components"])

    set_net = {
        "op": "set_net",
        "net_id": "n_a",
        "value": {
            "id": "n_a",
            "driver": {"component": "IN_a", "pin": "out"},
            "sinks": [{"component": "G_xor", "pin": "a"}],
        },
    }
    after_net = apply_patch("combinational", HALF_ADDER, set_net)
    n_a = next(n for n in after_net["nets"] if n["id"] == "n_a")
    assert n_a["sinks"] == [{"component": "G_xor", "pin": "a"}]

    add_net = {
        "op": "add_net",
        "net_id": "n_new",
        "value": {"id": "n_new", "driver": {"component": "IN_b", "pin": "out"}, "sinks": []},
    }
    after_add_net = apply_patch("combinational", after_net, add_net)
    assert any(n["id"] == "n_new" for n in after_add_net["nets"])

    remove_net = {"op": "remove_net", "net_id": "n_new"}
    after_remove_net = apply_patch("combinational", after_add_net, remove_net)
    assert not any(n["id"] == "n_new" for n in after_remove_net["nets"])


def test_compute_deltas_rejects_unknown_model_kind() -> None:
    with pytest.raises(SchemaError) as excinfo:
        compute_deltas("quantum", HALF_ADDER, HALF_ADDER)
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"


def test_fsm_fsm_max_candidates_boundary_is_accepted() -> None:
    faulty = json.loads(json.dumps(TRAFFIC_LIGHT))
    faulty["transitions"][1]["to"] = "east_green"
    report = search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY], max_candidates=1)
    assert report.cap == 1
    assert len(report.candidates) == 1
    assert report.candidates[0].valid is True  # combined restore with a single delta

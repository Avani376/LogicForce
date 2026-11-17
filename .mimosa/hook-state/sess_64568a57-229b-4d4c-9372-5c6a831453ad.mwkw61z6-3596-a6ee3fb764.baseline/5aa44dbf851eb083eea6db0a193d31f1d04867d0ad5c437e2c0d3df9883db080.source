"""Fault experiment tests: behavior probes, detection honesty, determinism."""

from __future__ import annotations

import json
from typing import Any

from fault_engine import fault_experiment_report_to_dict, run_fault_experiment

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

SAFETY = {
    "property_schema_version": 1,
    "id": "P1",
    "kind": "fsm_invariant",
    "expression": "!(north_green & east_green)",
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

MUTUAL_EXCLUSION = {
    "property_schema_version": 1,
    "id": "P-ha",
    "kind": "combinational_invariant",
    "expression": "!(sum & carry_out)",
}


def test_fsm_experiment_detects_double_green() -> None:
    report = run_fault_experiment(
        "fsm",
        TRAFFIC_LIGHT,
        {
            "fault_schema_version": 1,
            "id": "F-dg",
            "operator": "transition_redirect",
            "target": {"transition_index": 1},
            "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
        },
        [SAFETY],
    )
    assert report.applied is True
    assert report.detected is True
    assert report.checks[0].nominal_verdict == "PASS"
    assert report.checks[0].faulty_verdict == "FAIL"
    assert report.checks[0].detected is True
    assert report.checks[0].counterexample is not None
    # behavior probe: divergence found in the bounded sweep
    assert report.behavior["kind"] == "fsm"
    assert report.behavior["first_divergence"] is not None


def test_fsm_experiment_undetected_fault_reported_honestly() -> None:
    """Removing the ped-request transition changes behavior but not safety — the
    suite does NOT detect it, and the report must say so."""
    report = run_fault_experiment(
        "fsm",
        TRAFFIC_LIGHT,
        {
            "fault_schema_version": 1,
            "id": "F-hold",
            "operator": "transition_remove",
            "target": {"transition_index": 1},
        },
        [SAFETY],
    )
    assert report.detected is False
    assert report.checks[0].nominal_verdict == "PASS"
    assert report.checks[0].faulty_verdict == "PASS"
    assert report.checks[0].detected is False
    # the behavior probe still saw the divergence (cycle 1: ped=1 holds)
    assert report.behavior["first_divergence"] is not None
    assert report.behavior["first_divergence"]["cycle"] == 1


def test_comb_experiment_detects_gate_swap() -> None:
    report = run_fault_experiment(
        "combinational",
        HALF_ADDER,
        {
            "fault_schema_version": 1,
            "id": "F-or",
            "operator": "gate_swap",
            "target": {"component_id": "G_xor"},
            "params": {"to": "OR"},
        },
        [MUTUAL_EXCLUSION],
    )
    assert report.detected is True
    assert report.behavior["kind"] == "combinational"
    assert report.behavior["scope"] == "EXHAUSTIVE(4 rows)"
    assert report.behavior["differing_rows"] == 1  # XOR vs OR differ only on 11
    assert report.behavior["first_divergence"] is not None


def test_comb_experiment_undetected_stuck_at_reported_honestly() -> None:
    """Stuck-at-0 on the carry input forces carry_out=0 — the mutual-exclusion
    property still passes, so the fault is undetected by this suite."""
    report = run_fault_experiment(
        "combinational",
        HALF_ADDER,
        {
            "fault_schema_version": 1,
            "id": "F-sa",
            "operator": "stuck_at",
            "target": {"component_id": "G_and", "pin": "a"},
            "params": {"value": "0"},
        },
        [MUTUAL_EXCLUSION],
    )
    assert report.detected is False
    assert report.behavior["differing_rows"] == 1  # only row a=1,b=1 changes carry


def test_experiment_is_deterministic() -> None:
    fault = {
        "fault_schema_version": 1,
        "id": "F-dg",
        "operator": "transition_redirect",
        "target": {"transition_index": 1},
        "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
    }
    a = fault_experiment_report_to_dict(run_fault_experiment("fsm", TRAFFIC_LIGHT, fault, [SAFETY]))
    b = fault_experiment_report_to_dict(run_fault_experiment("fsm", TRAFFIC_LIGHT, fault, [SAFETY]))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_report_serialization_shape() -> None:
    payload = fault_experiment_report_to_dict(
        run_fault_experiment(
            "fsm",
            TRAFFIC_LIGHT,
            {
                "fault_schema_version": 1,
                "id": "F",
                "operator": "transition_remove",
                "target": {"transition_index": 1},
            },
            [SAFETY],
        )
    )
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "input_hash",
        "fault",
        "applied",
        "nominal_hash",
        "faulty_hash",
        "behavior",
        "checks",
        "detected",
    }
    assert set(payload["checks"][0]) == {
        "id",
        "nominal_verdict",
        "faulty_verdict",
        "detected",
        "counterexample",
    }

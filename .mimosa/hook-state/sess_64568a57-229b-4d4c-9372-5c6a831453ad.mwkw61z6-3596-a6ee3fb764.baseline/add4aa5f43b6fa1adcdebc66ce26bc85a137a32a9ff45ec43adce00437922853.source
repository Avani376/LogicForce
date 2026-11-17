"""Repair engine tests: candidate generation, re-verification gate, honesty."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fault_engine import apply_fault
from logic_engine import SchemaError
from repair_engine import apply_patch, compute_deltas, repair_report_to_dict, search_repairs
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

DOUBLE_GREEN_FAULT = {
    "fault_schema_version": 1,
    "id": "F-dg",
    "operator": "transition_redirect",
    "target": {"transition_index": 1},
    "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
}

STUCK_AT_FAULT = {
    "fault_schema_version": 1,
    "id": "F-sa",
    "operator": "stuck_at",
    "target": {"component_id": "G_and", "pin": "a"},
    "params": {"value": "0"},
}


def test_fsm_double_green_fault_is_repaired_and_re_verified() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    report = search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY])
    assert report.re_verified is True
    assert report.repaired_model is not None
    # the combined restore candidate comes first and is valid
    assert report.candidates[0].valid is True
    assert list(report.candidates[0].verdicts) == [{"id": "P1", "verdict": "PASS"}]
    # repaired model passes the suite by construction — verify independently
    from verify_engine import verify_fsm_invariant

    independent = verify_fsm_invariant(report.repaired_model, SAFETY)
    assert independent.verdict == "PASS"
    # repaired model matches nominal on the repaired region
    assert report.repaired_model["transitions"][1]["to"] == "north_yellow"
    assert report.repaired_model["transitions"][1]["outputs"] == {
        "north_green": "0",
        "east_green": "0",
    }


def test_repair_non_mutation() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    before = json.dumps(faulty, sort_keys=True)
    search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY])
    assert json.dumps(faulty, sort_keys=True) == before


def test_comb_stuck_at_repair_single_deltas_are_invalid() -> None:
    """stuck_at adds a component, a net, AND rewires another net — no single-field
    patch restores validity; only the combined restore is valid."""
    faulty = apply_fault("combinational", HALF_ADDER, STUCK_AT_FAULT)
    report = search_repairs("combinational", HALF_ADDER, faulty, [MUTUAL_EXCLUSION])
    assert report.re_verified is True
    assert report.repaired_model is not None
    assert report.candidates[0].valid is True  # combined restore
    singles = report.candidates[1:]
    assert len(singles) >= 3
    assert all(candidate.valid is False for candidate in singles)


def test_repaired_comb_model_matches_nominal_exactly() -> None:
    faulty = apply_fault("combinational", HALF_ADDER, STUCK_AT_FAULT)
    report = search_repairs("combinational", HALF_ADDER, faulty, [MUTUAL_EXCLUSION])
    assert report.repaired_model is not None
    assert json.dumps(report.repaired_model, sort_keys=True) == json.dumps(HALF_ADDER, sort_keys=True)


def test_cap_limits_candidates_and_is_reported() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    report = search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY], max_candidates=2)
    assert report.candidates_considered == 3  # combined + 2 single deltas
    assert report.cap == 2
    assert len(report.candidates) == 2


def test_max_candidates_bounds_enforced() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    with pytest.raises(SchemaError) as excinfo:
        search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY], max_candidates=0)
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"
    with pytest.raises(SchemaError) as excinfo:
        search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY], max_candidates=33)
    assert excinfo.value.code == "FAULT_SCHEMA_ERROR"


def test_suite_failing_on_nominal_yields_no_repair() -> None:
    """If the property suite already fails on the nominal model, no candidate can
    be 'valid' — the honest result is repaired_model: null."""
    broken_safety = {
        "property_schema_version": 1,
        "id": "P-broken",
        "kind": "fsm_invariant",
        "expression": "north_green",  # must ALWAYS be 1 — the healthy FSM violates it
    }
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    report = search_repairs("fsm", TRAFFIC_LIGHT, faulty, [broken_safety])
    assert report.repaired_model is None
    assert report.re_verified is False
    assert all(candidate.valid is False for candidate in report.candidates)


def test_repaired_fsm_replay_matches_nominal_behavior() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    report = search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY])
    assert report.repaired_model is not None
    repaired = parse_fsm(report.repaired_model)
    nominal = parse_fsm(TRAFFIC_LIGHT)
    inputs = [{"ped_button": "1"}, {"ped_button": "0"}, {"ped_button": "1"}, {"ped_button": "0"}]
    repaired_trace = fsm_simulate(repaired, inputs)
    nominal_trace = fsm_simulate(nominal, inputs)
    assert [row.state for row in repaired_trace.cycles] == [row.state for row in nominal_trace.cycles]


def test_compute_deltas_counts_redirect_fields() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    deltas = compute_deltas("fsm", TRAFFIC_LIGHT, faulty)
    ops = [delta["op"] for delta in deltas]
    assert ops == ["set_to", "set_transition_outputs"]


def test_repair_report_serialization_shape() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    payload = repair_report_to_dict(search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY]))
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "input_hash",
        "candidates_considered",
        "cap",
        "candidates",
        "repaired_model",
        "re_verified",
    }
    assert payload["engine_version"] == "0.4.0"


def test_search_is_deterministic() -> None:
    faulty = apply_fault("fsm", TRAFFIC_LIGHT, DOUBLE_GREEN_FAULT)
    a = repair_report_to_dict(search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY]))
    b = repair_report_to_dict(search_repairs("fsm", TRAFFIC_LIGHT, faulty, [SAFETY]))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_apply_patch_never_mutates_input() -> None:
    faulty = apply_fault("combinational", HALF_ADDER, STUCK_AT_FAULT)
    deltas = compute_deltas("combinational", HALF_ADDER, faulty)
    combined = {"op": "restore_nominal", "ops": deltas}
    before = json.dumps(faulty, sort_keys=True)
    apply_patch("combinational", faulty, combined)
    assert json.dumps(faulty, sort_keys=True) == before

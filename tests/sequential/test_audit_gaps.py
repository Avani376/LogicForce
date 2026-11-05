"""Phase 1/2 audit additions (session 3): coverage gaps found by professional review.

Each test pins behavior that the original suites exercised only implicitly —
duplicate net ids in v2, unread-net warnings, param strictness on sequential
types, REGISTER async set, invalid async controls on counters, FSM document
duplicates, and input-free FSMs.
"""

from __future__ import annotations

from typing import Any

import pytest
from logic_engine import SchemaError
from sequential_engine import fsm_reachable, fsm_simulate, parse_fsm, simulate_sequential
from sequential_engine.graph import parse_circuit_v2
from sequential_engine.validation import validate_sequential


def dff_doc(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "C1", "type": "CONST1"},
            {"id": "FF1", "type": "DFF"},
            {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
        ],
        "nets": [
            {
                "id": "n_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "pre"}],
            },
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "clr"}],
            },
            {
                "id": "n_d",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "d"}],
            },
            {
                "id": "n_q",
                "driver": {"component": "FF1", "pin": "q"},
                "sinks": [{"component": "OUT_q", "pin": "in"}],
            },
        ],
    }
    doc.update(overrides)
    return doc


def seq_codes(doc: dict[str, Any]) -> tuple[list[str], list[str]]:
    components, nets, name = parse_circuit_v2(doc)
    report = validate_sequential(components, nets, name)
    return [i.code for i in report.errors], [w.code for w in report.warnings]


def test_duplicate_net_id_in_v2() -> None:
    doc = dff_doc()
    doc["nets"][3]["id"] = "n_pre"
    errors, _ = seq_codes(doc)
    assert "DUPLICATE_NET_ID" in errors


def test_unread_net_is_warning_in_v2() -> None:
    doc = dff_doc()
    doc["nets"].append({"id": "n_qn", "driver": {"component": "FF1", "pin": "qn"}, "sinks": []})
    errors, warnings = seq_codes(doc)
    assert errors == []
    assert warnings == ["UNREAD_NET"]


def test_duplicate_io_names_in_v2() -> None:
    doc = dff_doc()
    doc["components"].append({"id": "OUT_q2", "type": "OUTPUT", "params": {"name": "q"}})
    doc["nets"][3]["sinks"].append({"component": "OUT_q2", "pin": "in"})
    errors, _ = seq_codes(doc)
    assert "DUPLICATE_IO_NAME" in errors


def test_flipflop_rejects_width_param() -> None:
    doc = dff_doc()
    doc["components"][2] = {"id": "FF1", "type": "DFF", "params": {"width": 4}}
    errors, _ = seq_codes(doc)
    assert "INVALID_PARAM" in errors


def test_register_accepts_width_and_state_pins() -> None:
    doc = dff_doc()
    doc["components"].append({"id": "REG", "type": "REGISTER", "params": {"width": 2}})
    doc["nets"].extend(
        [
            {
                "id": "nr_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "pre"}],
            },
            {
                "id": "nr_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "clr"}],
            },
            {
                "id": "nr_d0",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "d0"}],
            },
            {
                "id": "nr_d1",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "d1"}],
            },
        ]
    )
    errors, _ = seq_codes(doc)
    assert errors == []


def test_register_async_set_forces_all_bits() -> None:
    """pre=1 forces EVERY bit of a REGISTER to 1 (async, per contract stage 2)."""
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "C1", "type": "CONST1"},
            {"id": "IN_pre", "type": "INPUT", "params": {"name": "pre"}},
            {"id": "REG", "type": "REGISTER", "params": {"width": 2}},
        ],
        "nets": [
            {
                "id": "n_pre",
                "driver": {"component": "IN_pre", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "pre"}],
            },
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "clr"}],
            },
            {
                "id": "n_d0",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "d0"}],
            },
            {
                "id": "n_d1",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "REG", "pin": "d1"}],
            },
        ],
    }
    result = simulate_sequential(doc, 2, [{"pre": "1"}, {"pre": "0"}])
    # cycle 0: async set observed on both bits; d=0 captures at the edge
    assert result.cycles[0].state == {"REG.q0": "1", "REG.q1": "1"}
    assert result.final_state == {"REG.q0": "0", "REG.q1": "0"}


def test_counter_unknown_clear_is_honest() -> None:
    """clr=X on a COUNTER is an invalid async control -> state X (honesty rule)."""
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C1", "type": "CONST1"},
            {"id": "IN_clr", "type": "INPUT", "params": {"name": "clr"}},
            {"id": "CNT", "type": "COUNTER", "params": {"width": 2}},
        ],
        "nets": [
            {
                "id": "n_clr",
                "driver": {"component": "IN_clr", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "clr"}],
            },
            {
                "id": "n_en",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "en"}],
            },
        ],
    }
    result = simulate_sequential(doc, 2, [{"clr": "X"}, {"clr": "0"}])
    assert result.cycles[0].state == {"CNT.q0": "X", "CNT.q1": "X"}
    # incrementing an unknown value yields an unknown successor (honesty rule)
    assert result.final_state == {"CNT.q0": "X", "CNT.q1": "X"}


def test_malformed_position_is_ignored() -> None:
    doc = dff_doc()
    doc["components"][2]["position"] = {"x": "not-a-number"}
    components, _, _ = parse_circuit_v2(doc)
    ff = next(c for c in components if c.id == "FF1")
    assert ff.position is None


def test_fsm_duplicate_states_rejected() -> None:
    doc = {
        "fsm_schema_version": 1,
        "inputs": ["a"],
        "outputs": ["o"],
        "states": ["s0", "s0"],
        "initial": "s0",
        "transitions": [{"from": "s0", "when": {}, "to": "s0", "outputs": {"o": "0"}}],
    }
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "FSM_SCHEMA_ERROR"


def test_fsm_without_inputs_is_valid_and_reachable() -> None:
    """An FSM with an empty input alphabet: unconditional transitions only."""
    doc = {
        "fsm_schema_version": 1,
        "inputs": [],
        "outputs": ["lamp"],
        "states": ["off", "on"],
        "initial": "off",
        "transitions": [
            {"from": "off", "when": {}, "to": "on", "outputs": {"lamp": "1"}},
            {"from": "on", "when": {}, "to": "off", "outputs": {"lamp": "0"}},
        ],
    }
    fsm = parse_fsm(doc)
    result = fsm_simulate(fsm, [{}, {}, {}])
    assert [row.state for row in result.cycles] == ["off", "on", "off"]
    reachable, scope = fsm_reachable(fsm)
    assert list(reachable) == ["off", "on"]
    assert scope == "EXHAUSTIVE(2 of 2 states)"


def test_engine_version_error_str() -> None:
    from logic_engine.errors import InvalidInputValueError

    error = InvalidInputValueError("a", "2")
    assert "invalid value for input 'a'" in str(error)

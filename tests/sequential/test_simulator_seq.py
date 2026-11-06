"""Sequential simulator behavior tests: tick order, async, honesty, bounds."""

from __future__ import annotations

from typing import Any

import pytest
from logic_engine import SchemaError
from sequential_engine import simulate_sequential


def dff_with_clr() -> dict[str, Any]:
    """DFF whose d is CONST1; clr driven by primary input; q observed."""
    return {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "C1", "type": "CONST1"},
            {"id": "IN_clr", "type": "INPUT", "params": {"name": "clr"}},
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
                "driver": {"component": "IN_clr", "pin": "out"},
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


def test_power_on_state_is_zero() -> None:
    result = simulate_sequential(dff_with_clr(), 1, [{"clr": "0"}])
    assert result.cycles[0].state == {"FF1.q": "0"}
    assert result.cycles[0].outputs == {"q": "0"}


def test_dff_captures_one_then_holds() -> None:
    result = simulate_sequential(dff_with_clr(), 3, [{"clr": "0"}] * 3)
    assert [row.state["FF1.q"] for row in result.cycles] == ["0", "1", "1"]
    assert result.final_state == {"FF1.q": "1"}
    causes = [(event.cycle, event.cause, event.old, event.new) for event in result.events]
    assert causes == [(0, "clock_edge", "0", "1")]


def test_async_clear_overrides_during_cycle() -> None:
    """clr=1 forces q to 0 the cycle it is asserted, overriding d=CONST1."""
    result = simulate_sequential(dff_with_clr(), 4, [{"clr": "0"}, {"clr": "1"}, {"clr": "1"}, {"clr": "0"}])
    assert [row.state["FF1.q"] for row in result.cycles] == ["0", "0", "0", "1"]
    async_events = [e for e in result.events if e.cause == "async"]
    assert any(e.cycle == 1 and e.new == "0" for e in async_events)


def test_async_set_forces_one() -> None:
    doc = dff_with_clr()
    doc["components"] = [
        {"id": "C0", "type": "CONST0"},
        {"id": "C1", "type": "CONST1"},
        {"id": "IN_pre", "type": "INPUT", "params": {"name": "pre"}},
        {"id": "FF1", "type": "DFF"},
        {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
    ]
    doc["nets"] = [
        {
            "id": "n_pre",
            "driver": {"component": "IN_pre", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "pre"}],
        },
        {
            "id": "n_clr",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "clr"}],
        },
        {
            "id": "n_d",
            "driver": {"component": "C0", "pin": "out"},
            "sinks": [{"component": "FF1", "pin": "d"}],
        },
        {
            "id": "n_q",
            "driver": {"component": "FF1", "pin": "q"},
            "sinks": [{"component": "OUT_q", "pin": "in"}],
        },
    ]
    result = simulate_sequential(doc, 2, [{"pre": "1"}, {"pre": "0"}])
    # cycle 0: async set observed immediately AND held through the edge;
    # cycle 1: pre released (observed 1), d=0 captures at the edge
    assert [row.state["FF1.q"] for row in result.cycles] == ["1", "1"]
    assert result.final_state == {"FF1.q": "0"}


def test_async_invalid_controls_yield_x() -> None:
    """pre=clr=1 is invalid; X control is invalid — both force X (honesty rule)."""
    doc = dff_with_clr()
    doc["components"].append({"id": "IN_pre", "type": "INPUT", "params": {"name": "pre"}})
    doc["nets"][0] = {
        "id": "n_pre",
        "driver": {"component": "IN_pre", "pin": "out"},
        "sinks": [{"component": "FF1", "pin": "pre"}],
    }
    result = simulate_sequential(doc, 2, [{"clr": "0", "pre": "1"}, {"clr": "X", "pre": "0"}])
    # cycle 0: pre=1 set observed; cycle 1: unknown clr is invalid -> X (honest)
    assert [row.state["FF1.q"] for row in result.cycles] == ["1", "X"]


def test_sr_forbidden_input_resolves_to_x_and_back() -> None:
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "IN_s", "type": "INPUT", "params": {"name": "s"}},
            {"id": "IN_r", "type": "INPUT", "params": {"name": "r"}},
            {"id": "SR1", "type": "SRFF"},
            {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
        ],
        "nets": [
            {
                "id": "n_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "SR1", "pin": "pre"}],
            },
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "SR1", "pin": "clr"}],
            },
            {
                "id": "n_s",
                "driver": {"component": "IN_s", "pin": "out"},
                "sinks": [{"component": "SR1", "pin": "s"}],
            },
            {
                "id": "n_r",
                "driver": {"component": "IN_r", "pin": "out"},
                "sinks": [{"component": "SR1", "pin": "r"}],
            },
            {
                "id": "n_q",
                "driver": {"component": "SR1", "pin": "q"},
                "sinks": [{"component": "OUT_q", "pin": "in"}],
            },
        ],
    }
    result = simulate_sequential(
        doc,
        4,
        [{"s": "1", "r": "0"}, {"s": "1", "r": "1"}, {"s": "0", "r": "0"}, {"s": "0", "r": "1"}],
    )
    assert [row.state["SR1.q"] for row in result.cycles] == ["0", "1", "X", "X"]
    assert [row.outputs["q"] for row in result.cycles] == ["0", "1", "X", "X"]
    assert result.final_state == {"SR1.q": "0"}  # reset recovers from X


def test_jk_toggle() -> None:
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "C1", "type": "CONST1"},
            {"id": "JK1", "type": "JKFF"},
            {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
        ],
        "nets": [
            {
                "id": "n_pre",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "JK1", "pin": "pre"}],
            },
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "JK1", "pin": "clr"}],
            },
            {
                "id": "n_j",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "JK1", "pin": "j"}],
            },
            {
                "id": "n_k",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "JK1", "pin": "k"}],
            },
            {
                "id": "n_q",
                "driver": {"component": "JK1", "pin": "q"},
                "sinks": [{"component": "OUT_q", "pin": "in"}],
            },
        ],
    }
    result = simulate_sequential(doc, 4, [])
    # observed states S_0..S_3: power-on 0, then toggling 1, 0, 1
    assert [row.state["JK1.q"] for row in result.cycles] == ["0", "1", "0", "1"]


def test_counter_wraps_modulo() -> None:
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "C1", "type": "CONST1"},
            {"id": "CNT", "type": "COUNTER", "params": {"width": 2}},
            {"id": "OUT_q0", "type": "OUTPUT", "params": {"name": "q0"}},
            {"id": "OUT_q1", "type": "OUTPUT", "params": {"name": "q1"}},
        ],
        "nets": [
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "clr"}],
            },
            {
                "id": "n_en",
                "driver": {"component": "C1", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "en"}],
            },
            {
                "id": "n_q0",
                "driver": {"component": "CNT", "pin": "q0"},
                "sinks": [{"component": "OUT_q0", "pin": "in"}],
            },
            {
                "id": "n_q1",
                "driver": {"component": "CNT", "pin": "q1"},
                "sinks": [{"component": "OUT_q1", "pin": "in"}],
            },
        ],
    }
    result = simulate_sequential(doc, 5, [])
    assert [row.state["CNT.q0"] for row in result.cycles] == ["0", "1", "0", "1", "0"]
    assert [row.state["CNT.q1"] for row in result.cycles] == ["0", "0", "1", "1", "0"]
    assert result.final_state == {"CNT.q0": "1", "CNT.q1": "0"}  # 5 mod 4 = 1


def test_counter_hold_on_enable_zero() -> None:
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "IN_en", "type": "INPUT", "params": {"name": "en"}},
            {"id": "CNT", "type": "COUNTER", "params": {"width": 2}},
        ],
        "nets": [
            {
                "id": "n_clr",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "clr"}],
            },
            {
                "id": "n_en",
                "driver": {"component": "IN_en", "pin": "out"},
                "sinks": [{"component": "CNT", "pin": "en"}],
            },
        ],
    }
    result = simulate_sequential(doc, 4, [{"en": "1"}, {"en": "0"}, {"en": "0"}, {"en": "1"}])
    values = [int(row.state["CNT.q0"]) + 2 * int(row.state["CNT.q1"]) for row in result.cycles]
    assert values == [0, 1, 1, 1]


def test_unknown_input_propagates_to_state() -> None:
    doc = dff_with_clr()
    doc["components"].append({"id": "IN_d", "type": "INPUT", "params": {"name": "d"}})
    doc["nets"][2] = {
        "id": "n_d",
        "driver": {"component": "IN_d", "pin": "out"},
        "sinks": [{"component": "FF1", "pin": "d"}],
    }
    result = simulate_sequential(doc, 3, [{"clr": "0", "d": "1"}, {"clr": "0", "d": "X"}, {"clr": "0", "d": "1"}])
    # observed: 0 (power-on), then 1 captured, then X captured, then 1 recovers
    assert [row.state["FF1.q"] for row in result.cycles] == ["0", "1", "X"]
    assert result.final_state == {"FF1.q": "1"}


def test_missing_trailing_inputs_default_to_x() -> None:
    doc = dff_with_clr()
    doc["components"].append({"id": "IN_d", "type": "INPUT", "params": {"name": "d"}})
    doc["nets"][2] = {
        "id": "n_d",
        "driver": {"component": "IN_d", "pin": "out"},
        "sinks": [{"component": "FF1", "pin": "d"}],
    }
    result = simulate_sequential(doc, 2, [{"clr": "0", "d": "1"}])
    # cycle 1 has no vector -> ALL inputs X, including clr; unknown async control
    # is invalid per the honesty rule -> state X (documented behavior)
    assert [row.state["FF1.q"] for row in result.cycles] == ["0", "X"]
    assert result.final_state == {"FF1.q": "X"}


def test_scope_label_and_event_order() -> None:
    result = simulate_sequential(dff_with_clr(), 2, [{"clr": "0"}])
    assert result.scope == "BOUNDED(2 cycles)"
    seqs = [(e.cycle, e.component, e.pin) for e in result.events]
    assert seqs == sorted(seqs)


def test_waveforms_have_one_entry_per_cycle() -> None:
    result = simulate_sequential(dff_with_clr(), 3, [{"clr": "0"}])
    for key, values in result.waveforms.items():
        assert len(values) == 3, key
    assert set(result.waveforms) == {"in:clr", "out:q", "FF1.q"}


def test_cycles_bounds_are_refused() -> None:
    with pytest.raises(SchemaError) as excinfo:
        simulate_sequential(dff_with_clr(), 0, [])
    assert excinfo.value.code == "INVALID_INPUT_SEQUENCE"
    with pytest.raises(SchemaError) as excinfo:
        simulate_sequential(dff_with_clr(), 257, [])
    assert excinfo.value.code == "CYCLES_LIMIT_EXCEEDED"


def test_input_sequence_longer_than_cycles_refused() -> None:
    with pytest.raises(SchemaError) as excinfo:
        simulate_sequential(dff_with_clr(), 2, [{"clr": "0"}, {"clr": "0"}, {"clr": "0"}])
    assert excinfo.value.code == "INPUT_SEQUENCE_TOO_LONG"


def test_state_components_listed() -> None:
    result = simulate_sequential(dff_with_clr(), 1, [{"clr": "0"}])
    assert result.state_components == ("FF1",)

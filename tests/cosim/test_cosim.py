"""Co-simulation tests: port wiring, event ordering, latency, determinism."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cosim_engine import run_cosim, cosim_report_to_dict

AND_CIRCUIT: dict[str, Any] = {
    "schema_version": 1,
    "components": [
        {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
        {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
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
            "id": "n_b",
            "driver": {"component": "IN_b", "pin": "out"},
            "sinks": [{"component": "G_and", "pin": "b"}],
        },
        {
            "id": "n_y",
            "driver": {"component": "G_and", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        },
    ],
}

# Program: write a=1 to port 64, write b=1 to port 65, read y from port 66,
# store it in BL, then HLT.
AND_PROGRAM = "MOV AL, 1\nOUT 64, AL\nMOV AL, 1\nOUT 65, AL\nMOV AL, 0\nIN AL, 66\nMOV BL, AL\nHLT"

DOCUMENT: dict[str, Any] = {
    "cosim_schema_version": 1,
    "name": "io_demo",
    "circuit": AND_CIRCUIT,
    "program": AND_PROGRAM,
    "ports": [
        {"port": 64, "signal": "a", "direction": "input"},
        {"port": 65, "signal": "b", "direction": "input"},
        {"port": 66, "signal": "y", "direction": "output"},
    ],
    "cycles": 16,
}


def test_cosim_and_gate_cpu_drives_and_reads() -> None:
    """CPU writes a=1, b=1 via OUT; IN reads y=1 back through the AND circuit."""
    report = run_cosim(DOCUMENT)
    assert report.verdict == "HALTED"
    assert report.port_writes_total == 2
    assert report.final_circuit_outputs == {"y": "1"}
    assert report.final_registers["AX"] == 1
    # the write of b landed at the settle AFTER the OUT (one-cycle latency):
    # the IN (cycle 4) reads y as settled with a=1,b=1 -> 1
    in_cycles = [c for c in report.cycles if any("IN" in (c.instruction or "") for _ in [0])]
    assert len(in_cycles) >= 1


def test_one_cycle_port_latency_is_observable() -> None:
    """OUT a=1 at cycle k: the circuit output y is still 0 at cycle k's record
    (settled with pre-write inputs) and 1 at cycle k+1's record."""
    report = run_cosim(DOCUMENT)
    cycles = report.cycles
    # cycle 1 = "OUT 64, AL": settle used pre-write inputs (X, X -> y=X)
    assert cycles[1].circuit_outputs == {"y": "X"}
    # cycle 4 = settled with a=1, b=1 -> y=1 (b applied at cycle 4's settle)
    assert cycles[4].circuit_outputs == {"y": "1"}


def test_cosim_is_deterministic() -> None:
    a = cosim_report_to_dict(run_cosim(DOCUMENT))
    b = cosim_report_to_dict(run_cosim(DOCUMENT))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_cosim_report_serialization_shape() -> None:
    payload = cosim_report_to_dict(run_cosim(DOCUMENT))
    assert set(payload) == {
        "schema_version",
        "engine_version",
        "input_hash",
        "executed",
        "port_writes_total",
        "trace",
        "final_registers",
        "final_circuit_outputs",
        "verdict",
        "scope",
        "assumptions",
        "reason",
    }
    assert payload["engine_version"] == "0.8.0"
    assert "one-cycle port latency" in " ".join(payload["assumptions"])


def test_unmapped_output_port_reads_0xff() -> None:
    """A program INs from an unmapped port — reads 0xFF (documented)."""
    doc = json.loads(json.dumps(DOCUMENT))
    doc["program"] = "IN AL, 200\nHLT"
    report = run_cosim(doc)
    assert report.verdict == "HALTED"
    assert report.final_registers["AX"] == 255


def test_unwritten_inputs_are_x() -> None:
    """No port writes: all inputs stay X -> AND output X (four-valued honesty)."""
    doc = json.loads(json.dumps(DOCUMENT))
    doc["program"] = "IN AL, 66\nHLT"
    report = run_cosim(doc)
    assert report.final_circuit_outputs == {"y": "X"}
    assert report.final_registers["AX"] == 255  # X byte-view reads as 0xFF


def test_bounded_run_when_no_hlt() -> None:
    doc = json.loads(json.dumps(DOCUMENT))
    doc["program"] = "top:\nJMP top"
    doc["cycles"] = 5
    report = run_cosim(doc)
    assert report.verdict == "BOUNDED"
    assert report.executed == 5
    assert report.scope == "BOUNDED(5 cycles)"


def test_cycles_bound_enforced() -> None:
    doc = json.loads(json.dumps(DOCUMENT))
    doc["cycles"] = 4097
    with pytest.raises(SchemaError) as excinfo:
        run_cosim(doc)
    assert excinfo.value.code == "COSIM_SCHEMA_ERROR"


def test_signal_wiring_validated() -> None:
    doc = json.loads(json.dumps(DOCUMENT))
    doc["ports"][0]["signal"] = "ghost"
    with pytest.raises(SchemaError) as excinfo:
        run_cosim(doc)
    assert excinfo.value.code == "COSIM_SCHEMA_ERROR"
    assert "primary input" in str(excinfo.value)


def test_duplicate_port_rejected() -> None:
    doc = json.loads(json.dumps(DOCUMENT))
    doc["ports"].append({"port": 64, "signal": "b", "direction": "input"})
    with pytest.raises(SchemaError) as excinfo:
        run_cosim(doc)
    assert excinfo.value.code == "COSIM_SCHEMA_ERROR"


def test_invalid_circuit_rejected() -> None:
    doc = json.loads(json.dumps(DOCUMENT))
    doc["circuit"]["nets"] = []
    with pytest.raises(SchemaError) as excinfo:
        run_cosim(doc)
    assert excinfo.value.code == "COSIM_SCHEMA_ERROR"


def test_x_input_excluded_from_equivalence() -> None:
    """Inputs start X; a settled X output byte-views as 0xFF via IN."""
    doc = json.loads(json.dumps(DOCUMENT))
    doc["program"] = "MOV AL, 255\nOUT 64, AL\nIN AL, 66\nHLT"
    report = run_cosim(doc)
    # bit-0 of 255 drives a=1; b is still X -> y = AND(1, X) = X -> IN reads 0xFF
    assert report.final_registers["AX"] == 255

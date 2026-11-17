"""SIGNATURE ACCEPTANCE TEST — Phase 5 exit criterion.

Master prompt requirement: "Objective improves without violating properties."
A deliberately wasteful half adder is optimized; the objective (gate count)
improves; the truth table is preserved EXHAUSTIVELY; every provided property
stays PASS; the improvement is independently re-verified through the engine.
"""

from __future__ import annotations

from logic_engine import parse_circuit
from logic_engine.truth_table import truth_table
from optimize_engine import optimize
from verify_engine import verify_combinational_invariant

WASTEFUL_HALF_ADDER = {
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

MUTUAL_EXCLUSION = {
    "property_schema_version": 1,
    "id": "P-ha",
    "kind": "combinational_invariant",
    "expression": "!(sum & carry_out)",
}


def test_phase5_signature_objective_improves_without_violation() -> None:
    report = optimize(WASTEFUL_HALF_ADDER, [MUTUAL_EXCLUSION])
    assert report.verdict == "OPTIMIZED"
    assert report.final_model is not None

    # objective: gate count strictly improves
    assert report.metrics_after["gate_count"] < report.metrics_before["gate_count"]
    assert report.metrics_after["logic_depth"] <= report.metrics_before["logic_depth"]

    # behavior preserved: EXHAUSTIVE truth-table equality against the original
    nominal_rows = truth_table(parse_circuit(WASTEFUL_HALF_ADDER)).rows
    optimized_rows = truth_table(parse_circuit(report.final_model)).rows
    assert nominal_rows == optimized_rows

    # every applied transformation carries per-step equivalence evidence
    for transformation in report.transformations:
        assert transformation.equivalence["equal"] is True

    # property suite: independently re-verified on the optimized model
    verdict = verify_combinational_invariant(report.final_model, MUTUAL_EXCLUSION)
    assert verdict.verdict == "PASS"


def test_phase5_signature_minimal_circuit_not_falsely_claimed() -> None:
    """An already-minimal half adder reports NO_CHANGE_APPLICABLE — no fabricated
    'optimization' when nothing is applicable."""
    minimal = {
        "schema_version": 1,
        "name": "minimal_half_adder",
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
    report = optimize(minimal, [MUTUAL_EXCLUSION])
    assert report.verdict == "NO_CHANGE_APPLICABLE"
    assert report.final_model is None
    assert report.metrics_after == report.metrics_before

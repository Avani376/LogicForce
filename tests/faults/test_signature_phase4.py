"""SIGNATURE ACCEPTANCE TEST — Phase 4 exit criterion.

Master prompt requirement: "Seeded fault detected and repair re-verifies."
Full pipeline, all through the deterministic engines:
  1. Seed a fault (double-green redirect) into the healthy traffic controller.
  2. The property suite DETECTS it (nominal PASS + faulty FAIL, with counterexample).
  3. Repair search proposes candidates; every candidate is re-verified.
  4. The repaired model PASSES the suite again and its behavior matches nominal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fault_engine import run_fault_experiment
from fault_engine import apply_fault
from repair_engine import search_repairs
from sequential_engine import fsm_simulate, parse_fsm
from verify_engine import verify_fsm_invariant

FSM_FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"
)

SAFETY = {
    "property_schema_version": 1,
    "id": "SIG-4",
    "kind": "fsm_invariant",
    "statement": "Two conflicting traffic directions must never be green simultaneously",
    "expression": "!(north_green & east_green)",
}

SEEDED_FAULT = {
    "fault_schema_version": 1,
    "id": "SIG-F1",
    "operator": "transition_redirect",
    "target": {"transition_index": 1},
    "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def nominal_controller() -> dict[str, Any]:
    return load(FSM_FIXTURE)["fsm"]


def test_phase4_signature_full_pipeline() -> None:
    # 1. seed the fault
    faulty = apply_fault("fsm", nominal_controller(), SEEDED_FAULT)
    assert faulty["transitions"][1]["to"] == "east_green"

    # 2. the experiment DETECTS the fault via the safety property
    experiment = run_fault_experiment("fsm", nominal_controller(), SEEDED_FAULT, [SAFETY])
    assert experiment.detected is True
    assert experiment.checks[0].counterexample is not None

    # 3. repair search finds candidates and re-verifies each one
    repair = search_repairs("fsm", nominal_controller(), faulty, [SAFETY])
    assert repair.candidates_considered >= 1
    assert repair.re_verified is True
    assert repair.repaired_model is not None

    # 4. the repaired model PASSES the suite again — independently verified
    verdict = verify_fsm_invariant(repair.repaired_model, SAFETY)
    assert verdict.verdict == "PASS"

    # 5. repaired behavior matches nominal on a demanding input sequence
    inputs = [
        {"ped_button": "0"},
        {"ped_button": "1"},
        {"ped_button": "0"},
        {"ped_button": "1"},
        {"ped_button": "0"},
        {"ped_button": "0"},
    ]
    repaired_trace = fsm_simulate(parse_fsm(repair.repaired_model), inputs)
    nominal_trace = fsm_simulate(parse_fsm(nominal_controller()), inputs)
    assert [row.state for row in repaired_trace.cycles] == [
        row.state for row in nominal_trace.cycles
    ]
    for repaired_row, nominal_row in zip(
        repaired_trace.cycles, nominal_trace.cycles, strict=True
    ):
        # safety observation on both traces: never two greens
        assert not (
            repaired_row.outputs.get("north_green") == "1"
            and repaired_row.outputs.get("east_green") == "1"
        )
        assert repaired_row.outputs == nominal_row.outputs


def test_phase4_signature_undetected_fault_is_reported_honestly() -> None:
    """A fault the suite cannot observe (transition removal changing only timing)
    is reported detected: false — the platform never overclaims detection."""
    hold_fault = {
        "fault_schema_version": 1,
        "id": "SIG-F2",
        "operator": "transition_remove",
        "target": {"transition_index": 1},
    }
    experiment = run_fault_experiment("fsm", nominal_controller(), hold_fault, [SAFETY])
    assert experiment.detected is False
    assert experiment.behavior["first_divergence"] is not None  # behavior DID change

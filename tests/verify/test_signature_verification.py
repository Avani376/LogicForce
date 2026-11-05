"""SIGNATURE ACCEPTANCE TEST — Phase 3 exit criterion.

Master prompt requirement: "Faulty traffic FSM yields a reproducible counterexample."
This file is the automated form of that demo: the healthy traffic-light controller
verifies PASS; a deliberately faulty controller FAILS; the counterexample replays
in the deterministic FSM simulator and reproduces the violation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sequential_engine import fsm_simulate, parse_fsm
from verify_engine import verification_report_to_dict, verify_fsm_invariant

FSM_FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"
)

SAFETY_PROPERTY = {
    "property_schema_version": 1,
    "id": "SIG-1",
    "kind": "fsm_invariant",
    "statement": "Two conflicting traffic directions must never be green simultaneously",
    "expression": "!(north_green & east_green)",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def healthy_controller() -> dict[str, Any]:
    return load(FSM_FIXTURE)["fsm"]


def faulty_controller() -> dict[str, Any]:
    """Deliberate fault: the crossing request from north_green jumps straight to
    east_green while north_green is still driven — a classic double-green wiring
    fault. The transition REPLACES the healthy one (no ambiguity), modeling a
    broken output decode."""
    doc = healthy_controller()
    doc["name"] = "traffic_light_faulty"
    doc["transitions"][1] = {
        "from": "north_green",
        "when": {"ped_button": "1"},
        "to": "east_green",
        "outputs": {"north_green": "1", "east_green": "1"},
    }
    return doc


def test_signature_step1_healthy_fsm_passes_exhaustively() -> None:
    report = verify_fsm_invariant(healthy_controller(), SAFETY_PROPERTY)
    assert report.verdict == "PASS"
    assert report.scope == "EXHAUSTIVE(8 firings over 4 of 4 states)"
    assert report.counterexample is None


def test_signature_step2_faulty_fsm_fails() -> None:
    report = verify_fsm_invariant(faulty_controller(), SAFETY_PROPERTY)
    assert report.verdict == "FAIL"
    counterexample = report.counterexample
    assert counterexample is not None
    assert counterexample["violating_state"] == "east_green"
    assert counterexample["outputs"]["north_green"] == "1"
    assert counterexample["outputs"]["east_green"] == "1"


def test_signature_step3_counterexample_is_replayable() -> None:
    """Replay guarantee: simulating the counterexample's input sequence against the
    faulty FSM reproduces the violating state and its outputs — deterministically."""
    faulty = parse_fsm(faulty_controller())
    report = verify_fsm_invariant(faulty_controller(), SAFETY_PROPERTY)
    counterexample = report.counterexample
    assert counterexample is not None
    sequence = counterexample["inputs_sequence"]
    replay = fsm_simulate(faulty, sequence)
    # firing semantics: the last replay row records the violating firing's outputs,
    # and the edge commits the violating state
    assert replay.final_state == counterexample["violating_state"]
    assert replay.cycles[-1].outputs == counterexample["outputs"]


def test_signature_step4_reports_carry_scope_labels() -> None:
    for doc in (healthy_controller(), faulty_controller()):
        payload = verification_report_to_dict(verify_fsm_invariant(doc, SAFETY_PROPERTY))
        assert payload["scope"].startswith("EXHAUSTIVE(")
        assert payload["verdict"] in ("PASS", "FAIL")
        assert payload["engine_version"] == "0.3.0"

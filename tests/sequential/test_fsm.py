"""FSM model tests: parsing, ambiguity, matching honesty, reachability, golden."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from logic_engine import SchemaError
from logic_engine.hashing import canonical_json
from sequential_engine import fsm_reachable, fsm_result_to_dict, fsm_simulate, parse_fsm

FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"
)


def traffic_light_doc() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["fsm"]


def test_valid_fsm_parses() -> None:
    fsm = parse_fsm(traffic_light_doc())
    assert fsm.initial == "north_green"
    assert len(fsm.transitions) == 6
    assert fsm.inputs == ("ped_button",)


def test_unknown_state_in_transition_rejected() -> None:
    doc = traffic_light_doc()
    doc["transitions"][0]["to"] = "atlantis"
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "FSM_SCHEMA_ERROR"


def test_unknown_input_in_when_rejected() -> None:
    doc = traffic_light_doc()
    doc["transitions"][0]["when"] = {"mars_weather": "0"}
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "FSM_SCHEMA_ERROR"


def test_non_binary_when_value_rejected() -> None:
    doc = traffic_light_doc()
    doc["transitions"][0]["when"] = {"ped_button": "X"}
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "FSM_SCHEMA_ERROR"


def test_initial_must_be_declared() -> None:
    doc = traffic_light_doc()
    doc["initial"] = "nowhere"
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "FSM_SCHEMA_ERROR"


def test_ambiguous_transitions_rejected_at_load() -> None:
    doc = traffic_light_doc()
    doc["transitions"].append(
        {"from": "north_green", "when": {"ped_button": "0"}, "to": "east_green", "outputs": {}}
    )
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "AMBIGUOUS_TRANSITION"


def test_partial_when_overlap_is_ambiguous_too() -> None:
    """{} matches everything; adding {} and {x:0} from one state is ambiguous."""
    doc = traffic_light_doc()
    doc["transitions"].append(
        {"from": "north_green", "when": {}, "to": "east_yellow", "outputs": {}}
    )
    with pytest.raises(SchemaError) as excinfo:
        parse_fsm(doc)
    assert excinfo.value.code == "AMBIGUOUS_TRANSITION"


def test_unknown_input_in_sequence_rejected() -> None:
    fsm = parse_fsm(traffic_light_doc())
    with pytest.raises(SchemaError) as excinfo:
        fsm_simulate(fsm, [{"teleport": "1"}])
    assert excinfo.value.code == "FSM_INPUT_ERROR"


def test_non_binary_sequence_value_rejected() -> None:
    fsm = parse_fsm(traffic_light_doc())
    with pytest.raises(SchemaError) as excinfo:
        fsm_simulate(fsm, [{"ped_button": "X"}])
    assert excinfo.value.code == "FSM_INPUT_ERROR"


def test_unmatched_input_holds_state_and_is_flagged() -> None:
    """Remove the north_green hold transition: ped=0 no longer matches -> hold."""
    doc = traffic_light_doc()
    del doc["transitions"][0]
    fsm = parse_fsm(doc)
    result = fsm_simulate(fsm, [{"ped_button": "0"}])
    assert result.cycles[0].state == "north_green"
    assert result.cycles[0].matched is False
    assert result.unmatched_count == 1


def test_golden_traffic_light_trace() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fsm = parse_fsm(fixture["fsm"])
    result = fsm_simulate(fsm, fixture["input_sequence"])

    assert result.scope == fixture["expected"]["scope"]
    assert result.final_state == fixture["expected"]["final_state"]
    actual = [
        {"cycle": row.cycle, "inputs": row.inputs, "state": row.state, "outputs": row.outputs}
        for row in result.cycles
    ]
    assert actual == fixture["expected"]["cycles"]
    # the safety observation over THIS trace: never two greens
    for row in result.cycles:
        assert not (row.outputs.get("north_green") == "1" and row.outputs.get("east_green") == "1")


def test_golden_reachability_is_exhaustive_over_model() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fsm = parse_fsm(fixture["fsm"])
    reachable, scope = fsm_reachable(fsm)
    assert list(reachable) == fixture["expected"]["reachable_states"]
    assert scope == fixture["expected"]["reachable_scope"]


def test_result_serialization_shape() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fsm = parse_fsm(fixture["fsm"])
    payload = fsm_result_to_dict(fsm_simulate(fsm, fixture["input_sequence"]))
    assert payload["scope"] == fixture["expected"]["scope"]
    assert len(payload["input_hash"]) == 64
    assert set(payload["cycles"][0]) == {"cycle", "inputs", "state", "outputs", "matched"}


def test_determinism_100_replays() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fsm = parse_fsm(fixture["fsm"])
    digests = {
        canonical_json(fsm_result_to_dict(fsm_simulate(fsm, fixture["input_sequence"])))
        for _ in range(100)
    }
    assert len(digests) == 1

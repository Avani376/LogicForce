"""Generate the traffic-light FSM golden fixture from its reference definition.

Provenance: expected cycle trace computed from the closed-form state machine below
(the specification of the controller), never by running the engine.

Run: .venv/Scripts/python scripts/gen_fsm_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "fixtures_fsm"

# Reference definition: two-direction controller; the safety property (never two
# greens) is structurally guaranteed by the state set — Phase 3 verifies it.
TRANSITIONS = [
    ("north_green", {"ped_button": "0"}, "north_green", {"north_green": "1", "east_green": "0"}),
    ("north_green", {"ped_button": "1"}, "north_yellow", {"north_green": "0", "east_green": "0"}),
    ("north_yellow", {}, "east_green", {"north_green": "0", "east_green": "1"}),
    ("east_green", {"ped_button": "0"}, "east_green", {"north_green": "0", "east_green": "1"}),
    ("east_green", {"ped_button": "1"}, "east_yellow", {"north_green": "0", "east_green": "0"}),
    ("east_yellow", {}, "north_green", {"north_green": "1", "east_green": "0"}),
]

# Input sequence: hold green, request crossing, complete both cycles, request again.
INPUT_SEQUENCE = [
    {"ped_button": "0"},
    {"ped_button": "1"},
    {"ped_button": "0"},
    {"ped_button": "0"},
    {"ped_button": "0"},
    {"ped_button": "1"},
    {"ped_button": "0"},
    {"ped_button": "0"},
]


def reference_step(state: str, vector: dict[str, str]) -> tuple[str, dict[str, str]]:
    for source, when, target, outputs in TRANSITIONS:
        if source == state and all(vector.get(k) == v for k, v in when.items()):
            return target, dict(outputs)
    return state, {}  # unmatched: hold


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    fsm_doc = {
        "fsm_schema_version": 1,
        "name": "traffic_light",
        "inputs": ["ped_button"],
        "outputs": ["north_green", "east_green"],
        "states": ["north_green", "north_yellow", "east_green", "east_yellow"],
        "initial": "north_green",
        "transitions": [
            {"from": src, "when": dict(when), "to": tgt, "outputs": dict(outs)} for src, when, tgt, outs in TRANSITIONS
        ],
    }
    expected_cycles: list[dict[str, object]] = []
    state = "north_green"
    for cycle, vector in enumerate(INPUT_SEQUENCE):
        expected_cycles.append({"cycle": cycle, "inputs": dict(vector), "state": state})
        state, outputs = reference_step(state, vector)
        expected_cycles[-1]["outputs"] = outputs
    reachable = ["east_green", "east_yellow", "north_green", "north_yellow"]
    fixture = {
        "fsm": fsm_doc,
        "input_sequence": INPUT_SEQUENCE,
        "expected": {
            "cycles": expected_cycles,
            "final_state": state,
            "reachable_states": reachable,
            "scope": f"BOUNDED({len(INPUT_SEQUENCE)} cycles)",
            "reachable_scope": f"EXHAUSTIVE({len(reachable)} of 4 states)",
            "safety_no_double_green": True,
        },
    }
    path = FIXTURES_DIR / "fsm_traffic_light.json"
    path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.name}: {len(INPUT_SEQUENCE)} cycles, final={state}")


if __name__ == "__main__":
    main()

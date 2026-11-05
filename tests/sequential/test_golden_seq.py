"""Sequential golden tests: committed waveforms/events + 100x determinism replay.

Fixture provenance: expected values come from closed-form reference models in
``scripts/gen_sequential_fixtures.py`` (Johnson shift formula, mod-2^w arithmetic,
toggle relation) — never from running the engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from logic_engine.hashing import canonical_json
from sequential_engine import sequential_result_to_dict, simulate_sequential

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "golden" / "fixtures_seq"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_sequential_fixtures_exist() -> None:
    assert {path.stem for path in FIXTURE_PATHS} == {
        "seq_divide_by_2",
        "seq_johnson_counter",
        "seq_mod8_counter",
    }


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_waveforms_and_events_match_committed_expected(path: Path) -> None:
    fixture = load_fixture(path)
    result = simulate_sequential(fixture["circuit"], fixture["cycles"], fixture["inputs_per_cycle"])
    expected = fixture["expected"]

    # exact waveform comparison (the authoritative check — keys cover both the
    # observed state signals and the primary outputs)
    for key, values in expected["waveforms"].items():
        assert list(result.waveforms[key]) == values, f"{path.name}: waveform {key}"

    # exact event comparison
    actual_events = [
        {
            "cycle": e.cycle,
            "component": e.component,
            "pin": e.pin,
            "old": e.old,
            "new": e.new,
            "cause": e.cause,
        }
        for e in result.events
    ]
    assert actual_events == expected["events"], path.name

    # final state
    assert result.final_state == expected["final_state"], path.name


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_sequential_determinism_100_replays(path: Path) -> None:
    fixture = load_fixture(path)
    digests = set()
    for _ in range(100):
        result = simulate_sequential(
            fixture["circuit"], fixture["cycles"], fixture["inputs_per_cycle"]
        )
        digests.add(canonical_json(sequential_result_to_dict(result)))
    assert len(digests) == 1, f"{path.name}: sequential simulation is not deterministic"


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_sequential_scope_label(path: Path) -> None:
    fixture = load_fixture(path)
    result = simulate_sequential(fixture["circuit"], fixture["cycles"], fixture["inputs_per_cycle"])
    assert result.scope == f"BOUNDED({fixture['cycles']} cycles)"
    assert len(result.cycles) == fixture["cycles"]

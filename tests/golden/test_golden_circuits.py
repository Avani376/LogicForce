"""Golden tests: committed reference circuits must reproduce committed truth tables.

Fixture provenance: expected tables were generated from closed-form reference
definitions (``scripts/gen_golden_fixtures.py``), never by running the engine — the
engine cannot rewrite its own oracle.

The determinism contract (byte-identical results) is enforced here by replaying each
fixture 100 times and comparing serialized bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from logic_engine import (
    parse_circuit,
    simulate,
    simulation_result_to_dict,
    truth_table,
    validate,
)
from logic_engine.hashing import canonical_json

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixtures_exist() -> None:
    names = {path.stem for path in FIXTURE_PATHS}
    assert names == {
        "half_adder",
        "full_adder",
        "mux2to1",
        "mux4to1",
        "decoder2to4",
    }


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_fixture_is_valid_and_matches_scope(path: Path) -> None:
    fixture = load_fixture(path)
    graph = parse_circuit(fixture["circuit"])
    report = validate(graph)
    assert report.ok, [e.code for e in report.errors]

    expected = fixture["expected"]
    result = truth_table(graph)
    n = len(expected["input_names"])
    assert result.scope == f"EXHAUSTIVE({2**n})"
    assert result.input_names == tuple(expected["input_names"])
    assert result.output_names == tuple(expected["output_names"])


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_truth_table_matches_committed_expected(path: Path) -> None:
    fixture = load_fixture(path)
    graph = parse_circuit(fixture["circuit"])
    result = truth_table(graph)
    actual_rows = [
        {"inputs": dict(row.inputs), "outputs": dict(row.outputs)} for row in result.rows
    ]
    assert actual_rows == fixture["expected"]["rows"], path.name


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_determinism_100_replays_byte_identical(path: Path) -> None:
    """Engine rule 2: same circuit + inputs + version => byte-identical output."""
    fixture = load_fixture(path)
    graph = parse_circuit(fixture["circuit"])
    first_row = fixture["expected"]["rows"][0]
    vector = {name: value for name, value in first_row["inputs"].items()}

    digests = set()
    for _ in range(100):
        result = simulate(graph, vector)
        payload = simulation_result_to_dict(result)
        digests.add(canonical_json(payload))
    assert len(digests) == 1, f"{path.name}: simulation is not deterministic"


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_single_vector_matches_truth_table_row(path: Path) -> None:
    """The simulate path and the truth-table path must agree on shared vectors."""
    fixture = load_fixture(path)
    graph = parse_circuit(fixture["circuit"])
    for row in fixture["expected"]["rows"]:
        result = simulate(graph, row["inputs"])
        assert result.outputs == row["outputs"], (path.name, row["inputs"])

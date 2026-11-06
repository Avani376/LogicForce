"""Phase C4 golden tests: combinational library circuits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from logic_engine import parse_circuit, truth_table
from logic_engine.validation import validate

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "golden" / "fixtures_comb"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_golden_comb_truth_table(path: Path) -> None:
    fixture = load(path)
    graph = parse_circuit(fixture["circuit"])
    report = validate(graph)
    assert report.ok, f"{path.name}: {[(e.code, e.message) for e in report.errors]}"
    result = truth_table(graph)
    expected_rows = fixture["expected"]["rows"]
    for i, row in enumerate(result.rows):
        expected = expected_rows[i]
        assert row.inputs == expected["inputs"], f"{path.name} row {i} inputs"
        assert row.outputs == expected["outputs"], f"{path.name} row {i} outputs"


def test_fixtures_exist() -> None:
    names = {p.stem for p in FIXTURE_PATHS}
    assert names == {"comb_full_adder", "comb_binary_to_gray", "comb_parity_gen", "comb_mux_4to1"}

"""Integration tests for sequential and FSM endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

SEQ_FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_seq" / "seq_divide_by_2.json"
)
FSM_FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_health_reports_both_engine_versions() -> None:
    body = client.get("/api/health").json()
    assert body["engine_version"] == "0.1.0"
    assert body["sequential_engine_version"] == "0.2.0"


def test_sequential_simulate_returns_contract_shape() -> None:
    fixture = load(SEQ_FIXTURE)
    response = client.post(
        "/api/sequential/simulate",
        json={
            "circuit": fixture["circuit"],
            "cycles": fixture["cycles"],
            "inputs_per_cycle": fixture["inputs_per_cycle"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "BOUNDED(6 cycles)"
    assert body["waveforms"]["FF1.q"] == ["0", "1", "0", "1", "0", "1"]
    assert body["final_state"] == {"FF1.q": "0"}
    assert len(body["input_hash"]) == 64
    assert body["cycles"][0]["state"] == {"FF1.q": "0"}


def test_sequential_invalid_circuit_is_400() -> None:
    fixture = load(SEQ_FIXTURE)
    doc = fixture["circuit"]
    doc["nets"] = [n for n in doc["nets"] if n["id"] != "n_d"]  # FF1.d dangling
    response = client.post(
        "/api/sequential/simulate", json={"circuit": doc, "cycles": 2, "inputs_per_cycle": []}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert any(e["code"] == "DANGLING_INPUT_PIN" for e in detail["errors"])


def test_sequential_invalid_input_value_is_400_not_500() -> None:
    """Audit regression: InvalidInputValueError must map to a typed 400, never 500."""
    doc = {
        "schema_version": 2,
        "components": [
            {"id": "C0", "type": "CONST0"},
            {"id": "IN_d", "type": "INPUT", "params": {"name": "d"}},
            {"id": "FF1", "type": "DFF"},
            {"id": "OUT_q", "type": "OUTPUT", "params": {"name": "q"}},
        ],
        "nets": [
            {
                "id": "n1",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "pre"}],
            },
            {
                "id": "n2",
                "driver": {"component": "C0", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "clr"}],
            },
            {
                "id": "n3",
                "driver": {"component": "IN_d", "pin": "out"},
                "sinks": [{"component": "FF1", "pin": "d"}],
            },
            {
                "id": "n4",
                "driver": {"component": "FF1", "pin": "q"},
                "sinks": [{"component": "OUT_q", "pin": "in"}],
            },
        ],
    }
    response = client.post(
        "/api/sequential/simulate",
        json={"circuit": doc, "cycles": 2, "inputs_per_cycle": [{"d": "2"}]},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_INPUT_VALUE"
    assert detail["input"] == "d"


def test_sequential_bool_cycles_is_a_shape_error() -> None:
    """cycles=true is a bool, not an integer — pydantic strict mode rejects the
    shape (HTTP 422); the engine's own bool guard remains defense in depth."""
    fixture = load(SEQ_FIXTURE)
    response = client.post(
        "/api/sequential/simulate",
        json={"circuit": fixture["circuit"], "cycles": True, "inputs_per_cycle": []},
    )
    assert response.status_code == 422


def test_sequential_cycles_bound_is_400() -> None:
    fixture = load(SEQ_FIXTURE)
    response = client.post(
        "/api/sequential/simulate",
        json={"circuit": fixture["circuit"], "cycles": 257, "inputs_per_cycle": []},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CYCLES_LIMIT_EXCEEDED"


def test_sequential_schema_v1_rejected() -> None:
    response = client.post(
        "/api/sequential/simulate",
        json={"circuit": {"schema_version": 1, "components": [], "nets": []}, "cycles": 1},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNSUPPORTED_SCHEMA_VERSION"


def test_fsm_simulate_matches_golden() -> None:
    fixture = load(FSM_FIXTURE)
    response = client.post(
        "/api/fsm/simulate",
        json={"fsm": fixture["fsm"], "input_sequence": fixture["input_sequence"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_state"] == fixture["expected"]["final_state"]
    assert body["scope"] == fixture["expected"]["scope"]
    assert [row["state"] for row in body["cycles"]] == [
        row["state"] for row in fixture["expected"]["cycles"]
    ]


def test_fsm_ambiguity_is_400() -> None:
    fixture = load(FSM_FIXTURE)
    doc = fixture["fsm"]
    doc["transitions"].append(
        {"from": "north_green", "when": {"ped_button": "0"}, "to": "east_green", "outputs": {}}
    )
    response = client.post("/api/fsm/simulate", json={"fsm": doc, "input_sequence": []})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "AMBIGUOUS_TRANSITION"


def test_fsm_reachable_reports_exhaustive_scope() -> None:
    fixture = load(FSM_FIXTURE)
    response = client.post("/api/fsm/reachable", json={"fsm": fixture["fsm"]})
    assert response.status_code == 200
    body = response.json()
    assert body["reachable_states"] == fixture["expected"]["reachable_states"]
    assert body["scope"] == fixture["expected"]["reachable_scope"]
    assert body["declared_states"] == fixture["fsm"]["states"]


def test_fsm_malformed_is_400_typed() -> None:
    response = client.post("/api/fsm/reachable", json={"fsm": {"fsm_schema_version": 9}})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "FSM_SCHEMA_ERROR"

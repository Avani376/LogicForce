"""Integration tests for fault and repair endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

FSM_FIXTURE = Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def traffic_light() -> dict[str, Any]:
    return load(FSM_FIXTURE)["fsm"]


def safety_property() -> dict[str, Any]:
    return {
        "property_schema_version": 1,
        "id": "P1",
        "kind": "fsm_invariant",
        "expression": "!(north_green & east_green)",
    }


DOUBLE_GREEN_FAULT = {
    "fault_schema_version": 1,
    "id": "F-dg",
    "operator": "transition_redirect",
    "target": {"transition_index": 1},
    "params": {"to": "east_green", "set_outputs": {"north_green": "1", "east_green": "1"}},
}


def test_apply_fault_returns_faulty_model() -> None:
    response = client.post(
        "/api/faults/apply",
        json={"model_kind": "fsm", "model": traffic_light(), "fault": DOUBLE_GREEN_FAULT},
    )
    assert response.status_code == 200
    faulty = response.json()["faulty_model"]
    assert faulty["transitions"][1]["to"] == "east_green"
    # the nominal document is untouched server-side: re-fetch semantics via simulate
    nominal_check = client.post(
        "/api/fsm/simulate",
        json={"fsm": traffic_light(), "input_sequence": [{"ped_button": "1"}]},
    )
    assert nominal_check.json()["cycles"][0]["outputs"] == {"north_green": "0", "east_green": "0"}


def test_fault_experiment_detects_over_http() -> None:
    response = client.post(
        "/api/fault-experiments",
        json={
            "model_kind": "fsm",
            "model": traffic_light(),
            "fault": DOUBLE_GREEN_FAULT,
            "properties": [safety_property()],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["detected"] is True
    assert body["checks"][0]["faulty_verdict"] == "FAIL"
    assert body["behavior"]["first_divergence"] is not None


def test_fault_experiment_bad_operator_is_400() -> None:
    response = client.post(
        "/api/fault-experiments",
        json={
            "model_kind": "fsm",
            "model": traffic_light(),
            "fault": {"fault_schema_version": 1, "id": "F", "operator": "teleport", "target": {}},
            "properties": [],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "FAULT_SCHEMA_ERROR"


def test_repair_search_reverifies_over_http() -> None:
    faulty_response = client.post(
        "/api/faults/apply",
        json={"model_kind": "fsm", "model": traffic_light(), "fault": DOUBLE_GREEN_FAULT},
    )
    faulty = faulty_response.json()["faulty_model"]
    response = client.post(
        "/api/repair-search",
        json={
            "model_kind": "fsm",
            "nominal": traffic_light(),
            "faulty": faulty,
            "properties": [safety_property()],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["re_verified"] is True
    assert body["candidates"][0]["valid"] is True
    assert body["repaired_model"] is not None
    # independently re-verify the repaired model through the verify endpoint
    verification = client.post(
        "/api/verify",
        json={
            "kind": "fsm_invariant",
            "model": body["repaired_model"],
            "property": safety_property(),
        },
    )
    assert verification.json()["verdict"] == "PASS"


def test_repair_search_max_candidates_out_of_range_is_400() -> None:
    faulty = client.post(
        "/api/faults/apply",
        json={"model_kind": "fsm", "model": traffic_light(), "fault": DOUBLE_GREEN_FAULT},
    ).json()["faulty_model"]
    response = client.post(
        "/api/repair-search",
        json={
            "model_kind": "fsm",
            "nominal": traffic_light(),
            "faulty": faulty,
            "properties": [safety_property()],
            "max_candidates": 99,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "FAULT_SCHEMA_ERROR"


def test_repair_search_shape_error_is_422() -> None:
    response = client.post("/api/repair-search", json={"model_kind": "fsm"})
    assert response.status_code == 422

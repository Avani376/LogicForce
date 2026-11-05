"""Integration tests for POST /api/verify (verification engine over HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

FSM_FIXTURE = (
    Path(__file__).resolve().parent.parent / "golden" / "fixtures_fsm" / "fsm_traffic_light.json"
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def traffic_light() -> dict[str, Any]:
    return load(FSM_FIXTURE)["fsm"]


def faulty_controller() -> dict[str, Any]:
    doc = traffic_light()
    doc["name"] = "traffic_light_faulty"
    doc["transitions"][1] = {
        "from": "north_green",
        "when": {"ped_button": "1"},
        "to": "east_green",
        "outputs": {"north_green": "1", "east_green": "1"},
    }
    return doc


def safety_property() -> dict[str, Any]:
    return {
        "property_schema_version": 1,
        "id": "SIG-1",
        "kind": "fsm_invariant",
        "statement": "Two conflicting directions must never be green simultaneously",
        "expression": "!(north_green & east_green)",
    }


def test_verify_fsm_pass_over_http() -> None:
    response = client.post(
        "/api/verify",
        json={"kind": "fsm_invariant", "model": traffic_light(), "property": safety_property()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "PASS"
    assert body["scope"] == "EXHAUSTIVE(8 firings over 4 of 4 states)"
    assert body["counterexample"] is None
    assert body["engine_version"] == "0.3.0"


def test_verify_fsm_fail_counterexample_over_http() -> None:
    response = client.post(
        "/api/verify",
        json={"kind": "fsm_invariant", "model": faulty_controller(), "property": safety_property()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "FAIL"
    counterexample = body["counterexample"]
    assert counterexample is not None
    assert counterexample["violating_state"] == "east_green"
    # replay the counterexample against the same faulty model over HTTP
    replay = client.post(
        "/api/fsm/simulate",
        json={"fsm": faulty_controller(), "input_sequence": counterexample["inputs_sequence"]},
    )
    assert replay.status_code == 200
    assert replay.json()["final_state"] == "east_green"
    assert replay.json()["cycles"][-1]["outputs"] == counterexample["outputs"]


def test_verify_combinational_pass_over_http() -> None:
    half_adder = {
        "schema_version": 1,
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
    response = client.post(
        "/api/verify",
        json={
            "kind": "combinational_invariant",
            "model": half_adder,
            "property": {
                "property_schema_version": 1,
                "id": "P-ha",
                "kind": "combinational_invariant",
                "expression": "!(sum & carry_out)",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "PASS"
    assert response.json()["scope"] == "EXHAUSTIVE(4 input vectors)"


def test_verify_invalid_circuit_is_400_validation_failed() -> None:
    bad = {
        "schema_version": 1,
        "components": [{"id": "G", "type": "AND"}],
        "nets": [],
    }
    response = client.post(
        "/api/verify",
        json={
            "kind": "combinational_invariant",
            "model": bad,
            "property": {
                "property_schema_version": 1,
                "id": "P",
                "kind": "combinational_invariant",
                "expression": "y",
            },
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert any(e["code"] == "DANGLING_INPUT_PIN" for e in detail["errors"])


def test_verify_syntax_error_is_400_typed() -> None:
    response = client.post(
        "/api/verify",
        json={
            "kind": "fsm_invariant",
            "model": traffic_light(),
            "property": {
                "property_schema_version": 1,
                "id": "P",
                "kind": "fsm_invariant",
                "expression": "a &",
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PROPERTY_SYNTAX_ERROR"


def test_verify_unknown_kind_is_400_typed() -> None:
    response = client.post(
        "/api/verify",
        json={
            "kind": "quantum_invariant",
            "model": traffic_light(),
            "property": safety_property(),
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PROPERTY_SCHEMA_ERROR"


def test_verify_body_shape_error_is_422() -> None:
    response = client.post("/api/verify", json={"kind": "fsm_invariant"})
    assert response.status_code == 422

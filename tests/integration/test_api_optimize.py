"""Integration tests for POST /api/optimize."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

WASTEFUL = {
    "schema_version": 1,
    "components": [
        {"id": "IN_a", "type": "INPUT", "params": {"name": "a"}},
        {"id": "IN_b", "type": "INPUT", "params": {"name": "b"}},
        {"id": "N1", "type": "NOT"},
        {"id": "N2", "type": "NOT"},
        {"id": "G_xor", "type": "XOR"},
        {"id": "OUT_sum", "type": "OUTPUT", "params": {"name": "sum"}},
    ],
    "nets": [
        {
            "id": "n_a",
            "driver": {"component": "IN_a", "pin": "out"},
            "sinks": [{"component": "G_xor", "pin": "a"}],
        },
        {
            "id": "n_b",
            "driver": {"component": "IN_b", "pin": "out"},
            "sinks": [{"component": "N1", "pin": "a"}],
        },
        {
            "id": "n_n1",
            "driver": {"component": "N1", "pin": "out"},
            "sinks": [{"component": "N2", "pin": "a"}],
        },
        {
            "id": "n_n2",
            "driver": {"component": "N2", "pin": "out"},
            "sinks": [{"component": "G_xor", "pin": "b"}],
        },
        {
            "id": "n_sum",
            "driver": {"component": "G_xor", "pin": "out"},
            "sinks": [{"component": "OUT_sum", "pin": "in"}],
        },
    ],
}


def test_optimize_reduces_gate_count_over_http() -> None:
    response = client.post("/api/optimize", json={"model": WASTEFUL, "properties": []})
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "OPTIMIZED"
    assert body["metrics_after"]["gate_count"] < body["metrics_before"]["gate_count"]
    assert body["final_model"] is not None
    assert all(t["equivalence"]["equal"] is True for t in body["transformations"])


def test_optimize_max_transformations_out_of_range_is_400() -> None:
    response = client.post(
        "/api/optimize", json={"model": WASTEFUL, "properties": [], "max_transformations": 99}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OPTIMIZATION_SCHEMA_ERROR"


def test_optimize_invalid_circuit_is_400() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "model": {"schema_version": 1, "components": [{"id": "G", "type": "AND"}], "nets": []},
            "properties": [],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_optimize_shape_error_is_422() -> None:
    response = client.post("/api/optimize", json={"properties": []})
    assert response.status_code == 422

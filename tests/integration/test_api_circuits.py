"""Integration tests for the FastAPI circuit endpoints (real app, TestClient)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)


def half_adder() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "half_adder",
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
                "sinks": [
                    {"component": "G_xor", "pin": "a"},
                    {"component": "G_and", "pin": "a"},
                ],
            },
            {
                "id": "n_b",
                "driver": {"component": "IN_b", "pin": "out"},
                "sinks": [
                    {"component": "G_xor", "pin": "b"},
                    {"component": "G_and", "pin": "b"},
                ],
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


def test_health_reports_versions() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "1"
    assert body["engine_version"] == "0.1.0"


def test_validate_valid_circuit_returns_ok_true() -> None:
    response = client.post("/api/circuits/validate", json={"circuit": half_adder()})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert body["warnings"] == []
    assert body["engine_version"] == "0.1.0"
    assert body["schema_version"] == 1


def test_validate_invalid_circuit_returns_report_not_error() -> None:
    doc = half_adder()
    doc["nets"] = [doc["nets"][0]]  # OUT pins left dangling
    response = client.post("/api/circuits/validate", json={"circuit": doc})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    codes = [issue["code"] for issue in body["errors"]]
    assert "DANGLING_INPUT_PIN" in codes


def test_validate_malformed_document_is_400_typed() -> None:
    response = client.post(
        "/api/circuits/validate", json={"circuit": {"schema_version": 2}}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "UNSUPPORTED_SCHEMA_VERSION"


def test_simulate_returns_outputs_trace_and_hash() -> None:
    response = client.post(
        "/api/circuits/simulate",
        json={"circuit": half_adder(), "inputs": {"a": "1", "b": "0"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outputs"] == {"sum": "1", "carry_out": "0"}
    assert body["scope"] == "SINGLE_VECTOR"
    assert body["event_count"] == len(body["trace"])
    assert len(body["input_hash"]) == 64
    assert body["trace"][0]["cause"]["type"] == "primary_input"
    assert body["trace"][0]["old"] == "X"


def test_simulate_accepts_integer_inputs() -> None:
    response = client.post(
        "/api/circuits/simulate",
        json={"circuit": half_adder(), "inputs": {"a": 1, "b": 1}},
    )
    assert response.status_code == 200
    assert response.json()["outputs"] == {"sum": "0", "carry_out": "1"}


def test_simulate_omitted_inputs_default_to_x() -> None:
    response = client.post(
        "/api/circuits/simulate", json={"circuit": half_adder(), "inputs": {}}
    )
    assert response.status_code == 200
    assert response.json()["outputs"] == {"sum": "X", "carry_out": "X"}


def test_simulate_invalid_circuit_is_400_validation_failed() -> None:
    doc = half_adder()
    doc["nets"] = [doc["nets"][0]]
    response = client.post(
        "/api/circuits/simulate", json={"circuit": doc, "inputs": {"a": "1"}}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert any(e["code"] == "DANGLING_INPUT_PIN" for e in detail["errors"])


def test_simulate_bad_input_value_is_400() -> None:
    response = client.post(
        "/api/circuits/simulate",
        json={"circuit": half_adder(), "inputs": {"a": "2", "b": "0"}},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_INPUT_VALUE"
    assert detail["input"] == "a"


def test_simulate_malformed_body_is_422() -> None:
    response = client.post("/api/circuits/simulate", json={"inputs": {}})
    assert response.status_code == 422


def test_truth_table_exhaustive() -> None:
    response = client.post("/api/circuits/truth-table", json={"circuit": half_adder()})
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "EXHAUSTIVE(4)"
    assert body["input_names"] == ["a", "b"]
    assert body["output_names"] == ["carry_out", "sum"]
    assert len(body["rows"]) == 4
    assert body["rows"][3] == {
        "inputs": {"a": "1", "b": "1"},
        "outputs": {"carry_out": "1", "sum": "0"},
    }


def test_truth_table_over_limit_is_400_not_truncated() -> None:
    import string

    components: list[dict[str, Any]] = [
        {"id": f"IN_i{i:02d}", "type": "INPUT", "params": {"name": f"i{i:02d}"}}
        for i in range(13)
    ]
    components.append({"id": "G", "type": "AND", "params": {"width": 13}})
    components.append({"id": "OUT_y", "type": "OUTPUT", "params": {"name": "y"}})
    nets = [
        {
            "id": f"n_{i:02d}",
            "driver": {"component": f"IN_i{i:02d}", "pin": "out"},
            "sinks": [{"component": "G", "pin": string.ascii_lowercase[i]}],
        }
        for i in range(13)
    ]
    nets.append(
        {
            "id": "n_y",
            "driver": {"component": "G", "pin": "out"},
            "sinks": [{"component": "OUT_y", "pin": "in"}],
        }
    )
    doc = {"schema_version": 1, "components": components, "nets": nets}
    response = client.post("/api/circuits/truth-table", json={"circuit": doc})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "TRUTH_TABLE_LIMIT_EXCEEDED"
    assert detail["input_count"] == 13
    assert detail["limit"] == 12


def test_truth_table_invalid_circuit_is_400() -> None:
    doc = half_adder()
    doc["nets"] = [doc["nets"][0]]
    response = client.post("/api/circuits/truth-table", json={"circuit": doc})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


@pytest.mark.parametrize(
    "endpoint",
    ["/api/circuits/validate", "/api/circuits/simulate", "/api/circuits/truth-table"],
)
def test_structurally_broken_circuit_is_400_typed(endpoint: str) -> None:
    """A dict-shaped body with missing required arrays reaches the engine, which
    raises INVALID_DOCUMENT (mapped to 400). A non-dict circuit would be rejected
    earlier by pydantic as a 422 shape error."""
    body: dict[str, Any] = {"circuit": {"schema_version": 1}}
    if endpoint.endswith("simulate"):
        body["inputs"] = {}
    response = client.post(endpoint, json=body)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_DOCUMENT"


def test_non_dict_circuit_body_is_422_shape_error() -> None:
    response = client.post("/api/circuits/validate", json={"circuit": "not-a-dict"})
    assert response.status_code == 422

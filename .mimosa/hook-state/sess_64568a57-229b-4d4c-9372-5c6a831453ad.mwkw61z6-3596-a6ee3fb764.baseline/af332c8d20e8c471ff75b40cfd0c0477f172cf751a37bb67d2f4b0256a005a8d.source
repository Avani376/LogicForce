"""Integration tests for POST /api/explain."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

CPU_TRACE = {
    "stop_reason": "hlt",
    "trace": [
        {
            "kind": "instruction",
            "step": 1,
            "ip": 0,
            "instruction": "MOV AL, 0x7F",
            "register_changes": {"AL": 0x7F, "IP": 1},
            "flag_changes": {},
            "memory_changes": [],
            "halted": False,
        },
        {
            "kind": "instruction",
            "step": 2,
            "ip": 1,
            "instruction": "ADD AL, 1",
            "register_changes": {"AL": 0x80, "IP": 2},
            "flag_changes": {"OF": 1, "SF": 1, "AF": 1},
            "memory_changes": [],
            "halted": False,
        },
        {
            "kind": "instruction",
            "step": 3,
            "ip": 2,
            "instruction": "HLT",
            "register_changes": {"IP": 3},
            "flag_changes": {},
            "memory_changes": [],
            "halted": True,
        },
    ],
}


def test_explain_cpu_trace_over_http() -> None:
    response = client.post("/api/explain", json={"kind": "cpu_trace", "evidence": CPU_TRACE, "question": "why OF=1?"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "cpu_trace"
    assert body["question"] == "why OF=1?"
    assert len(body["findings"]) >= 3
    assert body["disclaimer"].startswith("Generated from engine evidence")
    of_findings = [f for f in body["findings"] if "OF=1" in f["text"]]
    assert len(of_findings) >= 1
    assert any(e["step"] == 2 for e in of_findings[0]["evidence"])


def test_explain_deterministic_over_http() -> None:
    body = {"kind": "cpu_trace", "evidence": CPU_TRACE}
    a = client.post("/api/explain", json=body).json()
    b = client.post("/api/explain", json=body).json()
    assert a == b


def test_explain_unknown_kind_is_400() -> None:
    response = client.post("/api/explain", json={"kind": "tarot", "evidence": {"trace": []}})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "EXPLANATION_KIND_UNKNOWN"


def test_explain_empty_evidence_is_400() -> None:
    response = client.post("/api/explain", json={"kind": "cpu_trace", "evidence": {}})
    assert response.status_code == 400
    assert "non-empty" in response.json()["detail"]["message"]


def test_explain_shape_error_is_422() -> None:
    response = client.post("/api/explain", json={"evidence": {}})
    assert response.status_code == 422

"""Integration tests for POST /api/8086/pic (Phase C7 — 8259 PIC)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

PROGRAM = {"source": "STI\nMOV CX, 0\nwait:\nINC CX\nCMP CX, 50\nJNZ wait\nHLT\nisr:\nINC DX\nIRET"}


def test_pic_endpoint_deliveries_only() -> None:
    response = client.post(
        "/api/8086/pic",
        json={"base_vector": 8, "events": [{"at_step": 2, "op": "request", "line": 5}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "EXHAUSTIVE(1)"
    assert body["deliveries"] == [{"at_step": 2, "line": 5, "vector": 13}]
    assert body["final_registers"] == {"IRR": 0, "ISR": 32, "IMR": 0}
    assert any(e["kind"] == "ack" for e in body["pic_trace"])


def test_pic_endpoint_with_program_runs_cpu_pipeline() -> None:
    response = client.post(
        "/api/8086/pic",
        json={
            "base_vector": 8,
            "events": [{"at_step": 3, "op": "request", "line": 2}, {"at_step": 20, "op": "eoi"}],
            "program": {**PROGRAM, "interrupts": {10: "isr"}, "max_steps": 200},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deliveries"] == [{"at_step": 3, "line": 2, "vector": 10}]
    assert body["stop_reason"] == "hlt"
    fired = [r for r in body["cpu_trace"] if r["kind"] == "interrupt"]
    assert fired and fired[0]["number"] == 10 and fired[0]["source"] == "intr"
    assert body["registers"]["DX"] == 1
    assert body["registers"]["CX"] == 50


def test_pic_endpoint_masked_line_defers_delivery() -> None:
    response = client.post(
        "/api/8086/pic",
        json={
            "base_vector": 16,
            "events": [
                {"at_step": 1, "op": "mask", "line": 3, "masked": True},
                {"at_step": 2, "op": "request", "line": 3},
                {"at_step": 5, "op": "mask", "line": 3, "masked": False},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deliveries"] == [{"at_step": 5, "line": 3, "vector": 19}]
    assert body["scope"] == "EXHAUSTIVE(3)"


def test_pic_endpoint_bad_vector_base_is_400() -> None:
    response = client.post("/api/8086/pic", json={"base_vector": 12, "events": []})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "PIC_ERROR"
    assert detail["category"] == "BAD_VECTOR_BASE"


def test_pic_endpoint_bad_event_op_is_400() -> None:
    response = client.post(
        "/api/8086/pic", json={"base_vector": 8, "events": [{"at_step": 1, "op": "poll", "line": 0}]}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["category"] == "BAD_EVENT"


def test_pic_endpoint_program_syntax_error_is_400() -> None:
    response = client.post(
        "/api/8086/pic",
        json={"base_vector": 8, "events": [], "program": {"source": "FLY AX", "interrupts": {}}},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ASM_ERROR"


def test_pic_endpoint_determinism() -> None:
    payload = {
        "base_vector": 8,
        "events": [
            {"at_step": 2, "op": "request", "line": 5},
            {"at_step": 2, "op": "request", "line": 1},
            {"at_step": 10, "op": "eoi"},
        ],
    }
    a = client.post("/api/8086/pic", json=payload).json()
    b = client.post("/api/8086/pic", json=payload).json()
    assert a == b
    assert [d["vector"] for d in a["deliveries"]] == [13, 9]

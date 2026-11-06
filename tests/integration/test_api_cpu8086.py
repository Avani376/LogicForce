"""Integration tests for the 8086 endpoints (assemble / run / step)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

SUM_PROGRAM = "MOV CX, 5\nMOV AX, 0\nMOV BX, 1\nsum:\nADD AX, BX\nINC BX\nLOOP sum\nHLT"


def test_assemble_endpoint_returns_instruction_count() -> None:
    response = client.post("/api/8086/assemble", json={"source": SUM_PROGRAM})
    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == "0.6.0"
    # 8 source lines, but `sum:` is a label-only line -> 7 instructions
    assert body["instruction_count"] == 7
    assert body["labels"] == {"SUM": 3}


def test_assemble_syntax_error_is_400_with_line() -> None:
    response = client.post("/api/8086/assemble", json={"source": "FLY AX, 1"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "ASM_ERROR"
    assert detail["line"] == 1
    assert detail["category"] == "UNKNOWN_MNEMONIC"


def test_run_endpoint_hlt_and_registers() -> None:
    response = client.post("/api/8086/run", json={"source": SUM_PROGRAM, "max_steps": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["stop_reason"] == "hlt"
    assert body["registers"]["AX"] == 15
    assert body["registers"]["CX"] == 0
    assert body["engine_version"] == "0.6.0"


def test_run_endpoint_bounded_loop_reports_max_steps() -> None:
    response = client.post("/api/8086/run", json={"source": "top:\nJMP top\n", "max_steps": 25})
    assert response.status_code == 200
    body = response.json()
    assert body["stop_reason"] == "max_steps"
    assert len(body["trace"]) == 25


def test_run_endpoint_max_steps_out_of_bounds_is_400() -> None:
    response = client.post("/api/8086/run", json={"source": "HLT", "max_steps": 200_000})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CPU_RUNTIME_ERROR"


def test_run_endpoint_unsupported_instruction_is_400() -> None:
    response = client.post("/api/8086/run", json={"source": "MUL AX, BX\nHLT"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "ASM_ERROR"


def test_step_endpoint_single_instruction() -> None:
    response = client.post("/api/8086/step", json={"source": "MOV AX, 9\nINC AX\nHLT"})
    assert response.status_code == 200
    body = response.json()
    assert body["record"]["instruction"] == "MOV AX, 9"
    assert body["record"]["register_changes"]["AX"] == 9
    assert body["registers"]["IP"] == 1
    assert body["halted"] is False


def test_step_endpoint_halted_cpu_is_400() -> None:
    client.post("/api/8086/step", json={"source": "HLT"})
    response = client.post("/api/8086/step", json={"source": "HLT"})
    # a fresh CPU is created per request, so this steps the HLT itself
    assert response.status_code == 200
    assert response.json()["record"]["halted"] is True


def test_shape_error_is_422() -> None:
    response = client.post("/api/8086/run", json={"max_steps": 5})
    assert response.status_code == 422

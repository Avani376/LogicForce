"""Phase 7 interrupt API tests: IVT + schedule over HTTP, deterministic traces."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)

TICKER = "MOV WORD [0x200], 0\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET"


def test_run_endpoint_nmi_fires_and_returns_interrupt_trace() -> None:
    body = {
        "source": TICKER,
        "max_steps": 100,
        "interrupts": {2: "tick"},
        "schedule": [{"source": "nmi", "at_step": 3, "number": 2}],
    }
    response = client.post("/api/8086/run", json=body)
    assert response.status_code == 200
    result = response.json()
    interrupt_records = [r for r in result["trace"] if r["kind"] == "interrupt"]
    assert len(interrupt_records) == 1
    assert interrupt_records[0]["source"] == "nmi"
    assert interrupt_records[0]["number"] == 2
    assert interrupt_records[0]["handler"] is not None
    iret_records = [r for r in result["trace"] if r["kind"] == "iret"]
    assert len(iret_records) == 1
    assert iret_records[0]["resumed_at"] is not None


def test_run_endpoint_masked_intr_waits_for_sti() -> None:
    body = {
        "source": ("MOV WORD [0x200], 0\nCLI\nMOV BX, 7\nSTI\nwait:\nJMP wait\ntick:\nINC WORD [0x200]\nIRET"),
        "max_steps": 200,
        "interrupts": {4: "tick"},
        "schedule": [{"source": "intr", "at_step": 2, "number": 4}],
    }
    response = client.post("/api/8086/run", json=body)
    assert response.status_code == 200
    result = response.json()
    pending = [r for r in result["trace"] if r["kind"] == "pending_intr"]
    fired = [r for r in result["trace"] if r["kind"] == "interrupt"]
    assert len(pending) == 1
    assert len(fired) == 1
    assert fired[0]["source"] == "intr"
    assert result["registers"]["IF"] == 1  # STI raised IF before the INTR fired


def test_run_endpoint_schedule_is_deterministic_over_http() -> None:
    body = {
        "source": TICKER,
        "max_steps": 100,
        "interrupts": {2: "tick"},
        "schedule": [{"source": "nmi", "at_step": 3, "number": 2}],
    }
    a = client.post("/api/8086/run", json=body).json()
    b = client.post("/api/8086/run", json=body).json()
    keys_a = [
        (r["kind"], r["step"], r["number"], json.dumps(r["register_changes"], sort_keys=True)) for r in a["trace"]
    ]
    keys_b = [
        (r["kind"], r["step"], r["number"], json.dumps(r["register_changes"], sort_keys=True)) for r in b["trace"]
    ]
    assert keys_a == keys_b


SUM_HLT = "MOV AX, 0\nHLT"

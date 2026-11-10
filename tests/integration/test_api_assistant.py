"""Integration tests for POST /api/assistant/ask (Phase AI)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)


def test_ask_exercise_flow() -> None:
    response = client.post("/api/assistant/ask", json={"question": "test me"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "exercise"
    assert body["grounding"] == "catalog"
    assert body["scope"] == "RULE_BASED"


def test_ask_explain_with_evidence_is_engine_grounded() -> None:
    context = {
        "trace": [{"kind": "instruction", "step": 1, "ip": 0, "instruction": "HLT", "halted": True}],
        "stop_reason": "hlt",
    }
    response = client.post("/api/assistant/ask", json={"question": "why did it stop?", "context": context})
    assert response.status_code == 200
    body = response.json()
    assert body["grounding"] == "engine_output"
    assert body["data"]["explanation"]["kind"] == "cpu_trace"


def test_ask_empty_question_is_400() -> None:
    response = client.post("/api/assistant/ask", json={"question": "  "})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "ASSISTANT_ERROR"
    assert detail["category"] == "EMPTY_QUESTION"


def test_ask_determinism_over_http() -> None:
    payload = {"question": "what is a K-map?"}
    a = client.post("/api/assistant/ask", json=payload).json()
    b = client.post("/api/assistant/ask", json=payload).json()
    assert a == b


def test_ask_meta_suggestions() -> None:
    response = client.post("/api/assistant/ask", json={"question": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "meta"
    assert isinstance(body["suggestions"], list) and body["suggestions"]

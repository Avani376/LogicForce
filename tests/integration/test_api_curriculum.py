"""Integration tests for the curriculum endpoints (Phase C10)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from logicforge_api.main import app

client = TestClient(app)


def test_lessons_endpoint_lists_catalog() -> None:
    response = client.get("/api/curriculum/lessons")
    assert response.status_code == 200
    body = response.json()
    assert body["catalog_version"]
    assert len(body["lessons"]) == 6
    first = body["lessons"][0]
    assert first["id"] == "L1" and first["unit"] == "1" and first["key_points"]


def test_exercises_endpoint_hides_answers() -> None:
    response = client.get("/api/curriculum/exercises")
    assert response.status_code == 200
    body = response.json()
    assert len(body["exercises"]) == 7
    for exercise in body["exercises"]:
        assert set(exercise) == {"id", "lesson_id", "kind", "prompt", "hint", "answer_kind"}
        assert "data" not in exercise  # pinned answers never leave the engine


def test_single_exercise_endpoint_and_404() -> None:
    response = client.get("/api/curriculum/exercises/cpu-predict-ax")
    assert response.status_code == 200
    assert response.json()["kind"] == "cpu_predict"
    assert client.get("/api/curriculum/exercises/nope").status_code == 404


def test_grade_endpoint_correct_submission() -> None:
    response = client.post("/api/curriculum/grade", json={"exercise_id": "num-convert-hex2dec", "submission": "0x2F"})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["scope"] == "EXHAUSTIVE"
    assert body["evidence"]


def test_grade_endpoint_wrong_submission_still_200() -> None:
    response = client.post("/api/curriculum/grade", json={"exercise_id": "cpu-predict-ax", "submission": "7"})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["scope"] == "BOUNDED(10)"


def test_grade_endpoint_unknown_exercise_is_404() -> None:
    response = client.post("/api/curriculum/grade", json={"exercise_id": "nope", "submission": "1"})
    assert response.status_code == 404
    assert response.json()["detail"]["category"] == "UNKNOWN_EXERCISE"


def test_grade_endpoint_bad_submission_is_400() -> None:
    response = client.post(
        "/api/curriculum/grade", json={"exercise_id": "bool-equiv-demorgan", "submission": "A & & B"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["category"] == "BAD_SUBMISSION"


def test_grade_endpoint_determinism() -> None:
    payload = {"exercise_id": "kmap-minimize", "submission": "!B & !D"}
    a = client.post("/api/curriculum/grade", json=payload).json()
    b = client.post("/api/curriculum/grade", json=payload).json()
    assert a == b
    assert a["passed"] is True
    assert a["scope"] == "EXHAUSTIVE(16)"

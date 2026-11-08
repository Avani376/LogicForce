"""Curriculum endpoints: lessons, exercises, deterministic grading (Phase C10)."""

from __future__ import annotations

from typing import Any

from curriculum_engine import (
    CATALOG_VERSION,
    CURRICULUM_ENGINE_VERSION,
    EXERCISES,
    LESSONS,
    CurriculumError,
    get_exercise,
    grade,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


class GradeRequest(BaseModel):
    exercise_id: str
    submission: str


@router.get("/lessons")
def lessons_endpoint() -> dict[str, Any]:
    return {
        "catalog_version": CATALOG_VERSION,
        "engine_version": CURRICULUM_ENGINE_VERSION,
        "lessons": [
            {
                "id": lesson.id,
                "unit": lesson.unit,
                "title": lesson.title,
                "summary": lesson.summary,
                "key_points": list(lesson.key_points),
                "related_exercise_ids": list(lesson.related_exercise_ids),
            }
            for lesson in LESSONS
        ],
    }


@router.get("/exercises")
def exercises_endpoint() -> dict[str, Any]:
    return {
        "catalog_version": CATALOG_VERSION,
        "engine_version": CURRICULUM_ENGINE_VERSION,
        "exercises": [
            {
                "id": exercise.id,
                "lesson_id": exercise.lesson_id,
                "kind": exercise.kind,
                "prompt": exercise.prompt,
                "hint": exercise.hint,
                "answer_kind": exercise.answer_kind,
            }
            for exercise in EXERCISES
        ],
    }


@router.get("/exercises/{exercise_id}")
def exercise_endpoint(exercise_id: str) -> dict[str, Any]:
    try:
        exercise = get_exercise(exercise_id)
    except CurriculumError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "CURRICULUM_ERROR", "category": exc.category, "message": exc.message}
        ) from exc
    return {
        "id": exercise.id,
        "lesson_id": exercise.lesson_id,
        "kind": exercise.kind,
        "prompt": exercise.prompt,
        "hint": exercise.hint,
        "answer_kind": exercise.answer_kind,
    }


@router.post("/grade")
def grade_endpoint(request: GradeRequest) -> dict[str, Any]:
    try:
        result = grade(request.exercise_id, request.submission)
    except CurriculumError as exc:
        status = 404 if exc.category in ("UNKNOWN_EXERCISE", "UNKNOWN_LESSON") else 400
        raise HTTPException(
            status_code=status, detail={"code": "CURRICULUM_ERROR", "category": exc.category, "message": exc.message}
        ) from exc
    return result.to_json()

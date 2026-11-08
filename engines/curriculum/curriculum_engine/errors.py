"""Typed curriculum errors (curriculum.md — fail-fast, actionable)."""

from __future__ import annotations

from logic_engine import LogicEngineError

CURRICULUM_CATEGORIES = (
    "UNKNOWN_EXERCISE",
    "UNKNOWN_LESSON",
    "BAD_SUBMISSION",
)


class CurriculumError(LogicEngineError):
    """Catalog or submission error for the curriculum layer, with a category."""

    def __init__(self, category: str, message: str) -> None:
        if category not in CURRICULUM_CATEGORIES:
            raise ValueError(f"unknown curriculum category {category!r}")
        self.category = category
        self.message = message
        super().__init__(f"[{category}] {message}")

"""Typed 8259-PIC errors (pic8259.md — fail-fast, actionable)."""

from __future__ import annotations

from logic_engine import LogicEngineError

PIC_CATEGORIES = (
    "NOT_INITIALIZED",
    "INIT_SEQUENCE",
    "BAD_VECTOR_BASE",
    "BAD_LINE",
    "BAD_OCW",
)


class PicError(LogicEngineError):
    """Programming/operation error for the 8259 model, with a category."""

    def __init__(self, category: str, message: str) -> None:
        if category not in PIC_CATEGORIES:
            raise ValueError(f"unknown PIC category {category!r}")
        self.category = category
        self.message = message
        super().__init__(f"[{category}] {message}")

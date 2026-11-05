"""Typed engine errors.

Engine failures are explicit and typed, never silent defaults (master prompt rule 4).
API layer maps these onto HTTP 400 responses with machine-readable codes.

Design note: error classes are plain ``Exception`` subclasses, NOT frozen dataclasses
— frozen dataclass exceptions break traceback assignment (``__traceback__``) during
raise/handling, which surfaced in Phase 3's audit. Attribute contract is unchanged
(``.code`` / ``.message``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from logic_engine.validation import ValidationReport


class LogicEngineError(Exception):
    """Base class for all deterministic-engine errors."""


class SchemaError(LogicEngineError):
    """Document-level structural problem with a circuit JSON document.

    Raised by ``parse_circuit`` for garbage the graph model cannot even represent
    (wrong container types, unsupported ``schema_version``), and by the other engines
    for the same class of structural misuse. Semantic issues (dangling pins, cycles,
    …) are *not* raised here — they accumulate into a ValidationReport.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class CircuitNotValidError(LogicEngineError):
    """Simulation/truth-table attempted on a circuit whose validation has errors.

    Carries the full report so the API can surface every issue, not just the first.
    """

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        codes = ", ".join(issue.code for issue in report.errors)
        super().__init__(f"circuit failed validation ({codes})")


class InvalidInputValueError(LogicEngineError):
    """A primary-input vector entry is not a representable logic value."""

    def __init__(self, name: str, raw: object) -> None:
        self.name = name
        self.raw = raw
        super().__init__(f"invalid value for input {name!r}: {raw!r}")


class TruthTableLimitExceededError(LogicEngineError):
    """Truth-table requested for more primary inputs than the exhaustive bound (12)."""

    def __init__(self, input_count: int, limit: int) -> None:
        self.input_count = input_count
        self.limit = limit
        super().__init__(
            f"truth table needs 2^{input_count} rows; exhaustive limit is {limit} inputs"
        )

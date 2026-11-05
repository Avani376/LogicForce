"""Typed 8086-engine errors.

``AsmError`` carries the 1-based source line, a machine-readable category, and an
actionable message (per the v1.0 documentation's diagnostic requirements).
"""

from __future__ import annotations

from logic_engine import LogicEngineError

ASM_CATEGORIES = (
    "SYNTAX",
    "UNKNOWN_MNEMONIC",
    "UNKNOWN_REGISTER",
    "UNKNOWN_LABEL",
    "DUPLICATE_LABEL",
    "BAD_OPERAND_COUNT",
    "SIZE_MISMATCH",
    "UNSUPPORTED_INSTRUCTION",
)


class AsmError(LogicEngineError):
    """Assembly-time error with source line and category."""

    def __init__(self, line: int, category: str, message: str) -> None:
        if category not in ASM_CATEGORIES:
            raise ValueError(f"unknown ASM category {category!r}")
        self.line = line
        self.category = category
        self.message = message
        super().__init__(f"line {line}: [{category}] {message}")


class UnsupportedInstructionError(LogicEngineError):
    """A mnemonic outside the declared educational subset was requested."""

    def __init__(self, mnemonic: str, line: int) -> None:
        self.mnemonic = mnemonic
        self.line = line
        super().__init__(
            f"unsupported instruction {mnemonic!r} at line {line} — see the "
            "declared subset in docs/semantics/cpu8086.md"
        )


class CpuRuntimeError(LogicEngineError):
    """Execution-time failure (e.g. stack violation), with the step it occurred on."""

    def __init__(self, step: int, message: str) -> None:
        self.step = step
        super().__init__(f"execution error at step {step}: {message}")

"""Error-class guard tests: a wrong category must fail loudly, never silently.

These pin the category-validation branches of the typed-error classes — the
lines the coverage report flagged (audit finding N2).
"""

from __future__ import annotations

import pytest
from cpu8086.errors import AsmError, CpuRuntimeError, UnsupportedInstructionError
from curriculum_engine.errors import CURRICULUM_CATEGORIES, CurriculumError
from pic8259.errors import PIC_CATEGORIES, PicError


class TestCategoryGuards:
    def test_asm_error_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="unknown ASM category"):
            AsmError(1, "NOT_A_CATEGORY", "message")

    def test_pic_error_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="unknown PIC category"):
            PicError("NOT_A_CATEGORY", "message")

    def test_curriculum_error_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="unknown curriculum category"):
            CurriculumError("NOT_A_CATEGORY", "message")

    def test_valid_categories_accepted(self) -> None:
        assert AsmError(1, "SYNTAX", "m").category == "SYNTAX"
        assert PicError("BAD_LINE", "m").category == "BAD_LINE"
        assert CurriculumError("BAD_SUBMISSION", "m").category == "BAD_SUBMISSION"

    def test_category_sets_are_non_empty(self) -> None:
        assert len(PIC_CATEGORIES) >= 5
        assert len(CURRICULUM_CATEGORIES) >= 3


class TestErrorShape:
    """The typed errors carry their structured fields for API envelopes."""

    def test_unsupported_instruction_error_shape(self) -> None:
        err = UnsupportedInstructionError("LAHF", 7)
        assert err.mnemonic == "LAHF"
        assert err.line == 7
        assert "LAHF" in str(err) and "7" in str(err)

    def test_cpu_runtime_error_shape(self) -> None:
        err = CpuRuntimeError(12, "integer divide by zero")
        assert err.step == 12
        assert "divide by zero" in str(err)

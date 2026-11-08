"""Phase C10 tests: curriculum grader — per-kind verdicts, evidence, determinism."""

from __future__ import annotations

import pytest

from curriculum_engine import (
    CATALOG_VERSION,
    EXERCISES,
    LESSONS,
    CurriculumError,
    get_exercise,
    get_lesson,
    grade,
)


class TestCatalog:
    def test_catalog_shape(self) -> None:
        assert len(LESSONS) == 6
        assert len(EXERCISES) == 7
        assert CATALOG_VERSION
        for exercise in EXERCISES:
            assert exercise.lesson_id in {lesson.id for lesson in LESSONS}
            assert exercise.prompt and exercise.hint
        # every lesson's related exercises exist
        for lesson in LESSONS:
            for exercise_id in lesson.related_exercise_ids:
                get_exercise(exercise_id)  # must not raise

    def test_unknown_lesson_and_exercise_typed(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            get_lesson("L999")
        assert exc.value.category == "UNKNOWN_LESSON"
        with pytest.raises(CurriculumError) as exc:
            get_exercise("nope")
        assert exc.value.category == "UNKNOWN_EXERCISE"


class TestNumericGrading:
    def test_decimal_hex_and_bin_accepted(self) -> None:
        assert grade("num-convert-hex2dec", "47").passed
        assert grade("num-convert-hex2dec", "0x2F").passed
        assert grade("num-convert-hex2dec", "0b101111").passed

    def test_wrong_answer_fails_with_evidence(self) -> None:
        result = grade("num-convert-hex2dec", "46")
        assert not result.passed
        assert "46" in result.feedback and "47" in result.feedback
        assert result.scope == "EXHAUSTIVE"

    def test_malformed_submission_typed_error(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            grade("num-convert-hex2dec", "forty-seven")
        assert exc.value.category == "BAD_SUBMISSION"

    def test_pic_vector_hex_submission(self) -> None:
        assert grade("pic-vector", "0x25").passed
        assert not grade("pic-vector", "36").passed


class TestBinaryGrading:
    def test_twos_complement_correct(self) -> None:
        result = grade("num-twos-comp", "11110011")
        assert result.passed
        assert any("twos_complement(00001101, 8)" in line for line in result.evidence)

    def test_non_bits_rejected(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            grade("num-twos-comp", "111102011")
        assert exc.value.category == "BAD_SUBMISSION"


class TestExpressionGrading:
    def test_equivalent_forms_pass(self) -> None:
        for submission in ("!A | !B", "!(A & B)", "!B | (!A & 1)"):
            result = grade("bool-equiv-demorgan", submission)
            assert result.passed, submission
            assert result.scope == "EXHAUSTIVE(4)"

    def test_non_equivalent_fails(self) -> None:
        result = grade("bool-equiv-demorgan", "A & B")
        assert not result.passed

    def test_syntax_error_is_bad_submission(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            grade("bool-equiv-demorgan", "A & & B")
        assert exc.value.category == "BAD_SUBMISSION"


class TestMinimizeGrading:
    def test_minimal_sop_passes(self) -> None:
        result = grade("kmap-minimize", "!B & !D")
        assert result.passed
        assert result.scope == "EXHAUSTIVE(16)"

    def test_reordered_term_passes(self) -> None:
        assert grade("kmap-minimize", "!D & !B").passed

    def test_equivalent_but_not_minimal_fails(self) -> None:
        # !(B | D) is equivalent and equally minimal (2 literals) — passes.
        assert grade("kmap-minimize", "!(B | D)").passed
        # B & D is not equivalent — fails with a row mismatch.
        result = grade("kmap-minimize", "B & D")
        assert not result.passed
        assert "does not reproduce" in result.feedback

    def test_forbidden_variable_rejected(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            grade("kmap-minimize", "!B & !D & !E")
        assert exc.value.category == "BAD_SUBMISSION"


class TestFlipFlopGrading:
    def test_dff_next_state(self) -> None:
        result = grade("dff-next-state", "1")
        assert result.passed
        assert any("characteristic_table(DFF)" in line for line in result.evidence)
        assert not grade("dff-next-state", "0").passed


class TestCpuPredictGrading:
    def test_register_value_matches_engine_run(self) -> None:
        result = grade("cpu-predict-ax", "8")
        assert result.passed
        assert result.scope == "BOUNDED(10)"
        assert any("AX = 8" in line for line in result.evidence)
        assert not grade("cpu-predict-ax", "7").passed


class TestDeterminism:
    def test_same_submission_byte_identical(self) -> None:
        for exercise_id, submission in (
            ("num-convert-hex2dec", "0x2F"),
            ("bool-equiv-demorgan", "!A | !B"),
            ("kmap-minimize", "!B & !D"),
            ("cpu-predict-ax", "8"),
        ):
            a = grade(exercise_id, submission).to_json()
            b = grade(exercise_id, submission).to_json()
            assert a == b, exercise_id

    def test_empty_submission_rejected(self) -> None:
        with pytest.raises(CurriculumError) as exc:
            grade("num-convert-hex2dec", "   ")
        assert exc.value.category == "BAD_SUBMISSION"

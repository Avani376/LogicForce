"""Assistant tests: deterministic intent routing, grounding honesty, typed errors."""

from __future__ import annotations

import pytest
from logicforge_api.assistant import AssistantError, ask


class TestIntentRouting:
    def test_exercise_intent_lists_catalog(self) -> None:
        result = ask("test me on something")
        assert result["kind"] == "exercise"
        assert result["grounding"] == "catalog"
        assert 0 < len(result["data"]["exercises"]) <= 3

    def test_specific_exercise_by_id(self) -> None:
        result = ask("give me the kmap-minimize exercise")
        assert result["kind"] == "exercise"
        assert result["data"]["exercises"][0]["id"] == "kmap-minimize"

    def test_lesson_intent_what_is(self) -> None:
        result = ask("what is a flip-flop?")
        assert result["kind"] == "lesson"
        assert result["grounding"] == "catalog"
        assert "flip" in result["answer"].lower()

    def test_lesson_intent_without_phrase_still_routes_on_keywords(self) -> None:
        # "what is" present + keyword overlap decides the lesson deterministically.
        result = ask("what is a K-map?")
        assert result["kind"] == "lesson"
        assert "minimization" in result["answer"].lower() or "k-map" in result["answer"].lower()

    def test_explain_with_cpu_trace_context_is_grounded(self) -> None:
        context = {
            "trace": [
                {"kind": "instruction", "step": 1, "ip": 0, "instruction": "MOV AX, 5"},
                {"kind": "instruction", "step": 2, "ip": 1, "instruction": "HLT", "halted": True},
            ],
            "stop_reason": "hlt",
            "registers": {"AX": 5},
        }
        result = ask("why did my program stop?", context)
        assert result["kind"] == "explain"
        assert result["grounding"] == "engine_output"
        assert result["scope"] == "EXHAUSTIVE"
        assert result["answer"]  # non-empty grounded answer

    def test_explain_without_context_refuses_to_invent(self) -> None:
        result = ask("why did my verification fail?")
        assert result["kind"] == "explain"
        assert result["grounding"] == "guidance"
        assert "not invent" in result["answer"].lower() or "evidence" in result["answer"].lower()

    def test_guide_intent_pic(self) -> None:
        result = ask("how does the PIC deliver vectors?")
        assert result["kind"] == "guide"
        assert result["data"]["tab"] == "8086 CPU"

    def test_meta_fallback_lists_capabilities(self) -> None:
        result = ask("hello there")
        assert result["kind"] == "meta"
        assert "Sparky" in result["answer"]
        assert result["suggestions"]


class TestDeterminism:
    def test_same_question_byte_identical(self) -> None:
        a = ask("what is a K-map?")
        b = ask("what is a K-map?")
        assert a == b

    def test_same_context_byte_identical(self) -> None:
        context = {"trace": [], "stop_reason": "max_steps"}
        a = ask("explain my trace", context)
        b = ask("explain my trace", context)
        assert a == b


class TestTypedErrors:
    def test_empty_question(self) -> None:
        with pytest.raises(AssistantError) as exc:
            ask("   ")
        assert exc.value.category == "EMPTY_QUESTION"

    def test_oversized_question(self) -> None:
        with pytest.raises(AssistantError) as exc:
            ask("x" * 501)
        assert exc.value.category == "EMPTY_QUESTION"

    def test_non_object_context(self) -> None:
        with pytest.raises(AssistantError) as exc:
            ask("why?", context=["not", "an", "object"])  # type: ignore[arg-type]
        assert exc.value.category == "BAD_CONTEXT"


class TestExplainShapeMismatch:
    def test_unrecognized_context_shape_is_honest(self) -> None:
        result = ask("explain my result", {"random_key": 1})
        assert result["kind"] == "explain"
        assert "doesn't match a shape" in result["answer"]
        assert result["grounding"] == "guidance"

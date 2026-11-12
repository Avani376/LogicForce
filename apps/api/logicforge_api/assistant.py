"""Deterministic assistant: question → intent → grounded answer (assistant.md).

Not an LLM. Every answer routes to a real source — the explain engine, the
curriculum catalog, or authored product guidance — and cites it. Same question
+ same context + same versions ⇒ byte-identical response.
"""

from __future__ import annotations

from typing import Any, cast

from curriculum_engine import EXERCISES, LESSONS, CurriculumError, get_exercise
from logic_engine import LogicEngineError

MAX_QUESTION_CHARS = 500

#: Intent 4 keywords → authored guidance (product facts only; no engine claims).
GUIDES: dict[str, dict[str, str]] = {
    "pic": {
        "tab": "8086 CPU",
        "text": (
            "The 8259 PIC lab lives in the 8086 CPU tab. Set the ICW2 base vector "
            "(multiple of 8), schedule line events as JSON, and resolve the flow — "
            "you get the exact boundaries at which each vector reaches the CPU."
        ),
    },
    "interrupt": {
        "tab": "8086 CPU",
        "text": (
            "Interrupts: software INT, scheduled NMI/INTR with IF masking, and the "
            "8259 PIC. The interrupt trace shows every fire, park, and IRET with "
            "instruction-level boundaries."
        ),
    },
    "8086": {
        "tab": "8086 CPU",
        "text": (
            "The 8086 CPU tab assembles and runs the full educational subset: ALU, "
            "MUL/IMUL/DIV/IDIV, shifts, string ops with REP, CALL/RET, interrupts. "
            "Write assembly, press Run, read the registers, flags, and trace."
        ),
    },
    "optimize": {
        "tab": "Circuit",
        "text": (
            "Optimization rewrites your circuit while an exhaustive equivalence "
            "check proves the truth table is unchanged — the before/after metrics "
            "are engine-computed, never estimated."
        ),
    },
    "fault": {
        "tab": "Circuit",
        "text": (
            "Fault injection seeds stuck-at/bridge faults into your circuit, probes "
            "behavior, and reports detection. Repair candidates are only accepted "
            "after re-verification against the full suite."
        ),
    },
    "repair": {
        "tab": "Circuit",
        "text": (
            "Repair search proposes deltas, and every candidate must re-verify "
            "against the original property suite before it is called 'repaired'."
        ),
    },
    "verify": {
        "tab": "Verify",
        "text": (
            "The Verify tab checks invariants over the full truth table or FSM "
            "firing space and labels the result EXHAUSTIVE or BOUNDED — failures "
            "come with replayable counterexamples."
        ),
    },
    "visual": {
        "tab": "Visuals",
        "text": (
            "The Visuals tab animates your session's real engine output: the "
            "9-stage workflow, event bars, truth-table heatmaps, and waveforms. "
            "Run something in another tab first — the charts only show genuine data."
        ),
    },
    "kmap": {
        "tab": "Learn",
        "text": (
            "K-map and Quine-McCluskey minimization run in the boolean engine — the "
            "kmap_simplify and quine_mccluskey endpoints cross-check one against the "
            "other, and the curriculum API has a minimize exercise that checks "
            "equivalence AND minimality."
        ),
    },
    "gray": {
        "tab": "Learn",
        "text": (
            "Gray codes are lesson L1 in the curriculum engine: adjacent values "
            "differ in exactly one bit; binary → Gray is XOR-shift."
        ),
    },
    "bcd": {
        "tab": "Learn",
        "text": "BCD, Excess-3 and ASCII codes are lesson L1 in the curriculum engine.",
    },
}


def _normalize_words(text: str) -> set[str]:
    """Lowercase, split hyphenated compounds, strip punctuation and plural 's'."""
    words: set[str] = set()
    for raw in text.lower().replace("—", " ").split():
        for part in raw.split("-"):
            part = part.strip(".,!?;:()'\"")
            if len(part) > 2:
                words.add(part[:-1] if part.endswith("s") and len(part) > 3 else part)
    return words


#: Lesson keyword index — deterministic scoring for intent 2.
_LESSON_KEYWORDS: dict[str, set[str]] = {
    lesson.id: _normalize_words(" ".join([lesson.title, lesson.summary, *lesson.key_points])) for lesson in LESSONS
}

_LESSON_BY_ID = {lesson.id: lesson for lesson in LESSONS}


class AssistantError(LogicEngineError):
    """Typed assistant error (assistant.md)."""

    def __init__(self, category: str, message: str) -> None:
        self.category = category
        self.message = message
        super().__init__(f"[{category}] {message}")


def _validate(question: str, context: Any) -> str:
    if not isinstance(question, str) or not question.strip():
        raise AssistantError("EMPTY_QUESTION", "ask a non-empty question")
    if len(question.strip()) > MAX_QUESTION_CHARS:
        raise AssistantError("EMPTY_QUESTION", f"question exceeds {MAX_QUESTION_CHARS} characters")
    if context is not None and not isinstance(context, dict):
        raise AssistantError("BAD_CONTEXT", "context must be a JSON object of engine evidence")
    return question.strip().lower()


def _best_lesson(question: str) -> str | None:
    """Lesson id with the most keyword overlaps; None when nothing overlaps."""
    words = _normalize_words(question)
    best_id: str | None = None
    best_score = 0
    for lesson_id in sorted(_LESSON_KEYWORDS):  # sorted ⇒ deterministic tie-break
        score = len(words & _LESSON_KEYWORDS[lesson_id])
        if score > best_score:
            best_id = lesson_id
            best_score = score
    return best_id


def _exercise_answer(question: str) -> dict[str, Any]:
    wanted = None
    for exercise in EXERCISES:
        if exercise.id in question:
            wanted = exercise.id
            break
    if wanted is not None:
        exercise = get_exercise(wanted)
        return {
            "answer": f"Exercise {exercise.id}: {exercise.prompt} (hint: {exercise.hint})",
            "data": {
                "exercises": [
                    {
                        "id": exercise.id,
                        "prompt": exercise.prompt,
                        "hint": exercise.hint,
                        "kind": exercise.kind,
                    }
                ]
            },
        }
    return {
        "answer": (
            "Here are the open exercises — each one is graded by a real engine "
            "(truth tables, Quine-McCluskey, bounded CPU runs), never by string matching:"
        ),
        "data": {
            "exercises": [{"id": e.id, "prompt": e.prompt, "hint": e.hint, "kind": e.kind} for e in EXERCISES[:3]]
        },
    }


def _lesson_answer(question: str) -> dict[str, Any] | None:
    lesson_id = _best_lesson(question)
    if lesson_id is None:
        return None
    lesson = _LESSON_BY_ID[lesson_id]
    return {
        "answer": f"{lesson.title} — {lesson.summary} Key points: " + " ".join(lesson.key_points),
        "data": {"lesson": {"id": lesson.id, "title": lesson.title, "summary": lesson.summary}},
    }


def _guide_answer(question: str) -> dict[str, Any] | None:
    for keyword in sorted(GUIDES):  # sorted ⇒ deterministic when several match
        if keyword in question:
            guide = GUIDES[keyword]
            return {
                "answer": guide["text"],
                "data": {"tab": guide["tab"]},
            }
    return None


def _infer_explanation_kind(context: dict[str, Any]) -> str | None:
    """Deterministic kind inference from evidence shape (assistant.md)."""
    if "trace" in context and "stop_reason" in context:
        return "cpu_trace"
    if "verdict" in context or "report" in context or "counterexample" in context:
        return "verification"
    if "experiments" in context or "detection" in context:
        return "fault_experiment"
    if "circuit_events" in context or "cpu_events" in context:
        return "cosim"
    if "rows" in context or "outputs" in context and "inputs" in context:
        return "circuit_truth_table"
    return None


def _explain_answer(question: str, context: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """(body, grounded) — grounded is True only when the engine produced the answer."""
    if context is None:
        return (
            {
                "answer": (
                    "I can explain that from real engine output — but I need the evidence. "
                    "Run a simulation, verification, or trace first, then ask again with the "
                    "result attached (the panels do this automatically). I will not invent "
                    "an explanation without it."
                ),
                "data": {},
            },
            False,
        )
    kind = _infer_explanation_kind(context)
    if kind is None:
        return {
            "answer": (
                "That evidence doesn't match a shape I can explain (cpu_trace, "
                "verification, fault_experiment, cosim, or circuit_truth_table). "
                "Attach the full engine output and I'll ground the answer in it."
            ),
            "data": {},
        }, False
    try:
        # Imported lazily to avoid a router→engine import cycle at module load.
        from verify_engine.explain import explain, explanation_to_dict

        explanation = explanation_to_dict(explain(kind, context, question=question))
        raw_findings = cast(list[object], explanation.get("findings", []))
        findings = [f for f in raw_findings if isinstance(f, dict)]
        summary = str(explanation.get("summary", ""))
        first_texts = [str(f.get("text", "")) for f in findings[:3]]
        return (
            {
                "answer": summary + (" " + " ".join(first_texts) if first_texts else ""),
                "data": {"explanation": explanation},
            },
            True,
        )
    except (LogicEngineError, CurriculumError, ValueError, KeyError) as exc:
        return (
            {
                "answer": (
                    f"I could not ground an explanation in that evidence ({exc}). "
                    "Run the engine step again and attach its output — I only explain real results."
                ),
                "data": {},
            },
            False,
        )


def ask(question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Answer a question deterministically (assistant.md intent order)."""
    lowered = _validate(question, context)

    if any(word in lowered for word in ("exercise", "practice", "quiz", "test me")):
        body = _exercise_answer(lowered)
        return {
            "answer": body["answer"],
            "grounding": "catalog",
            "kind": "exercise",
            "scope": "RULE_BASED",
            "sources": ["curriculum_engine 0.1.0"],
            "suggestions": ["Grade answers via POST /api/curriculum/grade →"],
            "data": body["data"],
        }

    lesson_body = _lesson_answer(lowered)
    if lesson_body is not None and (
        "what is" in lowered or "lesson" in lowered or "define" in lowered or "concept" in lowered
    ):
        return {
            "answer": lesson_body["answer"],
            "grounding": "catalog",
            "kind": "lesson",
            "scope": "RULE_BASED",
            "sources": ["curriculum_engine 0.1.0"],
            "suggestions": ["Browse GET /api/curriculum/exercises →"],
            "data": lesson_body["data"],
        }

    wants_explanation = any(word in lowered for word in ("why", "explain", "trace", "counterexample", "fail"))
    if wants_explanation and context is not None:
        body, grounded = _explain_answer(lowered, context)
        return {
            "answer": body["answer"],
            "grounding": "engine_output" if grounded else "guidance",
            "kind": "explain",
            "scope": "EXHAUSTIVE" if grounded else "RULE_BASED",
            "sources": ["verify_engine explain 0.9.0"] if grounded else ["product docs"],
            "suggestions": ["Open the Explain tab to see the full evidence →"],
            "data": body["data"],
        }

    guide_body = _guide_answer(lowered)
    if guide_body is not None:
        return {
            "answer": guide_body["answer"],
            "grounding": "guidance",
            "kind": "guide",
            "scope": "RULE_BASED",
            "sources": ["product docs"],
            "suggestions": [f"Open the {guide_body['data']['tab']} tab →"],
            "data": guide_body["data"],
        }

    if wants_explanation:
        # Wants an explanation, no context, no specific tab — be honest about it.
        body, _grounded = _explain_answer(lowered, None)
        return {
            "answer": body["answer"],
            "grounding": "guidance",
            "kind": "explain",
            "scope": "RULE_BASED",
            "sources": ["product docs"],
            "suggestions": [
                "Run a simulation or verification first, then ask 'why' with the result attached.",
                "Try the Verify tab →",
            ],
            "data": {},
        }

    return {
        "answer": (
            "I'm Sparky — LogicForge's guide. Everything I say is grounded: I route "
            "questions to real engine output or the lesson catalog, and I never invent "
            "results. Ask me about the 8086, the PIC, interrupts, verification, faults, "
            "optimization, K-maps, or say 'test me' for an exercise."
        ),
        "grounding": "guidance",
        "kind": "meta",
        "scope": "RULE_BASED",
        "sources": ["product docs"],
        "suggestions": ["What is a D flip-flop?", "Tell me about the PIC", "Test me"],
        "data": {},
    }

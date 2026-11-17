"""Static lesson/exercise catalog (curriculum.md — ships with the engine, test-covered)."""

from __future__ import annotations

from dataclasses import dataclass, field

from curriculum_engine.errors import CurriculumError

CATALOG_VERSION = "0.1.0"


@dataclass(frozen=True)
class Lesson:
    id: str
    unit: str  # "1".."6" or "cross"
    title: str
    summary: str
    key_points: tuple[str, ...]
    related_exercise_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Exercise:
    id: str
    lesson_id: str
    kind: str  # numeric | binary | expression_equiv | minimize | flipflop_next | cpu_predict
    prompt: str
    hint: str
    answer_kind: str  # numeric | binary | expression
    #: kind-specific pinned data (answer, target expression, minterms, program, …)
    data: dict[str, object] = field(default_factory=dict)


_LESSONS = (
    Lesson(
        id="L1",
        unit="1",
        title="Number Systems & Codes",
        summary=(
            "Positional number systems, base conversion with working, and the "
            "complement arithmetic that makes subtraction free."
        ),
        key_points=(
            "Base conversion: repeated division (integer part) and repeated multiplication (fractions).",
            "Two's complement of an n-bit value: invert the bits and add 1 — one representation of zero.",
            "Gray code: adjacent values differ in exactly one bit; binary → Gray is XOR-shift.",
        ),
        related_exercise_ids=("num-convert-hex2dec", "num-twos-comp"),
    ),
    Lesson(
        id="L2",
        unit="1",
        title="Boolean Algebra & Theorems",
        summary=(
            "Expressions as functions; De Morgan's theorems and duality let you "
            "move negations through AND/OR structure."
        ),
        key_points=(
            "De Morgan: !(A & B) == !A | !B and !(A | B) == !A & !B.",
            "Two expressions are the same function iff their truth tables agree — the engine checks exactly that.",
            "NAND/NOR universality: any Boolean function can be built from one gate type.",
        ),
        related_exercise_ids=("bool-equiv-demorgan",),
    ),
    Lesson(
        id="L3",
        unit="2",
        title="Combinational Minimization",
        summary=(
            "Karnaugh maps and Quine-McCluskey both find minimal SOP forms; the "
            "engine cross-checks one against the other."
        ),
        key_points=(
            "A group on the K-map must be a power of two and rectangular (with wraparound).",
            "Don't-cares are free: include them when they enlarge a group, exclude them otherwise.",
            "Minimality is two-dimensional: fewest terms, then fewest literals.",
        ),
        related_exercise_ids=("kmap-minimize",),
    ),
    Lesson(
        id="L4",
        unit="3",
        title="Flip-Flops & Next State",
        summary=(
            "Flip-flops are the memory of a sequential circuit; the characteristic "
            "table is the contract between inputs and next state."
        ),
        key_points=(
            "D flip-flop: Q+ = D — a one-cycle delay line.",
            "T flip-flop: Q+ = Q xor T — divide-by-two when T is held high.",
            "JK = SR made safe: J=K=1 toggles instead of going invalid.",
        ),
        related_exercise_ids=("dff-next-state",),
    ),
    Lesson(
        id="L5",
        unit="5",
        title="8086 Registers & Arithmetic",
        summary=(
            "The 8086's register set and the exact flag semantics of its "
            "arithmetic — read them like the engine does, bit by bit."
        ),
        key_points=(
            "AX/BX/CX/DX are 16-bit; AH/AL etc. are the byte halves.",
            "ADD sets CF on carry out of the MSB and OF on signed overflow.",
            "MUL leaves CF/OF set when the product needs the upper half (DX/AH).",
        ),
        related_exercise_ids=("cpu-predict-ax",),
    ),
    Lesson(
        id="L6",
        unit="6",
        title="Interrupts & the 8259 PIC",
        summary=(
            "Maskable interrupts flow through the 8259: priority resolution, "
            "masking, and EOI keep the CPU serviceable and fair."
        ),
        key_points=(
            "Vector = ICW2 base + IR line; the base must be a multiple of 8 in 8086 mode.",
            "IMR masks a line from service; the IRR still records the request.",
            "Fully nested: a lower-priority request waits while a higher one is in service.",
        ),
        related_exercise_ids=("pic-vector",),
    ),
)

_EXERCISES = (
    Exercise(
        id="num-convert-hex2dec",
        lesson_id="L1",
        kind="numeric",
        prompt="Convert the hexadecimal value 0x2F to decimal.",
        hint="Weights: 16^1 and 16^0.",
        answer_kind="numeric",
        data={"answer": 47},
    ),
    Exercise(
        id="num-twos-comp",
        lesson_id="L1",
        kind="binary",
        prompt="Write the 8-bit two's complement of -13 as a bit string.",
        hint="Start from 8-bit +13 = 00001101, invert, add 1.",
        answer_kind="binary",
        data={"positive_bits": "00001101", "width": 8},
    ),
    Exercise(
        id="bool-equiv-demorgan",
        lesson_id="L2",
        kind="expression_equiv",
        prompt="Write any Boolean expression equivalent to !(A & B) using !, &, |, ^.",
        hint="De Morgan's theorem.",
        answer_kind="expression",
        data={"target": "!(A & B)"},
    ),
    Exercise(
        id="kmap-minimize",
        lesson_id="L3",
        kind="minimize",
        prompt="Minimize F(A,B,C,D) = sum of minterms 0, 2, 8, 10. Submit an SOP expression in A, B, C, D.",
        hint="All four minterms share two variables that stay constant.",
        answer_kind="expression",
        data={"minterms": [0, 2, 8, 10], "dont_cares": [], "num_vars": 4},
    ),
    Exercise(
        id="dff-next-state",
        lesson_id="L4",
        kind="flipflop_next",
        prompt="A D flip-flop has D=1 and current Q=0. What is Q after the next clock edge? (0 or 1)",
        hint="Q+ = D.",
        answer_kind="numeric",
        data={"ff_type": "DFF", "inputs": {"D": 1}, "current_q": 0},
    ),
    Exercise(
        id="cpu-predict-ax",
        lesson_id="L5",
        kind="cpu_predict",
        prompt="What is AX after this program runs?\nMOV AX, 5\nADD AX, 3\nHLT",
        hint="ADD AX, 3 adds the immediate to AX.",
        answer_kind="numeric",
        data={"program": "MOV AX, 5\nADD AX, 3\nHLT", "register": "AX", "max_steps": 10},
    ),
    Exercise(
        id="pic-vector",
        lesson_id="L6",
        kind="numeric",
        prompt=(
            "A PIC is initialized with ICW2 base vector 0x20 (32). IR5 is raised and "
            "serviced. Which vector number does the CPU receive?"
        ),
        hint="vector = base + line.",
        answer_kind="numeric",
        data={"answer": 37},
    ),
)

LESSONS: tuple[Lesson, ...] = _LESSONS
EXERCISES: tuple[Exercise, ...] = _EXERCISES
LESSON_IDS: frozenset[str] = frozenset(lesson.id for lesson in LESSONS)
EXERCISE_IDS: frozenset[str] = frozenset(exercise.id for exercise in EXERCISES)


def get_lesson(lesson_id: str) -> Lesson:
    for lesson in LESSONS:
        if lesson.id == lesson_id:
            return lesson
    raise CurriculumError(
        "UNKNOWN_LESSON",
        f"unknown lesson {lesson_id!r} — catalog has: {', '.join(sorted(LESSON_IDS))}",
    )


def get_exercise(exercise_id: str) -> Exercise:
    for exercise in EXERCISES:
        if exercise.id == exercise_id:
            return exercise
    raise CurriculumError(
        "UNKNOWN_EXERCISE",
        f"unknown exercise {exercise_id!r} — catalog has: {', '.join(sorted(EXERCISE_IDS))}",
    )

"""Deterministic grader: the other engines decide (curriculum.md).

Every pass/fail is decided by running the relevant engine — numsys, boolean,
kmap, sequential, cpu8086 — and the evidence lines cite what those engines
observed. Same submission ⇒ byte-identical result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from boolean_engine import BoolExpr, evaluate, parse, truth_table
from boolean_engine.kmap import quine_mccluskey
from cpu8086.machine import assemble_and_load
from logic_engine import LogicEngineError
from numsys import twos_complement
from sequential_engine import characteristic_table

from curriculum_engine.catalog import Exercise, get_exercise
from curriculum_engine.errors import CurriculumError

#: expressions with more variables than this are refused (bounds the 2^n table)
MAX_EXPRESSION_VARS = 8


@dataclass(frozen=True)
class GradedResult:
    """EXHAUSTIVE/BOUNDED-labeled verdict with engine evidence."""

    exercise_id: str
    passed: bool
    scope: str
    feedback: str
    evidence: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "exercise_id": self.exercise_id,
            "passed": self.passed,
            "scope": self.scope,
            "feedback": self.feedback,
            "evidence": list(self.evidence),
        }


def _parse_submission_int(submission: str) -> int:
    text = submission.strip().replace("_", "").replace(" ", "")
    try:
        value = int(text, 0)
    except ValueError:
        raise CurriculumError(
            "BAD_SUBMISSION", f"expected an integer (decimal, 0x… or 0b…), got {submission!r}"
        ) from None
    return value


def _parse_submission_bits(submission: str) -> str:
    text = submission.strip().replace("_", "").replace(" ", "")
    if not text or any(ch not in "01" for ch in text):
        raise CurriculumError("BAD_SUBMISSION", f"expected a bit string of 0s and 1s, got {submission!r}")
    return text


def _parse_submission_expr(submission: str) -> BoolExpr:
    try:
        return parse(submission)
    except LogicEngineError as exc:
        raise CurriculumError(
            "BAD_SUBMISSION",
            f"could not parse the expression {submission!r}: {exc} — use !, &, |, ^ and variable names",
        ) from None


def _expression_vars(expr: BoolExpr) -> list[str]:
    """Deterministic variable order (sorted) of an expression AST."""
    if expr.kind == "var":
        return [expr.value]
    if expr.kind == "lit" or expr.left is None:
        return []
    vars_found = _expression_vars(expr.left)
    if expr.right is not None:
        vars_found += _expression_vars(expr.right)
    return sorted(set(vars_found))


def _count_literals(expr: BoolExpr) -> int:
    if expr.kind == "var":
        return 1
    if expr.kind == "lit" or expr.left is None:
        return 0
    count = _count_literals(expr.left)
    if expr.right is not None:
        count += _count_literals(expr.right)
    return count


def _truth_table_equivalent(submission_expr: BoolExpr, target_expr: BoolExpr) -> tuple[bool, int, int]:
    """(equivalent, rows, n) — EXHAUSTIVE over the union of both expressions' variables."""
    variables = sorted(set(_expression_vars(submission_expr)) | set(_expression_vars(target_expr)))
    n = len(variables)
    if n > MAX_EXPRESSION_VARS:
        raise CurriculumError(
            "BAD_SUBMISSION",
            f"expression has {n} variables — the educational cap is {MAX_EXPRESSION_VARS}",
        )
    submission_table = {tuple(sorted(env.items())): value for env, value in truth_table(submission_expr)}
    target_table = {tuple(sorted(env.items())): value for env, value in truth_table(target_expr)}
    rows = 0
    for env_values in range(1 << n):
        env = {name: bool((env_values >> i) & 1) for i, name in enumerate(variables)}
        key = tuple(sorted(env.items()))
        if submission_table.get(key, evaluate(submission_expr, env)) != target_table.get(
            key, evaluate(target_expr, env)
        ):
            return False, rows, n
        rows += 1
    return True, rows, n


def _grade_numeric(exercise: Exercise, submission: str) -> GradedResult:
    answer = cast(int, exercise.data["answer"])
    value = _parse_submission_int(submission)
    passed = value == answer
    feedback = (
        f"Correct — {answer} is the value the engine's catalog pins for this exercise."
        if passed
        else f"Not yet: the submission parses as {value}, but the correct value is {answer}."
    )
    return GradedResult(
        exercise_id=exercise.id,
        passed=passed,
        scope="EXHAUSTIVE",
        feedback=feedback,
        evidence=(f"submission parses to {value}", f"expected {answer}"),
    )


def _grade_binary(exercise: Exercise, submission: str) -> GradedResult:
    positive_bits = str(exercise.data["positive_bits"])
    width = cast(int, exercise.data["width"])
    expected = twos_complement(positive_bits, width).result
    bits = _parse_submission_bits(submission)
    passed = bits == expected
    feedback = (
        f"Correct — {expected} is the {width}-bit two's complement computed by the numsys engine."
        if passed
        else (
            f"Not yet: the numsys engine computes {expected} for the {width}-bit "
            f"two's complement; the submission was {bits}."
        )
    )
    return GradedResult(
        exercise_id=exercise.id,
        passed=passed,
        scope="EXHAUSTIVE",
        feedback=feedback,
        evidence=(
            f"twos_complement({positive_bits}, {width}) = {expected}",
            f"submission bits {bits}",
        ),
    )


def _grade_expression_equiv(exercise: Exercise, submission: str) -> GradedResult:
    target = _parse_submission_expr(str(exercise.data["target"]))
    submitted = _parse_submission_expr(submission)
    equivalent, rows, n = _truth_table_equivalent(submitted, target)
    feedback = (
        f"Correct — the submission is truth-table equivalent to {exercise.data['target']}."
        if equivalent
        else "Not yet: the truth tables differ — the submission is not equivalent to the target."
    )
    return GradedResult(
        exercise_id=exercise.id,
        passed=equivalent,
        scope=f"EXHAUSTIVE({1 << n})",
        feedback=feedback,
        evidence=(
            f"truth-table equivalence over {n} variables: {1 << n} rows compared",
            f"submission parses to a {submitted.kind}-rooted expression "
            f"with variables {sorted(set(_expression_vars(submitted)))}",
        ),
    )


def _grade_minimize(exercise: Exercise, submission: str) -> GradedResult:
    minterms = list(cast(list[int], exercise.data["minterms"]))
    dont_cares = list(cast(list[int], exercise.data.get("dont_cares", [])))
    num_vars = cast(int, exercise.data["num_vars"])
    var_names = ["A", "B", "C", "D", "E", "F", "G", "H"][:num_vars]
    submitted = _parse_submission_expr(submission)
    submitted_vars = set(_expression_vars(submitted))
    if not submitted_vars <= set(var_names):
        raise CurriculumError(
            "BAD_SUBMISSION",
            f"minimization answer must use only {', '.join(var_names)} — found {sorted(submitted_vars)}",
        )
    env_names = var_names
    matches = True
    for env_values in range(1 << num_vars):
        # Minterm numbering: var_names[0] (A) is the MSB of the row index.
        env = {name: bool((env_values >> (num_vars - 1 - i)) & 1) for i, name in enumerate(env_names)}
        expected = env_values in minterms
        actual = evaluate(submitted, env)
        if expected != actual:
            matches = False
            break
    qm = quine_mccluskey(minterms, dont_cares, num_vars)
    qm_expression = str(qm["expression"])
    qm_literals = sum(pattern.count("0") + pattern.count("1") for pattern in cast(list[str], qm["cover"]))
    submitted_literals = _count_literals(submitted)
    compact = submitted_literals <= qm_literals
    passed = matches and compact
    if matches and compact:
        feedback = "Correct — equivalent to the original function and as compact as the QM solution."
    elif not matches:
        feedback = "Not yet: the submission does not reproduce the original function on every input row."
    else:
        feedback = f"Equivalent, but not minimal: {submitted_literals} literals vs the QM solution's {qm_literals}."
    return GradedResult(
        exercise_id=exercise.id,
        passed=passed,
        scope=f"EXHAUSTIVE({1 << num_vars})",
        feedback=feedback,
        evidence=(
            f"equivalence over {num_vars} variables: {1 << num_vars} rows "
            f"({'all match' if matches else 'mismatch found'})",
            f"QM reference: {qm_expression} ({qm_literals} literals); submission: {submitted_literals} literals",
        ),
    )


def _grade_flipflop_next(exercise: Exercise, submission: str) -> GradedResult:
    ff_type = str(exercise.data["ff_type"])
    inputs = {k: int(v) for k, v in cast(dict[str, int], exercise.data["inputs"]).items()}
    current_q = cast(int, exercise.data["current_q"])
    tables = characteristic_table(ff_type)
    entry = next((e for e in tables.characteristic if e.inputs == inputs and e.current_q == current_q), None)
    if entry is None:
        raise CurriculumError(
            "BAD_SUBMISSION",
            f"pinned exercise references a characteristic-table row that does not exist "
            f"({ff_type}, inputs {inputs}, Q={current_q}) — this is a catalog bug",
        )
    expected = entry.next_q
    value = _parse_submission_int(submission)
    passed = value == expected
    feedback = (
        f"Correct — the {ff_type} characteristic table gives Q+ = {expected}."
        if passed
        else f"Not yet: the {ff_type} characteristic table gives Q+ = {expected} for those inputs."
    )
    return GradedResult(
        exercise_id=exercise.id,
        passed=passed,
        scope="EXHAUSTIVE",
        feedback=feedback,
        evidence=(
            f"characteristic_table({ff_type}): inputs {inputs}, Q={current_q} → Q+ = {expected}",
            f"submission parses to {value}",
        ),
    )


def _grade_cpu_predict(exercise: Exercise, submission: str) -> GradedResult:
    program = str(exercise.data["program"])
    register = str(exercise.data["register"])
    max_steps = cast(int, exercise.data["max_steps"])
    machine = assemble_and_load(program)
    machine.run(max_steps=max_steps)
    expected = machine.registers.get(register)
    value = _parse_submission_int(submission)
    passed = value == expected
    feedback = (
        f"Correct — the engine run leaves {register} = {expected}."
        if passed
        else f"Not yet: a bounded engine run of the pinned program leaves {register} = {expected}."
    )
    return GradedResult(
        exercise_id=exercise.id,
        passed=passed,
        scope=f"BOUNDED({max_steps})",
        feedback=feedback,
        evidence=(
            f"engine run of {len(program.splitlines())} instructions: {register} = {expected}",
            f"submission parses to {value}",
        ),
    )


_GRADERS = {
    "numeric": _grade_numeric,
    "binary": _grade_binary,
    "expression_equiv": _grade_expression_equiv,
    "minimize": _grade_minimize,
    "flipflop_next": _grade_flipflop_next,
    "cpu_predict": _grade_cpu_predict,
}


def grade(exercise_id: str, submission: str) -> GradedResult:
    """Grade a submission for `exercise_id`. Pure: same inputs, same result."""
    if not isinstance(submission, str) or not submission.strip():
        raise CurriculumError("BAD_SUBMISSION", "submission must be a non-empty string")
    exercise = get_exercise(exercise_id)
    grader = _GRADERS.get(exercise.kind)
    if grader is None:
        raise CurriculumError(
            "BAD_SUBMISSION",
            f"exercise kind {exercise.kind!r} has no grader — this is a catalog bug",
        )
    return grader(exercise, submission)

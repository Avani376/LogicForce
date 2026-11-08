# Semantics: Curriculum Layer (Phase C10)

Status: **CONTRACT for Phase C10** (implemented in `engines/curriculum/`)
Engine version: 0.1.0 · Cross-cutting syllabus item: lessons + exercises

## What the layer is

A static, versioned catalog of lessons and exercises, plus a **deterministic
grader**. The existing engines are the graders: a submission is checked by
running the relevant engine, never by string comparison alone and never by an
LLM. Same submission ⇒ byte-identical graded result (the determinism contract
extends to grading).

## Catalog

- `Lesson`: `id`, `unit` (1–6 or "cross"), `title`, `summary`, `key_points`
  (ordered), `related_exercise_ids`.
- `Exercise`: `id`, `lesson_id`, `kind`, `prompt`, `hint`, `answer_kind`
  ("numeric" | "binary" | "expression").
- The catalog is code (not user data): it ships with the engine, is covered by
  tests, and changes only via a release. `CATALOG_VERSION` bumps on any change.

## Exercise kinds and their graders (deterministic, evidence-based)

| kind | Engine used | Pass condition |
|---|---|---|
| `numeric` | numsys | Parsed integer equals the precomputed answer (accepts `0x…`/`0b…`/decimal) |
| `binary` | numsys | Digit-normalized bit string equals the expected bit pattern |
| `expression_equiv` | boolean | Submission parses; truth-table equivalence with the target over the union of variables (EXHAUSTIVE(2^n)) |
| `minimize` | boolean + kmap | Equivalence with the original function AND literal count ≤ the QM solution's |
| `flipflop_next` | sequential | Next-state value matches the characteristic table |
| `cpu_predict` | cpu8086 | Parsed value equals the register value from a bounded engine run of the pinned program |

Evidence lines cite the engine facts that decided the grade (e.g. "16-row
truth-table equivalence held", "engine run: AX = 8"). Failures state what the
engines observed, not "wrong, try again".

## Grading result

```json
{ "exercise_id": "…", "passed": true, "scope": "EXHAUSTIVE(16)",
  "feedback": "…", "evidence": ["…"] }
```

`scope` labels the check exactly like every other engine result: EXHAUSTIVE(k)
for truth-table/equivalence checks, BOUNDED(k) for the pinned CPU run.

## Errors

`CurriculumError` (subclass of `LogicEngineError`) with categories:
`UNKNOWN_EXERCISE`, `UNKNOWN_LESSON`, `BAD_SUBMISSION` (unparseable or wrong
answer shape — always actionable, never silent). Engine-level failures inside
grading (e.g. an assembler error on a pinned program) are contract bugs:
tests pin every pinned program to run clean.

## Out of scope

User-authored lessons, progress persistence (no accounts — D5), adaptive
sequencing, and the "AI in Digital Systems" module (a future phase).

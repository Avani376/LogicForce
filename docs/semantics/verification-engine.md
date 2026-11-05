# Semantics: Verification Engine v1

Status: **CONTRACT for Phase 3** (implemented in `engines/verify/verify_engine`)
Engine version: 0.3.0 · Property schema version: **1**

## What v1 verifies

Two property kinds, both checked **exhaustively** over their (bounded) model space:

1. `combinational_invariant` — a boolean expression over a schema-v1 circuit's
   primary outputs must evaluate to `1` for **every** input vector
   (`EXHAUSTIVE(2^n)`, n ≤ 12 — the truth-table bound).
2. `fsm_invariant` — a boolean expression over an FSM's declared outputs must
   evaluate to `1` in **every reachable state** (`EXHAUSTIVE(k of N states)`).

Anything outside these bounds is refused with an `INCOMPLETE` verdict and a reason —
never silently bounded, never sampled.

## Property document (schema 1)

```json
{
  "property_schema_version": 1,
  "id": "P1",
  "kind": "fsm_invariant",
  "statement": "Two conflicting directions never green simultaneously",
  "expression": "!(north_green & east_green)"
}
```

- `id`: non-empty string. `kind`: one of the two kinds above. `statement`: optional
  human text (display only). `expression`: the formal property (below).
- Referential rule: every signal name in `expression` must exist in the model's
  signal universe (primary outputs for combinational; declared outputs for FSM) —
  otherwise `PROPERTY_SIGNAL_UNKNOWN` (fail-fast at load, complete list).

## Expression language (v1)

- Literals `0`, `1`; signal names `[A-Za-z_][A-Za-z0-9_]*`; operators `!` (not),
  `&` (and), `^` (xor), `|` (or); parentheses. Whitespace ignored.
- **Precedence (tightest first): `!`, then `&`, then `^`, then `|`.** All binary
  operators are left-associative. This is fixed normatively for reproducibility.
- Evaluation uses the **four-valued domain and v1 gate tables** (`logic-values.md`):
  `!` is NOT, `&` is AND, `|` is OR, `^` is XOR. There are no short-circuits —
  every operand is evaluated (evaluation has no side effects; determinism only).
- Syntax errors raise `PROPERTY_SYNTAX_ERROR` with character position.

## The unknowns-are-not-safety rule

An invariant **holds** only where the expression evaluates to exactly `1`.
`X` (or `Z`) counts as a **violation**. Rationale: safety claims cannot rest on
unknowns; a design that produces X under legal inputs is not proven safe. This is
checked and reported, never assumed away.

## Reachability and output assignment (FSM)

- Reachable states: BFS from `initial` over **all** binary input vectors
  (`2^|inputs|`), matching transitions as in `fsm-model.md` (first match in
  document order; unmatched vectors hold the state).
- Output assignment: each state's output vector is the `outputs` of the **first
  transition (document order) that enters it**; the initial state uses the first
  transition (document order) whose source is the initial state. The convention is
  deterministic and reported in `assumptions`.
- Bounds: states ≤ 256 and inputs ≤ 10 (2^10 vectors per state ⇒ ≤ 262,144 firings).
  Beyond either: verdict `INCOMPLETE`, reason `MODEL_TOO_LARGE` with the numbers.

## Verdicts and reports

```json
{
  "schema_version": 1,
  "engine_version": "0.3.0",
  "input_hash": "sha256-hex",
  "property": { "id": "P1", "statement": "…", "expression": "!(a & b)" },
  "model_kind": "fsm",
  "verdict": "PASS",
  "scope": "EXHAUSTIVE(4 of 4 states)",
  "explored_cases": 4,
  "assumptions": ["output assignment: first entering transition (document order)"],
  "counterexample": null,
  "reason": null
}
```

- `PASS` — expression evaluated to `1` in every explored case; scope label states
  exactly what was explored.
- `FAIL` — at least one case where the expression ≠ 1. The report carries a
  **replayable counterexample**:
  - combinational: `{ "inputs": {...}, "outputs": {...} }` — replay via
    `POST /api/circuits/simulate` with that vector.
  - FSM: `{ "inputs_sequence": [...], "violating_state": "…", "outputs": {...} }` —
    replay via `POST /api/fsm/simulate`; the last cycle must reach the violating
    state. The sequence is the BFS shortest path from `initial`.
- `INCOMPLETE` — model outside bounds or malformed model data at verification time;
  `reason` is mandatory; `counterexample` is null. INCOMPLETE is never rendered as
  a pass.

## Independence rule

Verdicts come only from this engine. The API, the UI, and (later) the AI layer may
render a report but never produce a verdict.

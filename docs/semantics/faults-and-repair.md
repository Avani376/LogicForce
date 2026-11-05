# Semantics: Fault Injection and Repair v1

Status: **CONTRACT for Phase 4** (implemented in `engines/faults/fault_engine` and
`engines/repair/repair_engine`)
Engine version: 0.4.0 · Fault schema version: **1**

## Core principle: faults are document transformations

Every fault operator is a pure function `(model document, fault document) → faulty
model document`. The nominal document is **never mutated**. A fault is therefore
deterministic and replayable: applying the same fault to the same model yields a
byte-identical faulty model. The faulty model is then checked by the *existing*
deterministic engines (simulate, truth-table, verify) — fault injection adds no new
evaluation semantics of its own.

## Fault document (schema 1)

```json
{
  "fault_schema_version": 1,
  "id": "F-double-green",
  "operator": "transition_redirect",
  "target": { "transition_index": 1 },
  "params": { "to": "east_green", "set_outputs": { "north_green": "1", "east_green": "1" } }
}
```

Typed application errors: `FAULT_SCHEMA_ERROR` (structural),
`FAULT_TARGET_NOT_FOUND` (index/component/pin does not exist),
`FAULT_APPLICATION_ERROR` (semantically impossible: unknown state, unknown
output, flip of a non-binary value, stuck-at on an output pin).

## Operators (v1, authoritative list)

### FSM models (schema-v2 FSM documents)

| Operator | Target | Params | Effect |
|---|---|---|---|
| `transition_redirect` | `{transition_index}` | `to?: state name`, `set_outputs?: {name: value}` | changes the transition's target state and/or merges output values |
| `transition_remove` | `{transition_index}` | — | removes the transition (its inputs become unmatched ⇒ hold, per `fsm-model.md`) |
| `output_flip` | `{transition_index}` | `{output: name}` | flips one declared output bit `0 ↔ 1` |

### Combinational models (schema-v1 circuit documents)

| Operator | Target | Params | Effect |
|---|---|---|---|
| `gate_swap` | `{component_id}` | `{to: type}` | substitutes the component type (revalidation of the faulty document catches arity damage) |
| `stuck_at` | `{component_id, pin}` | `{value: "0" \| "1"}` | rewires that **input** pin to a fresh `CONST0`/`CONST1` — the classic stuck-at fault |

Rules:

- `stuck_at` applies to input pins only (`FAULT_APPLICATION_ERROR` on output pins).
- `output_flip` requires the output to be declared on that transition with a
  binary value.
- `transition_redirect`'s `to` must be a declared state; `set_outputs` names must
  be declared outputs with binary values (merged into existing outputs).
- The faulty model is fully re-validated by the consuming engine; a fault that
  produces an invalid model (e.g. a `gate_swap` breaking a width) is still
  *applied* — detection then reports the validation failure as the experiment's
  outcome (a broken circuit is a legitimate fault result, not a crash).

## Fault experiment

Request: nominal model + fault + a **property suite** (Phase-3 property documents).
Pipeline:

1. Apply the fault → faulty model.
2. **Behavior probe** (bounded, labeled):
   - combinational: full truth-table diff nominal vs faulty —
     `EXHAUSTIVE(2^n rows)`, reports differing-row count and the first differing
     row (inputs + both output vectors);
   - FSM: vector sweep — every input vector fires once, in MSB order, for
     `2^|inputs|` cycles — `BOUNDED(2^|inputs| cycles)`, reports the first
     diverging cycle (inputs + both states + both outputs).
3. **Detection**: each property in the suite is verified against the faulty model
   (`verify_engine`). A property that **PASSes on nominal and FAILs on faulty**
   detects the fault. A fault no property detects is reported `detected: false` —
   that is a statement about the suite, and it is kept honest.

Report shape:

```json
{
  "schema_version": 1,
  "engine_version": "0.4.0",
  "input_hash": "sha256-hex",
  "fault": { … },
  "applied": true,
  "nominal_hash": "…", "faulty_hash": "…",
  "behavior": { "kind": "fsm", "scope": "BOUNDED(2 cycles)", "first_divergence": { … } | null },
  "checks": [ { "id": "P1", "nominal_verdict": "PASS", "faulty_verdict": "FAIL", "detected": true, "counterexample": { … } } ],
  "detected": true
}
```

## Repair search

Request: nominal model + faulty model + the property suite + `max_candidates`
(1–32, default 16). The v1 strategy is **delta-guided repair toward the nominal
reference**:

1. Diff faulty vs nominal (FSM: per-transition `to`/`outputs` fields aligned by
   index; combinational: per-component type, per-net driver by id). **v1 limitation**:
   FSM transitions are index-aligned — inserting/removing a *middle* transition shifts
   every later index and degrades delta quality (content-based alignment is future
   work); tail removals align cleanly.
2. Each differing field yields one **candidate patch** restoring that field to the
   nominal value (single-field patches; deterministic order: index, then field name).
3. Candidates are capped at `max_candidates` — the cap is reported, never hidden.
4. Every candidate is applied and **re-verified against the full property suite**;
   a candidate is `valid` only when every property PASSes on it.
5. `repaired_model` is the first valid candidate (deterministic order); if none is
   valid, `repaired_model` is null and the report says so — an unrepairable model
   within the operator set is a result, not an error.

Report shape:

```json
{
  "schema_version": 1,
  "engine_version": "0.4.0",
  "input_hash": "sha256-hex",
  "candidates_considered": 3,
  "cap": 16,
  "candidates": [ { "patch": { … }, "valid": true, "verdicts": [ { "id": "P1", "verdict": "PASS" } ] } ],
  "repaired_model": { … } | null,
  "re_verified": true
}
```

## Honesty rules

- "Repaired" is claimed only after the **full property suite** PASSes on the
  repaired model — equivalence to nominal beyond the suite is **not** claimed.
- Unrequested semantics (missing clock events, peripheral failures) are not
  modeled in v1 and are listed in `docs/LIMITATIONS.md`.
- Every report carries scope labels for its probes and checks.

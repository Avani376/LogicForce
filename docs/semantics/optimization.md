# Semantics: Optimization Engine v1

Status: **CONTRACT for Phase 5** (implemented in `engines/optimize/optimize_engine`)
Engine version: 0.5.0

## Scope and honesty

- Optimizes **combinational schema-v1 circuits** only. FSM optimization is future work.
- **No delay model exists** in this platform — "estimated delay" is therefore *not*
  reported. Metrics are abstract gate-level counts, labeled as such:
  - `gate_count`: non-I/O, non-constant components
  - `component_count`: all components
  - `logic_depth`: longest input→output path in gate levels (abstract structural
    metric — **not** measured or estimated hardware delay)
- Every claim about improvement cites the metric that improved and the equivalence
  evidence that proves behavior is preserved.

## Correctness gate (non-negotiable)

A candidate transformation is accepted only when **both** hold:

1. **Behavioral equivalence**: the transformed circuit's full truth table is
   identical to the original's (`EXHAUSTIVE(2^n)`, n ≤ 12). Circuits with more
   than 12 primary inputs cannot be verified exhaustively → optimization is
   **refused** with verdict `INCOMPLETE` and reason `MODEL_TOO_LARGE`.
2. **Property suite**: every provided Phase-3 property PASSes on the result.

If a pass fails either gate it is **rejected and reverted**, and optimization
stops (the transformation classes below are provably safe; a rejection indicates
an engine defect and must be investigated, not bypassed).

## Transformation classes (v1)

All transformations are local rewrites on the circuit document, applied in
deterministic component-id order:

| Class | Pattern | Rewrite |
|---|---|---|
| `double_negation` | NOT whose sole driver is a NOT | sinks of the outer gate re-wire to the inner gate's input net; outer gate removed |
| `buffer_elimination` | BUFFER | sinks of its `out` net re-wire to the net driving its `a` pin; buffer removed |
| `constant_fold` | AND with a `CONST0` input → `CONST0`; OR with `CONST1` → `CONST1`; NAND with `CONST0` → `CONST1`; NOR with `CONST1` → `CONST0`; XOR with `CONST0` → removed (pass-through); XOR with `CONST1` → NOT; XNOR with `CONST0` → NOT; XNOR with `CONST1` → removed; AND with all inputs `CONST1` → pass-through; OR with all inputs `CONST0` → pass-through; NAND all `CONST1` → NOT; NOR all `CONST0` → NOT |
| `duplicate_merge` | two gates of the same type with identical input-net sets | all sinks of one output net re-wire to the other's; the duplicate is removed |

Pass-through rewrites re-wire the consumers of the removed gate's output net to
the net that drove its (now-known) dominant/identity input. Gates whose inputs
are partially constant fold per the four-valued tables — the rewrite is only
emitted when the folded value is a constant or a single remaining signal.

## Passes and report

Optimization runs up to `max_passes` passes (default 8, hard cap 10). Each pass:
apply every applicable transformation (id order) → re-validate → equivalence
check → property suite. The report records, per pass, the transformations applied
and the metrics after the pass.

```json
{
  "schema_version": 1,
  "engine_version": "0.5.0",
  "input_hash": "sha256-hex",
  "metrics_before": { "gate_count": 7, "component_count": 10, "logic_depth": 4 },
  "metrics_after":  { "gate_count": 3, "component_count": 6, "logic_depth": 2 },
  "passes": [ { "pass": 1, "applied": ["constant_fold: G_and (CONST0 dominant)"], "metrics": { … }, "equivalence": { "equal": true, "scope": "EXHAUSTIVE(4 input vectors)" }, "suite_verdicts": [ { "id": "P", "verdict": "PASS" } ] } ],
  "final_model": { … },
  "verdict": "OPTIMIZED",
  "scope": "EXHAUSTIVE(4 input vectors) equivalence per pass",
  "assumptions": ["logic_depth is an abstract gate-level metric, not hardware delay"]
}
```

- `verdict`: `OPTIMIZED` (≥1 transformation accepted) or `NO_CHANGE_APPLICABLE`
  (the circuit already satisfies every v1 transformation).
- Metrics compare before vs after; a pass that would worsen any accepted metric is
  not possible under the classes above, and the equivalence gate protects behavior
  regardless.

## Out of scope for v1

Karnaugh-map resynthesis, mux-tree restructuring, FSM state minimization, technology
mapping, delay-driven rewrites, physical metrics. None are claimed.

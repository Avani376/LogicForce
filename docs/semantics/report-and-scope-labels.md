# Semantics: Result Reports and Scope Labels

Status: schemas **IMPLEMENTED** for simulation/validation/truth-table; the verification
report schema is **DEFINED NOW, implemented in Phase 3**.
Engine version: 0.1.0

## Scope labels (non-negotiable rule)

Every claim-producing result carries exactly one scope label:

| Label | Meaning |
|---|---|
| `EXHAUSTIVE(k)` | All `k` cases of a finite space were checked. Nothing was skipped. |
| `BOUNDED(k)` | Checking stopped at a limit `k` (depth, states, iterations). Result is not universal. |
| `SAMPLED(n)` | `n` cases were sampled; no coverage claim. |
| `INCOMPLETE` | Checking could not finish (error, timeout, unsupported model). |

The UI and docs must render this label next to any verdict. A PASS/FAIL without a scope
label is a contract violation.

## ValidationReport

```json
{
  "schema_version": 1,
  "engine_version": "0.1.0",
  "ok": false,
  "errors":   [ { "code": "DANGLING_INPUT_PIN", "message": "…", "component_id": "G1" } ],
  "warnings": [ { "code": "UNREAD_NET", "message": "…", "net_id": "n7" } ]
}
```

## SimulationResult

```json
{
  "schema_version": 1,
  "engine_version": "0.1.0",
  "input_hash": "sha256-hex",
  "scope": "SINGLE_VECTOR",
  "outputs": { "sum": "1", "carry_out": "0" },
  "trace": [ { "seq": 0, "delta": 0, "net": "n_a", "old": "X", "new": "1",
               "cause": { "type": "primary_input", "component": "IN_a" } } ],
  "event_count": 6
}
```

`scope` is the fixed label `SINGLE_VECTOR`: one input vector was evaluated; nothing broader
is claimed. `outputs` keys are the OUTPUT component names, values are `"0"|"1"|"X"|"Z"`.

## TruthTableResult

```json
{
  "schema_version": 1,
  "engine_version": "0.1.0",
  "input_hash": "sha256-hex",
  "scope": "EXHAUSTIVE(4)",
  "input_names": ["a", "b"],
  "output_names": ["sum", "carry_out"],
  "rows": [ { "inputs": { "a": "0", "b": "0" }, "outputs": { "sum": "0", "carry_out": "0" } } ]
}
```

- Inputs are enumerated in ascending `params.name` order; the first name is the most
  significant bit of the row index.
- Bound: primary input count ≤ 12 (4096 rows). Exceeding it returns
  `TRUTH_TABLE_LIMIT_EXCEEDED` rather than a truncated table — truncation would silently
  convert an exhaustive claim into a bounded one.

## VerificationReport (schema defined now; engine in Phase 3)

```json
{
  "schema_version": 1,
  "engine_version": "…",
  "input_hash": "…",
  "property": { "id": "P1", "statement": "G !(NorthGreen & EastGreen)" },
  "verdict": "PASS | FAIL | INCOMPLETE",
  "scope": "EXHAUSTIVE(16)",
  "explored_states": 16,
  "assumptions": ["…"],
  "counterexample": [ { "step": 0, "state": "…", "inputs": {}, "outputs": {} } ]
}
```

Rules already binding by convention: `FAIL` requires a reproducible counterexample whenever
the model class permits one; `INCOMPLETE` requires a reason string; verdicts may only be
produced by the verification engine, never by AI or the UI.

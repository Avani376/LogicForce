# Semantics: Abstract FSM Model (v2.0)

Status: **CONTRACT for Phase 2** (`sequential_engine.fsm`) — this module is the
stepping stone to the Phase 3 verification engine (reachability + counterexamples).

## FSM JSON schema (version 1)

```json
{
  "fsm_schema_version": 1,
  "name": "traffic_light",
  "inputs": ["ped_button"],
  "outputs": ["north_green", "east_green"],
  "states": ["north", "north_yellow", "east", "east_yellow"],
  "initial": "north",
  "transitions": [
    {
      "from": "north",
      "when": { "ped_button": "0" },
      "to": "north",
      "outputs": { "north_green": "1", "east_green": "0" }
    },
    {
      "from": "north",
      "when": { "ped_button": "1" },
      "to": "north_yellow",
      "outputs": { "north_green": "0", "east_green": "0" }
    }
  ]
}
```

Rules:

- `when` is an **exact partial assignment**: names listed must match the cycle's
  input values exactly; names omitted match any value. Deterministic matching order:
  1. All transitions from the current state whose `when` matches exactly.
  2. If none matched, the state **holds** and the cycle is flagged
     `"unmatched": true` in the trace — a gap in the transition table is a modeling
     fact, never silently patched.
- If two transitions from the same state match the same vector, that is a
  **construction error** (`AMBIGUOUS_TRANSITION`) reported at load time, not at
  runtime.
- `outputs` is Moore-style (functions of the state, attached to transitions as the
  output vector for the *destination* state). Mealy machines are expressible by
  varying outputs across transitions into the same state, but the model treats
  outputs as per-transition data.
- Unknown states, unknown input/output names, transitions to/from unknown states,
  or a missing `initial` → `FSM_SCHEMA_ERROR` (typed, fail-fast).
- `initial` must be in `states`.

## Simulation

Input: `input_sequence` (list of input-vector maps, each length ≤ 256).
Output per cycle: `{cycle, inputs, state, outputs, matched, unmatched}`.
Deterministic: same FSM + same sequence ⇒ byte-identical trace.

## Reachability (viz + Phase 3 foundation)

`fsm_reachable(fsm)` returns all states reachable from `initial` via the transition
relation (BFS over the explicit table; the table is finite, so this is
`EXHAUSTIVE(states)` — the label is attached to the result).

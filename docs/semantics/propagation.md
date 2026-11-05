# Semantics: Propagation, Evaluation Order, and Trace Events

Status: **IMPLEMENTED** (contract for `engines/logic/logic_engine/simulator.py`)
Engine version: 0.1.0

## Scope of v1

Pure **combinational** propagation. Sequential elements (flip-flops, clock edges) are Phase 2
and will extend, not replace, these rules. No delay model exists: this is a zero-delay,
value-change model, which is the honest semantics for gate-level logic behavior (not timing).

## Preconditions

A circuit is simulable only if `validate()` returns `ok = true`. In particular:

1. The component graph must be **acyclic** with respect to output→input dependence.
   Cycles are reported by validation as `COMBINATIONAL_LOOP` and simulation refuses to run.
   Delta-cycle convergence for intentional loops is therefore **not implemented in v1** and
   is listed in `docs/LIMITATIONS.md`.
2. Every gate/OUTPUT input pin is connected to exactly one net.
3. Every net has exactly one driver.

## Evaluation algorithm (topological fast path)

1. Compute each component's **depth**: `depth(INPUT | CONST) = 0`; for any other component,
   `depth(c) = 1 + max(depth(driver(d)) for each driving net d of c's input pins)`.
2. Evaluate components in order `(depth ascending, id ascending)` — the id tie-break is
   normative for determinism. `INPUT`/`CONST` components are sources and need no evaluation.
3. For each component in that order, compute its output pin value from its input pin values
   using the tables in `logic-values.md`, and assign it to the driven net.

Because the graph is validated acyclic, **one pass over topological layers is exact**: no
further iteration can change any value. This is the documented fast path; an event-driven
delta-cycle scheduler is unnecessary for acyclic combinational circuits and is deferred
(Phase 2) where clocked state makes it meaningful.

## Trace events

Every net whose value **changes** during evaluation emits one event. Fields:

```json
{
  "seq": 7,          // monotonically increasing emission counter, starts at 0
  "delta": 2,        // evaluation layer (component depth) at which the change occurred
  "net": "n_cout",   // net id
  "old": "X",        // value before (initial net value is always "X")
  "new": "1",        // value after
  "cause": {         // what drove the change
    "type": "gate",  // "primary_input" | "constant" | "gate"
    "component": "G_cout"
  }
}
```

Ordering rules:

- Events are emitted in `(delta ascending, component id ascending)` order — the same order
  as evaluation. `seq` reflects that order.
- Initial state: all nets start `X`; primary inputs and constants are assigned first at
  `delta = 0` (events with `type: "primary_input"` / `"constant"` only if they change `X`).
- A change from `X`→`X` is not an event (no-op). `Z` only appears if a driver drives `Z`,
  which no v1 component does; the field is kept for schema stability.

## Determinism contract

For the same `circuit` JSON, same `inputs` vector, and same `engine_version`, the simulation
result — outputs, event list including `seq`/`delta` assignment — is **byte-identical** across
runs, processes, and machines. Enforcement: golden determinism test replays each fixture
simulation 100× and compares serialized bytes. No clocks, no randomness, no wall-time anywhere
in the engine.

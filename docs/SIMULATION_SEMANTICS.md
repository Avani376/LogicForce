# Simulation Semantics — LogicForge (top-level summary)

This file summarizes the normative contracts. The detailed, binding documents live in
[`docs/semantics/`](semantics/):

| Contract | File | Status |
|---|---|---|
| Logic values {0,1,X,Z} + gate truth tables | [`semantics/logic-values.md`](semantics/logic-values.md) | **Implemented & tested** |
| Propagation, evaluation order, trace events, determinism | [`semantics/propagation.md`](semantics/propagation.md) | **Implemented & tested** |
| Circuit graph JSON schema v1 + validation codes | [`semantics/circuit-graph-schema.md`](semantics/circuit-graph-schema.md) | **Implemented & tested** |
| Clock-edge rules, flip-flop tables, tick order (v2) | [`semantics/clock-edge-rules.md`](semantics/clock-edge-rules.md) | **Implemented & tested (Phase 2)** |
| Circuit graph JSON schema v2 (sequential types) | [`semantics/circuit-graph-schema-v2.md`](semantics/circuit-graph-schema-v2.md) | **Implemented & tested (Phase 2)** |
| Abstract FSM model | [`semantics/fsm-model.md`](semantics/fsm-model.md) | **Implemented & tested (Phase 2)** |
| Report schemas + scope labels | [`semantics/report-and-scope-labels.md`](semantics/report-and-scope-labels.md) | Simulation/validation/truth-table **implemented**; verification schema defined for Phase 3 |

## One-paragraph model

A circuit is a validated acyclic directed graph of components (gates, constants, primary
inputs/outputs) connected by single-driver nets. Values are four-valued (`0`, `1`, `X`,
`Z`). A simulation assigns primary inputs (omitted ⇒ `X`), then evaluates components in
`(depth, id)` topological order using the documented gate tables. Every net value change
emits a trace event `{seq, delta, net, old, new, cause}`. For identical circuit JSON,
input vector, and engine version, the result is byte-identical every run — enforced by
test, not by intention.

## Not modeled (v1)

Delays/timing, tri-state bus resolution, sequential state (Phase 2), delta cycles for
intentional loops (D8), conditional-clock behavior. See `LIMITATIONS.md`.

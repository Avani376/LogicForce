# Verification Model — LogicForge

Status: **implemented** (verify_engine 0.3.0, Phase 3) — invariants over bounded
models with exhaustive scope labels and replayable counterexamples. Normative
contract: [`semantics/verification-engine.md`](semantics/verification-engine.md).

## What verification means here

Verification is a deterministic engine computation over a design model: it checks stated
properties against reachable behavior and reports a verdict with an explicit scope. It is
not AI, not sampling of demo examples, and never a UI-side assertion.

## Property language (committed progression)

| v | Property kinds | Algorithm |
|---|---|---|
| Phase 1 (done) | Truth-table equivalence of a circuit against expected rows | exhaustive enumeration (bounded to 12 inputs) |
| Phase 3 (done) | Invariants over outputs: `G !(A & B)` — combinational (all input vectors) and FSM (all reachable firings) | exhaustive over the bounded model; refusals beyond bounds become INCOMPLETE with reason |
| Later | Bounded reachability for larger models, transition constraints | bounded model checking; scope label `BOUNDED(k)` mandatory |

## Verdicts

- `PASS` — property holds over the explored space, with the scope label proving what was
  explored.
- `FAIL` — property violated; report carries a **replayable counterexample** (input/state
  sequence) whenever the model class permits producing one.
- `INCOMPLETE` — the check could not finish; report carries the reason. Never presented as
  PASS.

## Scope labels

Defined normatively in [`semantics/report-and-scope-labels.md`](semantics/report-and-scope-labels.md):
`EXHAUSTIVE(k)`, `BOUNDED(k)`, `SAMPLED(n)`, `INCOMPLETE`. UI rendering rule: every verdict
is displayed adjacent to its scope label.

## Reference property (signature use case, Appendix A)

Statement: “Two conflicting traffic directions must never have green outputs active
simultaneously.”
Formal: `G !(NorthGreen AND EastGreen)` over the FSM's reachable state space.
Report: PASS if no reachable violating state exists within the explored model; otherwise
FAIL with the state sequence and the first violating state; if the check is bounded, the
label says so explicitly.

## Anti-goals

- No universal-proof claims for unbounded or unsupported systems.
- No AI-authored verdicts. AI may summarize a VerificationReport only after it exists.
- No “verified” badge in the UI without a real report object behind it.

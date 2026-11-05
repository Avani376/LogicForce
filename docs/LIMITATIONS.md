# Limitations and Honest Claims — LogicForge

Current as of Phase 2 build sessions (logic engine 0.1.0, sequential engine 0.2.0). This
file is the anti-overclaim contract: nothing below is “planned soon” marketing; it is a
list of what the platform cannot do today.

## Engine (implemented scope)

- **Sequential semantics are cycle-accurate abstractions, not timing.** One implicit
  global clock; every tick is one rising edge. No setup/hold, propagation delays, pulse
  widths, half-cycle clocks, clock gating, per-component clock nets, or glitch analysis —
  none are claimed (`docs/semantics/clock-edge-rules.md`).
- **Power-on state is all-zero.** X initial states are not supported in v2.0.
- **Async controls are sampled per cycle** from the settled network and force state
  immediately; unknown async controls honestly force X.
- **SR=11 and unknown controls resolve to X** (honest four-valued behavior), never to a
  convenient 0/1.
- **Shift registers are not primitives** — composable from DFFs. Counters wrap at 2^w;
  mod-N needs user combinational logic.
- **Combinational loops are still rejected** in the combinational subnet; feedback
  through state components is legal and expected.
- **No tri-state resolution.** Multi-driver nets are errors; `Z` exists in the value
  domain but no component drives it.
- **Truth tables are exhaustive up to 12 primary inputs**; sequential runs are hard-bounded
  at 256 cycles — refused, never truncated.

## Platform scope

- **No verification engine yet** (Phase 3): no property checks, no counterexamples. The
  FSM reachability module computes EXHAUSTIVE(states) over the declared table only.
- **Fault model v1 scope**: document-transformation operators only (FSM transition
  edits/output flips; combinational gate swaps and stuck-at rewire-to-constant).
  Missing clock events, peripheral failures, and bridging faults are not modeled.
  Repair is delta-guided toward a passing reference — it does not claim equivalence
  beyond the checked property suite. Optimization (Phase 5) is not started.
- **No 8086 emulator, interrupts, or co-simulation** (Phases 6–8).
- **No AI assistance** (Phase 9). When it arrives it will be advisory and labeled; it will
  not compute results.
- **No persistence, users, auth, or multi-tenancy** (D5): the API is a stateless compute
  service. Anyone with network access to the dev server can submit circuits.
- **No Docker/deployment artifacts** (D6): local development only.
- **Workspace**: sequential circuits are simulable in the UI (example loader + waveform
  viewer) but sequential components cannot yet be placed from the palette, and FSM
  state-transition visualization is not rendered as a graph yet (transition data is
  available via the API).
- **Single-machine testing**: validated on Windows (Python 3.13, Node 24) and CI targets
  Ubuntu (Python 3.12, Node 20); no claim about other environments.

## Metrics honesty

Any future performance numbers will be measured on this repository's own benchmarks and
labeled with the machine they were measured on. Estimated metrics (e.g., logic depth vs
physical delay) will be labeled as abstract-model estimates, never as hardware behavior.

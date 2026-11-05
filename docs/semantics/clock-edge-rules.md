# Semantics: Clock-Edge Rules and Sequential Simulation (v2)

Status: **CONTRACT for Phase 2** (implemented in `engines/sequential/sequential_engine`)
Engine version: 0.2.0 · Schema version: **2** (extends circuit schema v1; v1 stays
combinational-only and fully supported)

## Time model

- One **implicit global clock**. Every simulation *tick* is one rising clock edge.
  There is no half-cycle evaluation, no per-component clock nets, and no clock gating
  in v2.0. (Rationale: a single scheduler with documented event ordering; per-gate
  clock nets add race conditions without educational value yet.)
- A simulation run is `N` ticks (`1 ≤ N ≤ 256`). Each tick has a fixed five-stage
  order (below). **No delays, no setup/hold, no pulse widths** are modeled — this is
  cycle-accurate abstract timing, and it is the only timing claim this engine makes.

## Tick order (normative — five stages per cycle)

1. **Async sample.** Every state component's async pins (`pre`, `clr` / `clr`) are
   read from the *current* input vector (they are combinational inputs sampled at
   cycle start, not mid-cycle events).
   - `pre=1, clr=0` → state forced to 1 (async set)
   - `pre=0, clr=1` → state forced to 0 (async clear)
   - `pre=1, clr=1` → **invalid** → state becomes `X`
   - `pre` or `clr` is `X`/`Z` → **invalid** → state becomes `X` (honesty rule: an
     unknown control input cannot be assumed inactive)
2. **Settle.** The combinational network is evaluated exactly once with the *current*
   state values on all `q`/`qn` feedback nets, using the v1 propagation rules
   (`docs/semantics/propagation.md`). Primary inputs for this cycle come from the
   input vector (missing names default to `X`, unchanged rule).
3. **Capture.** Each state component computes its *next state* from the settled
   input pins via its characteristic table (below). No component sees another
   component's new state — all captures read the settled network only.
4. **Commit.** All state components update **simultaneously**. There is no
   component ordering at the edge (simultaneous commit is what makes this
   deterministic and race-free). Events are recorded afterwards in component-id
   order.
5. **Record.** Outputs, state, and waveform entries for this cycle are snapshotted.

## Characteristic tables (normative)

All tables use the four-valued domain {0,1,X,Z}. `Q` is the state *before* the edge.

### D flip-flop (`DFF`, pins: `d`, `pre`, `clr`; out `q`, `qn`)

| d | next Q |
|---|---|
| 0 | 0 |
| 1 | 1 |
| X or Z | X |

`qn` is always `NOT(q)` (v1 NOT table).

### T flip-flop (`TFF`, pins: `t`, `pre`, `clr`)

| t | next Q |
|---|---|
| 0 | Q (hold) |
| 1 | NOT(Q) (toggle) |
| X or Z | X |

### JK flip-flop (`JKFF`, pins: `j`, `k`, `pre`, `clr`)

| j | k | next Q |
|---|---|---|
| 0 | 0 | Q (hold) |
| 0 | 1 | 0 (reset) |
| 1 | 0 | 1 (set) |
| 1 | 1 | NOT(Q) (toggle) |
| any X/Z | any | X |

### SR flip-flop (`SRFF`, pins: `s`, `r`, `pre`, `clr`)

| s | r | next Q |
|---|---|---|
| 0 | 0 | Q (hold) |
| 0 | 1 | 0 (reset) |
| 1 | 0 | 1 (set) |
| 1 | 1 | **X (forbidden — reported honestly, never resolved)** |
| any X/Z | any | X |

### Register (`REGISTER`, width w ∈ [1,16]; pins `d0..d(w-1)`, `pre`, `clr`)

Per bit: `di` → `qi` follows the D table; `pre`/`clr` apply to **all bits** (async
stage 1). Out pins `q0..q(w-1)` only (no `qn` on multi-bit components).

### Counter (`COUNTER`, width w ∈ [1,16]; pins `en`, `clr`; out `q0..q(w-1)`)

| en | next |
|---|---|
| 0 | Q (hold) |
| 1 | Q + 1 mod 2^w (binary up-count, wraps) |
| X or Z | all bits X |

`clr` is **async** (stage 1) and forces 0. There is no preset on counters (loading
is composable with feedback logic; not built in). `en` is the only synchronous
control. Wrap at `2^w − 1 → 0` is automatic and documented; mod-N behavior is built
combinatorially by the user (educational value, not a parameter).

## Power-on state

All state bits start at **`0`**. Rationale: deterministic and reproducible beats
"unknown at power-on" — and every golden test depends on it. `X` initial states are
deliberately *not* supported in v2.0 (they are a Phase 3+ modeling question).

## Required pins and tie-offs

Every async pin (`pre`/`clr`) and every synchronous input pin is a **required,
connected** input pin — a dangling one is a validation error (`DANGLING_INPUT_PIN`).
Tie-offs use `CONST0`/`CONST1` so intent is explicit in the document. This is the
same strictness as v1 (decision D4) and prevents silent misbehavior.

## Events and waveforms

```json
{ "cycle": 3, "component": "FF1", "pin": "q", "old": "0", "new": "1", "cause": "clock_edge" }
```

`cause` is `clock_edge` (stage 4 commit) or `async` (stage 1 override). Events are
emitted per changed state bit, ordered by `(cycle, component id)` — the commit is
simultaneous but the *report* order is deterministic. Waveforms map signal keys to
per-cycle value arrays:

- `"in:<name>"` — primary input `<name>`
- `"out:<name>"` — primary output `<name>`
- `"<component>.q"` — a state component's `q` (register/counter: per-bit keys
  `q0`, `q1`, …)

All waveforms have exactly `N` entries (one per cycle, post-commit state).

## Determinism contract

Same circuit + same input sequence + same engine version ⇒ byte-identical result
(cycles, events, waveforms). Enforced by a 100× replay test on every sequential
golden fixture. The v1 trace contract within each settle stage is unchanged.

## Out of scope for v2.0 (honest boundaries)

Setup/hold, propagation delays, glitch analysis, half-cycle clocks, clock gating,
per-component clock nets, tri-state on state outputs, X power-on states, shift
registers as primitives (composable from `DFF`s), mod-N counter parameters.

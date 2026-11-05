# Semantics: Circuit Graph JSON Schema v2 — Sequential Extension

Status: **CONTRACT for Phase 2** (implemented in `engines/sequential/sequential_engine`)
Schema version: **2** · Engine version: 0.2.0

Schema v2 is a strict superset of v1: every v1 document is a valid v2 document with
the same meaning; v1 documents stay combinational-only under `logic_engine`.
`schema_version` must be exactly `2` for the sequential engine (strict, like v1 —
`UNSUPPORTED_SCHEMA_VERSION` otherwise).

## Top-level document

Same shape as v1 (`schema_version`, `name?`, `components[]`, `nets[]`) — components
may additionally use the sequential types below. `docs/semantics/circuit-graph-schema.md`
(v1 rules) remains normative for everything not overridden here.

## Sequential component types

| Type | Input pins | Output pins | params |
|---|---|---|---|
| `DFF` | `d`, `pre`, `clr` | `q`, `qn` | — |
| `TFF` | `t`, `pre`, `clr` | `q`, `qn` | — |
| `JKFF` | `j`, `k`, `pre`, `clr` | `q`, `qn` | — |
| `SRFF` | `s`, `r`, `pre`, `clr` | `q`, `qn` | — |
| `REGISTER` | `d0..d(w-1)`, `pre`, `clr` | `q0..q(w-1)` | `width` int ∈ [1,16] (required) |
| `COUNTER` | `en`, `clr` | `q0..q(w-1)` | `width` int ∈ [1,16] (required) |

- The clock is **implicit and global** — there is no clock pin (see
  `docs/semantics/clock-edge-rules.md`).
- `pre`/`clr` are active-high async controls and are *required connected pins*:
  tie them with `CONST0`/`CONST1` explicitly. Both asserted (or any `X`/`Z` on
  them) forces the state bit to `X` per the async rules.
- Multi-bit pins are individual single-bit nets (`q0`, `q1`, …) — no bus vectors
  exist in the wire model.
- Sequential components participate in validation like any other component:
  duplicated ids, multi-driven input pins, dangling input pins, and cycles are
  errors. **Feedback loops through state components are legal and expected**
  (`q` → combinational logic → `d`); a cycle is only an error if it passes through
  *no* state component (`COMBINATIONAL_LOOP`, same as v1).

## Validation additions (v2 codes, authoritative)

All v1 codes apply unchanged, plus:

| Code | Severity | Meaning |
|---|---|---|
| `INVALID_STATE_WIDTH` | error | `width` missing/out-of-range on `REGISTER`/`COUNTER` |
| `UNKNOWN_STATE_PIN` | error | net references a pin that does not exist on a sequential component |

`COMBINATIONAL_LOOP` detection ignores paths that pass through state components:
state elements *cut* combinational cycles (their `q` output is a cycle boundary).

## Simulation request (engine API)

```json
{
  "circuit": { "schema_version": 2, "...": "..." },
  "cycles": 8,
  "inputs_per_cycle": [ { "clk_en": "1" }, { "clk_en": "0" } ]
}
```

- `cycles` ∈ [1, 256] (hard bound, refusal beyond — never truncation).
- `inputs_per_cycle` length ≤ `cycles`; missing trailing cycles use empty vectors
  (all primary inputs `X`). Each entry is a name→value map (v1 normalization rules).

## Result

```json
{
  "schema_version": 2,
  "engine_version": "0.2.0",
  "input_hash": "sha256-hex",
  "scope": "BOUNDED(8 cycles)",
  "cycles": [ { "cycle": 0, "inputs": {}, "state": { "FF1.q": "0" }, "outputs": {} } ],
  "events": [ { "cycle": 0, "component": "FF1", "pin": "q", "old": "0", "new": "1", "cause": "clock_edge" } ],
  "waveforms": { "in:x": ["0","1"], "FF1.q": ["0","1"] },
  "state_components": ["FF1"]
}
```

The scope label is `BOUNDED(N cycles)`: the run explored exactly N clock edges —
no universal claims are made about behavior beyond them. `input_hash` follows the
v1 canonicalization with the input sequence included in canonicalized form.
